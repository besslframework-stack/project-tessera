"""Tests for search query preprocessing and quality improvements."""

from __future__ import annotations

from src.search import _clean_query


class TestCleanQuery:
    def test_strips_markdown(self):
        result = _clean_query("# Header **bold** `code`")
        assert "#" not in result
        assert "*" not in result
        assert "`" not in result

    def test_strips_urls(self):
        result = _clean_query("Check https://example.com for details")
        assert "https://" not in result
        assert "details" in result

    def test_normalizes_whitespace(self):
        result = _clean_query("too   many    spaces\n\nand\nnewlines")
        assert "  " not in result
        assert "\n" not in result

    def test_preserves_korean(self):
        result = _clean_query("인증 플로우에 대한 **결정**")
        assert "인증" in result
        assert "플로우" in result
        assert "결정" in result
        assert "*" not in result

    def test_empty_string(self):
        result = _clean_query("")
        assert result == ""

    def test_plain_text_unchanged(self):
        result = _clean_query("simple query text")
        assert result == "simple query text"

    def test_wiki_links_cleaned(self):
        result = _clean_query("see [[Authentication Flow]]")
        assert "[[" not in result
        assert "]]" not in result
        assert "Authentication Flow" in result

    def test_mixed_markdown(self):
        result = _clean_query("## Title\n> quote\n- list item `code` [link](url)")
        assert "#" not in result
        assert ">" not in result
        assert "`" not in result
        assert "Title" in result
        assert "quote" in result
