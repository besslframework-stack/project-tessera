"""Tests for memory health analytics."""

import pytest
from datetime import datetime, timedelta

from src.memory_health import (
    classify_health,
    compute_growth_stats,
    format_health_report,
)


def _mem(content, date=None, category="decision", tags="test", source="user-request"):
    if date is None:
        date = datetime.now().isoformat()
    return {"content": content, "date": date, "category": category, "tags": tags, "source": source}


class TestClassifyHealth:
    def test_healthy_recent(self):
        memories = [_mem("Recent memory")]
        result = classify_health(memories)
        assert result["summary"]["healthy"] == 1
        assert result["summary"]["stale"] == 0

    def test_stale_old_memory(self):
        old_date = (datetime.now() - timedelta(days=100)).isoformat()
        memories = [_mem("Old memory", date=old_date)]
        result = classify_health(memories)
        assert result["summary"]["stale"] == 1

    def test_orphaned_minimal(self):
        memories = [{"content": "x", "date": datetime.now().isoformat(), "category": "", "tags": "", "source": ""}]
        result = classify_health(memories)
        assert result["summary"]["orphaned"] == 1

    def test_mixed_statuses(self):
        now = datetime.now().isoformat()
        old = (datetime.now() - timedelta(days=200)).isoformat()
        memories = [
            _mem("Fresh", date=now),
            _mem("Ancient", date=old),
            {"content": "tiny", "date": now, "category": "", "tags": "", "source": ""},
        ]
        result = classify_health(memories)
        assert result["summary"]["total"] == 3
        assert result["summary"]["healthy"] >= 1
        assert result["summary"]["stale"] >= 1

    def test_custom_stale_days(self):
        date = (datetime.now() - timedelta(days=50)).isoformat()
        memories = [_mem("Borderline", date=date)]
        # Default 90 days = healthy
        assert classify_health(memories)["summary"]["healthy"] == 1
        # Custom 30 days = stale
        assert classify_health(memories, stale_days=30)["summary"]["stale"] == 1

    def test_health_score(self):
        memories = [_mem("a"), _mem("b")]
        result = classify_health(memories)
        assert result["summary"]["health_score"] == 1.0

    def test_empty(self):
        result = classify_health([])
        assert result["summary"]["total"] == 0
        assert result["summary"]["health_score"] == 0

    def test_recommendations_generated(self):
        old = (datetime.now() - timedelta(days=200)).isoformat()
        memories = [_mem("Old", date=old)]
        result = classify_health(memories)
        assert len(result["recommendations"]) >= 1

    def test_no_recommendations_when_healthy(self):
        memories = [_mem("Fresh")]
        result = classify_health(memories)
        assert any("looks good" in r for r in result["recommendations"])


class TestComputeGrowthStats:
    def test_monthly_growth(self):
        memories = [
            _mem("a", date="2026-01-15T00:00:00"),
            _mem("b", date="2026-01-20T00:00:00"),
            _mem("c", date="2026-02-10T00:00:00"),
        ]
        result = compute_growth_stats(memories)
        assert result["monthly_growth"]["2026-01"] == 2
        assert result["monthly_growth"]["2026-02"] == 1

    def test_by_category(self):
        memories = [
            _mem("a", category="decision"),
            _mem("b", category="decision"),
            _mem("c", category="fact"),
        ]
        result = compute_growth_stats(memories)
        assert result["by_category"]["decision"] == 2
        assert result["by_category"]["fact"] == 1

    def test_by_source(self):
        memories = [
            _mem("a", source="user-request"),
            _mem("b", source="auto-learn"),
        ]
        result = compute_growth_stats(memories)
        assert "user-request" in result["by_source"]
        assert "auto-learn" in result["by_source"]

    def test_empty(self):
        result = compute_growth_stats([])
        assert result["total"] == 0


class TestFormatHealthReport:
    def test_basic_format(self):
        health = classify_health([_mem("test")])
        result = format_health_report(health)
        assert "Memory Health Report" in result
        assert "Health Score" in result

    def test_with_growth(self):
        memories = [_mem("a", date="2026-03-01T00:00:00")]
        health = classify_health(memories)
        growth = compute_growth_stats(memories)
        result = format_health_report(health, growth)
        assert "Growth" in result
        assert "2026-03" in result

    def test_empty_report(self):
        health = classify_health([])
        result = format_health_report(health)
        assert "0 memories" in result
