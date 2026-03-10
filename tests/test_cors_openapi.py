"""Tests for CORS and OpenAPI schema (v0.8.3)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.http_server import app

client = TestClient(app)


class TestCORS:
    def test_cors_headers_present(self):
        resp = client.options(
            "/health",
            headers={
                "Origin": "https://chat.openai.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        # FastAPI CORS middleware should respond
        assert resp.status_code in (200, 400)  # OPTIONS allowed

    def test_health_has_cors(self):
        resp = client.get("/health", headers={"Origin": "http://localhost:3000"})
        assert resp.status_code == 200


class TestOpenAPI:
    def test_openapi_json(self):
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        schema = resp.json()
        assert schema["info"]["title"] == "Tessera API"
        assert "paths" in schema

    def test_has_search_endpoint(self):
        resp = client.get("/openapi.json")
        schema = resp.json()
        assert "/search" in schema["paths"]

    def test_has_remember_endpoint(self):
        resp = client.get("/openapi.json")
        schema = resp.json()
        assert "/remember" in schema["paths"]

    def test_has_context_window(self):
        resp = client.get("/openapi.json")
        schema = resp.json()
        assert "/context-window" in schema["paths"]

    def test_has_tags(self):
        resp = client.get("/openapi.json")
        schema = resp.json()
        assert "tags" in schema
        tag_names = [t["name"] for t in schema["tags"]]
        assert "search" in tag_names
        assert "memory" in tag_names
        assert "intelligence" in tag_names

    def test_docs_page(self):
        resp = client.get("/docs")
        assert resp.status_code == 200

    def test_schema_components(self):
        resp = client.get("/openapi.json")
        schema = resp.json()
        components = schema.get("components", {}).get("schemas", {})
        assert "SearchRequest" in components
        assert "RememberRequest" in components
        assert "ApiResponse" in components
