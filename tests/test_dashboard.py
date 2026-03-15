"""Tests for the web dashboard (Phase 7a)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.dashboard import render_dashboard


class TestRenderDashboard:
    def test_basic_render(self):
        stats = {
            "memory_count": 42,
            "entity_count": 15,
            "relationship_count": 28,
            "health_score": "85/100",
            "contradiction_count": 2,
            "cluster_count": 3,
            "recent_memories": [],
            "entity_graph_mermaid": "",
            "version": "1.2.0",
        }
        html = render_dashboard(stats)
        assert "<!DOCTYPE html>" in html
        assert "Tessera" in html
        assert "42" in html  # memory count
        assert "15" in html  # entity count
        assert "85/100" in html  # health score
        assert "1.2.0" in html  # version

    def test_empty_stats(self):
        html = render_dashboard({})
        assert "<!DOCTYPE html>" in html
        assert "Tessera" in html

    def test_with_memories(self):
        stats = {
            "memory_count": 2,
            "entity_count": 0,
            "relationship_count": 0,
            "health_score": "—",
            "contradiction_count": 0,
            "cluster_count": 0,
            "recent_memories": [
                {
                    "date": "2026-03-15",
                    "category": "decision",
                    "tags": "db",
                    "content": "Use PostgreSQL for the project",
                },
            ],
            "entity_graph_mermaid": "",
            "version": "1.2.0",
        }
        html = render_dashboard(stats)
        assert "PostgreSQL" in html
        assert "decision" in html
        assert "Recent Memories" in html

    def test_with_mermaid_graph(self):
        stats = {
            "memory_count": 5,
            "entity_count": 3,
            "relationship_count": 4,
            "health_score": "90/100",
            "contradiction_count": 0,
            "cluster_count": 0,
            "recent_memories": [],
            "entity_graph_mermaid": "graph LR\n    A-->B",
            "version": "1.2.0",
        }
        html = render_dashboard(stats)
        assert "Entity Knowledge Graph" in html
        assert "mermaid" in html
        assert "graph LR" in html

    def test_xss_prevention(self):
        stats = {
            "memory_count": 0,
            "entity_count": 0,
            "relationship_count": 0,
            "health_score": "<script>alert(1)</script>",
            "contradiction_count": 0,
            "cluster_count": 0,
            "recent_memories": [
                {"date": "", "category": "", "tags": "", "content": "<img onerror=alert(1)>"},
            ],
            "entity_graph_mermaid": "",
            "version": "1.0",
        }
        html = render_dashboard(stats)
        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;" in html
        assert "<img onerror" not in html


class TestDashboardEndpoint:
    def setup_method(self):
        from fastapi.testclient import TestClient
        from src.http_server import app
        self.client = TestClient(app)

    @patch("src.http_server._gather_dashboard_stats")
    def test_dashboard_returns_html(self, mock_stats):
        mock_stats.return_value = {
            "memory_count": 10,
            "entity_count": 5,
            "relationship_count": 8,
            "health_score": "75/100",
            "contradiction_count": 1,
            "cluster_count": 0,
            "recent_memories": [],
            "entity_graph_mermaid": "",
            "version": "1.2.0",
        }
        resp = self.client.get("/dashboard")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "Tessera" in resp.text

    @patch("src.http_server._gather_dashboard_stats")
    def test_dashboard_not_in_openapi(self, mock_stats):
        """Dashboard should not appear in the API docs schema."""
        mock_stats.return_value = {}
        resp = self.client.get("/openapi.json")
        schema = resp.json()
        assert "/dashboard" not in schema.get("paths", {})


class TestParseMemoriesText:
    def test_parse_empty(self):
        from src.http_server import _parse_memories_text
        assert _parse_memories_text("") == []
        assert _parse_memories_text("No memories found") == []

    def test_parse_with_entries(self):
        from src.http_server import _parse_memories_text
        text = "[1] (similarity: 95.0%)  [decision]  date: 2026-03-15  tags: db\nUse PostgreSQL"
        result = _parse_memories_text(text)
        assert len(result) == 1
        assert result[0]["category"] == "decision"
        assert result[0]["date"] == "2026-03-15"
        assert "PostgreSQL" in result[0]["content"]
