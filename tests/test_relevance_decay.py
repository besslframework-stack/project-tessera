"""Tests for relevance decay (v0.7.6)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.relevance_decay import (
    _parse_date,
    apply_decay,
    compute_decay_factor,
)


class TestParseDate:
    def test_iso_date(self):
        dt = _parse_date("2026-03-01")
        assert dt is not None
        assert dt.year == 2026
        assert dt.month == 3

    def test_iso_datetime(self):
        dt = _parse_date("2026-03-01T10:30:00")
        assert dt is not None
        assert dt.hour == 10

    def test_datetime_object(self):
        original = datetime(2026, 3, 1, tzinfo=timezone.utc)
        dt = _parse_date(original)
        assert dt == original

    def test_naive_datetime(self):
        original = datetime(2026, 3, 1)
        dt = _parse_date(original)
        assert dt.tzinfo == timezone.utc

    def test_none(self):
        assert _parse_date(None) is None

    def test_empty_string(self):
        assert _parse_date("") is None

    def test_invalid(self):
        assert _parse_date("not a date") is None


class TestComputeDecayFactor:
    def test_same_day(self):
        ref = "2026-03-10"
        assert compute_decay_factor("2026-03-10", ref) == 1.0

    def test_one_half_life(self):
        # 30 days ago with 30-day half-life should give ~0.5
        factor = compute_decay_factor("2026-02-08", "2026-03-10", half_life_days=30)
        assert 0.45 < factor < 0.55

    def test_two_half_lives(self):
        # 60 days ago with 30-day half-life should give ~0.25
        factor = compute_decay_factor("2026-01-09", "2026-03-10", half_life_days=30)
        assert 0.2 < factor < 0.3

    def test_very_old(self):
        # 365 days ago — very low factor
        factor = compute_decay_factor("2025-03-10", "2026-03-10", half_life_days=30)
        assert factor < 0.01

    def test_future_date(self):
        # Future memory — no penalty
        assert compute_decay_factor("2026-03-15", "2026-03-10") == 1.0

    def test_no_date(self):
        # Can't compute — default to 1.0
        assert compute_decay_factor("", "2026-03-10") == 1.0

    def test_zero_half_life(self):
        assert compute_decay_factor("2026-03-01", "2026-03-10", half_life_days=0) == 1.0

    def test_short_half_life(self):
        # 7-day half-life, 7 days ago
        factor = compute_decay_factor("2026-03-03", "2026-03-10", half_life_days=7)
        assert 0.45 < factor < 0.55


class TestApplyDecay:
    def test_basic(self):
        memories = [
            {"content": "old", "score": 1.0, "date": "2025-03-10"},
            {"content": "new", "score": 1.0, "date": "2026-03-09"},
        ]
        result = apply_decay(memories, reference_date="2026-03-10", half_life_days=30)
        # New memory should be first after re-sorting
        assert result[0]["content"] == "new"
        assert result[0]["decay_factor"] > result[1]["decay_factor"]

    def test_preserves_original_score(self):
        memories = [{"content": "test", "score": 0.8, "date": "2026-03-01"}]
        result = apply_decay(memories, reference_date="2026-03-10")
        assert result[0]["original_score"] == 0.8
        assert result[0]["score"] < 0.8

    def test_min_factor(self):
        memories = [{"content": "ancient", "score": 1.0, "date": "2020-01-01"}]
        result = apply_decay(memories, reference_date="2026-03-10", min_factor=0.1)
        assert result[0]["decay_factor"] >= 0.1
        assert result[0]["score"] >= 0.1

    def test_empty_list(self):
        assert apply_decay([]) == []

    def test_no_date_no_penalty(self):
        memories = [{"content": "no date", "score": 1.0}]
        result = apply_decay(memories, reference_date="2026-03-10")
        assert result[0]["score"] == 1.0

    def test_reorders_by_adjusted_score(self):
        memories = [
            {"content": "high score old", "score": 1.0, "date": "2025-01-01"},
            {"content": "low score new", "score": 0.5, "date": "2026-03-09"},
        ]
        result = apply_decay(memories, reference_date="2026-03-10", half_life_days=30)
        # New one should rank higher despite lower original score
        assert result[0]["content"] == "low score new"

    def test_decay_factor_added(self):
        memories = [{"content": "test", "score": 1.0, "date": "2026-03-05"}]
        result = apply_decay(memories, reference_date="2026-03-10")
        assert "decay_factor" in result[0]
        assert 0 < result[0]["decay_factor"] <= 1.0
