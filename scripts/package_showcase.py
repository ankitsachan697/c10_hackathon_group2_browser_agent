"""Time-compress a verified real capture; add clearly disclosed chapter captions."""
import argparse
import asyncio
import hashlib
import html
import json
import subprocess
from pathlib import Path


def chapter_segments(evidence):
    if evidence.get("passed") is not True:
        raise ValueError("Only a verified complete capture may be packaged")
    marks = evidence["bookmarks"]
    segments = []
    for index, mark in enumerate(marks):
        end = marks[index + 1]["seconds"] if index + 1 < len(marks) else evidence["raw_duration_seconds"]
        length = end - mark["seconds"]
        if length <= 0:
            continue
        segments.append({"label": mark["label"], "start": mark["seconds"],
                         "source_duration": length, "duration": max(4, min(length, 10))})
    if not segments:
        raise ValueError("Capture contains no usable chapters")
    ratio = min(1, 110 / sum(item["duration"] for item in segments))
    for item in segments:
        item["duration"] *= ratio
        item["speed"] = item["source_duration"] / item["duration"]
    return segments


async def package(manifest: Path, destination: Path):
    from playwright.async_api import async_playwright
    evidence = json.loads(manifest.read_text())
    segments = chapter_segments(evidence)
    raw = Path(evidence["raw_video"])
    if not raw.is_absolute():
        raw = Path.cwd() / raw
    scratch = manifest.parent / "packaged"
    scratch.mkdir(exist_ok=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1280, "height": 72})
        for index, item in enumerate(segments):
            caption = scratch / f"caption-{index:02}.png"
            await page.set_content('<style>body{margin:0;padding:10px 22px;background:#080b06;color:#eaf0e3;font:600 22px Arial}small{display:block;margin-top:5px;color:#b7f536;font:12px Arial}</style>'
                                   + html.escape("Group2 · " + item["label"])
                                   + '<small>Real browser + real n8n · waits shortened · synthetic data only</small>')
            await page.screenshot(path=str(caption))
        await browser.close()
    for index, item in enumerate(segments):
        clip = scratch / f"chapter-{index:02}.mp4"
        graph = (f"[0:v]setpts=(PTS-STARTPTS)/{item['speed']:.6f},fps=25,scale=1280:888,"
                 "pad=1280:960:0:72:color=0x080b06[body];[body][1:v]overlay=0:0[out]")
        subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", str(item["start"]),
                        "-t", str(item["source_duration"]), "-i", str(raw), "-loop", "1", "-i", str(scratch / f"caption-{index:02}.png"),
                        "-filter_complex_threads", "1", "-filter_complex", graph, "-map", "[out]", "-t", str(item["duration"]),
                        "-an", "-c:v", "libx264", "-threads", "2", "-preset", "fast", "-crf", "24", "-pix_fmt", "yuv420p", str(clip)], check=True)
        print(item["label"], flush=True)
    concat = scratch / "chapters.txt"
    concat.write_text("".join(f"file 'chapter-{i:02}.mp4'\n" for i in range(len(segments))))
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "1", "-i", str(concat),
                    "-c", "copy", "-movflags", "+faststart", str(destination)], check=True)
    duration = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                             "-of", "default=noprint_wrappers=1:nokey=1", str(destination)], text=True))
    if not 0 < duration < 120:
        raise RuntimeError(f"Video duration {duration} violates the under-two-minute requirement")
    receipt = {"video": destination.name, "duration_seconds": duration, "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
               "capture_kind": evidence["capture_kind"], "waiting_shortened": True, "chapters": segments}
    destination.with_suffix(".receipt.json").write_text(json.dumps(receipt, indent=2))
    print(f"Verified video: {duration:.2f}s; {destination.stat().st_size} bytes", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    asyncio.run(package(args.manifest, args.destination))
