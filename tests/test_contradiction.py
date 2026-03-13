"""Tests for contradiction detection."""

import pytest

from src.contradiction import (
    _has_negation_signal,
    _normalize_content,
    _extract_subject,
    detect_contradictions,
    format_contradictions,
)


class TestNormalizeContent:
    """Test content normalization."""

    def test_lowercase(self):
        assert _normalize_content("Hello World") == "hello world"

    def test_whitespace(self):
        assert _normalize_content("  hello   world  ") == "hello world"

    def test_empty(self):
        assert _normalize_content("") == ""


class TestExtractSubject:
    """Test subject extraction from text."""

    def test_proper_nouns(self):
        subjects = _extract_subject("We decided to use PostgreSQL for the database")
        assert "PostgreSQL" in subjects

    def test_korean_nouns(self):
        subjects = _extract_subject("데이터베이스로 포스트그레스 사용")
        assert "데이터베이스" in subjects or "포스트그레스" in subjects

    def test_mixed_language(self):
        subjects = _extract_subject("React 컴포넌트 설계 방식")
        assert "React" in subjects
        assert "컴포넌트" in subjects

    def test_multiple_proper_nouns(self):
        subjects = _extract_subject("Switch from React to Vue for frontend")
        assert "React" in subjects
        assert "Vue" in subjects


class TestHasNegationSignal:
    """Test negation pattern detection."""

    def test_not_vs_will(self):
        assert _has_negation_signal(
            "We will not use PostgreSQL",
            "We will use PostgreSQL",
        )

    def test_stop_vs_start(self):
        assert _has_negation_signal(
            "Stop using Redis",
            "Start using Redis",
        )

    def test_remove_vs_add(self):
        assert _has_negation_signal(
            "Remove the caching layer",
            "Add the caching layer",
        )

    def test_korean_negation(self):
        assert _has_negation_signal(
            "Redis 안 쓰기로 했다",
            "Redis 쓰기로 했다",
        )

    def test_no_negation(self):
        assert not _has_negation_signal(
            "Use PostgreSQL for database",
            "Use PostgreSQL for storage",
        )

    def test_no_longer(self):
        assert _has_negation_signal(
            "We no longer use React",
            "We use React for frontend",
        )

    def test_replace_vs_keep(self):
        assert _has_negation_signal(
            "Replace the old system",
            "Keep the old system",
        )

    def test_korean_stop_vs_continue(self):
        assert _has_negation_signal(
            "배포 중단",
            "배포 계속",
        )


class TestDetectContradictions:
    """Test contradiction detection across memories."""

    def _make_memory(self, content, date="2026-03-01", category="decision"):
        return {"content": content, "date": date, "category": category}

    def test_clear_contradiction(self):
        memories = [
            self._make_memory("We will use PostgreSQL", "2026-01-01"),
            self._make_memory("We will not use PostgreSQL", "2026-03-01"),
        ]
        results = detect_contradictions(memories)
        assert len(results) >= 1
        assert results[0]["severity"] == "high"

    def test_no_contradiction_same_content(self):
        memories = [
            self._make_memory("Use React for frontend", "2026-01-01"),
            self._make_memory("Use React for frontend", "2026-03-01"),
        ]
        results = detect_contradictions(memories)
        assert len(results) == 0

    def test_different_topics_no_contradiction(self):
        memories = [
            self._make_memory("Use PostgreSQL for database", "2026-01-01"),
            self._make_memory("Deploy to AWS for hosting", "2026-03-01"),
        ]
        results = detect_contradictions(memories)
        assert len(results) == 0

    def test_medium_severity_same_subject(self):
        memories = [
            self._make_memory("Switch to React for the frontend framework", "2026-01-01"),
            self._make_memory("Switch to Vue for the frontend framework", "2026-03-01"),
        ]
        results = detect_contradictions(memories)
        # Should detect same subject (frontend, framework) with different stance
        assert len(results) >= 1

    def test_korean_contradiction(self):
        memories = [
            self._make_memory("Redis 쓰기로 했다", "2026-01-01"),
            self._make_memory("Redis 안 쓰기로 했다", "2026-03-01"),
        ]
        results = detect_contradictions(memories)
        assert len(results) >= 1

    def test_ignores_non_decision_categories(self):
        memories = [
            self._make_memory("Use PostgreSQL", "2026-01-01", category="context"),
            self._make_memory("Stop using PostgreSQL", "2026-03-01", category="context"),
        ]
        results = detect_contradictions(memories)
        assert len(results) == 0

    def test_includes_preferences(self):
        memories = [
            {"content": "I prefer dark mode", "date": "2026-01-01", "category": "preference"},
            {"content": "I prefer not dark mode", "date": "2026-03-01", "category": "preference"},
        ]
        results = detect_contradictions(memories)
        # Should detect preference contradiction
        assert len(results) >= 1

    def test_single_memory_no_contradiction(self):
        memories = [self._make_memory("Use React")]
        assert detect_contradictions(memories) == []

    def test_empty_memories(self):
        assert detect_contradictions([]) == []

    def test_newer_date_correctly_identified(self):
        memories = [
            self._make_memory("Start using Redis", "2026-01-01"),
            self._make_memory("Stop using Redis", "2026-06-01"),
        ]
        results = detect_contradictions(memories)
        assert len(results) >= 1
        assert results[0]["newer_date"] == "2026-06-01"
        assert results[0]["older_date"] == "2026-01-01"

    def test_severity_ordering(self):
        memories = [
            self._make_memory("Use PostgreSQL for database", "2026-01-01"),
            self._make_memory("Not use PostgreSQL for database", "2026-02-01"),
            self._make_memory("Switch to React for frontend framework", "2026-01-15"),
            self._make_memory("Switch to Vue for frontend framework", "2026-03-01"),
        ]
        results = detect_contradictions(memories)
        if len(results) >= 2:
            severity_order = {"high": 0, "medium": 1, "low": 2}
            for i in range(len(results) - 1):
                assert severity_order[results[i]["severity"]] <= severity_order[results[i + 1]["severity"]]


class TestFormatContradictions:
    """Test contradiction report formatting."""

    def test_no_contradictions(self):
        result = format_contradictions([])
        assert "No contradictions" in result

    def test_formats_high_severity(self):
        contradictions = [{
            "memory_a": {"content": "Use X", "date": "2026-01-01"},
            "memory_b": {"content": "Stop X", "date": "2026-03-01"},
            "reason": "negation pattern detected",
            "topic_keywords": ["database"],
            "severity": "high",
            "newer_date": "2026-03-01",
            "older_date": "2026-01-01",
        }]
        result = format_contradictions(contradictions)
        assert "HIGH" in result
        assert "database" in result
        assert "2026-01-01" in result
        assert "2026-03-01" in result

    def test_count_in_header(self):
        contradictions = [
            {
                "memory_a": {"content": "A"},
                "memory_b": {"content": "B"},
                "reason": "test",
                "topic_keywords": [],
                "severity": "low",
                "newer_date": "",
                "older_date": "",
            }
        ] * 3
        result = format_contradictions(contradictions)
        assert "3 found" in result

    def test_long_content_truncated(self):
        long_content = "x" * 300
        contradictions = [{
            "memory_a": {"content": long_content},
            "memory_b": {"content": "short"},
            "reason": "test",
            "topic_keywords": [],
            "severity": "low",
            "newer_date": "",
            "older_date": "",
        }]
        result = format_contradictions(contradictions)
        assert "..." in result
