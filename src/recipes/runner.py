"""RecipeRunner: execute recipes step-by-step using the primitive registry."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from src.primitives.registry import PrimitiveRegistry, get_registry
from src.recipes.context import RecipeContext
from src.recipes.models import Recipe, Step

logger = logging.getLogger(__name__)


@dataclass
class StepResult:
    """Result of a single step execution."""

    step_id: str
    primitive: str
    status: str  # "ok", "skipped", "error"
    result: Any = None
    error: str | None = None
    duration_ms: float = 0.0


@dataclass
class RecipeResult:
    """Result of a full recipe execution."""

    recipe_name: str
    status: str  # "ok", "error"
    output: Any = None
    steps: list[StepResult] = field(default_factory=list)
    total_duration_ms: float = 0.0
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == "ok"


class RecipeRunner:
    """Execute recipes by resolving templates and invoking primitives.

    Usage::

        runner = RecipeRunner()
        result = runner.run(recipe, input={"text": "hello"})
    """

    def __init__(self, registry: PrimitiveRegistry | None = None) -> None:
        self._registry = registry or get_registry()

    def run(self, recipe: Recipe, **inputs: Any) -> RecipeResult:
        """Execute a recipe with the given inputs.

        Each step's result is stored in the context under its step id,
        accessible by subsequent steps as ``{{ step_id.result }}``.

        Args:
            recipe: Recipe to execute.
            **inputs: Input values accessible as ``{{ input.key }}``.

        Returns:
            RecipeResult with all step outcomes and the final output.
        """
        ctx = RecipeContext({"input": inputs, "config": {}})
        step_results: list[StepResult] = []
        start = time.monotonic()

        for step in recipe.steps:
            sr = self._run_step(step, ctx)
            step_results.append(sr)

            if sr.status == "error":
                elapsed = (time.monotonic() - start) * 1000
                return RecipeResult(
                    recipe_name=recipe.name,
                    status="error",
                    steps=step_results,
                    total_duration_ms=elapsed,
                    error=f"Step '{step.id}' failed: {sr.error}",
                )

        # Resolve output template
        output = ctx.resolve(recipe.output) if recipe.output else None

        elapsed = (time.monotonic() - start) * 1000
        return RecipeResult(
            recipe_name=recipe.name,
            status="ok",
            output=output,
            steps=step_results,
            total_duration_ms=elapsed,
        )

    def _run_step(self, step: Step, ctx: RecipeContext) -> StepResult:
        """Execute a single step."""
        # Evaluate when-condition
        if not ctx.evaluate_condition(step.when):
            logger.debug("Step %s skipped (condition false)", step.id)
            ctx.set(step.id, {"result": None, "status": "skipped"})
            return StepResult(
                step_id=step.id,
                primitive=step.primitive,
                status="skipped",
            )

        # Resolve params
        resolved_params = ctx.resolve(step.params)
        if not isinstance(resolved_params, dict):
            resolved_params = {}

        # Invoke primitive
        t0 = time.monotonic()
        try:
            result = self._registry.call(step.primitive, **resolved_params)
        except Exception as exc:
            duration = (time.monotonic() - t0) * 1000
            logger.warning("Step %s (%s) failed: %s", step.id, step.primitive, exc)
            ctx.set(step.id, {"result": None, "status": "error", "error": str(exc)})
            return StepResult(
                step_id=step.id,
                primitive=step.primitive,
                status="error",
                error=str(exc),
                duration_ms=duration,
            )

        duration = (time.monotonic() - t0) * 1000
        ctx.set(step.id, {"result": result, "status": "ok"})
        logger.debug("Step %s completed in %.1fms", step.id, duration)

        return StepResult(
            step_id=step.id,
            primitive=step.primitive,
            status="ok",
            result=result,
            duration_ms=duration,
        )

    def validate(self, recipe: Recipe) -> list[str]:
        """Validate a recipe without executing it.

        Returns:
            List of validation errors (empty if valid).
        """
        errors: list[str] = []

        if not recipe.name:
            errors.append("Recipe must have a name")

        if not recipe.steps:
            errors.append("Recipe must have at least one step")

        seen_ids: set[str] = set()
        for step in recipe.steps:
            if step.id in seen_ids:
                errors.append(f"Duplicate step id: {step.id}")
            seen_ids.add(step.id)

            if not self._registry.has(step.primitive):
                errors.append(f"Step '{step.id}': unknown primitive '{step.primitive}'")

        return errors
