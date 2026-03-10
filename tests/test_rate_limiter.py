"""Tests for rate limiter (v0.8.5)."""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from src.rate_limiter import RateLimiter, create_rate_limiter


class TestRateLimiter:
    def test_allows_under_limit(self):
        rl = RateLimiter(max_requests=5, window_seconds=60)
        for _ in range(5):
            assert rl.is_allowed() is True

    def test_blocks_over_limit(self):
        rl = RateLimiter(max_requests=3, window_seconds=60)
        for _ in range(3):
            rl.is_allowed()
        assert rl.is_allowed() is False

    def test_different_clients(self):
        rl = RateLimiter(max_requests=2, window_seconds=60)
        assert rl.is_allowed("client_a") is True
        assert rl.is_allowed("client_a") is True
        assert rl.is_allowed("client_a") is False
        # Different client should still be allowed
        assert rl.is_allowed("client_b") is True

    def test_remaining(self):
        rl = RateLimiter(max_requests=5, window_seconds=60)
        assert rl.remaining() == 5
        rl.is_allowed()
        assert rl.remaining() == 4

    def test_disabled(self):
        rl = RateLimiter(max_requests=0)
        for _ in range(100):
            assert rl.is_allowed() is True

    def test_window_expiry(self):
        rl = RateLimiter(max_requests=2, window_seconds=1)
        assert rl.is_allowed() is True
        assert rl.is_allowed() is True
        assert rl.is_allowed() is False
        time.sleep(1.1)
        assert rl.is_allowed() is True

    def test_reset_time(self):
        rl = RateLimiter(max_requests=5, window_seconds=60)
        assert rl.reset_time() == 0  # No requests yet
        rl.is_allowed()
        assert rl.reset_time() > 0


class TestCreateRateLimiter:
    def test_default(self):
        rl = create_rate_limiter()
        assert rl.max_requests == 60

    def test_from_env(self):
        import os
        with patch.dict(os.environ, {"TESSERA_RATE_LIMIT": "100"}):
            rl = create_rate_limiter()
            assert rl.max_requests == 100

    def test_disabled_from_env(self):
        import os
        with patch.dict(os.environ, {"TESSERA_RATE_LIMIT": "0"}):
            rl = create_rate_limiter()
            assert rl._enabled is False

    def test_invalid_env(self):
        import os
        with patch.dict(os.environ, {"TESSERA_RATE_LIMIT": "abc"}):
            rl = create_rate_limiter()
            assert rl.max_requests == 60  # Falls back to default
