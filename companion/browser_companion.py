"""Outbound-only local Chromium bridge for one explicitly approved CDP session."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import httpx
import websockets
from playwright.async_api import async_playwright


DEFAULT_DEVICE_FILE = Path.home() / ".config" / "outskill-browser-companion" / "device.json"


def require_secure_server(server: str) -> None:
    parsed = urlparse(server)
    if parsed.scheme == "https":
        return
    if parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}:
        return
    raise ValueError("Companion requires HTTPS, except for a loopback development server")


def browser_command(executable: str, profile_dir: Path) -> list[str]:
    return [executable, "--remote-debugging-address=127.0.0.1", "--remote-debugging-port=0",
            f"--user-data-dir={profile_dir}", "--no-first-run", "--no-default-browser-check", "about:blank"]


def save_device(path: Path, device: dict[str, str]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError("Device credential path must not be a symlink")
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, prefix=".device-", delete=False) as handle:
        os.chmod(handle.name, 0o600)
        json.dump({key: device[key] for key in ("id", "credential", "name")}, handle)
        temporary = Path(handle.name)
    os.replace(temporary, path)
    os.chmod(path, 0o600)


def load_device(path: Path) -> dict[str, str]:
    if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077:
        raise ValueError("Device credential file is missing or not private")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not all(isinstance(value.get(key), str) for key in ("id", "credential", "name")):
        raise ValueError("Device credential file is invalid")
    return value


def _websocket_url(server: str, path: str) -> str:
    return ("wss://" if server.startswith("https://") else "ws://") + server.split("://", 1)[1].rstrip("/") + path


async def _wait_for_devtools_port(profile_dir: Path, process: subprocess.Popen) -> str:
    file = profile_dir / "DevToolsActivePort"
    for _ in range(100):
        if process.poll() is not None:
            raise RuntimeError("Chromium exited before opening DevTools")
        if file.is_file():
            lines = file.read_text(encoding="utf-8").splitlines()
            if len(lines) >= 2 and lines[0].isdigit() and lines[1].startswith("/devtools/browser/"):
                return f"ws://127.0.0.1:{lines[0]}{lines[1]}"
        await asyncio.sleep(0.1)
    raise RuntimeError("Timed out waiting for local Chromium")


async def _forward(source, target):
    async for message in source:
        if not isinstance(message, str) or len(message.encode("utf-8")) > 1024 * 1024:
            raise ValueError("Invalid CDP frame")
        await target.send(message)


async def _approved_session(server: str, device: dict[str, str], session_id: str) -> None:
    async with async_playwright() as playwright:
        with tempfile.TemporaryDirectory(prefix="outskill-browser-") as directory:
            profile_dir = Path(directory)
            process = subprocess.Popen(browser_command(playwright.chromium.executable_path, profile_dir),
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                local_url = await _wait_for_devtools_port(profile_dir, process)
                remote_url = _websocket_url(server, f"/api/companions/relay/{session_id}/companion")
                async with websockets.connect(remote_url, additional_headers={
                    "X-Companion-Device-Id": device["id"], "Authorization": f"Bearer {device['credential']}",
                }, max_size=1024 * 1024) as remote:
                    async with websockets.connect(local_url, max_size=1024 * 1024) as local:
                        tasks = [asyncio.create_task(_forward(remote, local)), asyncio.create_task(_forward(local, remote))]
                        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                        for task in pending:
                            task.cancel()
                        await asyncio.gather(*pending, return_exceptions=True)
                        for task in done:
                            task.result()
            finally:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


async def run(server: str, device_file: Path) -> None:
    require_secure_server(server)
    device = load_device(device_file)
    headers = {"Authorization": f"Bearer {device['credential']}"}
    seen: set[str] = set()
    async with httpx.AsyncClient(base_url=server, timeout=10) as client:
        while True:
            heartbeat = await client.post("/api/companions/heartbeat", json={"device_id": device["id"]}, headers=headers)
            heartbeat.raise_for_status()
            response = await client.get(f"/api/companions/{device['id']}/sessions", headers=headers)
            response.raise_for_status()
            for offer in response.json()["data"]:
                session_id = offer.get("session_id")
                if not session_id or session_id in seen:
                    continue
                seen.add(session_id)
                answer = await asyncio.to_thread(input, f"Open local Chromium for run {offer.get('run_id')}? [y/N] ")
                if answer.strip().lower() not in {"y", "yes"}:
                    continue
                await _approved_session(server, device, session_id)
            await asyncio.sleep(2)


async def pair(server: str, code: str, device_name: str, device_file: Path) -> None:
    require_secure_server(server)
    async with httpx.AsyncClient(base_url=server, timeout=10) as client:
        response = await client.post("/api/companions/exchange", json={"code": code, "device_name": device_name})
        response.raise_for_status()
        save_device(device_file, response.json()["data"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Outskill local headed browser companion")
    parser.add_argument("command", choices=("pair", "run"))
    parser.add_argument("--server", required=True, help="HTTPS backend URL, or loopback HTTP for development")
    parser.add_argument("--device-file", type=Path, default=DEFAULT_DEVICE_FILE)
    parser.add_argument("--code", help="One-time operator pairing code")
    parser.add_argument("--device-name", default="Local browser")
    args = parser.parse_args()
    if args.command == "pair":
        if not args.code:
            parser.error("--code is required for pairing")
        asyncio.run(pair(args.server, args.code, args.device_name, args.device_file))
        print(f"Paired {args.device_name}; credential saved privately to {args.device_file}")
    else:
        asyncio.run(run(args.server, args.device_file))


if __name__ == "__main__":
    main()
