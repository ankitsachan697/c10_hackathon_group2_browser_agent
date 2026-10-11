import pytest
from scripts.package_showcase import chapter_segments


def test_chapters_keep_real_capture_order_and_finish_under_two_minutes():
    evidence = {"passed": True, "raw_duration_seconds": 500,
                "bookmarks": [{"label": f"Chapter {i}", "seconds": i * 40} for i in range(12)]}
    chapters = chapter_segments(evidence)
    assert [item["start"] for item in chapters] == list(range(0, 480, 40))
    assert 0 < sum(item["duration"] for item in chapters) <= 110
    assert all(item["speed"] >= 1 for item in chapters)


def test_failed_capture_cannot_be_packaged_as_success():
    with pytest.raises(ValueError, match="verified"):
        chapter_segments({"passed": False})


def test_brief_objective_chapter_is_held_long_enough_to_read():
    chapters = chapter_segments({"passed": True, "raw_duration_seconds": 2,
                                "bookmarks": [{"label": "Objective", "seconds": 0}]})
    assert chapters[0]["duration"] == 4
