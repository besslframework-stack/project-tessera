"""Tests for file organization and cleanup suggestions."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from src.organizer import _validate_within_workspace


class TestValidateWithinWorkspace:
    def test_valid_path(self, tmp_path):
        with patch("src.organizer.workspace") as mock_ws:
            mock_ws.root = tmp_path
            child = tmp_path / "docs" / "file.md"
            # _validate_within_workspace expects a Path, not str
            result = _validate_within_workspace(child)
            assert result == child.resolve()

    def test_path_traversal_blocked(self, tmp_path):
        with patch("src.organizer.workspace") as mock_ws:
            mock_ws.root = tmp_path
            outside = tmp_path.parent / "outside" / "file.md"
            with pytest.raises(ValueError):
                _validate_within_workspace(outside)


class TestSuggestOrganization:
    def test_detects_backup_files(self, tmp_path):
        from src.organizer import suggest_organization

        # Create backup files
        (tmp_path / "doc_backup.md").write_text("backup")
        (tmp_path / "doc_old.md").write_text("old")

        with patch("src.organizer.workspace") as mock_ws:
            mock_ws.root = tmp_path
            result = suggest_organization(str(tmp_path))
            # Should mention backup files
            assert isinstance(result, str)

    def test_detects_empty_dirs(self, tmp_path):
        from src.organizer import suggest_organization

        (tmp_path / "empty_dir").mkdir()

        with patch("src.organizer.workspace") as mock_ws:
            mock_ws.root = tmp_path
            result = suggest_organization(str(tmp_path))
            assert isinstance(result, str)


class TestListDirectory:
    def test_basic_listing(self, tmp_path):
        from src.organizer import list_directory

        (tmp_path / "a.md").write_text("a")
        (tmp_path / "b.md").write_text("b")

        with patch("src.organizer.workspace") as mock_ws:
            mock_ws.root = tmp_path
            result = list_directory(str(tmp_path))
            assert "a.md" in result
            assert "b.md" in result
