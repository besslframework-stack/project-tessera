"""Tests for operational tools: tessera_status, list_memories, forget_memory."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest


class TestListMemories:
    def test_no_memories(self, tmp_path):
        from mcp_server import list_memories

        with patch("src.memory._memory_dir", return_value=tmp_path):
            result = list_memories()
            assert "no memories" in result.lower()

    def test_with_memories(self, tmp_path):
        from mcp_server import list_memories

        mem = tmp_path / "20260309_120000_test.md"
        mem.write_text("---\ntags: [general]\n---\n\nTest memory content here")

        with patch("src.memory._memory_dir", return_value=tmp_path):
            result = list_memories()
            assert "20260309_120000_test" in result
            assert "Test memory content" in result

    def test_limit(self, tmp_path):
        from mcp_server import list_memories

        for i in range(5):
            (tmp_path / f"mem_{i:02d}.md").write_text(f"---\n---\n\nContent {i}")

        with patch("src.memory._memory_dir", return_value=tmp_path):
            result = list_memories(limit=2)
            # Should show limited results
            assert "2" in result


class TestForgetMemory:
    def test_empty_name(self):
        from mcp_server import forget_memory

        result = forget_memory(memory_name="")
        assert "provide" in result.lower()

    def test_not_found(self, tmp_path):
        from mcp_server import forget_memory

        with patch("src.memory._memory_dir", return_value=tmp_path):
            result = forget_memory(memory_name="nonexistent")
            assert "not found" in result.lower()

    def test_delete_success(self, tmp_path):
        from mcp_server import forget_memory

        mem = tmp_path / "test_memory.md"
        mem.write_text("some content")

        with patch("src.memory._memory_dir", return_value=tmp_path):
            result = forget_memory(memory_name="test_memory")
            assert "deleted" in result.lower()
            assert not mem.exists()


class TestSyncHistory:
    def test_sync_history(self, tmp_path):
        from src.sync import FileMetaDB, SyncResult

        db = FileMetaDB(tmp_path / "test.db")
        result = SyncResult(new=[], changed=[], deleted=[], unchanged_count=5)
        db.record_sync(result)

        history = db.sync_history(limit=5)
        assert len(history) == 1
        assert history[0]["new_count"] == 0
        assert history[0]["deleted_count"] == 0
        db.close()

    def test_file_count(self, tmp_path):
        from src.sync import FileMetaDB

        db = FileMetaDB(tmp_path / "test.db")
        assert db.file_count() == 0

        db.upsert_file("/a.md", mtime=1.0, size=10)
        db.upsert_file("/b.md", mtime=2.0, size=20)
        assert db.file_count() == 2
        db.close()

    def test_empty_history(self, tmp_path):
        from src.sync import FileMetaDB

        db = FileMetaDB(tmp_path / "test.db")
        history = db.sync_history()
        assert history == []
        db.close()
