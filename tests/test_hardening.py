"""Hardening tests — edge cases, error handling, robustness (v0.9.7)."""

from __future__ import annotations

import json

import pytest

# --- Export edge cases ---

from src.export_formats import export_csv, export_json_pretty, export_markdown, export_obsidian


class TestExportEdgeCases:
    def test_missing_fields(self):
        mems = [{"content": "hello"}]
        assert "hello" in export_markdown(mems)
        assert "hello" in export_obsidian(mems)
        assert "hello" in export_csv(mems)
        data = json.loads(export_json_pretty(mems))
        assert data[0]["content"] == "hello"

    def test_none_tags(self):
        mems = [{"content": "test", "tags": None, "date": "2026-01-01", "category": "fact"}]
        # Should not crash
        export_markdown(mems)
        export_obsidian(mems)
        export_csv(mems)
        export_json_pretty(mems)

    def test_unicode_content(self):
        mems = [{"content": "日本語テスト 🎌", "date": "2026-01-01", "category": "fact", "tags": []}]
        assert "日本語" in export_markdown(mems)
        assert "日本語" in export_json_pretty(mems)

    def test_special_chars_csv(self):
        mems = [{"content": 'He said "hello, world"', "date": "2026-01-01", "category": "fact", "tags": []}]
        result = export_csv(mems)
        assert "hello" in result


# --- Cross-AI edge cases ---

from src.cross_ai import export_for_chatgpt, export_for_gemini, import_from_chatgpt, import_from_gemini


class TestCrossAIEdgeCases:
    def test_none_tags_export(self):
        mems = [{"content": "test", "tags": None, "date": "2026-01-01", "category": "fact"}]
        result = export_for_chatgpt(mems)
        assert "test" in result

    def test_deeply_nested_invalid_import(self):
        assert import_from_chatgpt("[[[]]]") == []
        assert import_from_gemini('{"facts": "not a list"}') == []

    def test_empty_objects_import(self):
        assert import_from_chatgpt('[{}]') == []
        assert import_from_gemini('{"facts": [{}], "preferences": [{}]}') == []


# --- Conversation import edge cases ---

from src.conversation_import import import_chatgpt_conversations, import_claude_conversations, _classify_content


class TestConversationImportEdgeCases:
    def test_classify_none_for_generic(self):
        assert _classify_content("just a random thing") is None

    def test_classify_empty(self):
        assert _classify_content("") is None

    def test_chatgpt_missing_mapping(self):
        data = json.dumps([{"title": "test"}])
        assert import_chatgpt_conversations(data) == []

    def test_chatgpt_string_content(self):
        data = json.dumps([{
            "title": "test",
            "create_time": 1709251200,
            "mapping": {
                "0": {
                    "message": {
                        "author": {"role": "user"},
                        "content": "I decided to use Python for the backend",
                    }
                }
            },
        }])
        result = import_chatgpt_conversations(data)
        assert len(result) == 1

    def test_claude_missing_messages(self):
        data = json.dumps([{"uuid": "x", "name": "test"}])
        result = import_claude_conversations(data)
        assert result == []


# --- Vault edge cases ---

import os
from src.vault import encrypt, decrypt, init_vault


class TestVaultEdgeCases:
    @pytest.fixture(autouse=True)
    def _reset(self):
        import src.vault
        src.vault._vault_key = None
        yield
        src.vault._vault_key = None
        os.environ.pop("TESSERA_VAULT_KEY", None)

    def test_very_long_text(self):
        os.environ["TESSERA_VAULT_KEY"] = "test"
        init_vault()
        text = "한국어 " * 5000
        assert decrypt(encrypt(text)) == text

    def test_null_bytes(self):
        os.environ["TESSERA_VAULT_KEY"] = "test"
        init_vault()
        text = "hello\x00world"
        assert decrypt(encrypt(text)) == text

    def test_newlines(self):
        os.environ["TESSERA_VAULT_KEY"] = "test"
        init_vault()
        text = "line1\nline2\nline3"
        assert decrypt(encrypt(text)) == text


# --- Migration edge cases ---

from src.migrate import normalize_memory, _normalize_date


class TestMigrationEdgeCases:
    def test_none_content(self):
        m = {"content": None}
        result = normalize_memory(m)
        assert result["content"] == "None"

    def test_numeric_tags(self):
        m = {"content": "test", "tags": [1, 2, 3]}
        result = normalize_memory(m)
        assert result["tags"] == ["1", "2", "3"]

    def test_nested_date_formats(self):
        assert _normalize_date("2026/03/01") == "2026-03-01"
        assert _normalize_date("2026.03.01") == "2026-03-01"

    def test_truncated_date(self):
        assert _normalize_date("2026") == "2026"


# --- User profile edge cases ---

from src.user_profile import build_profile


class TestUserProfileEdgeCases:
    def test_no_date_memories(self):
        mems = [{"content": "hello", "category": "fact"}]
        profile = build_profile(mems)
        assert profile["total_memories"] == 1

    def test_mixed_languages(self):
        mems = [
            {"content": "한국어만", "category": "fact", "date": "2026-01-01"},
            {"content": "English only", "category": "fact", "date": "2026-01-01"},
        ]
        profile = build_profile(mems)
        assert profile["language_preference"] in ("korean", "english", "bilingual")


# --- Relevance decay edge cases ---

from src.relevance_decay import compute_decay_factor


class TestDecayEdgeCases:
    def test_future_date(self):
        factor = compute_decay_factor("2099-01-01")
        assert factor >= 1.0  # Future dates shouldn't decay

    def test_invalid_date(self):
        factor = compute_decay_factor("not-a-date")
        assert factor == 1.0  # Fallback to no decay

    def test_empty_date(self):
        factor = compute_decay_factor("")
        assert factor == 1.0


# --- Smart suggest edge cases ---

from src.smart_suggest import suggest_from_history


class TestSmartSuggestEdgeCases:
    def test_empty_inputs(self):
        result = suggest_from_history([], [], 5)
        assert result == []

    def test_single_query(self):
        result = suggest_from_history(["hello"], [], 5)
        assert isinstance(result, list)


# --- Rate limiter edge cases ---

from src.rate_limiter import RateLimiter


class TestRateLimiterEdgeCases:
    def test_single_request_limit(self):
        rl = RateLimiter(max_requests=1, window_seconds=60)
        assert rl.is_allowed()
        assert not rl.is_allowed()

    def test_very_high_rate(self):
        rl = RateLimiter(max_requests=1000, window_seconds=1)
        for _ in range(100):
            assert rl.is_allowed()

    def test_remaining_never_negative(self):
        rl = RateLimiter(max_requests=1, window_seconds=60)
        rl.is_allowed()
        rl.is_allowed()
        assert rl.remaining() >= 0


# --- Knowledge stats edge cases ---

from src.knowledge_stats import compute_stats


class TestKnowledgeStatsEdgeCases:
    def test_empty(self):
        stats = compute_stats([], [])
        assert stats["total_memories"] == 0
        assert stats["total_documents"] == 0

    def test_no_dates(self):
        mems = [{"content": "hello", "category": "fact"}]
        stats = compute_stats(mems)
        assert stats["total_memories"] == 1
