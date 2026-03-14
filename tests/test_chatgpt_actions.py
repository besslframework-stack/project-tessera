"""Tests for ChatGPT Custom GPT Actions integration."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from src.chatgpt_actions import get_gpt_instructions, get_openapi_spec, get_setup_guide
from src.http_server import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Unit tests: spec generation
# ---------------------------------------------------------------------------

class TestOpenAPISpec:
    def test_spec_structure(self):
        spec = get_openapi_spec()
        assert spec["openapi"] == "3.1.0"
        assert spec["info"]["title"] == "Tessera — Personal Knowledge Layer"
        assert spec["info"]["version"] == "1.1.1"

    def test_spec_server_url_default(self):
        spec = get_openapi_spec()
        assert spec["servers"][0]["url"] == "http://localhost:8394"

    def test_spec_server_url_custom(self):
        spec = get_openapi_spec("https://abc.ngrok-free.app")
        assert spec["servers"][0]["url"] == "https://abc.ngrok-free.app"

    def test_spec_has_core_endpoints(self):
        spec = get_openapi_spec()
        paths = spec["paths"]
        assert "/search" in paths
        assert "/remember" in paths
        assert "/recall" in paths
        assert "/unified-search" in paths
        assert "/deep-search" in paths
        assert "/memories" in paths
        assert "/memories/{memory_id}" in paths
        assert "/knowledge-stats" in paths
        assert "/contradictions" in paths

    def test_spec_operation_ids(self):
        spec = get_openapi_spec()
        op_ids = set()
        for path, methods in spec["paths"].items():
            for method, detail in methods.items():
                op_ids.add(detail["operationId"])
        expected = {
            "searchDocuments", "rememberFact", "recallMemories",
            "unifiedSearch", "deepSearch", "listMemories",
            "forgetMemory", "getKnowledgeStats", "detectContradictions",
        }
        assert expected == op_ids

    def test_spec_is_valid_json(self):
        spec = get_openapi_spec()
        serialized = json.dumps(spec)
        parsed = json.loads(serialized)
        assert parsed["openapi"] == "3.1.0"

    def test_search_endpoint_has_required_query(self):
        spec = get_openapi_spec()
        schema = spec["paths"]["/search"]["post"]["requestBody"]["content"]["application/json"]["schema"]
        assert "query" in schema["required"]

    def test_remember_endpoint_tags_optional(self):
        spec = get_openapi_spec()
        schema = spec["paths"]["/remember"]["post"]["requestBody"]["content"]["application/json"]["schema"]
        assert "content" in schema["required"]
        assert "tags" not in schema.get("required", [])

    def test_recall_has_category_enum(self):
        spec = get_openapi_spec()
        schema = spec["paths"]["/recall"]["post"]["requestBody"]["content"]["application/json"]["schema"]
        cat_prop = schema["properties"]["category"]
        assert "enum" in cat_prop
        assert "decision" in cat_prop["enum"]


class TestGPTInstructions:
    def test_instructions_not_empty(self):
        instr = get_gpt_instructions()
        assert len(instr) > 100

    def test_instructions_mention_recall(self):
        instr = get_gpt_instructions()
        assert "recallMemories" in instr

    def test_instructions_mention_remember(self):
        instr = get_gpt_instructions()
        assert "rememberFact" in instr

    def test_instructions_no_tessera_exposure(self):
        instr = get_gpt_instructions()
        assert "Do NOT mention Tessera by name" in instr


class TestSetupGuide:
    def test_guide_default(self):
        guide = get_setup_guide()
        assert "ngrok" in guide
        assert "your-tunnel-url" in guide

    def test_guide_custom_url(self):
        guide = get_setup_guide("https://my-tunnel.example.com")
        assert "https://my-tunnel.example.com" in guide
        assert "your-tunnel-url" not in guide

    def test_guide_mentions_api_key(self):
        guide = get_setup_guide()
        assert "TESSERA_API_KEY" in guide


# ---------------------------------------------------------------------------
# Integration tests: HTTP endpoints
# ---------------------------------------------------------------------------

class TestHTTPEndpoints:
    def test_openapi_json_endpoint(self):
        resp = client.get("/chatgpt-actions/openapi.json")
        assert resp.status_code == 200
        data = resp.json()
        assert data["openapi"] == "3.1.0"
        assert "/search" in data["paths"]

    def test_openapi_json_custom_server(self):
        resp = client.get("/chatgpt-actions/openapi.json?server_url=https://test.ngrok.app")
        assert resp.status_code == 200
        data = resp.json()
        assert data["servers"][0]["url"] == "https://test.ngrok.app"

    def test_instructions_endpoint(self):
        resp = client.get("/chatgpt-actions/instructions")
        assert resp.status_code == 200
        data = resp.json()
        assert "instructions" in data
        assert "recallMemories" in data["instructions"]

    def test_setup_endpoint(self):
        resp = client.get("/chatgpt-actions/setup")
        assert resp.status_code == 200
        data = resp.json()
        assert "guide" in data
        assert "ngrok" in data["guide"]

    def test_setup_endpoint_with_tunnel(self):
        resp = client.get("/chatgpt-actions/setup?tunnel_url=https://abc.ngrok.app")
        assert resp.status_code == 200
        data = resp.json()
        assert "https://abc.ngrok.app" in data["guide"]

    def test_cors_header(self):
        resp = client.get("/chatgpt-actions/openapi.json")
        assert resp.headers.get("access-control-allow-origin") == "*"
