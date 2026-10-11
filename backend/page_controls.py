"""Small, value-free HTML control summary for the discovery agent."""

from html.parser import HTMLParser
from urllib.parse import urlparse

import requests


class _ControlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.controls: list[dict[str, str]] = []
        self.labels: dict[str, str] = {}
        self._capture: tuple[str, dict[str, str]] | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key: value or "" for key, value in attrs}
        if tag == "input":
            self.controls.append({key: attributes[key][:80] for key in ("id", "name", "type", "aria-label", "placeholder") if attributes.get(key)})
        elif tag in {"button", "label"}:
            self._capture = (tag, attributes)
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if not self._capture or self._capture[0] != tag:
            return
        _, attributes = self._capture
        visible = " ".join(" ".join(self._text).split())[:80]
        if tag == "label" and attributes.get("for") and visible:
            self.labels[attributes["for"]] = visible
        elif tag == "button":
            control = {key: attributes[key][:80] for key in ("id", "name", "type", "aria-label") if attributes.get(key)}
            if visible:
                control["text"] = visible
            self.controls.append({"tag": "button", **control})
        self._capture = None
        self._text = []


def summarize_controls(html: str) -> str:
    parser = _ControlParser()
    parser.feed(html)
    controls = []
    for control in parser.controls[:24]:
        item = dict(control)
        if "tag" not in item:
            item = {"tag": "input", **item}
        if item.get("id") in parser.labels:
            item["label"] = parser.labels[item["id"]]
        controls.append("; ".join(f"{key}={value}" for key, value in item.items()))
    return "\n".join(controls)[:3200]


def inspect_target_controls(url: str) -> str:
    if urlparse(url).scheme not in {"http", "https"}:
        return ""
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=10_000)
                summary = summarize_controls(page.content())
                if summary:
                    return summary
            finally:
                browser.close()
    except Exception:
        # Browser binaries may not be installed on every backend host.
        pass
    try:
        with requests.get(url, timeout=5, stream=True, headers={"Accept": "text/html"}) as response:
            response.raise_for_status()
            if "text/html" not in response.headers.get("Content-Type", ""):
                return ""
            chunks: list[bytes] = []
            remaining = 128_000
            for chunk in response.iter_content(chunk_size=8192):
                if not chunk:
                    continue
                chunks.append(chunk[:remaining])
                remaining -= min(len(chunk), remaining)
                if not remaining:
                    break
            body = b"".join(chunks)
        return summarize_controls(body.decode("utf-8", errors="replace"))
    except requests.RequestException:
        return ""
