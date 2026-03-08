"""Tests for SearchAnalyticsDB — query logging and statistics over SQLite."""

from __future__ import annotations

import time

import pytest
from pathlib import Path

from src.search_analytics import SearchAnalyticsDB


@pytest.fixture
def analytics(tmp_path: Path) -> SearchAnalyticsDB:
    """Create a SearchAnalyticsDB instance backed by a temporary SQLite DB."""
    db_path = tmp_path / "analytics.db"
    sa = SearchAnalyticsDB(db_path)
    yield sa
    sa.close()


class TestLogAndGetRecent:
    """Verify that logged queries are retrievable in reverse chronological order."""

    def test_log_and_get_recent(self, analytics: SearchAnalyticsDB) -> None:
        analytics.log_query("alpha", top_k=5, result_count=3, response_time_ms=10.0)
        analytics.log_query("beta", top_k=10, result_count=7, response_time_ms=20.0)
        analytics.log_query("gamma", top_k=5, result_count=1, response_time_ms=30.0)

        recent = analytics.get_recent(limit=20)

        assert len(recent) == 3
        # Most recent first
        assert recent[0]["query"] == "gamma"
        assert recent[1]["query"] == "beta"
        assert recent[2]["query"] == "alpha"

    def test_get_recent_respects_limit(self, analytics: SearchAnalyticsDB) -> None:
        for i in range(5):
            analytics.log_query(f"q{i}", top_k=5, result_count=1, response_time_ms=10.0)

        recent = analytics.get_recent(limit=2)
        assert len(recent) == 2


class TestStatsTotalAndAvg:
    """Verify total_queries count and avg_response_ms computation."""

    def test_stats_total_and_avg(self, analytics: SearchAnalyticsDB) -> None:
        analytics.log_query("a", top_k=5, result_count=1, response_time_ms=10.0)
        analytics.log_query("b", top_k=5, result_count=2, response_time_ms=20.0)
        analytics.log_query("c", top_k=5, result_count=3, response_time_ms=30.0)

        stats = analytics.get_stats(days=30)

        assert stats["total_queries"] == 3
        assert stats["avg_response_ms"] == pytest.approx(20.0, abs=0.01)

    def test_stats_single_query(self, analytics: SearchAnalyticsDB) -> None:
        analytics.log_query("only", top_k=5, result_count=1, response_time_ms=42.5)

        stats = analytics.get_stats(days=30)

        assert stats["total_queries"] == 1
        assert stats["avg_response_ms"] == pytest.approx(42.5, abs=0.01)


class TestStatsTopQueries:
    """Verify that top_queries are ordered by frequency descending."""

    def test_stats_top_queries(self, analytics: SearchAnalyticsDB) -> None:
        for _ in range(5):
            analytics.log_query("popular", top_k=5, result_count=3, response_time_ms=10.0)
        for _ in range(2):
            analytics.log_query("less popular", top_k=5, result_count=1, response_time_ms=15.0)
        analytics.log_query("rare", top_k=5, result_count=1, response_time_ms=20.0)

        stats = analytics.get_stats(days=30)
        top = stats["top_queries"]

        assert len(top) >= 2
        # First entry should be the most frequent query
        assert top[0]["query"] == "popular"
        assert top[0]["count"] == 5
        assert top[1]["query"] == "less popular"
        assert top[1]["count"] == 2


class TestStatsQueriesBySource:
    """Verify queries_by_source aggregates correctly per source."""

    def test_stats_queries_by_source(self, analytics: SearchAnalyticsDB) -> None:
        analytics.log_query("q1", top_k=5, result_count=1, response_time_ms=10.0, source="search")
        analytics.log_query("q2", top_k=5, result_count=2, response_time_ms=10.0, source="search")
        analytics.log_query("q3", top_k=5, result_count=1, response_time_ms=10.0, source="mcp")

        stats = analytics.get_stats(days=30)
        by_source = stats["queries_by_source"]

        assert by_source["search"] == 2
        assert by_source["mcp"] == 1

    def test_default_source_is_search(self, analytics: SearchAnalyticsDB) -> None:
        analytics.log_query("q", top_k=5, result_count=1, response_time_ms=10.0)

        stats = analytics.get_stats(days=30)
        by_source = stats["queries_by_source"]

        assert "search" in by_source
        assert by_source["search"] == 1


class TestStatsZeroResultQueries:
    """Verify that queries returning 0 results are tracked."""

    def test_stats_zero_result_queries(self, analytics: SearchAnalyticsDB) -> None:
        analytics.log_query("found", top_k=5, result_count=3, response_time_ms=10.0)
        analytics.log_query("nothing1", top_k=5, result_count=0, response_time_ms=15.0)
        analytics.log_query("nothing2", top_k=5, result_count=0, response_time_ms=20.0)

        stats = analytics.get_stats(days=30)
        zero_results = stats["zero_result_queries"]

        assert len(zero_results) == 2
        zero_query_texts = [q["query"] for q in zero_results]
        assert "nothing1" in zero_query_texts
        assert "nothing2" in zero_query_texts

    def test_no_zero_result_queries_when_all_have_results(
        self, analytics: SearchAnalyticsDB
    ) -> None:
        analytics.log_query("a", top_k=5, result_count=1, response_time_ms=10.0)
        analytics.log_query("b", top_k=5, result_count=5, response_time_ms=10.0)

        stats = analytics.get_stats(days=30)
        assert len(stats["zero_result_queries"]) == 0


class TestClearOld:
    """Verify clear_old behaviour on fresh data."""

    def test_clear_old_returns_zero_on_fresh_data(
        self, analytics: SearchAnalyticsDB
    ) -> None:
        analytics.log_query("recent", top_k=5, result_count=1, response_time_ms=10.0)

        deleted = analytics.clear_old(days=90)

        assert deleted == 0

    def test_clear_old_on_empty_db(self, analytics: SearchAnalyticsDB) -> None:
        deleted = analytics.clear_old(days=90)
        assert deleted == 0


class TestEmptyStats:
    """Verify get_stats returns sensible defaults on an empty database."""

    def test_empty_stats(self, analytics: SearchAnalyticsDB) -> None:
        stats = analytics.get_stats(days=30)

        assert stats["total_queries"] == 0
        assert stats["avg_response_ms"] == 0
        assert stats["top_queries"] == []
        assert stats["queries_by_source"] == {}
        assert stats["zero_result_queries"] == []
        assert stats["queries_per_day"] == []


class TestQueriesPerDay:
    """Verify queries_per_day aggregation."""

    def test_queries_per_day(self, analytics: SearchAnalyticsDB) -> None:
        analytics.log_query("a", top_k=5, result_count=1, response_time_ms=10.0)
        analytics.log_query("b", top_k=5, result_count=2, response_time_ms=20.0)
        analytics.log_query("c", top_k=5, result_count=3, response_time_ms=30.0)

        stats = analytics.get_stats(days=30)
        per_day = stats["queries_per_day"]

        assert len(per_day) >= 1
        # All queries logged today — total across all days should be 3
        total = sum(entry["count"] for entry in per_day)
        assert total == 3


class TestOptionalFields:
    """Verify project and doc_type optional parameters are logged."""

    def test_log_with_project_and_doc_type(self, analytics: SearchAnalyticsDB) -> None:
        analytics.log_query(
            "design tokens",
            top_k=10,
            result_count=5,
            response_time_ms=12.0,
            project="claudel",
            doc_type="design-system",
            source="mcp",
        )

        recent = analytics.get_recent(limit=1)
        assert len(recent) == 1
        entry = recent[0]
        assert entry["query"] == "design tokens"
        assert entry["project"] == "claudel"
        assert entry["doc_type"] == "design-system"
        assert entry["source"] == "mcp"
