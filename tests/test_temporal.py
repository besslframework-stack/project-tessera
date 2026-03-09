"""Tests for temporal index — time-based memory filtering (v0.7.2)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestRecallMemoriesFilters:
    """Test recall_memories with since/until/category filters."""

    def _make_recall_results(self):
        """Simulate LanceDB search results with dates and categories."""
        return [
            {"text": "Use PostgreSQL", "date": "2026-03-01T10:00:00", "category": "decision", "tags": "", "source": "", "file_path": "/tmp/a.md", "_distance": 0.1},
            {"text": "Prefer TypeScript", "date": "2026-03-05T10:00:00", "category": "preference", "tags": "", "source": "", "file_path": "/tmp/b.md", "_distance": 0.2},
            {"text": "API rate limit 100", "date": "2026-03-08T10:00:00", "category": "fact", "tags": "", "source": "", "file_path": "/tmp/c.md", "_distance": 0.3},
            {"text": "Old decision", "date": "2026-02-15T10:00:00", "category": "decision", "tags": "", "source": "", "file_path": "/tmp/d.md", "_distance": 0.4},
        ]

    def test_since_filter(self):
        from src.memory import recall_memories

        mock_table = MagicMock()
        mock_search = MagicMock()
        mock_search.limit.return_value = mock_search
        mock_search.to_list.return_value = self._make_recall_results()
        mock_table.search.return_value = mock_search

        mock_db = MagicMock()
        mock_db.table_names.return_value = ["memories"]
        mock_db.open_table.return_value = mock_table

        with patch("lancedb.connect", return_value=mock_db), \
             patch("src.memory.embed_query", return_value=[0.1] * 384), \
             patch("src.memory.Path.exists", return_value=True), \
             patch("src.config.settings") as ms:
            ms.data.lancedb_path = "/tmp/db"
            results = recall_memories("test", top_k=10, since="2026-03-04")
            # Should exclude "Use PostgreSQL" (March 1) and "Old decision" (Feb 15)
            dates = [r["date"][:10] for r in results]
            assert all(d >= "2026-03-04" for d in dates)
            assert len(results) == 2

    def test_until_filter(self):
        from src.memory import recall_memories

        mock_table = MagicMock()
        mock_search = MagicMock()
        mock_search.limit.return_value = mock_search
        mock_search.to_list.return_value = self._make_recall_results()
        mock_table.search.return_value = mock_search

        mock_db = MagicMock()
        mock_db.table_names.return_value = ["memories"]
        mock_db.open_table.return_value = mock_table

        with patch("lancedb.connect", return_value=mock_db), \
             patch("src.memory.embed_query", return_value=[0.1] * 384), \
             patch("src.memory.Path.exists", return_value=True), \
             patch("src.config.settings") as ms:
            ms.data.lancedb_path = "/tmp/db"
            results = recall_memories("test", top_k=10, until="2026-03-04")
            dates = [r["date"][:10] for r in results]
            assert all(d <= "2026-03-04" for d in dates)

    def test_category_filter(self):
        from src.memory import recall_memories

        mock_table = MagicMock()
        mock_search = MagicMock()
        mock_search.limit.return_value = mock_search
        mock_search.to_list.return_value = self._make_recall_results()
        mock_table.search.return_value = mock_search

        mock_db = MagicMock()
        mock_db.table_names.return_value = ["memories"]
        mock_db.open_table.return_value = mock_table

        with patch("lancedb.connect", return_value=mock_db), \
             patch("src.memory.embed_query", return_value=[0.1] * 384), \
             patch("src.memory.Path.exists", return_value=True), \
             patch("src.config.settings") as ms:
            ms.data.lancedb_path = "/tmp/db"
            results = recall_memories("test", top_k=10, category="decision")
            assert all(r["category"] == "decision" for r in results)
            assert len(results) == 2

    def test_combined_filters(self):
        from src.memory import recall_memories

        mock_table = MagicMock()
        mock_search = MagicMock()
        mock_search.limit.return_value = mock_search
        mock_search.to_list.return_value = self._make_recall_results()
        mock_table.search.return_value = mock_search

        mock_db = MagicMock()
        mock_db.table_names.return_value = ["memories"]
        mock_db.open_table.return_value = mock_table

        with patch("lancedb.connect", return_value=mock_db), \
             patch("src.memory.embed_query", return_value=[0.1] * 384), \
             patch("src.memory.Path.exists", return_value=True), \
             patch("src.config.settings") as ms:
            ms.data.lancedb_path = "/tmp/db"
            results = recall_memories("test", top_k=10, since="2026-03-01", category="decision")
            assert len(results) == 1
            assert results[0]["content"] == "Use PostgreSQL"

    def test_no_filters(self):
        from src.memory import recall_memories

        mock_table = MagicMock()
        mock_search = MagicMock()
        mock_search.limit.return_value = mock_search
        mock_search.to_list.return_value = self._make_recall_results()
        mock_table.search.return_value = mock_search

        mock_db = MagicMock()
        mock_db.table_names.return_value = ["memories"]
        mock_db.open_table.return_value = mock_table

        with patch("lancedb.connect", return_value=mock_db), \
             patch("src.memory.embed_query", return_value=[0.1] * 384), \
             patch("src.memory.Path.exists", return_value=True), \
             patch("src.config.settings") as ms:
            ms.data.lancedb_path = "/tmp/db"
            results = recall_memories("test", top_k=10)
            assert len(results) == 4


class TestRecallCoreFunction:
    """Test core.recall with filters."""

    def test_recall_with_filters_no_results(self):
        from src.core import recall
        with patch("src.memory.recall_memories", return_value=[]):
            result = recall("test query", since="2099-01-01")
            assert "No memories found" in result
            assert "since=2099-01-01" in result

    def test_recall_shows_category(self):
        from src.core import recall
        memories = [{
            "content": "Use PostgreSQL",
            "date": "2026-03-01",
            "category": "decision",
            "tags": "",
            "source": "",
            "similarity": 0.95,
        }]
        with patch("src.memory.recall_memories", return_value=memories):
            result = recall("database")
            assert "[decision]" in result
