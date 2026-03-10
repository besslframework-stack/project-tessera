"""Tests for user profile (v0.9.1)."""

from __future__ import annotations

import pytest

from src.user_profile import build_profile, format_profile


class TestBuildProfile:
    def _make_memories(self):
        return [
            {"content": "Prefer TypeScript over JavaScript", "category": "preference", "tags": ["lang"], "date": "2026-03-01"},
            {"content": "Use PostgreSQL for production", "category": "decision", "tags": ["db", "backend"], "date": "2026-03-02"},
            {"content": "API rate limit is 100/min", "category": "fact", "tags": ["api"], "date": "2026-03-03"},
            {"content": "React for frontend framework", "category": "decision", "tags": ["frontend"], "date": "2026-03-04"},
            {"content": "Always use dark mode", "category": "preference", "tags": ["ui"], "date": "2026-03-05"},
        ]

    def test_basic(self):
        profile = build_profile(self._make_memories())
        assert profile["total_memories"] == 5

    def test_preferences(self):
        profile = build_profile(self._make_memories())
        assert len(profile["preferences"]) == 2
        assert any("TypeScript" in p["content"] for p in profile["preferences"])

    def test_decisions(self):
        profile = build_profile(self._make_memories())
        assert len(profile["decisions"]) == 2

    def test_top_topics(self):
        profile = build_profile(self._make_memories())
        topic_names = [t["topic"] for t in profile["top_topics"]]
        assert "backend" in topic_names or "db" in topic_names

    def test_language_english(self):
        mems = [{"content": "This is English text only", "category": "fact", "tags": [], "date": ""}]
        profile = build_profile(mems)
        assert profile["language_preference"] == "english"

    def test_language_korean(self):
        mems = [{"content": "이것은 한국어 텍스트입니다 완전히", "category": "fact", "tags": [], "date": ""}]
        profile = build_profile(mems)
        assert profile["language_preference"] == "korean"

    def test_language_bilingual(self):
        mems = [{"content": "한국어 텍스트와 English text here 혼합된 콘텐츠", "category": "fact", "tags": [], "date": ""}]
        profile = build_profile(mems)
        assert profile["language_preference"] == "bilingual"

    def test_tool_usage(self):
        interactions = [
            {"tool_name": "search", "timestamp": "2026-03-01T10:00:00"},
            {"tool_name": "search", "timestamp": "2026-03-01T11:00:00"},
            {"tool_name": "remember", "timestamp": "2026-03-01T14:00:00"},
        ]
        profile = build_profile([], interactions=interactions)
        assert profile["tool_usage"]["search"] == 2

    def test_active_hours(self):
        interactions = [
            {"tool_name": "search", "timestamp": "2026-03-01T10:00:00"},
            {"tool_name": "search", "timestamp": "2026-03-01T10:30:00"},
            {"tool_name": "recall", "timestamp": "2026-03-01T14:00:00"},
        ]
        profile = build_profile([], interactions=interactions)
        assert profile["active_hours"].get(10) == 2

    def test_knowledge_areas(self):
        profile = build_profile(self._make_memories())
        areas = {a["area"]: a["count"] for a in profile["knowledge_areas"]}
        assert areas.get("decision") == 2
        assert areas.get("preference") == 2

    def test_empty(self):
        profile = build_profile([])
        assert profile["total_memories"] == 0


class TestFormatProfile:
    def test_format(self):
        profile = build_profile([
            {"content": "Use PostgreSQL", "category": "decision", "tags": ["db"], "date": "2026-03-01"},
            {"content": "Prefer dark mode", "category": "preference", "tags": ["ui"], "date": "2026-03-02"},
        ])
        result = format_profile(profile)
        assert "User Profile" in result
        assert "Memories: 2" in result
        assert "PostgreSQL" in result
        assert "dark mode" in result

    def test_empty(self):
        profile = build_profile([])
        result = format_profile(profile)
        assert "No profile" in result
