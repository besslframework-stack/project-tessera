"""Tests for topic map (v0.7.7)."""

from __future__ import annotations

import pytest

from src.topic_map import (
    _tokenize,
    build_topic_map,
    format_topic_map_mermaid,
    format_topic_map_text,
)


class TestTokenize:
    def test_basic(self):
        tokens = _tokenize("PostgreSQL database configuration")
        assert "postgresql" in tokens
        assert "database" in tokens
        assert "configuration" in tokens

    def test_stop_words(self):
        tokens = _tokenize("we decided to use the database")
        assert "we" not in tokens
        assert "decided" not in tokens
        assert "database" in tokens

    def test_korean(self):
        tokens = _tokenize("데이터베이스 설정 방법")
        assert "데이터베이스" in tokens

    def test_empty(self):
        assert _tokenize("") == []


class TestBuildTopicMap:
    def _make_memories(self):
        return [
            {"content": "PostgreSQL database setup for production"},
            {"content": "PostgreSQL database backup strategy"},
            {"content": "PostgreSQL index optimization"},
            {"content": "React component design patterns"},
            {"content": "React hooks best practices"},
            {"content": "React performance optimization"},
            {"content": "Docker container deployment"},
            {"content": "Docker compose configuration"},
        ]

    def test_creates_topics(self):
        topics = build_topic_map(self._make_memories())
        assert len(topics) >= 2

    def test_topic_has_label(self):
        topics = build_topic_map(self._make_memories())
        for t in topics:
            assert "label" in t
            assert "keywords" in t
            assert "count" in t
            assert t["count"] >= 2

    def test_postgresql_cluster(self):
        topics = build_topic_map(self._make_memories())
        labels = [t["label"] for t in topics]
        assert "postgresql" in labels

    def test_min_topic_size(self):
        topics = build_topic_map(self._make_memories(), min_topic_size=3)
        for t in topics:
            assert t["count"] >= 3

    def test_max_topics(self):
        topics = build_topic_map(self._make_memories(), max_topics=2)
        assert len(topics) <= 2

    def test_empty(self):
        assert build_topic_map([]) == []

    def test_single_memory(self):
        mems = [{"content": "just one thing"}]
        topics = build_topic_map(mems)
        assert topics == []  # min_topic_size=2

    def test_sorted_by_count(self):
        topics = build_topic_map(self._make_memories())
        counts = [t["count"] for t in topics]
        assert counts == sorted(counts, reverse=True)

    def test_memories_included(self):
        topics = build_topic_map(self._make_memories())
        for t in topics:
            assert len(t["memories"]) == t["count"]


class TestFormatTopicMapText:
    def test_format(self):
        topics = [
            {
                "label": "postgresql",
                "keywords": ["postgresql", "database", "backup"],
                "count": 3,
                "memories": [
                    {"content": "PostgreSQL setup"},
                    {"content": "PostgreSQL backup"},
                    {"content": "PostgreSQL index"},
                ],
            }
        ]
        result = format_topic_map_text(topics)
        assert "Topic Map" in result
        assert "postgresql" in result
        assert "3 memories" in result

    def test_empty(self):
        result = format_topic_map_text([])
        assert "No topic" in result

    def test_truncates_previews(self):
        topics = [
            {
                "label": "test",
                "keywords": ["test"],
                "count": 5,
                "memories": [{"content": f"item {i}"} for i in range(5)],
            }
        ]
        result = format_topic_map_text(topics)
        assert "and 2 more" in result


class TestFormatTopicMapMermaid:
    def test_mermaid_output(self):
        topics = [
            {
                "label": "postgresql",
                "keywords": ["postgresql", "database", "backup"],
                "count": 3,
                "memories": [],
            }
        ]
        result = format_topic_map_mermaid(topics)
        assert "```mermaid" in result
        assert "mindmap" in result
        assert "postgresql" in result
        assert "database" in result

    def test_empty(self):
        result = format_topic_map_mermaid([])
        assert "No topic" in result
