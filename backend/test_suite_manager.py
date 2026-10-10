"""
Test Suite & Golden Baseline Registry Manager.
Handles:
1. Test case persistence across projects/suites
2. Golden Baseline lifecycle (1st run vs subsequent runs)
3. Run history tracking with videos, screenshots, and telemetry
"""

import os
import re
import json
import time
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional
from visual_diff import compare_images

try:
    from .config import Settings
except ImportError:
    from config import Settings


DEFAULT_SUITES_DIR = Path(__file__).resolve().parent / "test_suites"


def _get_slug(url: str, name: str = "") -> str:
    combined = f"{name}_{url}" if name else url
    clean = re.sub(r'https?://', '', combined)
    clean = re.sub(r'[^a-zA-Z0-9_-]', '_', clean).strip('_')
    return clean[:50] or "default_test"


class TestSuiteManager:
    def __init__(self, suites_dir: Path | str = DEFAULT_SUITES_DIR, artifacts_root: Path | str | None = None):
        settings = Settings.from_env()
        self.suites_dir = Path(suites_dir)
        self.cases_file = self.suites_dir / "cases.json"
        self.runs_file = self.suites_dir / "runs_history.json"
        self.artifacts_root = Path(artifacts_root) if artifacts_root else settings.artifacts_root
        self.baselines_dir = self.artifacts_root / "baselines"
        self._ensure_files()

    def _ensure_files(self):
        self.suites_dir.mkdir(parents=True, exist_ok=True)
        self.baselines_dir.mkdir(parents=True, exist_ok=True)
        if not self.cases_file.exists():
            with self.cases_file.open("w", encoding="utf-8") as f:
                json.dump([], f, indent=2)

        if not self.runs_file.exists():
            with self.runs_file.open("w", encoding="utf-8") as f:
                json.dump([], f, indent=2)

    def get_test_cases(self) -> List[Dict[str, Any]]:
        try:
            with self.cases_file.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def save_test_case(self, case_data: Dict[str, Any]) -> Dict[str, Any]:
        cases = self.get_test_cases()
        case_id = case_data.get("id") or f"tc_{int(time.time())}"
        case_data["id"] = case_id
        case_data["created_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

        # Update if exists, else append
        existing_idx = next((i for i, c in enumerate(cases) if c["id"] == case_id), -1)
        if existing_idx >= 0:
            cases[existing_idx] = case_data
        else:
            cases.append(case_data)

        with self.cases_file.open("w", encoding="utf-8") as f:
            json.dump(cases, f, indent=2)
        return case_data

    def delete_test_case(self, case_id: str) -> bool:
        cases = self.get_test_cases()
        filtered = [c for c in cases if c["id"] != case_id]
        with self.cases_file.open("w", encoding="utf-8") as f:
            json.dump(filtered, f, indent=2)
        return len(filtered) < len(cases)

    def record_run(self, run_record: Dict[str, Any]):
        try:
            with self.runs_file.open("r", encoding="utf-8") as f:
                runs = json.load(f)
        except Exception:
            runs = []
        runs.insert(0, run_record)
        runs = runs[:100]  # Keep last 100 runs
        with self.runs_file.open("w", encoding="utf-8") as f:
            json.dump(runs, f, indent=2)

    def get_run_history(self) -> List[Dict[str, Any]]:
        try:
            with self.runs_file.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def get_test_case(self, case_id: str) -> Optional[Dict[str, Any]]:
        cases = self.get_test_cases()
        return next((c for c in cases if c.get("id") == case_id), None)

    def handle_visual_baseline_lifecycle(
        self,
        url: str,
        test_case_name: str,
        screenshots: List[str],
        run_dir: str,
        threshold: float,
        tolerance_percent: float,
    ) -> Dict[str, Any]:
        """
        Manages Golden Baseline lifecycle:
        - 1st Run: Saves captured screenshots as the reference Golden Baseline.
        - Subsequent Runs: Performs Pixelmatch comparison against the stored Golden Baseline!
        """
        if not screenshots:
            return {
                "status": "NO_SCREENSHOTS",
                "passed": True,
                "summary": "No screenshots captured to evaluate.",
                "is_first_run": False,
            }

        slug = _get_slug(url, test_case_name)
        case_baseline_dir = self.baselines_dir / slug
        golden_file = os.path.join(case_baseline_dir, "golden_result.png")

        candidate_file = os.path.join(run_dir, screenshots[-1])

        # First Run Check: If no baseline exists, establish it!
        if not os.path.exists(golden_file):
            case_baseline_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(candidate_file, golden_file)
            return {
                "status": "BASELINE_ESTABLISHED",
                "passed": True,
                "is_first_run": True,
                "baseline_key": slug,
                "golden_path": f"baselines/{slug}/golden_result.png",
                "golden_image": f"baselines/{slug}/golden_result.png",
                "summary": f"🌟 Golden Baseline established for '{slug}'. Subsequent runs will monitor layout drift against this master snapshot.",
                "mismatch_percentage": 0.0,
            }

        # Subsequent Run: Perform Pixelmatch diff against Golden Baseline!
        diff_out = os.path.join(run_dir, "visual_diff.png")
        diff_res = compare_images(
            baseline_path=golden_file,
            candidate_path=candidate_file,
            output_diff_path=diff_out,
            threshold=threshold,
            tolerance_percent=tolerance_percent,
        )
        diff_res["is_first_run"] = False
        diff_res["baseline_key"] = slug
        diff_res["baseline_image"] = f"baselines/{slug}/golden_result.png"
        diff_res["candidate_image"] = screenshots[-1]
        diff_res["diff_image"] = "visual_diff.png"
        return diff_res


suite_manager = TestSuiteManager()
