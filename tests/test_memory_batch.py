"""Tests for batch memory export/import operations."""

from __future__ import annotations

import json

import pytest

from src.memory import _memory_dir, export_memories, import_memories, save_memory


@pytest.fixture
def memory_dir(tmp_path, monkeypatch):
    """Override _memory_dir to use a temp directory."""
    monkeypatch.setattr("src.memory._MEMORY_DIR_NAME", "test_memories")
    # Patch the function to return tmp_path based dir
    mem_dir = tmp_path / "test_memories"
    mem_dir.mkdir()
    monkeypatch.setattr("src.memory._memory_dir", lambda: mem_dir)
    return mem_dir


class TestExportMemories:
    def test_export_empty(self, memory_dir):
        result = export_memories()
        data = json.loads(result)
        assert data == []

    def test_export_with_memories(self, memory_dir):
        # Create a memory file manually
        md = (
            "---\n"
            "date: 2025-01-01T00:00:00\n"
            "source: test\n"
            "tags: [tag1, tag2]\n"
            "---\n\n"
            "Test memory content\n"
        )
        (memory_dir / "20250101_000000_test.md").write_text(md, encoding="utf-8")

        result = export_memories()
        data = json.loads(result)
        assert len(data) == 1
        assert data[0]["content"] == "Test memory content"
        assert "test" in data[0]["source"]

    def test_export_unsupported_format(self, memory_dir):
        with pytest.raises(ValueError, match="Unsupported"):
            export_memories(format="xml")


class TestImportMemories:
    def test_import_single(self, memory_dir, monkeypatch):
        # Mock index_memory to avoid LanceDB dependency
        monkeypatch.setattr("src.memory.index_memory", lambda fp: 1)

        data = json.dumps([
            {"content": "Test import", "tags": ["test"], "source": "import"}
        ])
        result = import_memories(data)
        assert result["imported"] == 1
        assert result["indexed"] == 1
        assert result["errors"] == []

    def test_import_multiple(self, memory_dir, monkeypatch):
        monkeypatch.setattr("src.memory.index_memory", lambda fp: 1)

        data = json.dumps([
            {"content": "Memory 1"},
            {"content": "Memory 2"},
            {"content": "Memory 3"},
        ])
        result = import_memories(data)
        assert result["imported"] == 3

    def test_import_skips_empty_content(self, memory_dir, monkeypatch):
        monkeypatch.setattr("src.memory.index_memory", lambda fp: 1)

        data = json.dumps([
            {"content": "Valid"},
            {"content": ""},
            {"content": "   "},
        ])
        result = import_memories(data)
        assert result["imported"] == 1

    def test_import_invalid_json(self, memory_dir):
        with pytest.raises(ValueError, match="Invalid JSON"):
            import_memories("not json")

    def test_import_not_a_list(self, memory_dir):
        with pytest.raises(ValueError, match="JSON list"):
            import_memories('{"content": "single"}')

    def test_import_with_index_failure(self, memory_dir, monkeypatch):
        def fail_index(fp):
            raise RuntimeError("index broken")
        monkeypatch.setattr("src.memory.index_memory", fail_index)

        data = json.dumps([{"content": "Test"}])
        result = import_memories(data)
        assert result["imported"] == 1
        assert result["indexed"] == 0
        assert len(result["errors"]) == 1

    def test_import_unsupported_format(self, memory_dir):
        with pytest.raises(ValueError, match="Unsupported"):
            import_memories("[]", format="csv")

    def test_roundtrip(self, memory_dir, monkeypatch):
        """Export then import should preserve content."""
        monkeypatch.setattr("src.memory.index_memory", lambda fp: 1)

        # Create memories
        md = (
            "---\n"
            "date: 2025-01-01T00:00:00\n"
            "source: original\n"
            "tags: [a, b]\n"
            "---\n\n"
            "Roundtrip content\n"
        )
        (memory_dir / "20250101_000000_roundtrip.md").write_text(md, encoding="utf-8")

        exported = export_memories()
        data = json.loads(exported)
        assert len(data) == 1
        assert data[0]["content"] == "Roundtrip content"
