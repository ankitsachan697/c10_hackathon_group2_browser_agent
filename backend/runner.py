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
import ast
import stat
from typing import Dict, Any, List, Optional, Callable
from pathlib import Path

try:
    from .redaction import SensitiveDataRedactor
    from .action_events import MARKER, instrument_script, insert_after_future_imports
except ImportError:
    from redaction import SensitiveDataRedactor
    from action_events import MARKER, instrument_script, insert_after_future_imports


SecretRedactor = SensitiveDataRedactor


class UnsafeScriptError(ValueError):
    """Raised when a saved script requests capabilities outside browser automation."""


def validate_browser_script(script: str) -> None:
    """Allow Playwright automation while denying host/network/process escape primitives."""
    tree = ast.parse(script)
    allowed_imports = {"os", "sys", "re", "time", "json", "playwright.sync_api"}
    blocked_calls = {"eval", "exec", "compile", "__import__", "input", "breakpoint", "open"}
    blocked_roots = {"subprocess", "socket", "pathlib", "requests", "urllib", "http", "shutil"}
    allowed_os = {"environ", "getenv", "makedirs", "path"}
    allowed_os_path = {"join", "basename", "dirname", "exists"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name not in allowed_imports for alias in node.names):
                raise UnsafeScriptError("Script imports a module outside the browser automation allowlist")
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "") not in allowed_imports:
                raise UnsafeScriptError("Script imports a module outside the browser automation allowlist")
        elif isinstance(node, ast.Name) and node.id in blocked_roots:
            raise UnsafeScriptError(f"Script capability is not allowed: {node.id}")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in blocked_calls:
            raise UnsafeScriptError(f"Script capability is not allowed: {node.func.id}")
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("__"):
                raise UnsafeScriptError("Dunder attribute access is not allowed")
            if isinstance(node.value, ast.Name) and node.value.id == "os" and node.attr not in allowed_os:
                raise UnsafeScriptError(f"os.{node.attr} is not allowed")
            if (
                isinstance(node.value, ast.Attribute)
                and isinstance(node.value.value, ast.Name)
                and node.value.value.id == "os"
                and node.value.attr == "path"
                and node.attr not in allowed_os_path
            ):
                raise UnsafeScriptError(f"os.path.{node.attr} is not allowed")


class PlaywrightRunner:
    def __init__(self, artifacts_dir: str, cdp_endpoint: str | None = None, cdp_timeout_seconds: int | None = None, container_image: str | None = None, allow_unsafe_local_execution: bool = False):
        self.artifacts_dir = artifacts_dir
        self.cdp_endpoint = cdp_endpoint
        self.cdp_timeout_seconds = cdp_timeout_seconds
        self.container_image = container_image
        self.allow_unsafe_local_execution = allow_unsafe_local_execution
        os.makedirs(self.artifacts_dir, exist_ok=True)

    async def execute_script(
        self,
        script_code: str,
        env_vars: Optional[Dict[str, str]] = None,
        secrets_to_mask: Optional[List[str]] = None,
        secrets: Optional[List[str]] = None,
        timeout_seconds: Optional[int] = None,
        on_log: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_action: Optional[Callable[[Dict[str, Any]], None]] = None,
        headed: bool = False,
        execution_id: str | None = None,
        cdp_endpoint: str | None = None,
        cdp_runner_secret: str | None = None,
    ) -> Dict[str, Any]:
        """
        Executes a Python Playwright script.
        Logs are streamed through on_log callback with secret redaction.
        """
        run_id = execution_id or f"run_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        run_dir = os.path.join(self.artifacts_dir, run_id)
        os.makedirs(run_dir, exist_ok=True)
        if self.container_image:
            os.chmod(run_dir, 0o777)

        redactor = SecretRedactor([*(secrets_to_mask or []), *(secrets or []), *([cdp_runner_secret] if cdp_runner_secret else [])])
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

        validate_browser_script(script_code)

        # Ensure script saves artifacts to run_dir if not explicitly set
        script_path = os.path.join(run_dir, "test_script.py")
        
        # Inject standard runner helper or wrap script if needed
        worker_run_dir = "/work" if self.container_image else run_dir
        wrapped_code = self._wrap_script(instrument_script(script_code), worker_run_dir, headed=headed)
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(wrapped_code)

        # Prepare execution environment
        exec_env = self._execution_environment(env_vars, worker_run_dir, cdp_endpoint=cdp_endpoint,
                                               cdp_runner_secret=cdp_runner_secret)

        emit_log("INFO", f"⚡ Launching Chromium browser runner (headed={headed})...")

        start_time = time.time()
        container_name = f"outskill-{re.sub(r'[^a-zA-Z0-9_.-]', '-', run_id)[:100]}" if self.container_image else None
        try:
            command = self._worker_command(script_path, run_dir, exec_env, container_name=container_name)
            proc = await asyncio.create_subprocess_exec(
                *command,
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
                        if decoded.startswith(MARKER):
                            try:
                                action_event = json.loads(decoded[len(MARKER):])
                                if (on_action and action_event.get("action") in {"navigate", "click", "fill", "press", "check", "select_option", "screenshot", "expect"}
                                        and action_event.get("phase") in {"started", "finished", "failed"}):
                                    on_action(action_event)
                            except (ValueError, TypeError, AttributeError):
                                pass
                            continue
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
                await proc.wait()
            except Exception:
                pass
            exit_code = -1
        except Exception as e:
            duration = round(time.time() - start_time, 2)
            emit_log("ERROR", f"Execution error: {str(e)}")
            exit_code = 1
        finally:
            if container_name:
                cleanup = await asyncio.create_subprocess_exec(
                    "docker", "rm", "-f", container_name,
                    stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
                )
                await cleanup.wait()

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
        if self._safe_regular_file(Path(dom_snapshot_file), Path(run_dir)):
            with open(dom_snapshot_file, "r", encoding="utf-8", errors="replace") as f:
                dom_snapshot = f.read(50000)  # Max 50KB summary
            sanitized = redactor.redact(dom_snapshot)
            with open(dom_snapshot_file, "w", encoding="utf-8") as f:
                f.write(sanitized)
            dom_snapshot = sanitized

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
            "stdout": redactor.redact("\n".join(stdout_lines)),
            "stderr": redactor.redact("\n".join(stderr_lines)),
            "logs": logs,
        }

    def _execution_environment(self, env_vars: Optional[Dict[str, str]], run_dir: str | os.PathLike[str],
                               cdp_endpoint: str | None = None, cdp_runner_secret: str | None = None) -> Dict[str, str]:
        """Build a minimal worker environment without backend credentials."""
        allowed_host_keys = (
            "PATH", "LANG", "LC_ALL", "TMPDIR", "TEMP", "TMP",
            "PLAYWRIGHT_BROWSERS_PATH", "PLAYWRIGHT_NODEJS_PATH",
        )
        environment = {key: os.environ[key] for key in allowed_host_keys if key in os.environ}
        environment["ARTIFACTS_DIR"] = str(run_dir)
        environment["PYTHONUNBUFFERED"] = "1"
        for key, value in (env_vars or {}).items():
            environment[key] = str(value)
        endpoint = cdp_endpoint or self.cdp_endpoint
        if endpoint:
            environment["PLAYWRIGHT_CDP_ENDPOINT"] = endpoint
            environment["PLAYWRIGHT_CDP_TIMEOUT_SECONDS"] = str(self.cdp_timeout_seconds or 30)
        if cdp_runner_secret:
            environment["PLAYWRIGHT_CDP_RUNNER_SECRET"] = cdp_runner_secret
        return environment

    @staticmethod
    def _safe_regular_file(path: Path, root: Path) -> bool:
        try:
            if path.is_symlink() or not stat.S_ISREG(path.lstat().st_mode):
                return False
            path.resolve().relative_to(root.resolve())
            return True
        except (FileNotFoundError, OSError, ValueError):
            return False

    def _worker_command(self, script_path: str, run_dir: str, environment: Dict[str, str], container_name: str | None = None) -> List[str]:
        if self.container_image:
            command = [
                "docker", "run", "--rm", "--name", container_name or "outskill-browser-runner", "--read-only", "--cap-drop=ALL",
                "--security-opt=no-new-privileges", "--pids-limit=256", "--memory=1g", "--cpus=1",
                "--user=65532:65532", "--tmpfs=/tmp:rw,nosuid,size=256m",
                "--mount", f"type=bind,src={Path(run_dir).resolve()},dst=/work",
                "--workdir=/work", "--add-host=host.docker.internal:host-gateway",
            ]
            for key in sorted(environment):
                if key in {"AUTH_USERNAME", "AUTH_PASSWORD", "ARTIFACTS_DIR", "PLAYWRIGHT_CDP_ENDPOINT", "PLAYWRIGHT_CDP_TIMEOUT_SECONDS", "PLAYWRIGHT_CDP_RUNNER_SECRET", "PYTHONUNBUFFERED"}:
                    command.extend(["--env", key])
            command.extend([self.container_image, "python", "/work/test_script.py"])
            return command
        if not self.allow_unsafe_local_execution:
            raise UnsafeScriptError("Container runner is not configured; host execution is disabled")
        return [sys.executable, script_path]

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
            def add_video(match: re.Match[str]) -> str:
                arguments = match.group(1)
                if "record_video_dir" in arguments:
                    return match.group(0)
                prefix = f"{arguments}, " if arguments.strip() else ""
                return f'new_context({prefix}record_video_dir={run_dir!r}, record_video_size={{"width": 1280, "height": 800}})'
            script = re.sub(r'new_context\((.*?)\)', add_video, script, flags=re.DOTALL)
        elif "new_page" in script and "new_context" not in script:
            # Wrap browser.new_page with a context that records video
            script = re.sub(
                r"(?m)^([ \t]*)page\s*=\s*browser\.new_page\(\)[ \t]*$",
                lambda match: (
                    f"{match.group(1)}context = browser.new_context("
                    f"record_video_dir={run_dir!r}, "
                    "record_video_size={'width': 1280, 'height': 800})\n"
                    f"{match.group(1)}page = context.new_page()"
                ),
                script,
            )

        credential_mask = """(() => { const apply = () => document.querySelectorAll('input[type=password],input[type=email],input[name=username],input#username,input#email,input[autocomplete=username],input[autocomplete^="cc-"],input[name*="card" i],input[id*="card" i],input[name*="cvv" i],input[id*="cvv" i],input[name*="cvc" i],input[id*="cvc" i]').forEach(el => { el.style.filter = 'blur(10px)'; }); new MutationObserver(apply).observe(document.documentElement, {subtree:true, childList:true}); addEventListener('DOMContentLoaded', apply); })();"""
        script = re.sub(
            r"(?m)^([ \t]*)(page\s*=\s*context\.new_page\(\)[ \t]*)$",
            lambda match: f"{match.group(1)}context.add_init_script({credential_mask!r})\n{match.group(1)}{match.group(2)}",
            script,
        )

        # Ensure context.close() is explicitly called before browser.close()
        if "browser.close()" in script:
            script = re.sub(
                r"(?m)^([ \t]*)browser\.close\(\)[ \t]*$",
                lambda match: (
                    f"{match.group(1)}try:\n"
                    f"{match.group(1)}    if 'context' in locals():\n"
                    f"{match.group(1)}        context.close()\n"
                    f"{match.group(1)}except Exception:\n"
                    f"{match.group(1)}    pass\n"
                    f"{match.group(1)}browser.close()"
                ),
                script,
            )

        header = f"""# Auto-injected environment setup
import os, sys
os.environ.setdefault("ARTIFACTS_DIR", {repr(run_dir)})
run_dir = {repr(run_dir)}

def _worker_target_url(url):
    # A paired browser runs on its own machine; only isolated worker navigation
    # needs a Docker gateway. Public deployment origins remain untouched.
    if {bool(self.container_image)!r} and not os.environ.get("PLAYWRIGHT_CDP_ENDPOINT"):
        from urllib.parse import urlsplit, urlunsplit
        parts = urlsplit(url)
        if parts.scheme in ("http", "https") and parts.hostname in ("localhost", "127.0.0.1", "[::1]", "::1"):
            authority = "host.docker.internal" + (f":{{parts.port}}" if parts.port else "")
            return urlunsplit((parts.scheme, authority, parts.path, parts.query, parts.fragment))
    return url

from playwright.sync_api import Page as _WorkerPage
_worker_original_goto = _WorkerPage.goto
def _worker_goto(self, url, *args, **kwargs):
    return _worker_original_goto(self, _worker_target_url(url), *args, **kwargs)
_WorkerPage.goto = _worker_goto

def _connect_or_launch(browser_type, *args, **kwargs):
    endpoint = os.environ.get("PLAYWRIGHT_CDP_ENDPOINT")
    if endpoint:
        timeout_ms = int(os.environ.get("PLAYWRIGHT_CDP_TIMEOUT_SECONDS", "30")) * 1000
        secret = os.environ.get("PLAYWRIGHT_CDP_RUNNER_SECRET")
        headers = {{"Authorization": f"Bearer {{secret}}"}} if secret else None
        return browser_type.connect_over_cdp(endpoint, headers=headers, timeout=timeout_ms)
    return browser_type.launch(*args, **kwargs)
"""
        return insert_after_future_imports(header, script)
