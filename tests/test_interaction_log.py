"""Tests for the interaction logging system."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.interaction_log import InteractionLog, SESSION_ID


class TestInteractionLog:
    def test_create_db(self, tmp_path):
        db_path = tmp_path / "test_interactions.db"
        log = InteractionLog(db_path)
        assert db_path.exists()

    def test_log_and_retrieve(self, tmp_path):
        log = InteractionLog(tmp_path / "test.db")
        log.log("search_documents", "query='test'", "5 results", 42)

        interactions = log.get_session_interactions()
        assert len(interactions) == 1
        assert interactions[0]["tool_name"] == "search_documents"
        assert interactions[0]["input_summary"] == "query='test'"
        assert interactions[0]["output_summary"] == "5 results"
        assert interactions[0]["duration_ms"] == 42

    def test_multiple_logs(self, tmp_path):
        log = InteractionLog(tmp_path / "test.db")
        log.log("search_documents", "q1", "r1")
        log.log("remember", "q2", "r2")
        log.log("recall", "q3", "r3")

        interactions = log.get_session_interactions()
        assert len(interactions) == 3
        # Most recent first
        assert interactions[0]["tool_name"] == "recall"

    def test_session_id_is_consistent(self, tmp_path):
        log = InteractionLog(tmp_path / "test.db")
        log.log("tool1", "in", "out")
        log.log("tool2", "in", "out")

        interactions = log.get_session_interactions()
        # All logged under current SESSION_ID
        assert len(interactions) == 2

    def test_get_recent_sessions(self, tmp_path):
        log = InteractionLog(tmp_path / "test.db")
        log.log("tool1", "in", "out")

        sessions = log.get_recent_sessions()
        assert len(sessions) == 1
        assert sessions[0]["session_id"] == SESSION_ID
        assert sessions[0]["interaction_count"] == 1

    def test_get_stats(self, tmp_path):
        log = InteractionLog(tmp_path / "test.db")
        log.log("search", "q1", "r1")
        log.log("search", "q2", "r2")
        log.log("recall", "q3", "r3")

        stats = log.get_stats()
        assert stats["total_interactions"] == 3
        assert stats["total_sessions"] == 1
        assert stats["unique_tools"] == 2

    def test_input_truncation(self, tmp_path):
        log = InteractionLog(tmp_path / "test.db")
        long_input = "x" * 5000
        log.log("tool", long_input, "out")

        interactions = log.get_session_interactions()
        assert len(interactions[0]["input_summary"]) <= 2000

    def test_empty_session(self, tmp_path):
        log = InteractionLog(tmp_path / "test.db")
        interactions = log.get_session_interactions("nonexistent_session")
        assert interactions == []

    def test_limit(self, tmp_path):
        log = InteractionLog(tmp_path / "test.db")
        for i in range(10):
            log.log(f"tool_{i}", f"in_{i}", f"out_{i}")

        interactions = log.get_session_interactions(limit=3)
        assert len(interactions) == 3
