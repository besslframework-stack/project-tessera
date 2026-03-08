"""Tests for search result caching."""

from __future__ import annotations

import time

from src.search import (
    _cache_key,
    _get_cached,
    _put_cache,
    _search_cache,
    invalidate_search_cache,
)


class TestCacheKey:
    def test_basic(self):
        key = _cache_key("hello", 5, None, None)
        assert "hello" in key
        assert "5" in key

    def test_different_params(self):
        k1 = _cache_key("hello", 5, None, None)
        k2 = _cache_key("hello", 10, None, None)
        k3 = _cache_key("hello", 5, "proj", None)
        assert k1 != k2
        assert k1 != k3

    def test_same_params(self):
        k1 = _cache_key("test", 5, "proj", "prd")
        k2 = _cache_key("test", 5, "proj", "prd")
        assert k1 == k2


class TestCacheOperations:
    def setup_method(self):
        invalidate_search_cache()

    def test_miss(self):
        assert _get_cached("nonexistent") is None

    def test_put_and_get(self):
        results = [{"text": "hello", "similarity": 0.9}]
        _put_cache("key1", results)
        cached = _get_cached("key1")
        assert cached is not None
        assert cached[0]["text"] == "hello"

    def test_invalidate(self):
        _put_cache("key1", [{"text": "a"}])
        _put_cache("key2", [{"text": "b"}])
        invalidate_search_cache()
        assert _get_cached("key1") is None
        assert _get_cached("key2") is None

    def test_eviction_when_full(self):
        # Fill cache beyond max
        for i in range(70):
            _put_cache(f"key_{i}", [{"text": f"val_{i}"}])
        # Cache should not exceed 64
        assert len(_search_cache) <= 64


class TestEmbedQueryCache:
    def test_lru_cache_exists(self):
        from src.embedding import embed_query
        # embed_query should have cache_info (from @lru_cache)
        assert hasattr(embed_query, "cache_info")
