"""Tests for context window builder (v0.7.4)."""

from __future__ import annotations

import pytest

from src.context_window import (
    build_context_window,
    estimate_tokens,
    format_context_summary,
    _format_memory_entry,
    _format_document_entry,
)


class TestEstimateTokens:
    def test_basic(self):
        assert estimate_tokens("hello world") >= 2

    def test_empty(self):
        assert estimate_tokens("") == 1  # min 1

    def test_long_text(self):
        text = "a" * 400
        assert estimate_tokens(text) == 100  # 400 / 4

    def test_korean(self):
        # Korean chars are ~3 bytes but we count chars
        text = "안녕하세요 세계"
        tokens = estimate_tokens(text)
        assert tokens >= 1


class TestFormatMemoryEntry:
    def test_full_entry(self):
        mem = {
            "content": "Use PostgreSQL for database",
            "date": "2026-03-01T10:00:00",
            "category": "decision",
            "tags": ["db", "backend"],
        }
        result = _format_memory_entry(mem)
        assert "[2026-03-01]" in result
        assert "(decision)" in result
        assert "Use PostgreSQL" in result
        assert "#db" in result

    def test_minimal_entry(self):
        mem = {"content": "some fact"}
        result = _format_memory_entry(mem)
        assert "some fact" in result
        assert result.startswith("- ")

    def test_no_date(self):
        mem = {"content": "test", "category": "fact"}
        result = _format_memory_entry(mem)
        assert "(fact)" in result
        assert "[" not in result.replace("(fact)", "").replace("- ", "")


class TestFormatDocumentEntry:
    def test_with_source(self):
        doc = {"content": "Document content here", "source": "readme.md"}
        result = _format_document_entry(doc)
        assert "[readme.md]" in result
        assert "Document content here" in result

    def test_long_content_truncated(self):
        doc = {"content": "x" * 600, "source": "big.md"}
        result = _format_document_entry(doc)
        assert len(result) < 600
        assert "..." in result

    def test_no_source(self):
        doc = {"content": "orphan content"}
        result = _format_document_entry(doc)
        assert "orphan content" in result


class TestBuildContextWindow:
    def _make_memories(self, n=5):
        return [
            {
                "content": f"Memory item {i} with enough content to take space",
                "score": 1.0 - i * 0.1,
                "date": f"2026-03-0{i+1}",
                "category": "fact",
                "tags": [f"tag{i}"],
            }
            for i in range(n)
        ]

    def _make_documents(self, n=3):
        return [
            {
                "content": f"Document snippet {i} from project files",
                "score": 0.9 - i * 0.1,
                "source": f"file{i}.md",
            }
            for i in range(n)
        ]

    def test_basic(self):
        result = build_context_window(self._make_memories(3))
        assert result["included_memories"] == 3
        assert result["token_count"] > 0
        assert "Memory item 0" in result["context"]

    def test_sorted_by_score(self):
        mems = self._make_memories(3)
        result = build_context_window(mems)
        # Highest score first
        ctx = result["context"]
        pos0 = ctx.index("Memory item 0")
        pos1 = ctx.index("Memory item 1")
        assert pos0 < pos1

    def test_includes_documents(self):
        result = build_context_window(
            self._make_memories(2),
            documents=self._make_documents(2),
        )
        assert result["included_memories"] == 2
        assert result["included_documents"] == 2
        assert "Document snippet" in result["context"]

    def test_respects_budget(self):
        # Very small budget — should truncate
        result = build_context_window(
            self._make_memories(10),
            token_budget=200,
            reserve_tokens=50,
        )
        assert result["token_count"] <= 200
        assert result["included_memories"] < 10

    def test_truncated_flag(self):
        result = build_context_window(
            self._make_memories(10),
            token_budget=100,
            reserve_tokens=20,
        )
        assert result["truncated"] is True

    def test_no_truncation_large_budget(self):
        result = build_context_window(
            self._make_memories(2),
            token_budget=10000,
        )
        assert result["truncated"] is False
        assert result["included_memories"] == 2

    def test_empty_memories(self):
        result = build_context_window([])
        assert result["included_memories"] == 0
        assert result["context"] == ""

    def test_zero_budget(self):
        result = build_context_window(
            self._make_memories(3),
            token_budget=100,
            reserve_tokens=200,
        )
        assert result["token_count"] == 0
        assert result["context"] == ""

    def test_memories_before_documents(self):
        result = build_context_window(
            self._make_memories(2),
            documents=self._make_documents(2),
        )
        ctx = result["context"]
        mem_pos = ctx.index("Relevant Memories")
        doc_pos = ctx.index("Relevant Documents")
        assert mem_pos < doc_pos

    def test_documents_only(self):
        result = build_context_window(
            [],
            documents=self._make_documents(2),
        )
        assert result["included_documents"] == 2
        assert result["included_memories"] == 0

    def test_empty_content_skipped(self):
        mems = [
            {"content": "", "score": 1.0},
            {"content": "real content", "score": 0.5},
        ]
        result = build_context_window(mems)
        assert result["included_memories"] == 1


class TestFormatContextSummary:
    def test_with_data(self):
        result = {
            "context": "## Relevant Memories\n- test",
            "token_count": 50,
            "included_memories": 3,
            "included_documents": 1,
            "truncated": False,
        }
        summary = format_context_summary(result)
        assert "~50 tokens" in summary
        assert "Memories: 3" in summary
        assert "Documents: 1" in summary
        assert "truncated" not in summary

    def test_truncated(self):
        result = {
            "context": "...",
            "token_count": 100,
            "included_memories": 5,
            "included_documents": 0,
            "truncated": True,
        }
        summary = format_context_summary(result)
        assert "truncated" in summary

    def test_empty(self):
        result = {
            "context": "",
            "token_count": 0,
            "included_memories": 0,
            "included_documents": 0,
            "truncated": False,
        }
        summary = format_context_summary(result)
        assert "No relevant context" in summary
