"""Tests for entity search and entity graph (Phase 6c)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.core import entity_graph, entity_search


class TestEntitySearch:
    def test_empty_query(self):
        result = entity_search("")
        assert "provide" in result.lower()

    def test_none_query(self):
        result = entity_search(None)
        assert "provide" in result.lower()

    @patch("src.entity_store.EntityStore")
    def test_no_results(self, MockStore):
        store = MockStore.return_value
        store.search_entities_with_memories.return_value = []
        result = entity_search("nonexistent")
        assert "No entities found" in result

    @patch("src.entity_store.EntityStore")
    def test_found_entities(self, MockStore):
        store = MockStore.return_value
        store.search_entities_with_memories.return_value = [
            {
                "entity": {
                    "id": 1,
                    "name": "PostgreSQL",
                    "entity_type": "technology",
                    "mention_count": 3,
                },
                "relationships": [
                    {
                        "subject_name": "team",
                        "predicate": "chose",
                        "object_name": "PostgreSQL",
                    }
                ],
                "memory_ids": ["mem1"],
            }
        ]
        result = entity_search("postgres")
        assert "Found 1 entities" in result
        assert "PostgreSQL" in result
        assert "chose" in result

    @patch("src.entity_store.EntityStore")
    def test_limit_clamped(self, MockStore):
        store = MockStore.return_value
        store.search_entities_with_memories.return_value = []
        entity_search("test", limit=999)
        store.search_entities_with_memories.assert_called_once_with("test", limit=50)

    @patch("src.entity_store.EntityStore")
    def test_limit_min(self, MockStore):
        store = MockStore.return_value
        store.search_entities_with_memories.return_value = []
        entity_search("test", limit=0)
        store.search_entities_with_memories.assert_called_once_with("test", limit=1)


class TestEntityGraph:
    @patch("src.entity_store.EntityStore")
    def test_empty_store(self, MockStore):
        store = MockStore.return_value
        store.entity_count.return_value = 0
        result = entity_graph()
        assert "No entities" in result

    @patch("src.entity_store.EntityStore")
    def test_no_matching_entities(self, MockStore):
        store = MockStore.return_value
        store.entity_count.return_value = 5
        store.search_entities_with_memories.return_value = []
        result = entity_graph(query="nonexistent")
        assert "No entities found" in result

    @patch("src.entity_store.EntityStore")
    def test_entities_no_relationships(self, MockStore):
        store = MockStore.return_value
        store.entity_count.return_value = 3
        store.get_all_relationships.return_value = []
        result = entity_graph()
        assert "no relationships" in result.lower()

    @patch("src.entity_store.EntityStore")
    def test_mermaid_output(self, MockStore):
        store = MockStore.return_value
        store.entity_count.return_value = 5
        store.get_all_relationships.return_value = [
            {
                "subject_name": "team",
                "subject_type": "organization",
                "predicate": "chose",
                "object_name": "PostgreSQL",
                "object_type": "technology",
                "memory_id": "mem1",
                "confidence": 0.8,
            },
            {
                "subject_name": "API",
                "subject_type": "project",
                "predicate": "uses",
                "object_name": "PostgreSQL",
                "object_type": "technology",
                "memory_id": "mem2",
                "confidence": 0.9,
            },
        ]
        result = entity_graph()
        assert "```mermaid" in result
        assert "graph LR" in result
        assert "Entity Graph" in result
        assert "PostgreSQL" in result

    @patch("src.entity_store.EntityStore")
    def test_query_filter(self, MockStore):
        store = MockStore.return_value
        store.entity_count.return_value = 5
        store.search_entities_with_memories.return_value = [
            {
                "entity": {"id": 1, "name": "PostgreSQL", "entity_type": "technology"},
                "relationships": [
                    {
                        "subject_name": "team",
                        "subject_type": "organization",
                        "predicate": "chose",
                        "object_name": "PostgreSQL",
                        "object_type": "technology",
                        "memory_id": "mem1",
                        "confidence": 0.8,
                    }
                ],
                "memory_ids": ["mem1"],
            }
        ]
        result = entity_graph(query="postgres")
        assert "```mermaid" in result
        store.search_entities_with_memories.assert_called_once()

    @patch("src.entity_store.EntityStore")
    def test_max_nodes_clamped(self, MockStore):
        store = MockStore.return_value
        store.entity_count.return_value = 5
        store.get_all_relationships.return_value = []
        entity_graph(max_nodes=999)
        # Should be clamped to 100
        store.get_all_relationships.assert_called_once_with(limit=100 * 5)


class TestEntityHTTPEndpoints:
    """Test HTTP endpoints for entity search and graph."""

    def setup_method(self):
        from fastapi.testclient import TestClient
        from src.http_server import app
        self.client = TestClient(app)

    @patch("src.core.entity_search", return_value="Found 2 entities")
    def test_entity_search_endpoint(self, mock_es):
        resp = self.client.get("/entity-search?query=postgres")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        mock_es.assert_called_once_with("postgres", 10)

    @patch("src.core.entity_search", return_value="Found 1 entity")
    def test_entity_search_with_limit(self, mock_es):
        resp = self.client.get("/entity-search?query=test&limit=5")
        assert resp.status_code == 200
        mock_es.assert_called_once_with("test", 5)

    @patch("src.core.entity_graph", return_value="Entity Graph: 3 entities")
    def test_entity_graph_endpoint(self, mock_eg):
        resp = self.client.post("/entity-graph", json={})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        mock_eg.assert_called_once_with(None, 30)

    @patch("src.core.entity_graph", return_value="Entity Graph: filtered")
    def test_entity_graph_with_query(self, mock_eg):
        resp = self.client.post("/entity-graph", json={"query": "postgres", "max_nodes": 20})
        assert resp.status_code == 200
        mock_eg.assert_called_once_with("postgres", 20)
