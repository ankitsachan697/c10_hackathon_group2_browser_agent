import os
from pathlib import Path

import pytest

from companion.browser_companion import browser_command, require_secure_server, save_device


def test_browser_listens_only_on_loopback(tmp_path):
    command = browser_command("/path/to/chromium", tmp_path)
    assert "--remote-debugging-address=127.0.0.1" in command
    assert "--remote-debugging-port=0" in command
    assert not any("0.0.0.0" in item for item in command)


def test_device_secret_file_is_private(tmp_path):
    target = tmp_path / "device.json"
    save_device(target, {"id": "device-1", "credential": "secret", "name": "Laptop"})
    assert target.exists()
    assert os.stat(target).st_mode & 0o077 == 0
    assert "secret" in target.read_text()


def test_remote_plain_http_is_refused():
    with pytest.raises(ValueError):
        require_secure_server("http://public.example")
    require_secure_server("http://127.0.0.1:8000")
    require_secure_server("https://public.example")
