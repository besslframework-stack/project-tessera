"""Tests for incremental file sync and FileMetaDB."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from src.sync import FileMetaDB, SyncResult


class TestSyncResult:
    def test_no_changes(self):
        r = SyncResult(new=[], changed=[], deleted=[], unchanged_count=5)
        assert not r.has_changes
        assert "5 unchanged" in r.summary()

    def test_has_changes(self, tmp_path):
        r = SyncResult(
            new=[tmp_path / "a.md"],
            changed=[tmp_path / "b.md"],
            deleted=["c.md"],
            unchanged_count=2,
        )
        assert r.has_changes
        summary = r.summary()
        assert "1 new" in summary
        assert "1 changed" in summary
        assert "1 deleted" in summary
        assert "2 unchanged" in summary

    def test_only_new(self, tmp_path):
        r = SyncResult(new=[tmp_path / "x.md"], changed=[], deleted=[], unchanged_count=0)
        assert r.has_changes


class TestFileMetaDB:
    def test_create_and_query(self, tmp_path):
        db = FileMetaDB(tmp_path / "test.db")
        assert db.get_file_meta("/some/file.md") is None

    def test_upsert_and_retrieve(self, tmp_path):
        db = FileMetaDB(tmp_path / "test.db")
        db.upsert_file("/docs/test.md", mtime=1000.0, size=500, chunk_count=3)

        meta = db.get_file_meta("/docs/test.md")
        assert meta is not None
        assert meta["mtime"] == 1000.0
        assert meta["size"] == 500
        assert meta["chunk_count"] == 3

    def test_upsert_updates_existing(self, tmp_path):
        db = FileMetaDB(tmp_path / "test.db")
        db.upsert_file("/docs/test.md", mtime=1000.0, size=500, chunk_count=3)
        db.upsert_file("/docs/test.md", mtime=2000.0, size=600, chunk_count=5)

        meta = db.get_file_meta("/docs/test.md")
        assert meta["mtime"] == 2000.0
        assert meta["size"] == 600
        assert meta["chunk_count"] == 5

    def test_delete_file(self, tmp_path):
        db = FileMetaDB(tmp_path / "test.db")
        db.upsert_file("/docs/test.md", mtime=1000.0, size=500)
        db.delete_file("/docs/test.md")

        assert db.get_file_meta("/docs/test.md") is None

    def test_all_tracked_paths(self, tmp_path):
        db = FileMetaDB(tmp_path / "test.db")
        db.upsert_file("/a.md", mtime=1.0, size=10)
        db.upsert_file("/b.md", mtime=2.0, size=20)

        paths = db.all_tracked_paths()
        assert set(paths) == {"/a.md", "/b.md"}

    def test_record_sync(self, tmp_path):
        db = FileMetaDB(tmp_path / "test.db")
        result = SyncResult(
            new=[tmp_path / "a.md", tmp_path / "b.md", tmp_path / "c.md"],
            changed=[tmp_path / "d.md"],
            deleted=[],
            unchanged_count=0,
        )
        db.record_sync(result)
        # Should not raise

    def test_close(self, tmp_path):
        db = FileMetaDB(tmp_path / "test.db")
        db.close()
        # Double close should not raise
