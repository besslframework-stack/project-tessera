"""Tests for API authentication (v0.8.2)."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from src.api_auth import (
    generate_api_key,
    hash_key,
    init_auth,
    is_auth_required,
    validate_key,
)


class TestGenerateApiKey:
    def test_format(self):
        key = generate_api_key()
        assert key.startswith("tsr_")
        assert len(key) > 20

    def test_unique(self):
        keys = {generate_api_key() for _ in range(10)}
        assert len(keys) == 10


class TestHashKey:
    def test_deterministic(self):
        key = "test-key-123"
        assert hash_key(key) == hash_key(key)

    def test_different_keys(self):
        assert hash_key("key1") != hash_key("key2")

    def test_short_output(self):
        assert len(hash_key("test")) == 16


class TestInitAuth:
    def test_env_key(self):
        import src.api_auth as auth_mod
        # Reset state
        auth_mod._REQUIRE_AUTH = False
        auth_mod._API_KEYS = set()

        with patch.dict(os.environ, {"TESSERA_API_KEY": "test-key-xyz"}):
            init_auth()
            assert is_auth_required() is True
            assert validate_key("test-key-xyz") is True
            assert validate_key("wrong-key") is False

        # Cleanup
        auth_mod._REQUIRE_AUTH = False
        auth_mod._API_KEYS = set()

    def test_no_env_key(self):
        import src.api_auth as auth_mod
        auth_mod._REQUIRE_AUTH = False
        auth_mod._API_KEYS = set()

        with patch.dict(os.environ, {}, clear=True):
            # Remove TESSERA_API_KEY if present
            os.environ.pop("TESSERA_API_KEY", None)
            init_auth()
            assert is_auth_required() is False
            assert validate_key("anything") is True  # No auth, always valid

        auth_mod._REQUIRE_AUTH = False
        auth_mod._API_KEYS = set()


class TestValidateKey:
    def test_no_auth_required(self):
        import src.api_auth as auth_mod
        auth_mod._REQUIRE_AUTH = False
        assert validate_key("") is True
        assert validate_key("anything") is True

    def test_auth_required_valid(self):
        import src.api_auth as auth_mod
        auth_mod._REQUIRE_AUTH = True
        auth_mod._API_KEYS = {"valid-key"}
        assert validate_key("valid-key") is True
        # Cleanup
        auth_mod._REQUIRE_AUTH = False
        auth_mod._API_KEYS = set()

    def test_auth_required_invalid(self):
        import src.api_auth as auth_mod
        auth_mod._REQUIRE_AUTH = True
        auth_mod._API_KEYS = {"valid-key"}
        assert validate_key("invalid") is False
        assert validate_key("") is False
        # Cleanup
        auth_mod._REQUIRE_AUTH = False
        auth_mod._API_KEYS = set()


class TestHttpAuth:
    """Test auth integration with HTTP endpoints."""

    def test_health_no_auth(self):
        from fastapi.testclient import TestClient
        from src.http_server import app
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_protected_endpoint_with_auth(self):
        import src.api_auth as auth_mod
        auth_mod._REQUIRE_AUTH = True
        auth_mod._API_KEYS = {"test-api-key"}

        from fastapi.testclient import TestClient
        from src.http_server import app
        client = TestClient(app)

        # Without key — should fail
        with patch("src.core.knowledge_stats", return_value="stats"):
            resp = client.get("/knowledge-stats")
            assert resp.status_code == 401

        # With correct key — should pass
        with patch("src.core.knowledge_stats", return_value="stats"):
            resp = client.get("/knowledge-stats", headers={"X-API-Key": "test-api-key"})
            assert resp.status_code == 200

        # Cleanup
        auth_mod._REQUIRE_AUTH = False
        auth_mod._API_KEYS = set()
