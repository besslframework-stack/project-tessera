"""Tests for migration tool (v0.9.6)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.migrate import (
    detect_version,
    format_migration_result,
    migrate_memories_file,
    normalize_memory,
    run_migration,
    write_schema_version,
    _normalize_date,
)


class TestNormalizeMemory:
    def test_basic(self):
        m = {"content": "  Use PostgreSQL  ", "date": "2026-03-01", "category": "decision", "tags": ["db"]}
        result = normalize_memory(m)
        assert result["content"] == "Use PostgreSQL"
        assert result["date"] == "2026-03-01"
        assert result["category"] == "decision"
        assert result["tags"] == ["db"]

    def test_legacy_fields(self):
        m = {"content": "hello", "created_at": "2026-03-01T10:00:00Z", "type": "preference"}
        result = normalize_memory(m)
        assert result["date"] == "2026-03-01"
        assert result["category"] == "preference"

    def test_string_tags(self):
        m = {"content": "hello", "tags": "db, backend, api"}
        result = normalize_memory(m)
        assert result["tags"] == ["db", "backend", "api"]

    def test_invalid_category(self):
        m = {"content": "hello", "category": "invalid_type"}
        result = normalize_memory(m)
        assert result["category"] == "general"

    def test_missing_fields(self):
        m = {"content": "hello"}
        result = normalize_memory(m)
        assert result["date"] == ""
        assert result["category"] == "general"
        assert result["tags"] == []
        assert result["source"] == ""

    def test_preserves_id(self):
        m = {"content": "hello", "id": "abc-123"}
        result = normalize_memory(m)
        assert result["id"] == "abc-123"

    def test_non_string_content(self):
        m = {"content": 42}
        result = normalize_memory(m)
        assert result["content"] == "42"


class TestNormalizeDate:
    def test_iso_format(self):
        assert _normalize_date("2026-03-01") == "2026-03-01"

    def test_iso_with_time(self):
        assert _normalize_date("2026-03-01T10:00:00Z") == "2026-03-01"

    def test_slash_format(self):
        assert _normalize_date("2026/03/01") == "2026-03-01"

    def test_empty(self):
        assert _normalize_date("") == ""


class TestDetectVersion:
    def test_nonexistent_dir(self, tmp_path):
        assert detect_version(tmp_path / "nonexistent") == "none"

    def test_with_version_marker(self, tmp_path):
        (tmp_path / ".schema_version").write_text("1.0")
        assert detect_version(tmp_path) == "1.0"

    def test_empty_dir(self, tmp_path):
        assert detect_version(tmp_path) == "unknown"

    def test_v06_heuristic(self, tmp_path):
        (tmp_path / "lancedb").mkdir()
        assert detect_version(tmp_path) == "0.6"

    def test_v07_heuristic(self, tmp_path):
        (tmp_path / "lancedb").mkdir()
        (tmp_path / "memories.db").touch()
        assert detect_version(tmp_path) == "0.7"

    def test_v09_heuristic(self, tmp_path):
        (tmp_path / "interactions.db").touch()
        (tmp_path / "profile.json").touch()
        assert detect_version(tmp_path) == "0.9"


class TestMigrateMemoriesFile:
    def test_list_format(self, tmp_path):
        filepath = tmp_path / "memories.json"
        data = [
            {"content": "Use PostgreSQL", "category": "decision"},
            {"content": "Prefer TypeScript"},
        ]
        filepath.write_text(json.dumps(data))
        result = migrate_memories_file(filepath)
        assert len(result) == 2
        assert result[0]["category"] == "decision"
        assert result[1]["category"] == "general"

    def test_wrapped_format(self, tmp_path):
        filepath = tmp_path / "memories.json"
        data = {"memories": [{"content": "hello"}]}
        filepath.write_text(json.dumps(data))
        result = migrate_memories_file(filepath)
        assert len(result) == 1

    def test_skips_empty_content(self, tmp_path):
        filepath = tmp_path / "memories.json"
        data = [{"content": ""}, {"content": "valid"}]
        filepath.write_text(json.dumps(data))
        result = migrate_memories_file(filepath)
        assert len(result) == 1

    def test_invalid_json(self, tmp_path):
        filepath = tmp_path / "bad.json"
        filepath.write_text("not json")
        result = migrate_memories_file(filepath)
        assert result == []


class TestRunMigration:
    def test_no_data(self, tmp_path):
        result = run_migration(tmp_path / "nonexistent")
        assert result["status"] == "no_data"

    def test_already_current(self, tmp_path):
        (tmp_path / ".schema_version").write_text("1.0")
        result = run_migration(tmp_path)
        assert result["status"] == "up_to_date"

    def test_dry_run(self, tmp_path):
        (tmp_path / "lancedb").mkdir()
        data = [{"content": "hello", "category": "fact"}]
        (tmp_path / "memories.json").write_text(json.dumps(data))
        result = run_migration(tmp_path, dry_run=True)
        assert result["status"] == "dry_run"
        assert result["memories_processed"] == 1
        # Version marker should NOT be written in dry run
        assert not (tmp_path / ".schema_version").exists()

    def test_actual_migration(self, tmp_path):
        (tmp_path / "lancedb").mkdir()
        data = [{"content": "  hello  ", "type": "preference", "tags": "a, b"}]
        (tmp_path / "memories.json").write_text(json.dumps(data))
        result = run_migration(tmp_path)
        assert result["status"] == "migrated"
        assert result["memories_normalized"] == 1
        # Check normalized file
        migrated = json.loads((tmp_path / "memories.json").read_text())
        assert migrated[0]["content"] == "hello"
        assert migrated[0]["category"] == "preference"
        assert migrated[0]["tags"] == ["a", "b"]
        # Version marker written
        assert (tmp_path / ".schema_version").read_text() == "1.0"

    def test_backup_created(self, tmp_path):
        (tmp_path / "lancedb").mkdir()
        (tmp_path / "memories.json").write_text(json.dumps([{"content": "test"}]))
        result = run_migration(tmp_path)
        assert result["backup_path"] is not None
        assert Path(result["backup_path"]).exists()


class TestFormatResult:
    def test_up_to_date(self):
        result = format_migration_result({"status": "up_to_date"})
        assert "latest" in result

    def test_no_data(self):
        result = format_migration_result({"status": "no_data"})
        assert "No data" in result

    def test_migrated(self):
        result = format_migration_result({
            "status": "migrated",
            "from_version": "0.6",
            "to_version": "1.0",
            "memories_processed": 10,
            "memories_normalized": 10,
            "message": "Done.",
        })
        assert "v0.6" in result
        assert "v1.0" in result

    def test_with_errors(self):
        result = format_migration_result({
            "status": "migrated",
            "errors": ["file.json: parse error"],
            "memories_processed": 0,
        })
        assert "Errors" in result


class TestWriteSchemaVersion:
    def test_creates_file(self, tmp_path):
        write_schema_version(tmp_path)
        assert (tmp_path / ".schema_version").read_text() == "1.0"

    def test_creates_dir(self, tmp_path):
        new_dir = tmp_path / "new" / "data"
        write_schema_version(new_dir)
        assert (new_dir / ".schema_version").exists()
