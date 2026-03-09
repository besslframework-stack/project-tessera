"""Tests for knowledge stats (v0.7.8)."""

from __future__ import annotations

import pytest

from src.knowledge_stats import compute_stats, format_stats


class TestComputeStats:
    def _make_memories(self):
        return [
            {"content": "Use PostgreSQL", "date": "2026-01-15", "category": "decision", "tags": ["db"]},
            {"content": "Prefer TypeScript", "date": "2026-02-01", "category": "preference", "tags": ["lang"]},
            {"content": "API rate limit is 100/min", "date": "2026-02-15", "category": "fact", "tags": ["api"]},
            {"content": "React for frontend", "date": "2026-03-01", "category": "decision", "tags": ["frontend"]},
            {"content": "Deploy to AWS", "date": "2026-03-05", "category": "decision", "tags": ["infra", "aws"]},
        ]

    def test_total_counts(self):
        stats = compute_stats(self._make_memories(), documents=[{"content": "doc"}])
        assert stats["total_memories"] == 5
        assert stats["total_documents"] == 1

    def test_categories(self):
        stats = compute_stats(self._make_memories())
        assert stats["categories"]["decision"] == 3
        assert stats["categories"]["preference"] == 1
        assert stats["categories"]["fact"] == 1

    def test_top_tags(self):
        stats = compute_stats(self._make_memories())
        tag_names = [t["tag"] for t in stats["top_tags"]]
        assert "db" in tag_names

    def test_growth_by_month(self):
        stats = compute_stats(self._make_memories())
        assert "2026-01" in stats["growth_by_month"]
        assert "2026-03" in stats["growth_by_month"]
        assert stats["growth_by_month"]["2026-03"] == 2

    def test_avg_length(self):
        stats = compute_stats(self._make_memories())
        assert stats["avg_memory_length"] > 0

    def test_date_range(self):
        stats = compute_stats(self._make_memories())
        assert stats["oldest_memory"] == "2026-01-15"
        assert stats["newest_memory"] == "2026-03-05"

    def test_empty(self):
        stats = compute_stats([])
        assert stats["total_memories"] == 0
        assert stats["categories"] == {}

    def test_no_dates(self):
        mems = [{"content": "no date", "category": "fact", "tags": []}]
        stats = compute_stats(mems)
        assert stats["oldest_memory"] is None

    def test_no_documents(self):
        stats = compute_stats(self._make_memories())
        assert stats["total_documents"] == 0

    def test_missing_category(self):
        mems = [{"content": "test", "date": "2026-03-01", "tags": []}]
        stats = compute_stats(mems)
        assert stats["categories"]["general"] == 1


class TestFormatStats:
    def test_format(self):
        stats = {
            "total_memories": 5,
            "total_documents": 2,
            "categories": {"decision": 3, "fact": 2},
            "top_tags": [{"tag": "db", "count": 3}],
            "growth_by_month": {"2026-03": 5},
            "avg_memory_length": 50,
            "oldest_memory": "2026-01-01",
            "newest_memory": "2026-03-10",
        }
        result = format_stats(stats)
        assert "Knowledge Statistics" in result
        assert "Memories: 5" in result
        assert "Documents: 2" in result
        assert "decision: 3" in result
        assert "#db" in result
        assert "2026-03" in result

    def test_empty(self):
        stats = {
            "total_memories": 0,
            "total_documents": 0,
            "categories": {},
            "top_tags": [],
            "growth_by_month": {},
            "avg_memory_length": 0,
            "oldest_memory": None,
            "newest_memory": None,
        }
        result = format_stats(stats)
        assert "No knowledge" in result

    def test_percentage(self):
        stats = {
            "total_memories": 10,
            "total_documents": 0,
            "categories": {"decision": 5, "fact": 5},
            "top_tags": [],
            "growth_by_month": {},
            "avg_memory_length": 30,
            "oldest_memory": "2026-01-01",
            "newest_memory": "2026-03-01",
        }
        result = format_stats(stats)
        assert "50%" in result
