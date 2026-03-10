"""Tests for batch API (v0.8.4)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.http_server import app

client = TestClient(app)


class TestBatchAPI:
    @patch("src.core.search_documents", return_value="results")
    @patch("src.core.remember", return_value="saved")
    def test_multiple_operations(self, mock_remember, mock_search):
        resp = client.post("/batch", json={
            "operations": [
                {"method": "search", "params": {"query": "test"}},
                {"method": "remember", "params": {"content": "fact"}},
            ]
        })
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 2
        assert data[0]["method"] == "search"
        assert data[0]["status"] == "ok"
        assert data[1]["method"] == "remember"
        assert data[1]["status"] == "ok"

    def test_unknown_method(self):
        resp = client.post("/batch", json={
            "operations": [
                {"method": "nonexistent", "params": {}},
            ]
        })
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data[0]["status"] == "error"
        assert "Unknown method" in data[0]["data"]

    @patch("src.core.search_documents", side_effect=Exception("DB error"))
    def test_error_handling(self, mock_search):
        resp = client.post("/batch", json={
            "operations": [
                {"method": "search", "params": {"query": "test"}},
            ]
        })
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data[0]["status"] == "error"
        assert "DB error" in data[0]["data"]

    def test_empty_batch(self):
        resp = client.post("/batch", json={"operations": []})
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    @patch("src.core.recall", return_value="memories")
    def test_recall_with_filters(self, mock_recall):
        resp = client.post("/batch", json={
            "operations": [
                {"method": "recall", "params": {"query": "db", "since": "2026-03-01"}},
            ]
        })
        assert resp.status_code == 200
        mock_recall.assert_called_once_with("db", 5, since="2026-03-01", until=None, category=None)

    @patch("src.core.knowledge_stats", return_value="stats")
    def test_no_params_operation(self, mock_ks):
        resp = client.post("/batch", json={
            "operations": [
                {"method": "knowledge_stats"},
            ]
        })
        assert resp.status_code == 200
        assert resp.json()["data"][0]["status"] == "ok"

    @patch("src.core.search_documents", return_value="r")
    def test_max_20_operations(self, mock_search):
        resp = client.post("/batch", json={
            "operations": [
                {"method": "search", "params": {"query": "test"}}
                for _ in range(25)
            ]
        })
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 20  # Capped at 20
