"""Tests for memory confidence scoring."""

import pytest
from datetime import datetime, timedelta

from src.memory_confidence import (
    _compute_repetition_score,
    _compute_source_diversity_score,
    _compute_recency_score,
    _compute_category_weight,
    compute_confidence,
    score_all_memories,
    format_confidence_report,
)


def _mem(content, date=None, category="decision", source="user-request", tags=""):
    if date is None:
        date = datetime.now().isoformat()
    return {"content": content, "date": date, "category": category, "source": source, "tags": tags}


class TestRepetitionScore:
    def test_no_confirmations(self):
        mem = _mem("Use PostgreSQL")
        others = [_mem("Deploy to AWS")]
        assert _compute_repetition_score(mem, others) == 0.0

    def test_one_confirmation(self):
        mem = _mem("Use PostgreSQL for database")
        others = [_mem("PostgreSQL is our database choice")]
        score = _compute_repetition_score(mem, others)
        assert score == 0.3

    def test_multiple_confirmations(self):
        mem = _mem("Use PostgreSQL for database")
        others = [
            _mem("PostgreSQL is our database"),
            _mem("We chose PostgreSQL"),
            _mem("Database: PostgreSQL"),
        ]
        score = _compute_repetition_score(mem, others)
        assert score >= 0.5

    def test_self_excluded(self):
        mem = _mem("Use PostgreSQL")
        # Same object should not count
        score = _compute_repetition_score(mem, [mem])
        assert score == 0.0

    def test_empty_content(self):
        mem = _mem("")
        assert _compute_repetition_score(mem, [_mem("hello")]) == 0.0


class TestSourceDiversityScore:
    def test_single_source(self):
        mem = _mem("Use React", source="user-request")
        others = [_mem("React frontend", source="user-request")]
        score = _compute_source_diversity_score(mem, others)
        assert score == 0.2

    def test_two_sources(self):
        mem = _mem("Use React", source="user-request")
        others = [_mem("React frontend", source="auto-learn")]
        score = _compute_source_diversity_score(mem, others)
        assert score == 0.6

    def test_three_sources(self):
        mem = _mem("Use React", source="user-request")
        others = [
            _mem("React frontend", source="auto-learn"),
            _mem("React for UI", source="conversation"),
        ]
        score = _compute_source_diversity_score(mem, others)
        assert score == 1.0


class TestRecencyScore:
    def test_recent(self):
        mem = _mem("test", date=datetime.now().isoformat())
        assert _compute_recency_score(mem) == 1.0

    def test_week_old(self):
        date = (datetime.now() - timedelta(days=5)).isoformat()
        mem = _mem("test", date=date)
        assert _compute_recency_score(mem) == 1.0

    def test_month_old(self):
        date = (datetime.now() - timedelta(days=20)).isoformat()
        mem = _mem("test", date=date)
        assert _compute_recency_score(mem) == 0.8

    def test_old(self):
        date = (datetime.now() - timedelta(days=200)).isoformat()
        mem = _mem("test", date=date)
        assert _compute_recency_score(mem) == 0.2

    def test_no_date(self):
        mem = _mem("test", date="")
        assert _compute_recency_score(mem) == 0.3


class TestCategoryWeight:
    def test_fact(self):
        assert _compute_category_weight({"category": "fact"}) == 0.9

    def test_decision(self):
        assert _compute_category_weight({"category": "decision"}) == 0.5

    def test_preference(self):
        assert _compute_category_weight({"category": "preference"}) == 0.6

    def test_unknown(self):
        assert _compute_category_weight({"category": "xyz"}) == 0.5


class TestComputeConfidence:
    def test_returns_score_and_label(self):
        mem = _mem("Use PostgreSQL for database")
        result = compute_confidence(mem, [mem])
        assert "score" in result
        assert "label" in result
        assert "factors" in result
        assert result["label"] in ("high", "medium", "low")

    def test_high_confidence(self):
        mem = _mem("Use PostgreSQL", source="user-request")
        others = [
            _mem("PostgreSQL database", source="auto-learn"),
            _mem("PostgreSQL for storage", source="conversation"),
            _mem("Database: PostgreSQL", source="import"),
        ]
        result = compute_confidence(mem, [mem] + others)
        assert result["label"] in ("high", "medium")

    def test_low_confidence_old_single(self):
        old_date = (datetime.now() - timedelta(days=200)).isoformat()
        mem = _mem("Some random note", date=old_date, category="general", source="auto-learn")
        result = compute_confidence(mem, [mem])
        assert result["label"] == "low"


class TestScoreAllMemories:
    def test_sorts_by_score(self):
        memories = [
            _mem("low value note", category="general"),
            _mem("Use PostgreSQL for database", source="user-request"),
        ]
        scored = score_all_memories(memories)
        assert scored[0]["confidence"]["score"] >= scored[1]["confidence"]["score"]

    def test_adds_confidence_to_all(self):
        memories = [_mem("a"), _mem("b"), _mem("c")]
        score_all_memories(memories)
        for m in memories:
            assert "confidence" in m


class TestFormatConfidenceReport:
    def test_empty(self):
        result = format_confidence_report([])
        assert "No memories" in result

    def test_with_scored_memories(self):
        memories = [
            _mem("Use PostgreSQL"),
            _mem("Deploy to AWS"),
        ]
        score_all_memories(memories)
        result = format_confidence_report(memories)
        assert "Memory Confidence Report" in result
        assert "analyzed" in result

    def test_no_confidence_key(self):
        result = format_confidence_report([_mem("test")])
        assert "No confidence" in result
