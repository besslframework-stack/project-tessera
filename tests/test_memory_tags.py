"""Tests for src.memory.list_memory_tags and search_memories_by_tag."""

from __future__ import annotations

import pytest

from src.memory import list_memory_tags, search_memories_by_tag


@pytest.fixture
def memory_dir(tmp_path, monkeypatch):
    """Create a temporary memories directory with sample .md files."""
    mem_dir = tmp_path / "memories"
    mem_dir.mkdir()
    monkeypatch.setattr("src.memory._memory_dir", lambda: mem_dir)

    # Create test memory files
    (mem_dir / "20250101_test1.md").write_text(
        "---\ndate: 2025-01-01\nsource: test\ntags: [design, api]\n---\n\nDesign decisions for API\n"
    )
    (mem_dir / "20250102_test2.md").write_text(
        "---\ndate: 2025-01-02\nsource: test\ntags: [api, performance]\n---\n\nAPI performance notes\n"
    )
    (mem_dir / "20250103_test3.md").write_text(
        "---\ndate: 2025-01-03\nsource: test\ntags: [design]\n---\n\nDesign system update\n"
    )
    return mem_dir


class TestListMemoryTags:
    """Tests for list_memory_tags()."""

    def test_list_tags_empty(self, tmp_path, monkeypatch) -> None:
        """No files should return an empty dict."""
        empty_dir = tmp_path / "empty_memories"
        empty_dir.mkdir()
        monkeypatch.setattr("src.memory._memory_dir", lambda: empty_dir)

        result = list_memory_tags()
        assert result == {}

    def test_list_tags_counts(self, memory_dir) -> None:
        """Multiple files with overlapping tags should produce correct counts."""
        result = list_memory_tags()
        # "api" appears in test1 and test2
        assert result["api"] == 2
        # "design" appears in test1 and test3
        assert result["design"] == 2
        # "performance" appears only in test2
        assert result["performance"] == 1

    def test_list_tags_sorted(self, memory_dir) -> None:
        """Tags should be sorted by count descending."""
        result = list_memory_tags()
        counts = list(result.values())
        assert counts == sorted(counts, reverse=True)


class TestSearchMemoriesByTag:
    """Tests for search_memories_by_tag(tag)."""

    def test_search_by_tag_found(self, memory_dir) -> None:
        """Should find memories that have the matching tag."""
        results = search_memories_by_tag("api")
        assert len(results) == 2
        filenames = {r["filename"] for r in results}
        assert "20250101_test1" in filenames
        assert "20250102_test2" in filenames

    def test_search_by_tag_case_insensitive(self, memory_dir) -> None:
        """Tag matching should be case-insensitive: 'Design' matches 'design'."""
        results = search_memories_by_tag("Design")
        assert len(results) == 2

    def test_search_by_tag_not_found(self, memory_dir) -> None:
        """Non-existent tag should return an empty list."""
        results = search_memories_by_tag("nonexistent_tag")
        assert results == []

    def test_search_returns_content(self, memory_dir) -> None:
        """Returned dicts should have correct keys and content values."""
        results = search_memories_by_tag("performance")
        assert len(results) == 1

        entry = results[0]
        assert "filename" in entry
        assert "content" in entry
        assert "date" in entry
        assert "tags" in entry
        assert "source" in entry

        assert entry["content"] == "API performance notes"
        assert entry["date"] == "2025-01-02"
        assert entry["source"] == "test"
