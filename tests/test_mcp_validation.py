"""Tests for MCP tool input validation."""

from __future__ import annotations

from unittest.mock import patch, MagicMock


class TestSearchValidation:
    def test_empty_query(self):
        from mcp_server import search_documents

        result = search_documents(query="")
        assert "provide a search query" in result.lower()

    def test_whitespace_query(self):
        from mcp_server import search_documents

        result = search_documents(query="   ")
        assert "provide a search query" in result.lower()

    def test_top_k_clamped_negative(self):
        from mcp_server import search_documents

        with patch("mcp_server.search", return_value=[]) as mock_search:
            search_documents(query="test", top_k=-5)
            # top_k should be clamped to 1
            mock_search.assert_called_once_with("test", top_k=1, project=None, doc_type=None)

    def test_top_k_clamped_too_high(self):
        from mcp_server import search_documents

        with patch("mcp_server.search", return_value=[]) as mock_search:
            search_documents(query="test", top_k=999)
            mock_search.assert_called_once_with("test", top_k=50, project=None, doc_type=None)


class TestRecallValidation:
    def test_empty_query(self):
        from mcp_server import recall

        result = recall(query="")
        assert "provide a search query" in result.lower()


class TestRememberValidation:
    def test_empty_content(self):
        from mcp_server import remember

        result = remember(content="")
        assert "remember" in result.lower() or "provide content" in result.lower()

    def test_whitespace_content(self):
        from mcp_server import remember

        result = remember(content="   \n  ")
        assert "remember" in result.lower() or "provide content" in result.lower()


class TestLearnValidation:
    def test_empty_content(self):
        from mcp_server import learn

        result = learn(content="")
        assert "remember" in result.lower() or "provide content" in result.lower()


class TestUnifiedSearchValidation:
    def test_empty_query(self):
        from mcp_server import unified_search

        result = unified_search(query="")
        assert "provide a search query" in result.lower()

    def test_whitespace_query(self):
        from mcp_server import unified_search

        result = unified_search(query="   ")
        assert "provide a search query" in result.lower()


class TestExploreValidation:
    def test_empty_query(self):
        from mcp_server import explore_connections

        result = explore_connections(query="")
        assert "provide a topic" in result.lower()
