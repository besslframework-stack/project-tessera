"""Tests for smart suggest (v0.7.5)."""

from __future__ import annotations

import pytest

from src.smart_suggest import (
    _extract_keywords,
    format_suggestions,
    suggest_from_history,
)


class TestExtractKeywords:
    def test_basic(self):
        kw = _extract_keywords("How to configure PostgreSQL database")
        assert "configure" in kw
        assert "postgresql" in kw
        assert "database" in kw
        assert "how" not in kw
        assert "to" not in kw

    def test_korean(self):
        kw = _extract_keywords("데이터베이스 설정 방법")
        assert "데이터베이스" in kw
        assert "설정" in kw

    def test_empty(self):
        assert _extract_keywords("") == []

    def test_short_words_filtered(self):
        kw = _extract_keywords("a b c longer")
        assert "a" not in kw
        assert "longer" in kw


class TestSuggestFromHistory:
    def test_frequent_keywords(self):
        queries = [
            "postgresql setup",
            "postgresql configuration",
            "postgresql backup",
            "react components",
        ]
        suggestions = suggest_from_history(queries)
        # "postgresql" appeared 3 times, should be suggested
        query_texts = [s["query"] for s in suggestions]
        assert "postgresql" in query_texts

    def test_memory_topics_not_searched(self):
        queries = ["react components"]
        memories = [
            {"content": "We use Docker for deployment", "tags": []},
            {"content": "Docker compose configuration for production", "tags": []},
        ]
        suggestions = suggest_from_history(queries, memories=memories)
        query_texts = [s["query"] for s in suggestions]
        assert "docker" in query_texts

    def test_tag_suggestions(self):
        queries = ["something"]
        memories = [
            {"content": "fact1", "tags": ["backend", "api"]},
            {"content": "fact2", "tags": ["backend", "database"]},
            {"content": "fact3", "tags": ["backend"]},
        ]
        suggestions = suggest_from_history(queries, memories=memories)
        query_texts = [s["query"] for s in suggestions]
        assert "#backend" in query_texts

    def test_max_suggestions(self):
        queries = [f"query {i}" for i in range(20)]
        suggestions = suggest_from_history(queries, max_suggestions=3)
        assert len(suggestions) <= 3

    def test_empty_input(self):
        assert suggest_from_history([]) == []

    def test_no_duplicates(self):
        queries = ["postgresql", "postgresql", "postgresql", "postgresql"]
        suggestions = suggest_from_history(queries)
        query_texts = [s["query"] for s in suggestions]
        assert len(query_texts) == len(set(query_texts))

    def test_recent_excluded(self):
        # Last query keywords should not be suggested as "frequent"
        queries = [
            "react hooks",
            "react hooks",
            "react hooks",
        ]
        suggestions = suggest_from_history(queries)
        # "react" and "hooks" are in the most recent query,
        # so they shouldn't appear as "frequent" suggestions
        frequent = [s for s in suggestions if "frequently" in s["reason"]]
        frequent_queries = [s["query"] for s in frequent]
        assert "react" not in frequent_queries
        assert "hooks" not in frequent_queries

    def test_scores_sorted(self):
        queries = [
            "postgresql setup",
            "postgresql backup",
            "postgresql monitoring",
            "react app",
            "react app",
        ]
        suggestions = suggest_from_history(queries)
        scores = [s["score"] for s in suggestions]
        assert scores == sorted(scores, reverse=True)

    def test_memories_only(self):
        memories = [
            {"content": "kubernetes cluster deployment", "tags": ["infra"]},
            {"content": "kubernetes pod scaling policy", "tags": ["infra"]},
            {"content": "kubernetes service mesh", "tags": ["infra"]},
        ]
        suggestions = suggest_from_history([], memories=memories)
        assert len(suggestions) > 0


class TestFormatSuggestions:
    def test_format(self):
        suggestions = [
            {"query": "postgresql", "reason": "frequently searched (3 times)", "score": 1.5},
            {"query": "docker", "reason": "appears in 2 memories", "score": 0.8},
        ]
        result = format_suggestions(suggestions)
        assert "Suggested Queries" in result
        assert "postgresql" in result
        assert "docker" in result

    def test_empty(self):
        result = format_suggestions([])
        assert "No suggestions" in result
