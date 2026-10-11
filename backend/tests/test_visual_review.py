from pathlib import Path

from PIL import Image

from backend.database import Database
from backend.repositories import JourneyRepository, ProjectRepository
from backend.visual_review import VisualReview


class FakeAgents:
    def __init__(self, error=None):
        self.calls = []
        self.error = error
        self.settings = type("Settings", (), {"enable_n8n_visual": True})()

    def review_visual(self, summary):
        self.calls.append(summary)
        if self.error:
            raise self.error
        return {"summary": "Reviewed", "agent_id": "visual-agent"}


def setup(tmp_path):
    database = Database(tmp_path / "app.db")
    database.initialize()
    project = ProjectRepository(database).create({"name": "Web"})
    journey = JourneyRepository(database).create({"project_id": project["id"], "name": "Login", "target_url": "https://example.test", "script": "print(1)"})
    return database, journey


def screenshot(path: Path, color):
    Image.new("RGB", (12, 12), color).save(path)


def test_visual_first_pass_creates_baseline_and_second_compares_without_overwriting(tmp_path):
    database, journey = setup(tmp_path)
    agents = FakeAgents()
    review = VisualReview(database, tmp_path / "artifacts", agents, 0.1, 0.5)
    first, second = tmp_path / "first.png", tmp_path / "second.png"
    screenshot(first, "white")
    screenshot(second, "black")

    created = review.review(journey["id"], "run_one", [str(first)], passed=True)
    changed = review.review(journey["id"], "run_two", [str(second)], passed=True)

    assert created["status"] == "BASELINE_CREATED"
    assert changed["status"] == "DIFFERENCE"
    assert len(agents.calls) == 2
    assert set(agents.calls[-1]).issubset({"status", "mismatch_percentage", "mismatched_pixels", "tolerance_threshold", "baseline_key"})
    assert "100" in str(changed["mismatch_percentage"])
    assert JourneyRepository(database).get(journey["id"])["baseline_state"] == created["baseline_key"]


def test_visual_missing_and_failed_first_run_do_not_create_baseline(tmp_path):
    database, journey = setup(tmp_path)
    review = VisualReview(database, tmp_path / "artifacts", FakeAgents(), 0.1, 0.5)
    first = tmp_path / "first.png"
    screenshot(first, "white")

    assert review.review(journey["id"], "one", [str(first)], passed=False)["status"] == "BASELINE_NEEDED"
    assert review.review(journey["id"], "two", [], passed=True)["status"] == "UNAVAILABLE"
    assert JourneyRepository(database).get(journey["id"])["baseline_state"] is None


def test_visual_agent_error_does_not_change_local_comparison(tmp_path):
    database, journey = setup(tmp_path)
    first = tmp_path / "first.png"
    screenshot(first, "white")
    review = VisualReview(database, tmp_path / "artifacts", FakeAgents(error=TimeoutError()), 0.1, 0.5)

    result = review.review(journey["id"], "one", [str(first)], passed=True)

    assert result["status"] == "BASELINE_CREATED"
    assert result["agent_status"] == "ERROR"


def test_visual_retains_baseline_and_current_copies_independent_of_attempt_files(tmp_path):
    database, journey = setup(tmp_path)
    root = tmp_path / 'artifacts'
    shot = tmp_path / 'result.png'
    screenshot(shot, 'white')
    review = VisualReview(database, root, FakeAgents(), 0.1, 0.5)
    result = review.review(journey['id'], 'one', [str(shot)], passed=True)
    shot.unlink()
    assert Path(result['baseline_path']).is_file()
    assert Path(result['candidate_path']).is_file()
    assert Path(result['baseline_path']) != root / result['baseline_key']
