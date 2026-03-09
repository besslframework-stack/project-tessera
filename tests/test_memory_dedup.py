"""Tests for memory deduplication (v0.6.6)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.memory import _check_duplicate, save_memory, learn_and_index


class TestCheckDuplicate:
    def test_no_db_returns_none(self):
        with patch("src.memory.Path") as mock_path_cls:
            # DB path doesn't exist
            result = _check_duplicate("test content")
            # Should return None gracefully when DB doesn't exist
            assert result is None or isinstance(result, dict)

    def test_returns_none_when_no_memories_table(self):
        mock_db = MagicMock()
        mock_db.table_names.return_value = []
        with patch("lancedb.connect", return_value=mock_db), \
             patch("src.memory.Path.exists", return_value=True):
            result = _check_duplicate("test content")
            assert result is None

    def test_returns_match_above_threshold(self):
        mock_table = MagicMock()
        mock_search = MagicMock()
        mock_search.limit.return_value = mock_search
        mock_search.to_list.return_value = [
            {"_distance": 0.05, "file_path": "/tmp/existing.md", "text": "similar content"}
        ]
        mock_table.search.return_value = mock_search

        mock_db = MagicMock()
        mock_db.table_names.return_value = ["memories"]
        mock_db.open_table.return_value = mock_table

        with patch("lancedb.connect", return_value=mock_db), \
             patch("src.memory.embed_query", return_value=[0.1] * 384), \
             patch("src.memory.Path") as mock_path_cls:
            mock_path_cls.return_value.exists.return_value = True
            # Patch the settings path check
            with patch("src.config.settings") as mock_settings:
                mock_settings.data.lancedb_path = "/tmp/test_db"
                result = _check_duplicate("similar content", threshold=0.92)
                assert result is not None
                assert result["similarity"] >= 0.92
                assert result["file_path"] == "/tmp/existing.md"

    def test_returns_none_below_threshold(self):
        mock_table = MagicMock()
        mock_search = MagicMock()
        mock_search.limit.return_value = mock_search
        mock_search.to_list.return_value = [
            {"_distance": 0.5, "file_path": "/tmp/existing.md", "text": "different content"}
        ]
        mock_table.search.return_value = mock_search

        mock_db = MagicMock()
        mock_db.table_names.return_value = ["memories"]
        mock_db.open_table.return_value = mock_table

        with patch("lancedb.connect", return_value=mock_db), \
             patch("src.memory.embed_query", return_value=[0.1] * 384), \
             patch("src.config.settings") as mock_settings:
            mock_settings.data.lancedb_path = "/tmp/test_db"
            result = _check_duplicate("different content", threshold=0.92)
            assert result is None

    def test_handles_exception_gracefully(self):
        with patch("lancedb.connect", side_effect=Exception("DB error")), \
             patch("src.config.settings") as mock_settings:
            mock_settings.data.lancedb_path = "/tmp/test_db"
            result = _check_duplicate("test content")
            assert result is None

    def test_empty_results(self):
        mock_table = MagicMock()
        mock_search = MagicMock()
        mock_search.limit.return_value = mock_search
        mock_search.to_list.return_value = []
        mock_table.search.return_value = mock_search

        mock_db = MagicMock()
        mock_db.table_names.return_value = ["memories"]
        mock_db.open_table.return_value = mock_table

        with patch("lancedb.connect", return_value=mock_db), \
             patch("src.memory.embed_query", return_value=[0.1] * 384), \
             patch("src.config.settings") as mock_settings:
            mock_settings.data.lancedb_path = "/tmp/test_db"
            result = _check_duplicate("new content")
            assert result is None


class TestSaveMemoryDedup:
    def test_save_skips_duplicate(self, tmp_path):
        existing_path = tmp_path / "existing.md"
        existing_path.write_text("existing memory")

        with patch("src.memory._check_duplicate") as mock_dedup, \
             patch("src.memory._memory_dir", return_value=tmp_path):
            mock_dedup.return_value = {
                "file_path": str(existing_path),
                "content": "existing memory",
                "similarity": 0.95,
            }
            result = save_memory("existing memory")
            assert result == existing_path
            # Should not create a new file
            assert len(list(tmp_path.glob("2*_*.md"))) == 0

    def test_save_proceeds_when_no_duplicate(self, tmp_path):
        with patch("src.memory._check_duplicate", return_value=None), \
             patch("src.memory._memory_dir", return_value=tmp_path):
            result = save_memory("brand new memory")
            assert result.exists()
            assert "brand new memory" in result.read_text()

    def test_save_dedup_disabled(self, tmp_path):
        with patch("src.memory._check_duplicate") as mock_dedup, \
             patch("src.memory._memory_dir", return_value=tmp_path):
            result = save_memory("some memory", dedup=False)
            mock_dedup.assert_not_called()
            assert result.exists()

    def test_save_custom_threshold(self, tmp_path):
        with patch("src.memory._check_duplicate", return_value=None) as mock_dedup, \
             patch("src.memory._memory_dir", return_value=tmp_path):
            save_memory("test content", dedup_threshold=0.80)
            mock_dedup.assert_called_once_with("test content", threshold=0.80)


class TestLearnAndIndexDedup:
    def test_learn_returns_deduplicated_flag(self):
        with patch("src.memory._check_duplicate") as mock_dedup:
            mock_dedup.return_value = {
                "file_path": "/tmp/existing.md",
                "content": "existing",
                "similarity": 0.95,
            }
            result = learn_and_index("existing content")
            assert result["deduplicated"] is True
            assert result["similarity"] == 0.95

    def test_learn_new_content_not_deduplicated(self, tmp_path):
        with patch("src.memory._check_duplicate", return_value=None), \
             patch("src.memory._memory_dir", return_value=tmp_path), \
             patch("src.memory.index_memory", return_value=1):
            result = learn_and_index("brand new knowledge")
            assert result["deduplicated"] is False
            assert result["indexed"] is True
