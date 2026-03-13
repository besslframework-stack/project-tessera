"""Tests for search verdict classification."""

import pytest

from src.search_verdict import (
    THRESHOLD_FOUND,
    THRESHOLD_WEAK,
    add_verdicts,
    classify_verdict,
    compute_overall_verdict,
    format_verdict_label,
)


class TestClassifyVerdict:
    """Test individual verdict classification."""

    def test_found_high_score(self):
        assert classify_verdict(0.90) == "found"

    def test_found_at_threshold(self):
        assert classify_verdict(THRESHOLD_FOUND) == "found"

    def test_weak_mid_score(self):
        assert classify_verdict(0.35) == "weak"

    def test_weak_at_threshold(self):
        assert classify_verdict(THRESHOLD_WEAK) == "weak"

    def test_none_low_score(self):
        assert classify_verdict(0.10) == "none"

    def test_none_zero(self):
        assert classify_verdict(0.0) == "none"

    def test_found_perfect(self):
        assert classify_verdict(1.0) == "found"

    def test_just_below_found(self):
        assert classify_verdict(0.449) == "weak"

    def test_just_below_weak(self):
        assert classify_verdict(0.249) == "none"


class TestAddVerdicts:
    """Test batch verdict assignment."""

    def test_adds_verdicts_to_results(self):
        results = [
            {"text": "a", "similarity": 0.8},
            {"text": "b", "similarity": 0.3},
            {"text": "c", "similarity": 0.1},
        ]
        add_verdicts(results)
        assert results[0]["verdict"] == "found"
        assert results[1]["verdict"] == "weak"
        assert results[2]["verdict"] == "none"

    def test_empty_list(self):
        results = []
        add_verdicts(results)
        assert results == []

    def test_custom_score_key(self):
        results = [{"text": "x", "score": 0.5}]
        add_verdicts(results, score_key="score")
        assert results[0]["verdict"] == "found"

    def test_missing_score_key(self):
        results = [{"text": "x"}]
        add_verdicts(results)
        assert results[0]["verdict"] == "none"

    def test_mutates_in_place(self):
        results = [{"similarity": 0.6}]
        returned = add_verdicts(results)
        assert returned is results
        assert "verdict" in results[0]


class TestComputeOverallVerdict:
    """Test overall verdict computation."""

    def test_found_if_any_found(self):
        results = [
            {"similarity": 0.1, "verdict": "none"},
            {"similarity": 0.6, "verdict": "found"},
        ]
        assert compute_overall_verdict(results) == "found"

    def test_weak_if_no_found(self):
        results = [
            {"similarity": 0.3, "verdict": "weak"},
            {"similarity": 0.1, "verdict": "none"},
        ]
        assert compute_overall_verdict(results) == "weak"

    def test_none_if_all_none(self):
        results = [
            {"similarity": 0.1, "verdict": "none"},
        ]
        assert compute_overall_verdict(results) == "none"

    def test_empty_results(self):
        assert compute_overall_verdict([]) == "none"

    def test_without_verdict_key(self):
        results = [{"similarity": 0.5}]
        assert compute_overall_verdict(results) == "found"


class TestFormatVerdictLabel:
    """Test verdict label formatting."""

    def test_found_label(self):
        assert format_verdict_label("found") == "confident match"

    def test_weak_label(self):
        assert format_verdict_label("weak") == "possible match"

    def test_none_label(self):
        assert format_verdict_label("none") == "low relevance"

    def test_unknown_label(self):
        assert format_verdict_label("unknown") == "unknown"
