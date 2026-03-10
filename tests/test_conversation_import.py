"""Tests for conversation import (v0.9.4)."""

from __future__ import annotations

import json

import pytest

from src.conversation_import import (
    format_import_summary,
    import_chatgpt_conversations,
    import_claude_conversations,
    import_gemini_conversations,
    import_plain_text,
    _classify_content,
    _sanitize_tag,
    _timestamp_to_iso,
)


# --- ChatGPT Import ---

class TestChatGPTImport:
    def _make_export(self, messages):
        mapping = {}
        for i, (role, text) in enumerate(messages):
            mapping[str(i)] = {
                "message": {
                    "author": {"role": role},
                    "content": {"parts": [text]},
                }
            }
        return json.dumps([{
            "title": "Test Conversation",
            "create_time": 1709251200,
            "mapping": mapping,
        }])

    def test_extracts_decisions(self):
        data = self._make_export([
            ("user", "I decided to use PostgreSQL for the database"),
            ("assistant", "Great choice!"),
        ])
        result = import_chatgpt_conversations(data)
        assert len(result) == 1
        assert result[0]["category"] == "decision"
        assert result[0]["source"] == "chatgpt-conversation"

    def test_extracts_preferences(self):
        data = self._make_export([
            ("user", "I prefer dark mode for all my editors"),
        ])
        result = import_chatgpt_conversations(data)
        assert len(result) == 1
        assert result[0]["category"] == "preference"

    def test_skips_short_messages(self):
        data = self._make_export([("user", "yes")])
        result = import_chatgpt_conversations(data)
        assert len(result) == 0

    def test_skips_assistant_messages(self):
        data = self._make_export([
            ("assistant", "I decided to recommend PostgreSQL for you"),
        ])
        result = import_chatgpt_conversations(data)
        assert len(result) == 0

    def test_tag_from_title(self):
        data = self._make_export([
            ("user", "I prefer using TypeScript over JavaScript"),
        ])
        result = import_chatgpt_conversations(data)
        assert "test-conversation" in result[0]["tags"]

    def test_invalid_json(self):
        assert import_chatgpt_conversations("not json") == []

    def test_empty_list(self):
        assert import_chatgpt_conversations("[]") == []


# --- Claude Import ---

class TestClaudeImport:
    def _make_export(self, messages):
        msgs = [{"sender": role, "text": text} for role, text in messages]
        return json.dumps([{
            "uuid": "abc-123",
            "name": "Claude Chat",
            "created_at": "2026-03-01T10:00:00Z",
            "chat_messages": msgs,
        }])

    def test_extracts_decisions(self):
        data = self._make_export([
            ("human", "I decided to switch to React for the frontend"),
            ("assistant", "That makes sense!"),
        ])
        result = import_claude_conversations(data)
        assert len(result) == 1
        assert result[0]["category"] == "decision"
        assert result[0]["source"] == "claude-conversation"

    def test_extracts_preferences(self):
        data = self._make_export([
            ("human", "I always use black for Python formatting"),
        ])
        result = import_claude_conversations(data)
        assert len(result) == 1
        assert result[0]["category"] == "preference"

    def test_skips_assistant(self):
        data = self._make_export([
            ("assistant", "I prefer to give concise answers"),
        ])
        result = import_claude_conversations(data)
        assert len(result) == 0

    def test_date_extracted(self):
        data = self._make_export([
            ("human", "I decided to use FastAPI for the REST API"),
        ])
        result = import_claude_conversations(data)
        assert result[0]["date"] == "2026-03-01"

    def test_invalid_json(self):
        assert import_claude_conversations("{bad}") == []


# --- Gemini Import ---

class TestGeminiImport:
    def _make_export(self, messages):
        msgs = [{"role": role, "content": text, "timestamp": "2026-03-01T10:00:00Z"} for role, text in messages]
        return json.dumps([{
            "title": "Gemini Chat",
            "messages": msgs,
        }])

    def test_extracts_facts(self):
        data = self._make_export([
            ("user", "Note that the API endpoint is /v2/users"),
        ])
        result = import_gemini_conversations(data)
        assert len(result) == 1
        assert result[0]["category"] == "fact"
        assert result[0]["source"] == "gemini-conversation"

    def test_skips_model_messages(self):
        data = self._make_export([
            ("model", "Remember that this API has rate limits"),
        ])
        result = import_gemini_conversations(data)
        assert len(result) == 0

    def test_invalid_json(self):
        assert import_gemini_conversations("bad") == []


# --- Plain Text Import ---

class TestPlainTextImport:
    def test_basic(self):
        data = "I decided to use PostgreSQL\nI prefer TypeScript\nshort"
        result = import_plain_text(data)
        assert len(result) == 2  # "short" is < 5 chars → skipped

    def test_classification(self):
        data = "I prefer dark mode always"
        result = import_plain_text(data)
        assert result[0]["category"] == "preference"

    def test_unclassified_defaults_to_fact(self):
        data = "This is just a regular sentence with enough words"
        result = import_plain_text(data)
        assert result[0]["category"] == "fact"


# --- Korean ---

class TestKorean:
    def test_korean_decision(self):
        assert _classify_content("PostgreSQL로 결정했습니다") == "decision"

    def test_korean_preference(self):
        assert _classify_content("다크 모드를 선호합니다") == "preference"

    def test_korean_fact(self):
        assert _classify_content("이것은 중요한 사항입니다") == "fact"


# --- Helpers ---

class TestHelpers:
    def test_sanitize_tag(self):
        assert _sanitize_tag("My Test Chat!") == "my-test-chat"

    def test_sanitize_tag_korean(self):
        assert _sanitize_tag("한국어 채팅") == "한국어-채팅"

    def test_sanitize_tag_empty(self):
        assert _sanitize_tag("!!!") == "conversation"

    def test_timestamp_to_iso(self):
        result = _timestamp_to_iso(1709251200)
        assert result.startswith("2024-")

    def test_timestamp_none(self):
        assert _timestamp_to_iso(None) == ""

    def test_format_summary(self):
        mems = [
            {"category": "decision", "source": "chatgpt-conversation"},
            {"category": "preference", "source": "chatgpt-conversation"},
            {"category": "decision", "source": "chatgpt-conversation"},
        ]
        result = format_import_summary(mems)
        assert "3 memories" in result
        assert "Decision" in result

    def test_format_summary_empty(self):
        result = format_import_summary([])
        assert "No extractable" in result
