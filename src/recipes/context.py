"""RecipeContext: variable resolution and template rendering for recipes.

Supports a minimal Jinja-like template syntax:
  {{ input.text }}          — dot access into context variables
  {{ step_id.result }}      — access prior step results
  {{ expr | count }}        — pipe filter: count (len)
  {{ expr | first }}        — pipe filter: first element
  {{ expr | format }}       — pipe filter: str()
  {{ val in ['a', 'b'] }}   — membership test
"""

from __future__ import annotations

import ast
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_TEMPLATE_RE = re.compile(r"\{\{\s*(.+?)\s*\}\}")


class RecipeContext:
    """Holds runtime state for a recipe execution."""

    def __init__(self, initial: dict[str, Any] | None = None) -> None:
        self._data: dict[str, Any] = {}
        if initial:
            self._data.update(initial)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    # ------------------------------------------------------------------
    # Template resolution
    # ------------------------------------------------------------------

    def resolve(self, value: Any) -> Any:
        """Resolve template expressions in *value*.

        - str containing {{ ... }}: rendered
        - list/dict: recursively resolved
        - other types: returned as-is
        """
        if isinstance(value, str):
            return self._resolve_string(value)
        if isinstance(value, list):
            return [self.resolve(v) for v in value]
        if isinstance(value, dict):
            return {k: self.resolve(v) for k, v in value.items()}
        return value

    def _resolve_string(self, s: str) -> Any:
        # If the entire string is a single {{ expr }}, return the raw value
        match = _TEMPLATE_RE.fullmatch(s.strip())
        if match:
            return self._eval_expr(match.group(1))

        # Otherwise, interpolate all {{ }} blocks as strings
        def replacer(m: re.Match) -> str:
            return str(self._eval_expr(m.group(1)))

        return _TEMPLATE_RE.sub(replacer, s)

    def _eval_expr(self, expr: str) -> Any:
        expr = expr.strip()

        # Handle pipe filters: expr | filter_name
        if "|" in expr:
            parts = expr.rsplit("|", 1)
            inner = self._eval_expr(parts[0])
            filt = parts[1].strip()
            return self._apply_filter(inner, filt)

        # Handle 'in' membership: val in ['a', 'b']
        in_match = re.match(r"^(.+?)\s+in\s+(\[.+\])$", expr)
        if in_match:
            val = self._eval_expr(in_match.group(1))
            try:
                container = ast.literal_eval(in_match.group(2))
            except (ValueError, SyntaxError):
                container = []
            return val in container

        # Handle comparison operators: val > 0, val == 'x'
        for op_str, op_fn in [
            (">=", lambda a, b: a >= b),
            ("<=", lambda a, b: a <= b),
            ("!=", lambda a, b: a != b),
            ("==", lambda a, b: a == b),
            (">", lambda a, b: a > b),
            ("<", lambda a, b: a < b),
        ]:
            if op_str in expr:
                left, right = expr.split(op_str, 1)
                left_val = self._eval_expr(left)
                right_val = self._eval_expr(right)
                return op_fn(left_val, right_val)

        # Dot access: input.text, step_id.result.field
        return self._dot_access(expr)

    def _dot_access(self, expr: str) -> Any:
        parts = expr.split(".")
        # Try as literal first
        try:
            return ast.literal_eval(expr)
        except (ValueError, SyntaxError):
            pass

        current: Any = self._data
        for part in parts:
            if isinstance(current, dict):
                if part not in current:
                    logger.debug("Key %r not found in context at %r", part, expr)
                    return None
                current = current[part]
            elif hasattr(current, part):
                current = getattr(current, part)
            else:
                logger.debug("Cannot access %r on %r in expr %r", part, type(current).__name__, expr)
                return None
        return current

    def _apply_filter(self, value: Any, filt: str) -> Any:
        if filt == "count":
            return len(value) if value else 0
        if filt == "first":
            if isinstance(value, (list, tuple)) and value:
                return value[0]
            return None
        if filt == "format":
            return str(value)
        if filt == "keys":
            return list(value.keys()) if isinstance(value, dict) else []
        if filt == "values":
            return list(value.values()) if isinstance(value, dict) else []
        logger.warning("Unknown filter: %s", filt)
        return value

    # ------------------------------------------------------------------
    # Condition evaluation
    # ------------------------------------------------------------------

    def evaluate_condition(self, condition: str | None) -> bool:
        """Evaluate a when-condition. Returns True if condition is None."""
        if condition is None:
            return True
        result = self.resolve(condition)
        return bool(result)
