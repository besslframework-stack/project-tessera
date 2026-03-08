"""Tests for document freshness checking (src/freshness.py)."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.sync import FileMetaDB


@pytest.fixture
def setup_workspace(tmp_path: Path, monkeypatch):
    """Create a temp workspace with real files and a FileMetaDB.

    Produces two files:
    - old_doc.md  -- mtime set to 120 days ago
    - recent_doc.md -- mtime left at creation time (now)

    Patches ``src.freshness.workspace`` so check_freshness reads from
    the temp DB instead of the real workspace.
    """
    db_path = tmp_path / "file_meta.db"

    mock_ws = MagicMock(
        meta_db_path=db_path,
        projects={},
    )
    monkeypatch.setattr("src.freshness.workspace", mock_ws)

    meta_db = FileMetaDB(db_path)

    # Old file -- 120 days ago
    old_file = tmp_path / "old_doc.md"
    old_file.write_text("old content")
    old_mtime = (datetime.now() - timedelta(days=120)).timestamp()
    os.utime(old_file, (old_mtime, old_mtime))
    meta_db.upsert_file(str(old_file), old_mtime, old_file.stat().st_size)

    # Recent file -- just created
    recent_file = tmp_path / "recent_doc.md"
    recent_file.write_text("recent content")
    meta_db.upsert_file(
        str(recent_file),
        recent_file.stat().st_mtime,
        recent_file.stat().st_size,
    )

    meta_db.close()
    return tmp_path


@pytest.fixture
def setup_workspace_all_recent(tmp_path: Path, monkeypatch):
    """Workspace where every tracked file is recent (< 10 days old)."""
    db_path = tmp_path / "file_meta.db"

    mock_ws = MagicMock(
        meta_db_path=db_path,
        projects={},
    )
    monkeypatch.setattr("src.freshness.workspace", mock_ws)

    meta_db = FileMetaDB(db_path)

    for name in ("alpha.md", "beta.md", "gamma.md"):
        f = tmp_path / name
        f.write_text(f"content of {name}")
        meta_db.upsert_file(str(f), f.stat().st_mtime, f.stat().st_size)

    meta_db.close()
    return tmp_path


@pytest.fixture
def setup_workspace_multiple_stale(tmp_path: Path, monkeypatch):
    """Workspace with several stale files of varying age."""
    db_path = tmp_path / "file_meta.db"

    mock_ws = MagicMock(
        meta_db_path=db_path,
        projects={},
    )
    monkeypatch.setattr("src.freshness.workspace", mock_ws)

    meta_db = FileMetaDB(db_path)

    ages = [200, 150, 300, 100]
    for i, days in enumerate(ages):
        f = tmp_path / f"stale_{i}.md"
        f.write_text(f"stale content {i}")
        mtime = (datetime.now() - timedelta(days=days)).timestamp()
        os.utime(f, (mtime, mtime))
        meta_db.upsert_file(str(f), mtime, f.stat().st_size)

    meta_db.close()
    return tmp_path


class TestCheckFreshness:
    """Tests for check_freshness()."""

    def test_no_stale_files(self, setup_workspace_all_recent: Path) -> None:
        """When all files are recent, check_freshness returns an empty list."""
        from src.freshness import check_freshness

        result = check_freshness(days_threshold=90)
        assert result == []

    def test_stale_files_detected(self, setup_workspace: Path) -> None:
        """Files older than the threshold are returned as stale."""
        from src.freshness import check_freshness

        result = check_freshness(days_threshold=90)
        assert len(result) == 1

        entry = result[0]
        assert entry["file_name"] == "old_doc.md"
        assert entry["status"] == "stale"
        assert entry["days_ago"] > 90
        assert "file_path" in entry
        assert "last_modified" in entry

    def test_sorted_by_days_ago(self, setup_workspace_multiple_stale: Path) -> None:
        """Results are sorted by days_ago descending (oldest first)."""
        from src.freshness import check_freshness

        result = check_freshness(days_threshold=90)
        assert len(result) >= 2

        days_values = [r["days_ago"] for r in result]
        assert days_values == sorted(days_values, reverse=True), (
            "Expected results sorted by days_ago descending"
        )

    def test_custom_threshold(self, setup_workspace: Path) -> None:
        """A stricter threshold (30 days) catches more files."""
        from src.freshness import check_freshness

        result_90 = check_freshness(days_threshold=90)
        result_30 = check_freshness(days_threshold=30)

        # The 120-day-old file should appear in both; recent file only in the
        # 30-day check (if it were > 30 days, which it isn't since it's fresh).
        assert len(result_30) >= len(result_90)

    def test_entry_fields(self, setup_workspace: Path) -> None:
        """Each entry dict contains the documented keys."""
        from src.freshness import check_freshness

        result = check_freshness(days_threshold=90)
        assert len(result) >= 1

        required_keys = {"file_path", "file_name", "last_modified", "days_ago", "status"}
        for entry in result:
            assert required_keys.issubset(entry.keys())

    def test_missing_file_skipped(self, tmp_path: Path, monkeypatch) -> None:
        """If a tracked file no longer exists on disk, it is silently skipped."""
        from src.freshness import check_freshness

        db_path = tmp_path / "file_meta.db"
        mock_ws = MagicMock(meta_db_path=db_path, projects={})
        monkeypatch.setattr("src.freshness.workspace", mock_ws)

        meta_db = FileMetaDB(db_path)
        # Track a non-existent file
        meta_db.upsert_file("/nonexistent/ghost.md", 1000.0, 42)
        meta_db.close()

        result = check_freshness(days_threshold=1)
        assert result == []


class TestFreshnessSummary:
    """Tests for freshness_summary()."""

    def test_summary_no_stale(self, setup_workspace_all_recent: Path) -> None:
        """When no files are stale, returns the 'up to date' message."""
        from src.freshness import freshness_summary

        summary = freshness_summary(days_threshold=90)
        assert summary == "All documents are up to date."

    def test_summary_with_stale(self, setup_workspace: Path) -> None:
        """Summary contains markdown formatting and the stale file name."""
        from src.freshness import freshness_summary

        summary = freshness_summary(days_threshold=90)
        assert "# Stale Documents" in summary
        assert "old_doc.md" in summary
        assert "days ago" in summary

    def test_summary_contains_count(self, setup_workspace_multiple_stale: Path) -> None:
        """Summary header includes the total count of stale files."""
        from src.freshness import freshness_summary

        summary = freshness_summary(days_threshold=90)
        # All 4 files (ages 200, 150, 300, 100) exceed 90 days
        assert "4 files" in summary

    def test_summary_custom_threshold(self, setup_workspace: Path) -> None:
        """Summary respects a custom threshold value."""
        from src.freshness import freshness_summary

        summary = freshness_summary(days_threshold=30)
        assert "30 days" in summary or summary == "All documents are up to date."
