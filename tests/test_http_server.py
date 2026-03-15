"""Tests for HTTP API server (v0.8.1)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.http_server import app

client = TestClient(app)


class TestHealth:
    def test_health(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_version(self):
        resp = client.get("/version")
        assert resp.status_code == 200
        assert "version" in resp.json()


class TestSearch:
    @patch("src.core.search_documents", return_value="Found 3 results")
    def test_search(self, mock_search):
        resp = client.post("/search", json={"query": "test", "top_k": 5})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        mock_search.assert_called_once_with("test", 5)

    @patch("src.core.unified_search", return_value="Found docs + memories")
    def test_unified_search(self, mock_search):
        resp = client.post("/unified-search", json={"query": "test"})
        assert resp.status_code == 200
        mock_search.assert_called_once()


class TestMemory:
    @patch("src.core.remember", return_value="Saved to memory")
    def test_remember(self, mock_remember):
        resp = client.post("/remember", json={"content": "Use PostgreSQL", "tags": ["db"]})
        assert resp.status_code == 200
        mock_remember.assert_called_once_with("Use PostgreSQL", ["db"])

    @patch("src.core.recall", return_value="Found 2 memories")
    def test_recall(self, mock_recall):
        resp = client.post("/recall", json={"query": "database", "top_k": 3})
        assert resp.status_code == 200
        mock_recall.assert_called_once_with("database", 3, since=None, until=None, category=None, include_superseded=False)

    @patch("src.core.recall", return_value="Found 1 memory")
    def test_recall_with_filters(self, mock_recall):
        resp = client.post("/recall", json={
            "query": "database",
            "since": "2026-03-01",
            "category": "decision",
        })
        assert resp.status_code == 200
        mock_recall.assert_called_once_with(
            "database", 5, since="2026-03-01", until=None, category="decision",
            include_superseded=False,
        )

    @patch("src.core.learn", return_value="Learned and indexed")
    def test_learn(self, mock_learn):
        resp = client.post("/learn", json={"content": "API key is XYZ"})
        assert resp.status_code == 200
        mock_learn.assert_called_once()

    @patch("src.core.list_memories", return_value="5 memories")
    def test_list_memories(self, mock_list):
        resp = client.get("/memories?limit=10")
        assert resp.status_code == 200
        mock_list.assert_called_once_with(10)

    @patch("src.core.forget_memory", return_value="Deleted")
    def test_forget(self, mock_forget):
        resp = client.delete("/memories/test-memory")
        assert resp.status_code == 200
        mock_forget.assert_called_once_with("test-memory")

    @patch("src.core.memory_categories", return_value="3 categories")
    def test_categories(self, mock_cat):
        resp = client.get("/memories/categories")
        assert resp.status_code == 200

    @patch("src.core.search_by_category", return_value="2 decisions")
    def test_search_by_category(self, mock_sbc):
        resp = client.get("/memories/search-by-category?category=decision")
        assert resp.status_code == 200
        mock_sbc.assert_called_once_with("decision")

    @patch("src.core.memory_tags", return_value="5 tags")
    def test_tags(self, mock_tags):
        resp = client.get("/memories/tags")
        assert resp.status_code == 200

    @patch("src.core.search_by_tag", return_value="3 memories")
    def test_search_by_tag(self, mock_sbt):
        resp = client.get("/memories/search-by-tag?tag=db")
        assert resp.status_code == 200
        mock_sbt.assert_called_once_with("db")


class TestIntelligence:
    @patch("src.core.context_window", return_value="Context assembled")
    def test_context_window(self, mock_cw):
        resp = client.post("/context-window", json={"query": "database", "token_budget": 2000})
        assert resp.status_code == 200
        mock_cw.assert_called_once_with("database", 2000, True)

    @patch("src.core.decision_timeline", return_value="2 topics")
    def test_decision_timeline(self, mock_dt):
        resp = client.get("/decision-timeline")
        assert resp.status_code == 200

    @patch("src.core.smart_suggest", return_value="3 suggestions")
    def test_smart_suggest(self, mock_ss):
        resp = client.get("/smart-suggest?max_suggestions=3")
        assert resp.status_code == 200
        mock_ss.assert_called_once_with(3)

    @patch("src.core.topic_map", return_value="5 topics")
    def test_topic_map(self, mock_tm):
        resp = client.get("/topic-map?output_format=mermaid")
        assert resp.status_code == 200
        mock_tm.assert_called_once_with("mermaid")

    @patch("src.core.knowledge_stats", return_value="Stats")
    def test_knowledge_stats(self, mock_ks):
        resp = client.get("/knowledge-stats")
        assert resp.status_code == 200


class TestWorkspace:
    @patch("src.core.tessera_status", return_value="All good")
    def test_status(self, mock_status):
        resp = client.get("/status")
        assert resp.status_code == 200

    @patch("src.core.health_check", return_value="Healthy")
    def test_health_check(self, mock_hc):
        resp = client.get("/health-check")
        assert resp.status_code == 200
