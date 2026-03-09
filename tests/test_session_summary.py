"""Tests for session summary (v0.6.9)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.session_summary import generate_session_summary, save_session_summary


def _make_interactions(count: int, tool_name: str = "search_documents") -> list[dict]:
    """Helper to create test interactions."""
    return [
        {
            "tool_name": tool_name,
            "input_summary": f"query='test query {i}'",
            "output_summary": f"Found {i} results",
            "timestamp": f"2026-03-10T10:{i:02d}:00",
        }
        for i in range(count)
    ]


class TestGenerateSessionSummary:
    def test_too_short(self):
        assert generate_session_summary([]) is None
        assert generate_session_summary(_make_interactions(1)) is None
        assert generate_session_summary(_make_interactions(2)) is None

    def test_minimum_interactions(self):
        result = generate_session_summary(_make_interactions(3))
        assert result is not None
        assert "3 interactions" in result

    def test_contains_tool_usage(self):
        result = generate_session_summary(_make_interactions(5))
        assert "search_documents x5" in result

    def test_contains_time_range(self):
        result = generate_session_summary(_make_interactions(5))
        assert "2026-03-10" in result

    def test_extracts_queries(self):
        result = generate_session_summary(_make_interactions(5))
        assert "Searched:" in result
        assert "test query" in result

    def test_extracts_remembered_content(self):
        interactions = [
            {
                "tool_name": "remember",
                "input_summary": "content='Use PostgreSQL for main DB'",
                "output_summary": "saved",
                "timestamp": "2026-03-10T10:00:00",
            },
            {
                "tool_name": "search_documents",
                "input_summary": "query='database'",
                "output_summary": "3 results",
                "timestamp": "2026-03-10T10:01:00",
            },
            {
                "tool_name": "search_documents",
                "input_summary": "query='schema'",
                "output_summary": "2 results",
                "timestamp": "2026-03-10T10:02:00",
            },
        ]
        result = generate_session_summary(interactions)
        assert "Remembered: Use PostgreSQL" in result

    def test_multiple_tools(self):
        interactions = [
            {"tool_name": "search_documents", "input_summary": "query='a'", "output_summary": "ok", "timestamp": "2026-03-10T10:00:00"},
            {"tool_name": "remember", "input_summary": "content='b'", "output_summary": "ok", "timestamp": "2026-03-10T10:01:00"},
            {"tool_name": "recall", "input_summary": "query='c'", "output_summary": "ok", "timestamp": "2026-03-10T10:02:00"},
        ]
        result = generate_session_summary(interactions)
        assert "search_documents" in result
        assert "remember" in result

    def test_no_timestamps(self):
        interactions = [
            {"tool_name": "search_documents", "input_summary": "", "output_summary": ""},
            {"tool_name": "search_documents", "input_summary": "", "output_summary": ""},
            {"tool_name": "search_documents", "input_summary": "", "output_summary": ""},
        ]
        result = generate_session_summary(interactions)
        assert result is not None
        assert "unknown" in result

    def test_deduplicates_queries(self):
        interactions = [
            {"tool_name": "search_documents", "input_summary": "query='same query'", "output_summary": "", "timestamp": f"2026-03-10T10:0{i}:00"}
            for i in range(5)
        ]
        result = generate_session_summary(interactions)
        # Should only show unique queries
        assert result.count("same query") == 1


class TestSaveSessionSummary:
    def test_saves_summary(self, tmp_path):
        interactions = _make_interactions(5)
        with patch("src.memory.save_memory") as mock_save, \
             patch("src.memory.index_memory", return_value=1):
            mock_save.return_value = tmp_path / "summary.md"
            (tmp_path / "summary.md").write_text("test")
            result = save_session_summary("abc123", interactions)
            assert result is not None
            assert result["indexed"] is True
            mock_save.assert_called_once()
            call_kwargs = mock_save.call_args
            assert "session-summary" in call_kwargs.kwargs.get("tags", call_kwargs[1].get("tags", []))
            assert call_kwargs.kwargs.get("category", call_kwargs[1].get("category")) == "context"

    def test_skips_short_session(self):
        result = save_session_summary("abc123", _make_interactions(1))
        assert result is None

    def test_handles_index_failure(self, tmp_path):
        interactions = _make_interactions(5)
        with patch("src.memory.save_memory") as mock_save, \
             patch("src.memory.index_memory", side_effect=Exception("DB error")):
            mock_save.return_value = tmp_path / "summary.md"
            (tmp_path / "summary.md").write_text("test")
            result = save_session_summary("abc123", interactions)
            assert result is not None
            assert result["indexed"] is False
