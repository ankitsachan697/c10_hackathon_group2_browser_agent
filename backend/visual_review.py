"""Deterministic screenshot baseline lifecycle with optional bounded agent review."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

try:
    from .database import Database
    from .repositories import JourneyRepository
    from .visual_diff import compare_images
except ImportError:
    from database import Database
    from repositories import JourneyRepository
    from visual_diff import compare_images


class VisualReview:
    def __init__(self, database: Database, artifacts_dir: str | Path, agents: Any,
                 threshold: float, tolerance_percent: float):
        self.journeys = JourneyRepository(database)
        self.artifacts_dir = Path(artifacts_dir).resolve()
        self.agents = agents
        self.threshold = threshold
        self.tolerance_percent = tolerance_percent

    def review(self, journey_id: str, run_id: str, screenshots: list[str], *, passed: bool) -> dict[str, Any]:
        journey = self.journeys.get(journey_id)
        if not journey:
            raise KeyError(journey_id)
        candidate = next((Path(item).resolve() for item in screenshots if Path(item).is_file()), None)
        if not candidate:
            return {"status": "UNAVAILABLE", "reason": "No screenshot was captured"}
        baseline_key = journey.get("baseline_state")
        if not baseline_key:
            if not passed:
                return {"status": "BASELINE_NEEDED", "reason": "A passing run is required to establish a baseline"}
            baseline_key = f"baselines/{journey_id}.png"
            baseline = (self.artifacts_dir / baseline_key).resolve()
            if not baseline.is_relative_to(self.artifacts_dir):
                raise ValueError("Invalid baseline path")
            baseline.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(candidate, baseline)
            self.journeys.update(journey_id, {"baseline_state": baseline_key})
            result: dict[str, Any] = {"status": "BASELINE_CREATED", "baseline_key": baseline_key}
        else:
            baseline = (self.artifacts_dir / baseline_key).resolve()
            if not baseline.is_relative_to(self.artifacts_dir) or not baseline.is_file():
                return {"status": "ERROR", "reason": "Saved baseline is unavailable"}
            diff_path = (self.artifacts_dir / "visual_diffs" / f"{run_id}.png").resolve()
            if not diff_path.is_relative_to(self.artifacts_dir):
                raise ValueError("Invalid diff path")
            comparison = compare_images(str(baseline), str(candidate), str(diff_path), self.threshold, self.tolerance_percent)
            result = {
                "status": "MATCH" if comparison.get("passed") else "DIFFERENCE",
                "baseline_key": baseline_key,
                "mismatch_percentage": comparison.get("mismatch_percentage"),
                "mismatched_pixels": comparison.get("mismatched_pixels"),
                "tolerance_threshold": self.tolerance_percent,
                "diff_path": str(diff_path),
            }
        settings = getattr(self.agents, "settings", None)
        if getattr(settings, "enable_n8n_visual", False):
            summary = {key: result[key] for key in (
                "status", "baseline_key", "mismatch_percentage", "mismatched_pixels", "tolerance_threshold"
            ) if key in result}
            try:
                agent_result = self.agents.review_visual(summary)
                result["agent_status"] = "REVIEWED"
                result["agent_id"] = agent_result.get("agent_id")
                result["agent_summary"] = str(agent_result.get("summary", ""))[:1000]
            except Exception as error:
                result["agent_status"] = "ERROR"
                result["agent_error_code"] = str(getattr(error, "code", type(error).__name__))
        else:
            result["agent_status"] = "DISABLED"
        return result
