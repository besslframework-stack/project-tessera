"""Tests for plugin hooks system."""

import pytest

from src.hooks import (
    EVENTS,
    register_hook,
    unregister_hook,
    fire_event,
    list_hooks,
    clear_hooks,
)


@pytest.fixture(autouse=True)
def clean_hooks():
    """Clear all hooks before each test."""
    clear_hooks()
    yield
    clear_hooks()


class TestRegisterHook:
    def test_register_callable(self):
        def my_hook(**ctx):
            return "ok"
        assert register_hook("on_memory_created", my_hook) is True

    def test_register_script(self):
        assert register_hook("on_search", "/path/to/script.sh") is True

    def test_invalid_event(self):
        assert register_hook("invalid_event", lambda: None) is False

    def test_custom_name(self):
        register_hook("on_memory_created", lambda **ctx: None, name="my-hook")
        hooks = list_hooks()
        assert "my-hook" in hooks["on_memory_created"]

    def test_all_events_valid(self):
        for event in EVENTS:
            assert register_hook(event, lambda **ctx: None) is True


class TestUnregisterHook:
    def test_unregister_existing(self):
        register_hook("on_search", lambda **ctx: None, name="test-hook")
        assert unregister_hook("on_search", "test-hook") is True
        assert list_hooks() == {}

    def test_unregister_nonexistent(self):
        assert unregister_hook("on_search", "nope") is False

    def test_invalid_event(self):
        assert unregister_hook("invalid", "hook") is False


class TestFireEvent:
    def test_fire_callable(self):
        results_captured = []

        def handler(**ctx):
            results_captured.append(ctx)
            return "handled"

        register_hook("on_memory_created", handler, name="test")
        results = fire_event("on_memory_created", content="hello", tags="test")

        assert len(results) == 1
        assert results[0]["status"] == "ok"
        assert results[0]["result"] == "handled"
        assert results_captured[0]["content"] == "hello"

    def test_fire_multiple_hooks(self):
        register_hook("on_search", lambda **ctx: "a", name="hook-a")
        register_hook("on_search", lambda **ctx: "b", name="hook-b")

        results = fire_event("on_search", query="test")
        assert len(results) == 2

    def test_fire_no_hooks(self):
        results = fire_event("on_search", query="test")
        assert results == []

    def test_fire_invalid_event(self):
        results = fire_event("invalid_event")
        assert results == []

    def test_hook_error_captured(self):
        def bad_hook(**ctx):
            raise ValueError("boom")

        register_hook("on_search", bad_hook, name="bad")
        results = fire_event("on_search", query="test")

        assert len(results) == 1
        assert results[0]["status"] == "error"
        assert "boom" in results[0]["error"]

    def test_error_doesnt_block_other_hooks(self):
        def bad(**ctx):
            raise RuntimeError("fail")

        def good(**ctx):
            return "ok"

        register_hook("on_search", bad, name="bad")
        register_hook("on_search", good, name="good")

        results = fire_event("on_search")
        assert len(results) == 2
        assert results[0]["status"] == "error"
        assert results[1]["status"] == "ok"


class TestListHooks:
    def test_empty(self):
        assert list_hooks() == {}

    def test_lists_registered(self):
        register_hook("on_search", lambda **ctx: None, name="a")
        register_hook("on_memory_created", lambda **ctx: None, name="b")

        hooks = list_hooks()
        assert "on_search" in hooks
        assert "on_memory_created" in hooks
        assert "a" in hooks["on_search"]
        assert "b" in hooks["on_memory_created"]

    def test_excludes_empty_events(self):
        register_hook("on_search", lambda **ctx: None, name="a")
        hooks = list_hooks()
        assert "on_memory_deleted" not in hooks


class TestClearHooks:
    def test_clear_specific_event(self):
        register_hook("on_search", lambda **ctx: None, name="a")
        register_hook("on_memory_created", lambda **ctx: None, name="b")

        cleared = clear_hooks("on_search")
        assert cleared == 1
        hooks = list_hooks()
        assert "on_search" not in hooks
        assert "on_memory_created" in hooks

    def test_clear_all(self):
        register_hook("on_search", lambda **ctx: None, name="a")
        register_hook("on_memory_created", lambda **ctx: None, name="b")

        cleared = clear_hooks()
        assert cleared == 2
        assert list_hooks() == {}

    def test_clear_empty(self):
        assert clear_hooks() == 0
