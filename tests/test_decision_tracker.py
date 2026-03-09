"""Tests for decision tracker (v0.7.3)."""

from __future__ import annotations

import pytest

from src.decision_tracker import (
    _extract_topic_keywords,
    _topic_similarity,
    format_decision_timeline,
    get_decision_timeline,
)


class TestExtractTopicKeywords:
    def test_english(self):
        kw = _extract_topic_keywords("We decided to use PostgreSQL for the main database")
        assert "postgresql" in kw
        assert "database" in kw
        assert "main" in kw
        # Stop words removed
        assert "the" not in kw
        assert "to" not in kw

    def test_korean(self):
        kw = _extract_topic_keywords("PostgreSQL을 메인 데이터베이스로 결정")
        assert "postgresql" in kw
        assert "메인" in kw

    def test_short_words_filtered(self):
        kw = _extract_topic_keywords("I do a b c thing")
        assert "a" not in kw
        assert "b" not in kw

    def test_empty(self):
        assert _extract_topic_keywords("") == set()


class TestTopicSimilarity:
    def test_identical(self):
        a = {"postgresql", "database", "main"}
        assert _topic_similarity(a, a) == 1.0

    def test_no_overlap(self):
        a = {"postgresql", "database"}
        b = {"react", "frontend"}
        assert _topic_similarity(a, b) == 0.0

    def test_partial_overlap(self):
        a = {"postgresql", "database", "production"}
        b = {"mysql", "database", "production"}
        sim = _topic_similarity(a, b)
        assert 0.3 < sim < 0.8

    def test_empty_set(self):
        assert _topic_similarity(set(), {"a", "b"}) == 0.0


class TestGetDecisionTimeline:
    def _make_decisions(self):
        return [
            {"content": "Use PostgreSQL for the main database", "date": "2026-03-01", "category": "decision"},
            {"content": "Switch from PostgreSQL to MySQL for the database", "date": "2026-03-05", "category": "decision"},
            {"content": "Use React for the frontend framework", "date": "2026-03-02", "category": "decision"},
            {"content": "Prefer TypeScript", "date": "2026-03-03", "category": "preference"},  # Not a decision
        ]

    def test_groups_by_topic(self):
        groups = get_decision_timeline(self._make_decisions())
        # Should have at least 2 groups: database decisions and React decision
        assert len(groups) >= 2

    def test_detects_change(self):
        groups = get_decision_timeline(self._make_decisions())
        # The database topic should be marked as changed
        db_group = None
        for g in groups:
            if any("postgresql" in kw or "database" in kw for kw in g["topic_keywords"]):
                db_group = g
                break
        if db_group:
            assert db_group["changed"] is True

    def test_filters_non_decisions(self):
        decisions = self._make_decisions()
        groups = get_decision_timeline(decisions)
        # Preference should not appear
        all_contents = []
        for g in groups:
            for d in g["decisions"]:
                all_contents.append(d["content"])
        assert not any("Prefer TypeScript" in c for c in all_contents)

    def test_sorted_by_date(self):
        groups = get_decision_timeline(self._make_decisions())
        for g in groups:
            dates = [d.get("date", "") for d in g["decisions"]]
            assert dates == sorted(dates)

    def test_empty_input(self):
        assert get_decision_timeline([]) == []

    def test_no_decisions(self):
        mems = [{"content": "fact", "date": "2026-03-01", "category": "fact"}]
        assert get_decision_timeline(mems) == []

    def test_single_decision(self):
        mems = [{"content": "Use PostgreSQL for production database systems", "date": "2026-03-01", "category": "decision"}]
        groups = get_decision_timeline(mems)
        assert len(groups) == 1
        assert groups[0]["changed"] is False


class TestFormatDecisionTimeline:
    def test_format_output(self):
        groups = [{
            "topic_keywords": ["postgresql", "database"],
            "decisions": [
                {"content": "Use PostgreSQL", "date": "2026-03-01"},
                {"content": "Switch to MySQL", "date": "2026-03-05"},
            ],
            "changed": True,
            "count": 2,
        }]
        result = format_decision_timeline(groups)
        assert "Decision Timeline" in result
        assert "postgresql" in result
        assert "(changed)" in result
        assert "[2026-03-01]" in result
        assert "[2026-03-05]" in result
        assert "Use PostgreSQL" in result
        assert "Switch to MySQL" in result

    def test_empty(self):
        assert "No decision" in format_decision_timeline([])

    def test_truncates_long_content(self):
        groups = [{
            "topic_keywords": ["test"],
            "decisions": [{"content": "x" * 200, "date": "2026-03-01"}],
            "changed": False,
            "count": 1,
        }]
        result = format_decision_timeline(groups)
        assert "..." in result
