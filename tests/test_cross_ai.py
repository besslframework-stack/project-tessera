"""Tests for cross-AI format converters (v0.9.3)."""

from __future__ import annotations

import json

import pytest

from src.cross_ai import (
    export_for_chatgpt,
    export_for_gemini,
    export_standard,
    import_from_chatgpt,
    import_from_gemini,
    import_standard,
)


def _make_memories():
    return [
        {"content": "Use PostgreSQL for production", "date": "2026-03-01", "category": "decision", "tags": ["db", "backend"], "id": "m1"},
        {"content": "Prefer TypeScript", "date": "2026-03-02", "category": "preference", "tags": ["lang"]},
        {"content": "API rate limit is 100/min", "date": "2026-03-03", "category": "fact", "tags": ["api"]},
    ]


# --- ChatGPT Export ---

class TestExportChatGPT:
    def test_valid_json(self):
        result = export_for_chatgpt(_make_memories())
        data = json.loads(result)
        assert len(data) == 3

    def test_fields(self):
        result = export_for_chatgpt(_make_memories())
        data = json.loads(result)
        assert "id" in data[0]
        assert "content" in data[0]
        assert "created_at" in data[0]

    def test_category_in_content(self):
        result = export_for_chatgpt(_make_memories())
        data = json.loads(result)
        assert "[decision]" in data[0]["content"]

    def test_tags_in_content(self):
        result = export_for_chatgpt(_make_memories())
        data = json.loads(result)
        assert "tags: db, backend" in data[0]["content"]

    def test_empty(self):
        assert json.loads(export_for_chatgpt([])) == []

    def test_korean(self):
        mems = [{"content": "한국어 메모", "date": "2026-03-01", "category": "fact", "tags": []}]
        result = export_for_chatgpt(mems)
        assert "한국어" in result


# --- ChatGPT Import ---

class TestImportChatGPT:
    def test_basic(self):
        data = json.dumps([
            {"id": "1", "content": "Use dark mode", "created_at": "2026-03-01"},
            {"id": "2", "content": "API timeout is 30s [fact]", "created_at": "2026-03-02"},
        ])
        result = import_from_chatgpt(data)
        assert len(result) == 2

    def test_category_extraction(self):
        data = json.dumps([{"content": "Prefer vim [preference]", "created_at": "2026-03-01"}])
        result = import_from_chatgpt(data)
        assert result[0]["category"] == "preference"
        assert "Prefer vim" in result[0]["content"]
        assert "[preference]" not in result[0]["content"]

    def test_tag_extraction(self):
        data = json.dumps([{"content": "Use React (tags: frontend, js) [decision]", "created_at": "2026-03-01"}])
        result = import_from_chatgpt(data)
        assert result[0]["tags"] == ["frontend", "js"]
        assert result[0]["category"] == "decision"
        assert "(tags:" not in result[0]["content"]

    def test_source_set(self):
        data = json.dumps([{"content": "hello", "created_at": "2026-03-01"}])
        result = import_from_chatgpt(data)
        assert result[0]["source"] == "chatgpt-import"

    def test_empty_content_skipped(self):
        data = json.dumps([{"content": "", "created_at": "2026-03-01"}, {"content": "valid"}])
        result = import_from_chatgpt(data)
        assert len(result) == 1

    def test_invalid_json(self):
        assert import_from_chatgpt("not json") == []

    def test_not_list(self):
        assert import_from_chatgpt('{"key": "value"}') == []


# --- Gemini Export ---

class TestExportGemini:
    def test_valid_json(self):
        result = export_for_gemini(_make_memories())
        data = json.loads(result)
        assert "facts" in data
        assert "preferences" in data

    def test_preference_separated(self):
        result = export_for_gemini(_make_memories())
        data = json.loads(result)
        assert len(data["preferences"]) == 1
        assert "TypeScript" in data["preferences"][0]["text"]

    def test_facts_count(self):
        result = export_for_gemini(_make_memories())
        data = json.loads(result)
        assert len(data["facts"]) == 2

    def test_topics_included(self):
        result = export_for_gemini(_make_memories())
        data = json.loads(result)
        fact = next(f for f in data["facts"] if "PostgreSQL" in f["text"])
        assert fact["topics"] == ["db", "backend"]

    def test_empty(self):
        result = export_for_gemini([])
        data = json.loads(result)
        assert data == {"facts": [], "preferences": []}


# --- Gemini Import ---

class TestImportGemini:
    def test_basic(self):
        data = json.dumps({
            "facts": [{"text": "Python is great", "date": "2026-03-01"}],
            "preferences": [{"text": "Dark mode", "date": "2026-03-02"}],
        })
        result = import_from_gemini(data)
        assert len(result) == 2

    def test_categories(self):
        data = json.dumps({
            "facts": [{"text": "fact text"}],
            "preferences": [{"text": "pref text"}],
        })
        result = import_from_gemini(data)
        cats = {m["category"] for m in result}
        assert cats == {"fact", "preference"}

    def test_source_set(self):
        data = json.dumps({"facts": [{"text": "hello"}], "preferences": []})
        result = import_from_gemini(data)
        assert result[0]["source"] == "gemini-import"

    def test_invalid_json(self):
        assert import_from_gemini("bad") == []


# --- Standard Format ---

class TestStandard:
    def test_roundtrip(self):
        original = _make_memories()
        exported = export_standard(original)
        imported = import_standard(exported)
        assert len(imported) == len(original)
        assert imported[0]["content"] == original[0]["content"]
        assert imported[0]["category"] == original[0]["category"]
        assert imported[0]["tags"] == original[0]["tags"]

    def test_version_field(self):
        result = export_standard(_make_memories())
        data = json.loads(result)
        assert data["version"] == "1.0"
        assert data["source"] == "tessera"

    def test_empty(self):
        result = export_standard([])
        data = json.loads(result)
        assert data["memories"] == []

    def test_import_invalid(self):
        assert import_standard("not json") == []

    def test_import_empty_content_skipped(self):
        data = json.dumps({"version": "1.0", "memories": [{"content": ""}, {"content": "valid"}]})
        result = import_standard(data)
        assert len(result) == 1
