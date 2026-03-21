"""Tests for the Primitive Registry."""

import pytest

from src.primitives.registry import PrimitiveRegistry, PrimitiveSpec


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _dummy_add(a: int, b: int = 0) -> int:
    return a + b


def _dummy_greet(name: str) -> str:
    return f"hello {name}"


@pytest.fixture
def registry():
    return PrimitiveRegistry()


# ------------------------------------------------------------------
# Registration
# ------------------------------------------------------------------

class TestRegistration:
    def test_register_and_get(self, registry):
        spec = registry.register("add", _dummy_add, category="math", description="Add two numbers")
        assert isinstance(spec, PrimitiveSpec)
        assert spec.name == "add"
        assert spec.category == "math"
        assert spec.fn is _dummy_add

        retrieved = registry.get("add")
        assert retrieved is spec

    def test_register_duplicate_raises(self, registry):
        registry.register("add", _dummy_add)
        with pytest.raises(ValueError, match="already registered"):
            registry.register("add", _dummy_greet)

    def test_register_decorator(self, registry):
        @registry.register_decorator("greet", category="util", description="Greet someone")
        def greet(name: str) -> str:
            return f"hi {name}"

        spec = registry.get("greet")
        assert spec.fn is greet
        assert spec.category == "util"

    def test_register_decorator_auto_name(self, registry):
        @registry.register_decorator(category="util")
        def my_func():
            pass

        assert registry.has("my_func")


# ------------------------------------------------------------------
# Invocation
# ------------------------------------------------------------------

class TestInvocation:
    def test_call(self, registry):
        registry.register("add", _dummy_add)
        result = registry.call("add", a=3, b=5)
        assert result == 8

    def test_call_with_defaults(self, registry):
        registry.register("add", _dummy_add)
        result = registry.call("add", a=7)
        assert result == 7

    def test_call_unknown_raises(self, registry):
        with pytest.raises(KeyError, match="Unknown primitive"):
            registry.call("nonexistent")

    def test_spec_is_callable(self, registry):
        spec = registry.register("greet", _dummy_greet)
        assert spec("world") == "hello world"


# ------------------------------------------------------------------
# Lookup & introspection
# ------------------------------------------------------------------

class TestIntrospection:
    def test_has(self, registry):
        assert not registry.has("add")
        registry.register("add", _dummy_add)
        assert registry.has("add")

    def test_contains(self, registry):
        registry.register("add", _dummy_add)
        assert "add" in registry

    def test_len(self, registry):
        assert len(registry) == 0
        registry.register("add", _dummy_add)
        registry.register("greet", _dummy_greet)
        assert len(registry) == 2

    def test_list_all(self, registry):
        registry.register("add", _dummy_add, category="math")
        registry.register("greet", _dummy_greet, category="util")
        all_specs = registry.list_all()
        assert len(all_specs) == 2
        names = {s.name for s in all_specs}
        assert names == {"add", "greet"}

    def test_list_by_category(self, registry):
        registry.register("add", _dummy_add, category="math")
        registry.register("greet", _dummy_greet, category="util")
        math_prims = registry.list_by_category("math")
        assert len(math_prims) == 1
        assert math_prims[0].name == "add"

    def test_categories(self, registry):
        registry.register("add", _dummy_add, category="math")
        registry.register("greet", _dummy_greet, category="util")
        assert registry.categories == ["math", "util"]

    def test_get_unknown_raises(self, registry):
        with pytest.raises(KeyError, match="Unknown primitive"):
            registry.get("nope")

    def test_signature(self, registry):
        spec = registry.register("add", _dummy_add)
        sig = spec.signature
        params = list(sig.parameters.keys())
        assert "a" in params
        assert "b" in params

    def test_repr(self, registry):
        registry.register("add", _dummy_add)
        assert "1 primitives" in repr(registry)


# ------------------------------------------------------------------
# Global registry with real primitives
# ------------------------------------------------------------------

class TestGlobalRegistry:
    def test_get_registry_bootstraps(self):
        from src.primitives.registry import get_registry

        reg = get_registry()
        # Should have at least the core primitives
        assert reg.has("search")
        assert reg.has("save_memory")
        assert reg.has("recall_memories")
        assert reg.has("extract_facts")
        assert reg.has("detect_contradictions")
        assert reg.has("llm_classify")

    def test_categories_present(self):
        from src.primitives.registry import get_registry

        reg = get_registry()
        cats = reg.categories
        assert "memory" in cats
        assert "search" in cats
        assert "analysis" in cats
        assert "llm" in cats

    def test_memory_primitives_registered(self):
        from src.primitives.registry import get_registry

        reg = get_registry()
        memory_prims = reg.list_by_category("memory")
        names = {p.name for p in memory_prims}
        assert "save_memory" in names
        assert "recall_memories" in names
        assert "index_memory" in names
        assert "supersede_memory" in names
        assert "list_memory_tags" in names
        assert "list_memory_categories" in names

    def test_search_primitives_registered(self):
        from src.primitives.registry import get_registry

        reg = get_registry()
        search_prims = reg.list_by_category("search")
        names = {p.name for p in search_prims}
        assert "search" in names
        assert "highlight_matches" in names
        assert "build_search_angles" in names
        assert "merge_results" in names
        assert "parse_time_expression" in names

    def test_llm_primitives_raise_not_implemented(self):
        from src.primitives.registry import get_registry

        reg = get_registry()
        with pytest.raises(NotImplementedError):
            reg.call("llm_classify", text="hello")
