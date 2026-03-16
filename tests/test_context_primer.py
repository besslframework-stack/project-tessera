"""Tests for context primer."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.context_primer import format_primer, prime_context


class TestPrimeContext:
    @patch("src.memory.recall_memories", return_value=[])
    @patch("src.quiet_curation.get_health_pulse", return_value=None)
    def test_empty_state(self, mock_pulse, mock_recall):
        ctx = prime_context()
        assert ctx["health_pulse"] is None
        assert ctx["recent_decisions"] == []
        assert ctx["recent_preferences"] == []
        assert ctx["active_topics"] == []
        assert "generated_at" in ctx

    @patch("src.memory.recall_memories")
    @patch("src.quiet_curation.get_health_pulse", return_value="Background: 3 classified")
    def test_with_health_pulse(self, mock_pulse, mock_recall):
        mock_recall.return_value = []
        ctx = prime_context()
        assert ctx["health_pulse"] == "Background: 3 classified"

    @patch("src.memory.recall_memories")
    @patch("src.quiet_curation.get_health_pulse", return_value=None)
    def test_with_decisions(self, mock_pulse, mock_recall):
        def fake_recall(query, top_k=5, since=None, category=None, **kw):
            if category == "decision":
                return [
                    {"content": "Use PostgreSQL for prod", "date": "2026-03-15T10:00:00", "similarity": 0.9},
                    {"content": "Deploy on Railway", "date": "2026-03-14T09:00:00", "similarity": 0.8},
                ]
            return []
        mock_recall.side_effect = fake_recall
        ctx = prime_context(days=7)
        assert len(ctx["recent_decisions"]) == 2
        assert "PostgreSQL" in ctx["recent_decisions"][0]["content"]

    @patch("src.memory.recall_memories")
    @patch("src.quiet_curation.get_health_pulse", return_value=None)
    def test_with_preferences(self, mock_pulse, mock_recall):
        def fake_recall(query, top_k=5, since=None, category=None, **kw):
            if category == "preference":
                return [{"content": "Dark mode preferred", "date": "2026-03-15", "similarity": 0.9}]
            return []
        mock_recall.side_effect = fake_recall
        ctx = prime_context()
        assert len(ctx["recent_preferences"]) == 1
        assert "Dark mode" in ctx["recent_preferences"][0]["content"]

    @patch("src.memory.recall_memories")
    @patch("src.quiet_curation.get_health_pulse", return_value=None)
    def test_active_topics(self, mock_pulse, mock_recall):
        def fake_recall(query, top_k=5, since=None, category=None, **kw):
            if category is None and top_k == 100:
                return [
                    {"content": "x", "tags": "python, api", "similarity": 0.5},
                    {"content": "y", "tags": "python, database", "similarity": 0.5},
                    {"content": "z", "tags": "api", "similarity": 0.5},
                ]
            return []
        mock_recall.side_effect = fake_recall
        ctx = prime_context()
        topics = {t["topic"]: t["count"] for t in ctx["active_topics"]}
        assert topics.get("python") == 2
        assert topics.get("api") == 2

    @patch("src.memory.recall_memories")
    @patch("src.quiet_curation.get_health_pulse", return_value=None)
    def test_language_detection_korean(self, mock_pulse, mock_recall):
        def fake_recall(query, top_k=5, since=None, category=None, **kw):
            if top_k == 20:
                return [{"content": "한국어 테스트 메모리입니다", "similarity": 0.5}]
            return []
        mock_recall.side_effect = fake_recall
        ctx = prime_context()
        assert ctx["stats"]["language"] == "korean"

    @patch("src.memory.recall_memories")
    @patch("src.quiet_curation.get_health_pulse", return_value=None)
    def test_language_detection_english(self, mock_pulse, mock_recall):
        def fake_recall(query, top_k=5, since=None, category=None, **kw):
            if top_k == 20:
                return [{"content": "This is an English memory test content", "similarity": 0.5}]
            return []
        mock_recall.side_effect = fake_recall
        ctx = prime_context()
        assert ctx["stats"]["language"] == "english"

    @patch("src.memory.recall_memories", side_effect=Exception("db missing"))
    @patch("src.quiet_curation.get_health_pulse", side_effect=Exception("no curation"))
    def test_handles_all_failures(self, mock_pulse, mock_recall):
        ctx = prime_context()
        assert ctx["health_pulse"] is None
        assert ctx["recent_decisions"] == []
        assert ctx["recent_preferences"] == []
        assert ctx["active_topics"] == []

    @patch("src.memory.recall_memories", return_value=[])
    @patch("src.quiet_curation.get_health_pulse", return_value=None)
    def test_custom_days(self, mock_pulse, mock_recall):
        ctx = prime_context(days=30, max_items=3)
        assert ctx["recent_decisions"] == []


class TestFormatPrimer:
    def test_empty_context(self):
        ctx = {
            "health_pulse": None,
            "recent_decisions": [],
            "recent_preferences": [],
            "active_topics": [],
            "last_session": None,
            "stats": {"total_memories": 0, "language": "unknown"},
        }
        result = format_primer(ctx)
        assert "Session Context Briefing" in result
        assert "fresh start" in result

    def test_full_context(self):
        ctx = {
            "health_pulse": "Background: 5 classified",
            "recent_decisions": [
                {"content": "Use React", "date": "2026-03-15"},
            ],
            "recent_preferences": [
                {"content": "Dark mode", "date": "2026-03-14"},
            ],
            "active_topics": [
                {"topic": "python", "count": 5},
                {"topic": "api", "count": 3},
            ],
            "last_session": {
                "session_id": "abc123",
                "interactions": 15,
                "top_tools": "recall x5, search x3",
                "started": "2026-03-15T10:00",
                "ended": "2026-03-15T11:30",
            },
            "stats": {"total_memories": 42, "language": "bilingual"},
        }
        result = format_primer(ctx)
        assert "Background: 5 classified" in result
        assert "Use React" in result
        assert "Dark mode" in result
        assert "python (5)" in result
        assert "15 interactions" in result
        assert "42 memories" in result

    def test_decisions_only(self):
        ctx = {
            "health_pulse": None,
            "recent_decisions": [{"content": "Ship it", "date": "2026-03-15"}],
            "recent_preferences": [],
            "active_topics": [],
            "last_session": None,
            "stats": {"total_memories": 10, "language": "english"},
        }
        result = format_primer(ctx)
        assert "Ship it" in result
        assert "fresh start" not in result


class TestSessionPrimeEndpoint:
    def setup_method(self):
        from fastapi.testclient import TestClient
        from src.http_server import app
        self.client = TestClient(app)

    def test_endpoint(self):
        resp = self.client.get("/session-prime")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
