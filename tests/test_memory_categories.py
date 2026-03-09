"""Tests for memory categories (v0.6.7)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from src.memory import (
    _detect_category,
    list_memory_categories,
    save_memory,
    search_memories_by_category,
)


class TestDetectCategory:
    def test_decision(self):
        assert _detect_category("We decided to use PostgreSQL for the database") == "decision"

    def test_preference(self):
        assert _detect_category("I prefer using TypeScript over JavaScript for safety") == "preference"

    def test_fact(self):
        assert _detect_category("Note that the API rate limit is 100 requests per minute") == "fact"

    def test_signal(self):
        assert _detect_category("Remember this: always backup before deploying") == "fact"

    def test_no_match(self):
        assert _detect_category("The weather is nice today") == "general"

    def test_short_content(self):
        assert _detect_category("short") == "general"


class TestSaveMemoryCategory:
    def test_auto_detect_category(self, tmp_path):
        with patch("src.memory._memory_dir", return_value=tmp_path), \
             patch("src.memory._check_duplicate", return_value=None):
            path = save_memory("We decided to use FastAPI for the HTTP server")
            content = path.read_text()
            assert "category: decision" in content

    def test_explicit_category(self, tmp_path):
        with patch("src.memory._memory_dir", return_value=tmp_path), \
             patch("src.memory._check_duplicate", return_value=None):
            path = save_memory("Some content here for testing", category="reference")
            content = path.read_text()
            assert "category: reference" in content

    def test_general_category_fallback(self, tmp_path):
        with patch("src.memory._memory_dir", return_value=tmp_path), \
             patch("src.memory._check_duplicate", return_value=None):
            path = save_memory("The weather is nice today and tomorrow too")
            content = path.read_text()
            assert "category: general" in content


class TestListMemoryCategories:
    def test_empty_dir(self, tmp_path):
        with patch("src.memory._memory_dir", return_value=tmp_path):
            assert list_memory_categories() == {}

    def test_counts_categories(self, tmp_path):
        # Create test memory files with categories
        (tmp_path / "mem1.md").write_text(
            "---\ncategory: decision\n---\n\nUse PostgreSQL"
        )
        (tmp_path / "mem2.md").write_text(
            "---\ncategory: decision\n---\n\nUse FastAPI"
        )
        (tmp_path / "mem3.md").write_text(
            "---\ncategory: preference\n---\n\nPrefer TypeScript"
        )
        with patch("src.memory._memory_dir", return_value=tmp_path):
            cats = list_memory_categories()
            assert cats["decision"] == 2
            assert cats["preference"] == 1

    def test_skips_files_without_frontmatter(self, tmp_path):
        (tmp_path / "plain.md").write_text("No frontmatter here")
        with patch("src.memory._memory_dir", return_value=tmp_path):
            assert list_memory_categories() == {}

    def test_skips_empty_category(self, tmp_path):
        (tmp_path / "mem.md").write_text("---\ncategory: \n---\n\nContent")
        with patch("src.memory._memory_dir", return_value=tmp_path):
            assert list_memory_categories() == {}


class TestSearchByCategory:
    def test_find_decisions(self, tmp_path):
        (tmp_path / "mem1.md").write_text(
            "---\ndate: 2026-03-10\ncategory: decision\ntags: [arch]\n---\n\nUse PostgreSQL"
        )
        (tmp_path / "mem2.md").write_text(
            "---\ndate: 2026-03-09\ncategory: preference\ntags: [lang]\n---\n\nPrefer TypeScript"
        )
        with patch("src.memory._memory_dir", return_value=tmp_path):
            results = search_memories_by_category("decision")
            assert len(results) == 1
            assert results[0]["content"] == "Use PostgreSQL"
            assert results[0]["category"] == "decision"

    def test_case_insensitive(self, tmp_path):
        (tmp_path / "mem.md").write_text(
            "---\ncategory: Decision\n---\n\nContent"
        )
        with patch("src.memory._memory_dir", return_value=tmp_path):
            results = search_memories_by_category("decision")
            assert len(results) == 1

    def test_no_results(self, tmp_path):
        with patch("src.memory._memory_dir", return_value=tmp_path):
            results = search_memories_by_category("nonexistent")
            assert results == []

    def test_sorted_by_date_desc(self, tmp_path):
        (tmp_path / "old.md").write_text(
            "---\ndate: 2026-01-01\ncategory: fact\n---\n\nOld fact"
        )
        (tmp_path / "new.md").write_text(
            "---\ndate: 2026-03-10\ncategory: fact\n---\n\nNew fact"
        )
        with patch("src.memory._memory_dir", return_value=tmp_path):
            results = search_memories_by_category("fact")
            assert len(results) == 2
            assert results[0]["content"] == "New fact"
