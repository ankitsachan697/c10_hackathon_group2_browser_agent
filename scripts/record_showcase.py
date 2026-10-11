"""Capture genuine Studio UI/agent runs. Synthetic fixture only; never mocks n8n.

Run from repo root with backend/.venv/bin/python scripts/record_showcase.py.
The raw video/evidence remain under artifacts (gitignored); no private env is read.
"""
import argparse
import asyncio
import json
import time
from pathlib import Path

from playwright.async_api import async_playwright, expect


async def capture(origin: str, output: Path):
    output.mkdir(parents=True, exist_ok=True)
    evidence = {"origin": origin, "capture_kind": "real-browser-real-agents", "bookmarks": []}
    started = time.monotonic()

    def mark(label):
        evidence["bookmarks"].append({"label": label, "seconds": round(time.monotonic() - started, 2)})
        print(label, flush=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=180)
        context = await browser.new_context(viewport={"width": 1440, "height": 1000},
                                            record_video_dir=str(output / "raw"),
                                            record_video_size={"width": 1440, "height": 1000})
        page = await context.new_page()
        video = page.video
        started = time.monotonic()

        async def data(path):
            response = await context.request.get(origin + path)
            if not response.ok:
                raise RuntimeError(f"API status {response.status}: {path}")
            return (await response.json())["data"]

        async def wait_operation(operation_id):
            for _ in range(300):
                operation = await data(f"/api/operations/{operation_id}")
                if operation["status"] in {"COMPLETED", "FAILED"}:
                    return operation
                await asyncio.sleep(1)
            raise RuntimeError("Generation did not finish within five minutes")

        async def wait_run(run_id):
            for _ in range(300):
                run = await data(f"/api/runs/{run_id}")
                if run["status"] in {"PASSED", "PASSED_AFTER_REPAIR", "NEEDS_ATTENTION", "FAILED"}:
                    return run
                await asyncio.sleep(1)
            raise RuntimeError("Run did not finish within five minutes")

        async def replay(source_id, label):
            await page.goto(origin + f"/runs/{source_id}")
            async with page.expect_response(lambda r: r.request.method == "POST" and r.url.endswith("/rerun")) as pending:
                await page.get_by_role("button", name="Run current script", exact=True).click()
            response = await pending.value
            if response.status != 202:
                raise RuntimeError(f"Replay was not queued: {response.status}")
            queued = (await response.json())["data"]
            evidence[label + "_run_id"] = queued["id"]
            await page.get_by_role("tab", name="Activity", exact=True).click()
            result = await wait_run(queued["id"])
            evidence[label] = {key: result.get(key) for key in ("status", "attempt_count", "visual_outcome", "diagnosis_json", "final_decision", "visual_review")}
            evidence[label + "_events"] = await data(f"/api/runs/{queued['id']}/events")
            await expect(page.get_by_text("Run " + queued["id"][:12], exact=True).filter(visible=True)).to_be_visible()
            await expect(page.get_by_role("button", name="Run current script", exact=True)).to_be_enabled()
            await page.screenshot(path=str(output / f"{label}.png"))
            return result

        try:
            await page.goto(origin + "/demo-lab")
            mark("01 · Create isolated demo shop")
            async with page.expect_response(lambda r: r.request.method == "POST" and r.url.endswith("/demo-lab/scenarios")) as pending:
                await page.get_by_role("button", name="New scenario", exact=True).click()
            scenario = (await (await pending.value).json())["data"]
            evidence["scenario_id"] = scenario["id"]
            await expect(page.get_by_label("Target URL")).to_have_value(origin + scenario["target_path"])
            await page.get_by_role("link", name="Create demo journey", exact=True).click()
            await expect(page.get_by_label("Username", exact=True)).to_have_value("demo@example.test")
            await page.get_by_label("Password", exact=True).fill("DemoPass123!")
            # Create a dedicated project in the same real UI.
            await page.get_by_label("Project", exact=True).select_option("__new__")
            await page.get_by_label("Project name", exact=True).fill(f"Group2 Showcase {int(time.time())}")
            await page.get_by_label("Project description", exact=True).fill("Synthetic shop · live n8n discovery, repair and visual comparison")
            await page.get_by_role("button", name="Create project", exact=True).click()
            mark("02 · Objective and masked credentials")
            await page.screenshot(path=str(output / "objective.png"))
            async with page.expect_response(lambda r: r.request.method == "POST" and r.url.endswith("/operations/generations")) as pending:
                await page.get_by_role("button", name="Verify & record live", exact=True).click()
            operation_id = (await (await pending.value).json())["data"]["id"]
            evidence["operation_id"] = operation_id
            await page.get_by_role("tab", name="Live console", exact=True).click()
            await page.get_by_role("region", name="Live verification").scroll_into_view_if_needed()
            mark("03 · Real n8n discovery and first execution")
            operation = await wait_operation(operation_id)
            evidence["operation_events"] = await data(f"/api/operations/{operation_id}/events")
            evidence["journey_id"] = operation.get("journey_id")
            if operation["status"] != "COMPLETED" or not operation.get("run_id"):
                raise RuntimeError(operation.get("error_message") or "Generation failed")
            base = await data(f"/api/runs/{operation['run_id']}")
            evidence["baseline_run_id"] = base["id"]
            evidence["baseline"] = {key: base.get(key) for key in ("status", "attempt_count", "visual_outcome", "visual_review")}
            if base["status"] not in {"PASSED", "PASSED_AFTER_REPAIR"}:
                raise RuntimeError(f"First run requires attention: {base['status']}")
            mark("04 · First run passed and scripts captured")
            await page.get_by_role("tab", name="Playwright Script", exact=True).click()
            await asyncio.sleep(3)
            await page.screenshot(path=str(output / "script.png"))
            await page.get_by_role("tab", name="Screenshots", exact=True).click()
            await asyncio.sleep(3)
            mark("05 · Induce a stale checkout locator on the target")
            await page.goto(origin + "/demo-lab")
            await page.get_by_label("Demo scenario").select_option(scenario["id"])
            await page.get_by_label("Change checkout locator").check()
            await expect(page.get_by_role("status")).to_contain_text("Target updated")
            mark("06 · Saved replay fails; real repair agent and one retry")
            repaired = await replay(base["id"], "repair")
            if repaired["status"] != "PASSED_AFTER_REPAIR" or repaired["attempt_count"] != 2:
                raise RuntimeError(f"Repair outcome: {repaired['status']}, attempts {repaired['attempt_count']}")
            mark("07 · Verified automatic repair")
            await page.get_by_role("tab", name="Repair", exact=True).click()
            await asyncio.sleep(4)
            await page.screenshot(path=str(output / "diagnosis.png"))
            await page.get_by_role("tab", name="Recording", exact=True).click()
            videos = page.locator("video")
            if await videos.count():
                await videos.last.evaluate("video => video.play()")
            await asyncio.sleep(4)
            mark("08 · Apply visual-only redesign")
            await page.goto(origin + "/demo-lab")
            await page.get_by_label("Demo scenario").select_option(scenario["id"])
            await page.get_by_label("Apply visual redesign").check()
            await expect(page.get_by_role("status")).to_contain_text("Target updated")
            visual = await replay(base["id"], "visual")
            if visual["status"] != "PASSED" or visual["visual_outcome"] != "DIFFERENCE":
                raise RuntimeError(f"Visual outcome: {visual['status']} / {visual['visual_outcome']}")
            mark("09 · Visual comparison: baseline, current, heatmap")
            await page.get_by_role("tab", name="Visual", exact=True).click()
            await expect(page.get_by_role("img", name="Difference heatmap")).to_be_visible()
            await asyncio.sleep(5)
            await page.screenshot(path=str(output / "visual-comparison.png"))
            mark("10 · Genuine business error requires manual attention")
            await page.goto(origin + "/demo-lab")
            await page.get_by_label("Demo scenario").select_option(scenario["id"])
            await page.get_by_label("Reject checkout").check()
            await expect(page.get_by_role("status")).to_contain_text("Target updated")
            negative = await replay(base["id"], "business_error")
            if negative["status"] != "NEEDS_ATTENTION" or negative["attempt_count"] != 1:
                raise RuntimeError("Rejected order was incorrectly marked successful")
            if any(event["kind"] == "repair.started" for event in evidence["business_error_events"]):
                raise RuntimeError("Business expectation was incorrectly sent for repair")
            mark("11 · Dashboard reflects saved results")
            await page.goto(origin + "/")
            await asyncio.sleep(3)
            evidence["overview"] = await data("/api/overview")
            await page.screenshot(path=str(output / "overview.png"))
            evidence["passed"] = True
            mark("12 · Showcase complete")
        except Exception as failure:
            evidence["passed"] = False
            evidence["failure"] = str(failure)[:1000]
            await page.screenshot(path=str(output / "capture-failure.png"))
            print("Capture requires attention:", evidence["failure"], flush=True)
        finally:
            await context.close()
            evidence["raw_video"] = await video.path()
            evidence["raw_duration_seconds"] = round(time.monotonic() - started, 2)
            (output / "evidence.json").write_text(json.dumps(evidence, indent=2))
            await browser.close()
    return evidence["passed"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--origin", default="http://localhost:3000")
    parser.add_argument("--output", type=Path, default=Path("artifacts/showcase"))
    args = parser.parse_args()
    raise SystemExit(0 if asyncio.run(capture(args.origin.rstrip('/'), args.output)) else 1)
