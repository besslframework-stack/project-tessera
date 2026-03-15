"""Tests for temporal validity (valid_from, superseded_at, auto-supersede)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.memory import save_memory, supersede_memory, recall_memories


class TestValidFromInFrontmatter:
    def test_save_memory_includes_valid_from(self, tmp_path):
        with patch("src.memory._memory_dir", return_value=tmp_path), \
             patch("src.memory._check_duplicate", return_value=None):
            path = save_memory("Test memory content here for validation", tags=["test"])
            content = path.read_text(encoding="utf-8")
            assert "valid_from:" in content

    def test_valid_from_is_iso_format(self, tmp_path):
        with patch("src.memory._memory_dir", return_value=tmp_path), \
             patch("src.memory._check_duplicate", return_value=None):
            path = save_memory("Another test memory for format check", tags=["test"])
            content = path.read_text(encoding="utf-8")
            for line in content.splitlines():
                if line.startswith("valid_from:"):
                    val = line.split(":", 1)[1].strip()
                    assert "T" in val


class TestSupersedeMemory:
    def _make_memory(self, tmp_path, name: str, content: str = "test") -> Path:
        path = tmp_path / f"{name}.md"
        path.write_text(
            f"---\ndate: 2026-03-15\nvalid_from: 2026-03-15\nsource: test\n"
            f"category: decision\ntags: [test]\n---\n\n{content}\n",
            encoding="utf-8",
        )
        return path

    def test_supersede_adds_field(self, tmp_path):
        path = self._make_memory(tmp_path, "mem1", "Use PostgreSQL")
        with patch("src.memory.index_memory", return_value=1):
            result = supersede_memory(path, superseded_by="mem2")
        assert result is True
        text = path.read_text()
        assert "superseded_at:" in text
        assert "superseded_by: mem2" in text

    def test_supersede_nonexistent_file(self, tmp_path):
        result = supersede_memory(tmp_path / "nonexistent.md")
        assert result is False

    def test_supersede_already_superseded(self, tmp_path):
        path = tmp_path / "mem1.md"
        path.write_text(
            "---\ndate: 2026-03-15\nsuperseded_at: 2026-03-15\n---\n\nOld\n",
            encoding="utf-8",
        )
        result = supersede_memory(path)
        assert result is True

    def test_supersede_preserves_content(self, tmp_path):
        path = self._make_memory(tmp_path, "mem1", "Important decision about databases")
        with patch("src.memory.index_memory", return_value=1):
            supersede_memory(path, superseded_by="mem2")
        text = path.read_text()
        assert "Important decision about databases" in text
        assert "date: 2026-03-15" in text

    def test_supersede_without_superseded_by(self, tmp_path):
        path = self._make_memory(tmp_path, "mem1", "Some fact")
        with patch("src.memory.index_memory", return_value=1):
            result = supersede_memory(path)
        assert result is True
        text = path.read_text()
        assert "superseded_at:" in text
        assert "superseded_by:" not in text


class TestRecallFiltersSuperseded:
    def _mock_lancedb(self, results):
        mock_table = MagicMock()
        mock_table.search.return_value.limit.return_value.to_list.return_value = results
        mock_db = MagicMock()
        mock_db.table_names.return_value = ["memories"]
        mock_db.open_table.return_value = mock_table
        return mock_db

    def _make_results(self):
        return [
            {
                "text": "Use PostgreSQL",
                "date": "2026-03-01",
                "category": "decision",
                "tags": "db",
                "source": "test",
                "file_path": "/tmp/mem1.md",
                "_distance": 0.1,
                "superseded_at": "2026-03-10",
            },
            {
                "text": "Use MongoDB instead",
                "date": "2026-03-10",
                "category": "decision",
                "tags": "db",
                "source": "test",
                "file_path": "/tmp/mem2.md",
                "_distance": 0.2,
                "superseded_at": "",
            },
        ]

    def test_excludes_superseded_by_default(self):
        mock_db = self._mock_lancedb(self._make_results())
        with patch("lancedb.connect", return_value=mock_db), \
             patch("src.memory.embed_query", return_value=[0.1] * 384), \
             patch("src.memory.Path.exists", return_value=True), \
             patch("src.config.settings") as ms:
            ms.data.lancedb_path = "/tmp/db"
            results = recall_memories("database", top_k=5, include_superseded=False)
        assert len(results) == 1
        assert results[0]["content"] == "Use MongoDB instead"

    def test_includes_superseded_when_requested(self):
        mock_db = self._mock_lancedb(self._make_results())
        with patch("lancedb.connect", return_value=mock_db), \
             patch("src.memory.embed_query", return_value=[0.1] * 384), \
             patch("src.memory.Path.exists", return_value=True), \
             patch("src.config.settings") as ms:
            ms.data.lancedb_path = "/tmp/db"
            results = recall_memories("database", top_k=5, include_superseded=True)
        assert len(results) == 2

    def test_no_superseded_field_treated_as_active(self):
        """Memories without superseded_at field should be treated as active."""
        results = [
            {
                "text": "Active memory",
                "date": "2026-03-15",
                "category": "fact",
                "tags": "",
                "source": "test",
                "file_path": "/tmp/mem.md",
                "_distance": 0.1,
                # No superseded_at field at all
            },
        ]
        mock_db = self._mock_lancedb(results)
        with patch("lancedb.connect", return_value=mock_db), \
             patch("src.memory.embed_query", return_value=[0.1] * 384), \
             patch("src.memory.Path.exists", return_value=True), \
             patch("src.config.settings") as ms:
            ms.data.lancedb_path = "/tmp/db"
            results = recall_memories("test", top_k=5, include_superseded=False)
        assert len(results) == 1


class TestIndexMemoryTemporalFields:
    def test_index_parses_valid_from(self, tmp_path):
        path = tmp_path / "test_mem.md"
        path.write_text(
            "---\ndate: 2026-03-15\nvalid_from: 2026-03-15T10:00:00\n"
            "source: test\ncategory: fact\ntags: [test]\n---\n\nSome fact\n",
            encoding="utf-8",
        )

        captured = {}
        mock_table = MagicMock()
        mock_table.add = lambda records: captured.update(records[0])
        mock_table.delete = MagicMock()

        mock_db = MagicMock()
        mock_db.table_names.return_value = ["memories"]
        mock_db.open_table.return_value = mock_table

        with patch("lancedb.connect", return_value=mock_db), \
             patch("src.embedding.get_embed_model") as mock_model:
            mock_model.return_value.embed.return_value = iter([[0.1] * 384])
            from src.memory import index_memory
            index_memory(path)

        assert captured.get("valid_from") == "2026-03-15T10:00:00"
        assert captured.get("superseded_at") == ""

    def test_index_parses_superseded_at(self, tmp_path):
        path = tmp_path / "test_mem2.md"
        path.write_text(
            "---\ndate: 2026-03-01\nvalid_from: 2026-03-01\n"
            "superseded_at: 2026-03-10T14:00:00\n"
            "source: test\ncategory: decision\ntags: [db]\n---\n\nOld decision\n",
            encoding="utf-8",
        )

        captured = {}
        mock_table = MagicMock()
        mock_table.add = lambda records: captured.update(records[0])
        mock_table.delete = MagicMock()

        mock_db = MagicMock()
        mock_db.table_names.return_value = ["memories"]
        mock_db.open_table.return_value = mock_table

        with patch("lancedb.connect", return_value=mock_db), \
             patch("src.embedding.get_embed_model") as mock_model:
            mock_model.return_value.embed.return_value = iter([[0.1] * 384])
            from src.memory import index_memory
            index_memory(path)

        assert captured.get("superseded_at") == "2026-03-10T14:00:00"
