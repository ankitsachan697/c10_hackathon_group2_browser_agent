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
