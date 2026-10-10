"""
Execution Agent Engine for Python Playwright scripts.
Features:
- Subprocess execution with timeout
- Real-time password & secret redaction in stdout/stderr
- Artifact collection (screenshots, traces, DOM snapshot, error dumps)
- Structured live log emission for UI streaming
"""

import os
import re
import sys
import json
import time
import uuid
import shutil
import asyncio
import traceback
from typing import Dict, Any, List, Optional, Callable


class SecretRedactor:
    """Redacts plain secrets and passwords from strings and logs."""
    def __init__(self, secrets: Optional[List[str]] = None):
        self.secrets = set()
        if secrets:
            for s in secrets:
                if s and len(s.strip()) > 2:  # Avoid redacting 1-2 char noise
                    self.secrets.add(s.strip())

    def add_secret(self, secret: str):
        if secret and len(secret.strip()) > 2:
            self.secrets.add(secret.strip())

    def redact(self, text: str) -> str:
        if not text:
            return text
        sanitized = text
        # Redact known registered secrets
        for s in self.secrets:
            sanitized = sanitized.replace(s, "[REDACTED_SECRET:••••••••]")

        # Redact typical password patterns in logs (e.g. password="...", password: "...")
        sanitized = re.sub(
            r'(password|passwd|secret|token|api_key|auth_token)\s*[:=]\s*["\']([^"\']+)["\']',
            r'\1="[REDACTED_SECRET:••••••••]"',
            sanitized,
            flags=re.IGNORECASE
        )
        # Redact common env assignment lines like AUTH_SECRET=xyz
        sanitized = re.sub(
            r'(AUTH_SECRET|USER_PASSWORD|PASSWORD)\s*=\s*([^\s]+)',
            r'\1=[REDACTED_SECRET:••••••••]',
            sanitized,
            flags=re.IGNORECASE
        )
        return sanitized


class PlaywrightRunner:
    def __init__(self, artifacts_dir: str, cdp_endpoint: str | None = None, cdp_timeout_seconds: int | None = None):
        self.artifacts_dir = artifacts_dir
        self.cdp_endpoint = cdp_endpoint
        self.cdp_timeout_seconds = cdp_timeout_seconds
        os.makedirs(self.artifacts_dir, exist_ok=True)

    async def execute_script(
        self,
        script_code: str,
        env_vars: Optional[Dict[str, str]] = None,
        secrets_to_mask: Optional[List[str]] = None,
        timeout_seconds: Optional[int] = None,
        on_log: Optional[Callable[[Dict[str, Any]], None]] = None,
        headed: bool = False,
        execution_id: str | None = None,
    ) -> Dict[str, Any]:
        """
        Executes a Python Playwright script.
        Logs are streamed through on_log callback with secret redaction.
        """
        run_id = execution_id or f"run_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        run_dir = os.path.join(self.artifacts_dir, run_id)
        os.makedirs(run_dir, exist_ok=True)

        redactor = SecretRedactor(secrets_to_mask)
        if env_vars:
            for k, v in env_vars.items():
                if any(kw in k.lower() for kw in ["pass", "secret", "token", "key"]):
                    redactor.add_secret(v)

        logs: List[Dict[str, Any]] = []

        def emit_log(level: str, message: str, agent: str = "Execution Agent"):
            masked_msg = redactor.redact(message)
            log_item = {
                "timestamp": time.strftime("%H:%M:%S"),
                "level": level,
                "agent": agent,
                "message": masked_msg,
            }
            logs.append(log_item)
            if on_log:
                try:
                    on_log(log_item)
                except Exception:
                    pass

        emit_log("INFO", f"🚀 Initializing Playwright execution environment for {run_id}")
        emit_log("INFO", f"🔒 Secret Redactor activated. All credentials masked in real-time logs.")

        # Ensure script saves artifacts to run_dir if not explicitly set
        script_path = os.path.join(run_dir, "test_script.py")
        
        # Inject standard runner helper or wrap script if needed
        wrapped_code = self._wrap_script(script_code, run_dir, headed=headed)
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(wrapped_code)

        # Prepare execution environment
        exec_env = self._execution_environment(env_vars, run_dir)

        python_bin = sys.executable

        emit_log("INFO", f"⚡ Launching Chromium browser runner (headed={headed})...")

        start_time = time.time()
        try:
            proc = await asyncio.create_subprocess_exec(
                python_bin,
                script_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=exec_env,
                cwd=run_dir,
            )

            stdout_lines = []
            stderr_lines = []

            async def read_stream(stream, is_stderr=False):
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    decoded = line.decode("utf-8", errors="replace").rstrip()
                    if is_stderr:
                        stderr_lines.append(decoded)
                        emit_log("WARN" if "Deprecation" in decoded else "ERROR", decoded)
                    else:
                        stdout_lines.append(decoded)
                        emit_log("INFO", decoded)

            await asyncio.wait_for(
                asyncio.gather(
                    read_stream(proc.stdout, False),
                    read_stream(proc.stderr, True),
                ),
                timeout=timeout_seconds,
            )

            await proc.wait()
            duration = round(time.time() - start_time, 2)
            exit_code = proc.returncode

        except asyncio.TimeoutError:
            duration = round(time.time() - start_time, 2)
            emit_log("ERROR", f"⏱️ Script execution timed out after {timeout_seconds}s!")
            try:
                proc.kill()
            except Exception:
                pass
            exit_code = -1
        except Exception as e:
            duration = round(time.time() - start_time, 2)
            emit_log("ERROR", f"Execution error: {str(e)}")
            exit_code = 1

        # Scan for generated artifacts (screenshots and video)
        screenshots = [
            f for f in os.listdir(run_dir)
            if f.endswith((".png", ".jpg", ".jpeg")) and not f.startswith("diff_")
        ]
        
        # Look for video recording (.webm)
        video_filename = None
        for f in os.listdir(run_dir):
            if f.endswith(".webm"):
                orig_file = os.path.join(run_dir, f)
                target_video = os.path.join(run_dir, "session_video.webm")
                # Only accept video if it was flushed and has meaningful data (>500 bytes)
                if os.path.getsize(orig_file) > 500:
                    if f != "session_video.webm":
                        try:
                            shutil.move(orig_file, target_video)
                            video_filename = "session_video.webm"
                        except Exception:
                            video_filename = f
                    else:
                        video_filename = "session_video.webm"
                    break
                else:
                    # Clean up corrupted 0-byte video stub
                    try:
                        os.remove(orig_file)
                    except Exception:
                        pass

        dom_snapshot_file = os.path.join(run_dir, "dom_snapshot.html")
        dom_snapshot = ""
        if os.path.exists(dom_snapshot_file):
            with open(dom_snapshot_file, "r", encoding="utf-8", errors="replace") as f:
                dom_snapshot = f.read(50000)  # Max 50KB summary

        passed = (exit_code == 0)
        status_label = "PASSED" if passed else "FAILED"

        emit_log(
            "INFO" if passed else "ERROR",
            f"🏁 Run completed in {duration}s with status: {status_label} (Exit Code: {exit_code})"
        )

        return {
            "run_id": run_id,
            "status": status_label,
            "passed": passed,
            "exit_code": exit_code,
            "duration_seconds": duration,
            "run_dir": run_dir,
            "script_path": script_path,
            "screenshots": sorted(screenshots),
            "video": video_filename,
            "dom_snapshot": dom_snapshot,
            "dom_excerpt": dom_snapshot[:6000],
            "failed_action": self._extract_failed_action("\n".join(stderr_lines)),
            "locator_evidence": self._extract_locator_evidence("\n".join(stderr_lines)),
            "stdout": "\n".join(stdout_lines),
            "stderr": redactor.redact("\n".join(stderr_lines)),
            "logs": logs,
        }

    def _execution_environment(self, env_vars: Optional[Dict[str, str]], run_dir: str | os.PathLike[str]) -> Dict[str, str]:
        """Build a minimal worker environment without backend credentials."""
        allowed_host_keys = (
            "PATH", "LANG", "LC_ALL", "TMPDIR", "TEMP", "TMP",
            "PLAYWRIGHT_BROWSERS_PATH", "PLAYWRIGHT_NODEJS_PATH",
        )
        environment = {key: os.environ[key] for key in allowed_host_keys if key in os.environ}
        environment["ARTIFACTS_DIR"] = str(run_dir)
        environment["PYTHONUNBUFFERED"] = "1"
        if self.cdp_endpoint:
            environment["PLAYWRIGHT_CDP_ENDPOINT"] = self.cdp_endpoint
            environment["PLAYWRIGHT_CDP_TIMEOUT_SECONDS"] = str(self.cdp_timeout_seconds or 30)
        for key, value in (env_vars or {}).items():
            environment[key] = str(value)
        return environment

    @staticmethod
    def _extract_failed_action(stderr: str) -> str:
        for line in reversed((stderr or "").splitlines()):
            if any(token in line.lower() for token in ("locator", "click", "fill", "expect", "timeout")):
                return line.strip()[:500]
        return ""

    @staticmethod
    def _extract_locator_evidence(stderr: str) -> List[str]:
        candidates = re.findall(r"(?:locator\(|waiting for |selector[=:] ?)([^\n]+)", stderr or "", re.IGNORECASE)
        return [candidate.strip()[:300] for candidate in candidates[:5]]

    def _wrap_script(self, raw_script: str, run_dir: str, headed: bool = False) -> str:
        """
        Ensures the script handles screenshots on failure, sets ARTIFACTS_DIR,
        records full session video, and configures headed/headless browser mode.
        Guarantees context.close() is called before browser.close() to flush video.
        """
        script = raw_script
        if headed:
            # Replace headless=True with headless=False and add slow_mo for visual inspection
            script = re.sub(r'launch\(\s*headless\s*=\s*True', 'launch(headless=False, slow_mo=600', script)
            script = re.sub(r'launch\(\)', 'launch(headless=False, slow_mo=600)', script)
        else:
            script = re.sub(r'launch\(\s*headless\s*=\s*False', 'launch(headless=True', script)

        script = re.sub(
            r"([A-Za-z_][A-Za-z0-9_]*\.chromium)\.launch\(",
            r"_connect_or_launch(\1, ",
            script,
        )

        # Inject video recording into browser.new_context
        if "new_context" in script:
            script = re.sub(
                r'new_context\((.*?)\)',
                r'new_context(\1, record_video_dir=' + repr(run_dir) + ', record_video_size={"width": 1280, "height": 800})',
                script
            )
        elif "new_page" in script and "new_context" not in script:
            # Wrap browser.new_page with a context that records video
            script = script.replace(
                "page = browser.new_page()",
                f"context = browser.new_context(record_video_dir={repr(run_dir)}, record_video_size={{'width': 1280, 'height': 800}})\n        page = context.new_page()"
            )

        # Ensure context.close() is explicitly called before browser.close()
        if "browser.close()" in script:
            script = script.replace(
                "browser.close()",
                "try:\n            if 'context' in locals():\n                context.close()\n        except Exception:\n            pass\n        browser.close()"
            )

        header = f"""# Auto-injected environment setup
import os, sys
os.environ.setdefault("ARTIFACTS_DIR", {repr(run_dir)})
run_dir = {repr(run_dir)}

def _connect_or_launch(browser_type, *args, **kwargs):
    endpoint = os.environ.get("PLAYWRIGHT_CDP_ENDPOINT")
    if endpoint:
        timeout_ms = int(os.environ.get("PLAYWRIGHT_CDP_TIMEOUT_SECONDS", "30")) * 1000
        return browser_type.connect_over_cdp(endpoint, timeout=timeout_ms)
    return browser_type.launch(*args, **kwargs)
"""
        return header + "\n" + script
