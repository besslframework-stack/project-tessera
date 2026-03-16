"""Tests for auto-insight pipeline."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from src.auto_insight import (
    _build_digest,
    _find_decision_patterns,
    _find_hidden_connections,
    _find_trending_topics,
    format_insights,
    generate_insights,
)
from src.core import auto_insights


def _make_mem(content, category="fact", tags=None, days_ago=0):
    date = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
    return {
        "content": content,
        "category": category,
        "tags": tags or [],
        "date": date,
    }


class TestFindTrendingTopics:
    def test_new_topic_scores_high(self):
        recent = [_make_mem("postgres setup", tags=["db"])]
        older = []
        trends = _find_trending_topics(recent, older)
        assert len(trends) >= 1
        assert trends[0]["topic"] == "db"
        assert trends[0]["score"] > 0

    def test_growing_topic(self):
        recent = [
            _make_mem("api work", tags=["api"]),
            _make_mem("api fix", tags=["api"]),
        ]
        older = [_make_mem("old api", tags=["api"])]
        trends = _find_trending_topics(recent, older)
        assert any(t["topic"] == "api" for t in trends)

    def test_empty_memories(self):
        assert _find_trending_topics([], []) == []

    def test_max_five(self):
        recent = [
            _make_mem("a", tags=[f"tag{i}"]) for i in range(10)
        ]
        trends = _find_trending_topics(recent, [])
        assert len(trends) <= 5


class TestFindDecisionPatterns:
    def test_finds_recurring_subject(self):
        mems = [
            _make_mem("We decided to use postgres for prod", category="decision"),
            _make_mem("Switched postgres version to 16", category="decision"),
            _make_mem("Some random fact", category="fact"),
        ]
        patterns = _find_decision_patterns(mems)
        assert len(patterns) >= 1
        assert patterns[0]["decision_count"] >= 2

    def test_no_decisions(self):
        mems = [_make_mem("just a fact", category="fact")]
        assert _find_decision_patterns(mems) == []

    def test_empty(self):
        assert _find_decision_patterns([]) == []


class TestFindHiddenConnections:
    def test_finds_co_occurring_tags(self):
        mems = [
            _make_mem("a", tags=["db", "api"]),
            _make_mem("b", tags=["db", "api"]),
        ]
        conns = _find_hidden_connections(mems)
        assert len(conns) == 1
        assert set(conns[0]["topics"]) == {"db", "api"}
        assert conns[0]["co_occurrences"] == 2

    def test_no_overlap(self):
        mems = [
            _make_mem("a", tags=["db"]),
            _make_mem("b", tags=["api"]),
        ]
        assert _find_hidden_connections(mems) == []

    def test_single_co_occurrence_below_threshold(self):
        mems = [_make_mem("a", tags=["db", "api"])]
        assert _find_hidden_connections(mems) == []


class TestBuildDigest:
    def test_with_memories(self):
        mems = [
            _make_mem("First thing", category="decision"),
            _make_mem("Second thing", category="fact"),
        ]
        digest = _build_digest(mems, 7)
        assert "2 memories" in digest
        assert "decision" in digest

    def test_empty(self):
        digest = _build_digest([], 7)
        assert "No new memories" in digest


class TestGenerateInsights:
    @patch("src.memory.recall_memories")
    def test_basic_structure(self, mock_recall):
        mock_recall.return_value = [
            _make_mem("test memory", tags=["db"], days_ago=1),
        ]
        result = generate_insights(days=7)
        assert "period" in result
        assert "trending_topics" in result
        assert "decision_patterns" in result
        assert "connections" in result
        assert "digest" in result
        assert result["recent_count"] == 1

    @patch("src.memory.recall_memories")
    def test_empty(self, mock_recall):
        mock_recall.return_value = []
        result = generate_insights(days=7)
        assert result["recent_count"] == 0
        assert result["trending_topics"] == []

    @patch("src.memory.recall_memories", side_effect=Exception("boom"))
    def test_handles_error(self, mock_recall):
        result = generate_insights(days=7)
        assert result["total_memories"] == 0


class TestFormatInsights:
    def test_formats_output(self):
        insights = {
            "period": "Last 7 days",
            "total_memories": 10,
            "recent_count": 3,
            "trending_topics": [
                {"topic": "db", "score": 2.0, "recent_count": 2},
            ],
            "decision_patterns": [],
            "connections": [],
            "digest": "3 memories in the last 7 days",
        }
        text = format_insights(insights)
        assert "Auto-Insights" in text
        assert "db" in text
        assert "Digest" in text

    def test_empty_insights(self):
        insights = {
            "period": "Last 7 days",
            "total_memories": 0,
            "recent_count": 0,
            "trending_topics": [],
            "decision_patterns": [],
            "connections": [],
            "digest": "No new memories in the last 7 days.",
        }
        text = format_insights(insights)
        assert "No clear trends" in text


class TestCoreAutoInsights:
    @patch("src.auto_insight.generate_insights")
    def test_delegates_to_module(self, mock_gen):
        mock_gen.return_value = {
            "period": "Last 7 days",
            "total_memories": 5,
            "recent_count": 2,
            "trending_topics": [{"topic": "api", "score": 1.5, "recent_count": 2}],
            "decision_patterns": [],
            "connections": [],
            "digest": "2 memories in the last 7 days",
        }
        result = auto_insights(days=7)
        assert "Auto-Insights" in result
        assert "api" in result


class TestAutoInsightsEndpoint:
    def setup_method(self):
        from fastapi.testclient import TestClient
        from src.http_server import app
        self.client = TestClient(app)

    @patch("src.core.auto_insights", return_value="Insights report")
    def test_endpoint(self, mock_ai):
        resp = self.client.get("/auto-insights")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        mock_ai.assert_called_once()

    @patch("src.core.auto_insights", return_value="Insights report")
    def test_custom_days(self, mock_ai):
        resp = self.client.get("/auto-insights?days=30")
        assert resp.status_code == 200
        mock_ai.assert_called_once_with(days=30)
