"""Primitive registry: type-safe registration and lookup of atomic operations.

Each primitive is a plain Python callable wrapped in a PrimitiveSpec that
captures its name, category, parameter schema, and documentation.
Recipes compose primitives by name; the registry resolves names to callables.
"""

from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PrimitiveSpec:
    """Metadata wrapper around a primitive callable."""

    name: str
    fn: Callable[..., Any]
    category: str  # memory, search, analysis, llm, util
    description: str = ""
    params: dict[str, Any] = field(default_factory=dict)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self.fn(*args, **kwargs)

    @property
    def signature(self) -> inspect.Signature:
        return inspect.signature(self.fn)


class PrimitiveRegistry:
    """Central registry for all Tessera primitives.

    Usage::

        reg = PrimitiveRegistry()
        reg.register("search", search_fn, category="search", description="...")
        result = reg.call("search", query="hello")
    """

    def __init__(self) -> None:
        self._primitives: dict[str, PrimitiveSpec] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(
        self,
        name: str,
        fn: Callable[..., Any],
        *,
        category: str = "util",
        description: str = "",
        params: dict[str, Any] | None = None,
    ) -> PrimitiveSpec:
        """Register a callable as a named primitive.

        Raises ValueError if *name* is already registered.
        """
        if name in self._primitives:
            raise ValueError(f"Primitive already registered: {name}")

        spec = PrimitiveSpec(
            name=name,
            fn=fn,
            category=category,
            description=description,
            params=params or {},
        )
        self._primitives[name] = spec
        logger.debug("Primitive registered: %s [%s]", name, category)
        return spec

    def register_decorator(
        self,
        name: str | None = None,
        *,
        category: str = "util",
        description: str = "",
    ) -> Callable:
        """Decorator form of register.

        Usage::

            @registry.register_decorator("my_prim", category="search")
            def my_prim(query: str) -> list[dict]: ...
        """
        def decorator(fn: Callable) -> Callable:
            prim_name = name or fn.__name__
            self.register(prim_name, fn, category=category, description=description)
            return fn
        return decorator

    # ------------------------------------------------------------------
    # Lookup & invocation
    # ------------------------------------------------------------------

    def get(self, name: str) -> PrimitiveSpec:
        """Return the PrimitiveSpec for *name*, or raise KeyError."""
        if name not in self._primitives:
            raise KeyError(f"Unknown primitive: {name}. Available: {', '.join(sorted(self._primitives))}")
        return self._primitives[name]

    def call(self, name: str, **kwargs: Any) -> Any:
        """Invoke primitive *name* with the given keyword arguments."""
        spec = self.get(name)
        return spec.fn(**kwargs)

    def has(self, name: str) -> bool:
        return name in self._primitives

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def list_all(self) -> list[PrimitiveSpec]:
        return list(self._primitives.values())

    def list_by_category(self, category: str) -> list[PrimitiveSpec]:
        return [s for s in self._primitives.values() if s.category == category]

    @property
    def categories(self) -> list[str]:
        return sorted({s.category for s in self._primitives.values()})

    def __len__(self) -> int:
        return len(self._primitives)

    def __contains__(self, name: str) -> bool:
        return name in self._primitives

    def __repr__(self) -> str:
        return f"PrimitiveRegistry({len(self._primitives)} primitives)"


# ------------------------------------------------------------------
# Global singleton
# ------------------------------------------------------------------

_global_registry: PrimitiveRegistry | None = None


def get_registry() -> PrimitiveRegistry:
    """Return (and lazily create) the global primitive registry."""
    global _global_registry
    if _global_registry is None:
        _global_registry = PrimitiveRegistry()
        _bootstrap_all(_global_registry)
    return _global_registry


def _bootstrap_all(reg: PrimitiveRegistry) -> None:
    """Register all built-in primitives into *reg*."""
    from src.primitives.memory_primitives import register_memory_primitives
    from src.primitives.search_primitives import register_search_primitives
    from src.primitives.analysis_primitives import register_analysis_primitives
    from src.primitives.llm_primitives import register_llm_primitives

    register_memory_primitives(reg)
    register_search_primitives(reg)
    register_analysis_primitives(reg)
    register_llm_primitives(reg)
