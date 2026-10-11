"""Existing runner contract backed by clean cloud Chromium microVMs."""
from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

try:
    from .runner import PlaywrightRunner, validate_browser_script
    from .action_events import MARKER, instrument_script, insert_after_future_imports
    from .redaction import SensitiveDataRedactor
    from .page_controls import summarize_controls
    from .sandbox_transport import WORK, origin, PUBLIC_DEMO
except ImportError:
    from runner import PlaywrightRunner, validate_browser_script
    from action_events import MARKER, instrument_script, insert_after_future_imports
    from redaction import SensitiveDataRedactor
    from page_controls import summarize_controls
    from sandbox_transport import WORK, origin, PUBLIC_DEMO


class SandboxPlaywrightRunner(PlaywrightRunner):
    requires_target_url = True
    def __init__(self, artifacts_dir, transport):
        super().__init__(artifacts_dir)
        self.transport = transport

    def _network_guard(self, code, target):
        origins = [origin(target), *[origin(value) for value in getattr(self.transport, "dependencies", ())]]
        controller = getattr(getattr(self.transport, "policy", None), "origin", "")
        # Browser routing makes failures readable. The microVM firewall is the
        # actual security boundary and also constrains arbitrary generated Python.
        guard = f'''\nfrom urllib.parse import urlsplit as _cloud_urlsplit
from playwright.sync_api import Browser as _CloudBrowser, BrowserType as _CloudBrowserType
import re as _cloud_re
_cloud_original_context = _CloudBrowser.new_context
_cloud_original_launch = _CloudBrowserType.launch
def _cloud_launch(self, *args, **kwargs):
    kwargs['headless'] = True
    return _cloud_original_launch(self, *args, **kwargs)
_CloudBrowserType.launch = _cloud_launch
def _cloud_route(route):
    parts = _cloud_urlsplit(route.request.url)
    authority = parts.scheme + '://' + (parts.hostname or '').lower()
    allowed = authority in {origins!r} and parts.port in (None, 80, 443) and not parts.username
    if authority == {controller!r}:
        allowed = allowed and route.request.method in ('GET','HEAD') and bool(_cloud_re.fullmatch({PUBLIC_DEMO.pattern!r}, parts.path))
    if allowed: route.continue_()
    else: route.abort('blockedbyclient')
def _cloud_context(self, *args, **kwargs):
    kwargs['service_workers'] = 'block'
    context = _cloud_original_context(self, *args, **kwargs)
    context.route('**/*', _cloud_route)
    return context
_CloudBrowser.new_context = _cloud_context
'''
        return insert_after_future_imports(guard, code)

    async def execute_script(self, script_code, env_vars=None, secrets_to_mask=None, secrets=None, timeout_seconds=None,
                             on_log=None, on_action=None, headed=False, execution_id=None, cdp_endpoint=None,
                             cdp_runner_secret=None, target_url=None):
        if headed or cdp_endpoint:
            raise ValueError("Headed cloud execution requires the paired-browser transport; headless fallback is disabled")
        if not target_url or not timeout_seconds or not 1 <= timeout_seconds <= 300:
            raise ValueError("A target URL and bounded timeout are required for cloud execution")
        validate_browser_script(script_code)
        run_id = execution_id or f"run_{uuid.uuid4().hex}"
        if not re.fullmatch(r"[A-Za-z0-9_-]+(?:/attempt-[12])?", run_id):
            raise ValueError("Invalid execution output path")
        run_dir = Path(self.artifacts_dir) / run_id
        run_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        environment = {key: str(value) for key, value in (env_vars or {}).items() if key in {"AUTH_USERNAME", "AUTH_PASSWORD"}}
        redactor = SensitiveDataRedactor([*(secrets_to_mask or []), *(secrets or []), *environment.values()])
        environment.update(ARTIFACTS_DIR=WORK, PYTHONUNBUFFERED="1")
        code = self._network_guard(self._wrap_script(instrument_script(script_code), WORK), target_url)
        script_path = run_dir / "test_script.py"
        script_path.write_text(redactor.redact(script_code), encoding="utf-8")
        logs, stdout, stderr = [], [], []

        def log(level, message):
            value = {"timestamp": time.strftime("%H:%M:%S"), "level": level, "agent": "Execution Agent", "message": redactor.redact(message)[:3000]}
            logs.append(value)
            if on_log: on_log(value)

        def output(line):
            if line.startswith(MARKER):
                action = json.loads(line[len(MARKER):])
                if action.get("action") in {"navigate", "click", "fill", "press", "check", "select_option", "screenshot", "expect"} and action.get("phase") in {"started", "finished", "failed"}:
                    if on_action: on_action(json.loads(redactor.redact(json.dumps(action))))
            else:
                if sum(map(len, stdout)) < 50000: stdout.append(redactor.redact(line))
                log("INFO", line)

        def error(line):
            if sum(map(len, stderr)) < 50000: stderr.append(redactor.redact(line))
            log("ERROR", line)

        started = time.monotonic()
        log("INFO", "Preparing a clean cloud Chromium worker")
        result = await self.transport.execute(code=code, environment=environment, target_url=target_url,
                                              timeout_seconds=timeout_seconds, on_stdout=output, on_stderr=error)
        screenshots, video, dom = [], None, ""
        for name, data in result.files.items():
            if not re.fullmatch(r"[A-Za-z0-9_.@-]{1,180}", name) or name in {".", ".."}:
                raise ValueError("Invalid worker artifact path")
            if name.endswith((".png", ".jpg", ".jpeg")): screenshots.append(name)
            elif name.endswith(".webm") and len(data) > 500:
                if video: continue
                name = video = "session_video.webm"
            elif name == "dom_snapshot.html":
                dom = redactor.redact(data.decode("utf-8", errors="replace")[:50000])
                data = dom.encode()
            else: continue
            (run_dir / name).write_bytes(data)
        duration = round(time.monotonic() - started, 2)
        status = "PASSED" if result.exit_code == 0 else "FAILED"
        log("INFO" if result.exit_code == 0 else "ERROR", f"Cloud browser {status.lower()} in {duration}s (exit {result.exit_code}); evidence saved")
        stderr_text = "\n".join(stderr)
        return {"run_id": run_id, "status": status, "passed": result.exit_code == 0, "exit_code": result.exit_code,
                "duration_seconds": duration, "run_dir": str(run_dir), "script_path": str(script_path),
                "screenshots": screenshots, "video": video, "dom_snapshot": dom, "dom_excerpt": dom[:12000],
                "failed_action": self._extract_failed_action(stderr_text), "locator_evidence": self._extract_locator_evidence(stderr_text),
                "stdout": "\n".join(stdout), "stderr": stderr_text, "logs": logs}

    def inspect_target_controls(self, url):
        async def inspect():
            lines = []
            code = f'''from playwright.sync_api import sync_playwright
import json
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()
    page.goto({url!r}, wait_until='domcontentloaded', timeout=20000)
    controls = page.eval_on_selector_all('input, button, label', """(nodes) => nodes.slice(0, 48).map(node => {{
        const safe = document.createElement(node.tagName);
        for (const key of ['id', 'name', 'type', 'aria-label', 'placeholder', 'for']) {{
            const value = node.getAttribute(key); if (value) safe.setAttribute(key, value.slice(0, 80));
        }}
        if (node.tagName !== 'INPUT') safe.textContent = (node.innerText || '').trim().slice(0, 80);
        return safe.outerHTML;
    }}).join('')""")
    print(json.dumps({{"controls": controls}}))
    browser.close()
'''
            result = await self.transport.execute(code=self._network_guard(code, url), environment={"PYTHONUNBUFFERED": "1"},
                                                  target_url=url, timeout_seconds=30, on_stdout=lines.append, on_stderr=lambda line: None)
            if result.exit_code != 0: raise ValueError("Cloud browser inspection failed")
            for line in reversed(lines):
                try:
                    return summarize_controls(json.loads(line)["controls"])
                except (ValueError, KeyError, TypeError): continue
            raise ValueError("Cloud inspection returned no control evidence")
        # Discovery already runs in an orchestration thread, not the API loop.
        return asyncio.run(inspect())
