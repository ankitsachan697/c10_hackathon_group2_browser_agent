import json

import pytest


def test_supported_actions_emit_ordered_safe_events(capsys):
    from backend.action_events import instrument_script

    source = """
class Page:
    def goto(self, url): return 'opened'
    def click(self, target): return 'clicked'
    def fill(self, target, value): return 'filled'
    def press(self, key): return 'pressed'
    def check(self): return 'checked'
    def select_option(self, value): return 'selected'
    def screenshot(self): return 'captured'
page = Page()
page.goto('https://example.test')
page.click('#submit')
page.fill('#password', 'Password123')
page.press('Enter')
page.check()
page.select_option('private-option')
page.screenshot()
"""
    exec(instrument_script(source), {})
    lines = capsys.readouterr().out.splitlines()
    events = [json.loads(line.split(":", 1)[1]) for line in lines if line.startswith("__OUTSKILL_ACTION__:")]

    assert [event["action"] for event in events[::2]] == ["navigate", "click", "fill", "press", "check", "select_option", "screenshot"]
    assert all(event["phase"] == "started" for event in events[::2])
    assert all(event["phase"] == "finished" for event in events[1::2])
    assert "Password123" not in json.dumps(events)
    assert "private-option" not in json.dumps(events)


def test_action_failure_is_recorded_and_reraised(capsys):
    from backend.action_events import instrument_script

    source = "class Page:\n    def click(self): raise RuntimeError('broken')\npage = Page()\npage.click()"
    with pytest.raises(RuntimeError, match="broken"):
        exec(instrument_script(source), {})
    events = [json.loads(line.split(":", 1)[1]) for line in capsys.readouterr().out.splitlines()]
    assert [event["phase"] for event in events] == ["started", "failed"]
    assert "broken" not in json.dumps(events)


def test_failure_evidence_is_captured_before_generated_script_cleanup():
    from backend.action_events import instrument_script
    captured = []
    namespace = {}
    namespace["_worker_capture_failure"] = lambda: captured.append(namespace["closed"])
    source = "closed=False\nclass Page:\n    def click(self): raise RuntimeError('stale locator')\npage=Page()\ntry:\n    page.click()\nfinally:\n    closed=True"
    with pytest.raises(RuntimeError, match="stale locator"):
        exec(instrument_script(source), namespace)
    assert captured == [False]
    assert namespace["closed"] is True


def test_expect_call_is_logged_without_assertion_values(capsys):
    from backend.action_events import instrument_script

    source = "def expect(value): return True\nexpect('secret assertion value')"
    exec(instrument_script(source), {})
    output = capsys.readouterr().out
    assert '"action":"expect"' in output
    assert "secret assertion value" not in output


def test_instrumentation_keeps_future_imports_legal():
    from backend.action_events import instrument_script

    instrumented = instrument_script("from __future__ import annotations\nprint('ready')")

    compile(instrumented, "generated.py", "exec")


def test_runner_wrapper_keeps_future_imports_legal(tmp_path):
    from backend.runner import PlaywrightRunner

    wrapped = PlaywrightRunner(str(tmp_path))._wrap_script(
        "from __future__ import annotations\nprint('ready')", str(tmp_path)
    )

    compile(wrapped, "generated.py", "exec")


def test_failure_evidence_does_not_clear_fields_before_a_locator_fallback(tmp_path):
    """Exercise the real Chromium wrapper, including a caught action timeout."""
    from backend.action_events import instrument_script
    from backend.runner import PlaywrightRunner
    from playwright.sync_api import Page
    from urllib.parse import quote

    html = """<html><body>
      <input id="shipping" value="123 Synthetic Street">
      <input id="password" type="password" value="capture-secret">
      <textarea id="note">private-note</textarea>
      <div id="editor" contenteditable="true">private-editor</div>
      <output id="result"></output>
      <button id="fallback" onclick="document.querySelector('#result').textContent = document.querySelector('#shipping').value">Continue</button>
    </body></html>"""
    source = f"""
from playwright.sync_api import sync_playwright, TimeoutError
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()
    try:
        page.goto({('data:text/html,' + quote(html))!r})
        try:
            page.locator('#missing').click(timeout=100)
        except TimeoutError:
            page.locator('#fallback').click()
        assert page.locator('#result').inner_text() == '123 Synthetic Street'
        assert page.locator('#shipping').input_value() == '123 Synthetic Street'
        assert page.locator('#password').input_value() == 'capture-secret'
        assert page.locator('#note').input_value() == 'private-note'
        assert page.locator('#editor').inner_text() == 'private-editor'
    finally:
        context.close()
        browser.close()
"""
    wrapped = PlaywrightRunner(str(tmp_path))._wrap_script(instrument_script(source), str(tmp_path))
    namespace = {}
    original_goto = Page.goto
    try:
        exec(wrapped, namespace)
    finally:
        Page.goto = original_goto

    evidence = (tmp_path / "dom_snapshot.html").read_text()
    for private_value in ("123 Synthetic Street", "capture-secret", "private-note", "private-editor"):
        assert private_value not in evidence
    assert (tmp_path / "failure.png").stat().st_size > 0
