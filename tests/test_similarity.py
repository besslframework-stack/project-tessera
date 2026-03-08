"""Tests for src.similarity helper functions and find_similar_to_text."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.similarity import _build_result, _deduplicate_by_source, find_similar_to_text


class TestBuildResult:
    """Tests for _build_result(meta, similarity, text)."""

    def test_build_result(self) -> None:
        """Verify the returned dict has all expected keys with correct values."""
        meta = {
            "source_path": "/a/b.md",
            "file_name": "b.md",
            "section": "intro",
        }
        result = _build_result(meta, similarity=0.8, text="some text here")

        assert result["source_path"] == "/a/b.md"
        assert result["file_name"] == "b.md"
        assert result["section"] == "intro"
        assert result["similarity"] == 0.8
        assert result["text_preview"] == "some text here"

    def test_build_result_truncates_preview(self) -> None:
        """text_preview should be capped at 200 characters."""
        long_text = "x" * 500
        result = _build_result({}, similarity=0.5, text=long_text)
        assert len(result["text_preview"]) == 200

    def test_build_result_missing_meta_keys(self) -> None:
        """Missing metadata keys should default to empty strings."""
        result = _build_result({}, similarity=0.0, text="")
        assert result["source_path"] == ""
        assert result["file_name"] == ""
        assert result["section"] == ""
        assert result["text_preview"] == ""


class TestDeduplicateBySource:
    """Tests for _deduplicate_by_source(rows)."""

    def test_deduplicate_by_source(self) -> None:
        """Keeps only the highest similarity entry per source_path."""
        rows = [
            {"source_path": "/a.md", "similarity": 0.7, "other": "first"},
            {"source_path": "/a.md", "similarity": 0.9, "other": "second"},
            {"source_path": "/b.md", "similarity": 0.8, "other": "third"},
        ]
        result = _deduplicate_by_source(rows)

        assert len(result) == 2
        by_path = {r["source_path"]: r for r in result}
        assert by_path["/a.md"]["similarity"] == 0.9
        assert by_path["/a.md"]["other"] == "second"
        assert by_path["/b.md"]["similarity"] == 0.8

    def test_deduplicate_preserves_order(self) -> None:
        """After dedup, results can be sorted by similarity descending."""
        rows = [
            {"source_path": "/c.md", "similarity": 0.3},
            {"source_path": "/a.md", "similarity": 0.9},
            {"source_path": "/b.md", "similarity": 0.6},
        ]
        result = _deduplicate_by_source(rows)
        # Sort like the caller does
        result.sort(key=lambda x: x["similarity"], reverse=True)

        similarities = [r["similarity"] for r in result]
        assert similarities == sorted(similarities, reverse=True)
        assert similarities == [0.9, 0.6, 0.3]

    def test_deduplicate_single_entry(self) -> None:
        """Single entry list should pass through unchanged."""
        rows = [{"source_path": "/only.md", "similarity": 0.5}]
        result = _deduplicate_by_source(rows)
        assert len(result) == 1
        assert result[0]["source_path"] == "/only.md"

    def test_deduplicate_empty(self) -> None:
        """Empty input should return empty output."""
        assert _deduplicate_by_source([]) == []


class TestFindSimilarToText:
    """Tests for find_similar_to_text with mocked DB."""

    @patch("src.similarity._open_table", return_value=None)
    def test_find_similar_no_db(self, mock_open_table) -> None:
        """Returns empty list when the DB table does not exist."""
        result = find_similar_to_text("some query text", top_k=5)
        assert result == []
        mock_open_table.assert_called_once()
