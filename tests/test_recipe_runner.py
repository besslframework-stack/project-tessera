"""Tests for the Recipe system: models, context, loader, and runner."""

import pytest

from src.primitives.registry import PrimitiveRegistry
from src.recipes.context import RecipeContext
from src.recipes.loader import load_recipe, parse_recipe, discover_recipes
from src.recipes.models import Recipe, Step
from src.recipes.runner import RecipeRunner, RecipeResult, StepResult


# ==================================================================
# RecipeContext tests
# ==================================================================

class TestRecipeContext:
    def test_set_and_get(self):
        ctx = RecipeContext()
        ctx.set("foo", 42)
        assert ctx.get("foo") == 42

    def test_get_default(self):
        ctx = RecipeContext()
        assert ctx.get("missing", "default") == "default"

    def test_initial_data(self):
        ctx = RecipeContext({"x": 1})
        assert ctx.get("x") == 1

    def test_resolve_plain_string(self):
        ctx = RecipeContext()
        assert ctx.resolve("hello") == "hello"

    def test_resolve_template(self):
        ctx = RecipeContext({"input": {"text": "world"}})
        result = ctx.resolve("{{ input.text }}")
        assert result == "world"

    def test_resolve_interpolation(self):
        ctx = RecipeContext({"input": {"name": "Tessera"}})
        result = ctx.resolve("Hello {{ input.name }}!")
        assert result == "Hello Tessera!"

    def test_resolve_nested_dot(self):
        ctx = RecipeContext({"step1": {"result": {"category": "decision"}}})
        result = ctx.resolve("{{ step1.result.category }}")
        assert result == "decision"

    def test_resolve_filter_count(self):
        ctx = RecipeContext({"items": [1, 2, 3]})
        result = ctx.resolve("{{ items | count }}")
        assert result == 3

    def test_resolve_filter_first(self):
        ctx = RecipeContext({"items": ["a", "b", "c"]})
        result = ctx.resolve("{{ items | first }}")
        assert result == "a"

    def test_resolve_filter_first_empty(self):
        ctx = RecipeContext({"items": []})
        result = ctx.resolve("{{ items | first }}")
        assert result is None

    def test_resolve_filter_format(self):
        ctx = RecipeContext({"val": 42})
        result = ctx.resolve("{{ val | format }}")
        assert result == "42"

    def test_resolve_in_operator(self):
        ctx = RecipeContext({"cat": "decision"})
        result = ctx.resolve("{{ cat in ['decision', 'preference'] }}")
        assert result is True

    def test_resolve_in_operator_false(self):
        ctx = RecipeContext({"cat": "fact"})
        result = ctx.resolve("{{ cat in ['decision', 'preference'] }}")
        assert result is False

    def test_resolve_comparison_gt(self):
        ctx = RecipeContext({"count": 5})
        result = ctx.resolve("{{ count > 0 }}")
        assert result is True

    def test_resolve_list(self):
        ctx = RecipeContext({"input": {"a": 1, "b": 2}})
        result = ctx.resolve(["{{ input.a }}", "{{ input.b }}"])
        assert result == [1, 2]

    def test_resolve_dict(self):
        ctx = RecipeContext({"input": {"key": "val"}})
        result = ctx.resolve({"x": "{{ input.key }}"})
        assert result == {"x": "val"}

    def test_resolve_non_string(self):
        ctx = RecipeContext()
        assert ctx.resolve(42) == 42
        assert ctx.resolve(None) is None

    def test_evaluate_condition_none(self):
        ctx = RecipeContext()
        assert ctx.evaluate_condition(None) is True

    def test_evaluate_condition_true(self):
        ctx = RecipeContext({"x": True})
        assert ctx.evaluate_condition("{{ x }}") is True

    def test_evaluate_condition_false(self):
        ctx = RecipeContext({"x": False})
        assert ctx.evaluate_condition("{{ x }}") is False

    def test_evaluate_condition_truthy(self):
        ctx = RecipeContext({"items": [1, 2]})
        assert ctx.evaluate_condition("{{ items | count > 0 }}") is True


# ==================================================================
# Recipe models tests
# ==================================================================

class TestModels:
    def test_step_creation(self):
        step = Step(id="s1", primitive="search", params={"query": "hello"})
        assert step.id == "s1"
        assert step.primitive == "search"
        assert step.when is None

    def test_step_repr(self):
        step = Step(id="s1", primitive="search")
        assert "s1" in repr(step)

    def test_recipe_creation(self):
        r = Recipe(
            name="test",
            steps=[Step(id="s1", primitive="search")],
        )
        assert r.name == "test"
        assert len(r.steps) == 1
        assert r.version == 1

    def test_recipe_repr(self):
        r = Recipe(name="test", steps=[Step(id="s1", primitive="search")])
        assert "test" in repr(r)
        assert "1 steps" in repr(r)


# ==================================================================
# Loader tests
# ==================================================================

class TestLoader:
    def test_parse_recipe_minimal(self):
        data = {
            "name": "test_recipe",
            "steps": [
                {"id": "s1", "primitive": "search", "params": {"query": "hello"}},
            ],
        }
        recipe = parse_recipe(data)
        assert recipe.name == "test_recipe"
        assert len(recipe.steps) == 1
        assert recipe.steps[0].primitive == "search"

    def test_parse_recipe_full(self):
        data = {
            "name": "full",
            "description": "A full recipe",
            "version": 2,
            "steps": [
                {"id": "s1", "primitive": "extract_facts", "params": {"text": "{{ input.text }}"}},
                {"id": "s2", "primitive": "save_memory", "params": {"content": "{{ input.text }}"}, "when": "{{ s1.result | count > 0 }}"},
            ],
            "output": "{{ s1.result }}",
        }
        recipe = parse_recipe(data)
        assert recipe.version == 2
        assert recipe.steps[1].when is not None
        assert recipe.output == "{{ s1.result }}"

    def test_parse_recipe_no_name_raises(self):
        with pytest.raises(ValueError, match="must have a 'name'"):
            parse_recipe({"steps": []})

    def test_parse_recipe_duplicate_id_raises(self):
        with pytest.raises(ValueError, match="duplicate step id"):
            parse_recipe({
                "name": "dup",
                "steps": [
                    {"id": "s1", "primitive": "search"},
                    {"id": "s1", "primitive": "save_memory"},
                ],
            })

    def test_parse_recipe_no_primitive_raises(self):
        with pytest.raises(ValueError, match="must have a 'primitive'"):
            parse_recipe({
                "name": "bad",
                "steps": [{"id": "s1"}],
            })

    def test_load_recipe_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_recipe("/nonexistent/recipe.yaml")

    def test_discover_recipes(self):
        from pathlib import Path
        recipes_dir = Path(__file__).parent.parent / "recipes"
        found = discover_recipes(recipes_dir)
        assert len(found) >= 1
        assert all(p.suffix == ".yaml" for p in found)

    def test_discover_recipes_nonexistent_dir(self):
        found = discover_recipes("/nonexistent/dir")
        assert found == []


# ==================================================================
# Runner tests
# ==================================================================

class TestRunner:
    @pytest.fixture
    def mock_registry(self):
        reg = PrimitiveRegistry()
        reg.register("echo", lambda text: text, category="util")
        reg.register("upper", lambda text: text.upper(), category="util")
        reg.register("count_chars", lambda text: len(text), category="util")
        reg.register("add", lambda a, b: a + b, category="math")
        reg.register("fail", lambda: (_ for _ in ()).throw(RuntimeError("boom")), category="util")
        return reg

    @pytest.fixture
    def runner(self, mock_registry):
        return RecipeRunner(registry=mock_registry)

    def test_simple_recipe(self, runner):
        recipe = Recipe(
            name="simple",
            steps=[
                Step(id="step1", primitive="echo", params={"text": "{{ input.text }}"}),
            ],
            output="{{ step1.result }}",
        )
        result = runner.run(recipe, text="hello")
        assert result.ok
        assert result.output == "hello"
        assert result.recipe_name == "simple"
        assert len(result.steps) == 1
        assert result.steps[0].status == "ok"

    def test_chained_steps(self, runner):
        recipe = Recipe(
            name="chained",
            steps=[
                Step(id="s1", primitive="echo", params={"text": "{{ input.text }}"}),
                Step(id="s2", primitive="upper", params={"text": "{{ s1.result }}"}),
            ],
            output="{{ s2.result }}",
        )
        result = runner.run(recipe, text="hello")
        assert result.ok
        assert result.output == "HELLO"

    def test_step_with_condition_true(self, runner):
        recipe = Recipe(
            name="cond",
            steps=[
                Step(id="s1", primitive="echo", params={"text": "{{ input.text }}"}),
                Step(
                    id="s2",
                    primitive="upper",
                    params={"text": "{{ s1.result }}"},
                    when="{{ input.do_upper }}",
                ),
            ],
            output="{{ s2.result }}",
        )
        result = runner.run(recipe, text="hello", do_upper=True)
        assert result.ok
        assert result.output == "HELLO"

    def test_step_with_condition_false(self, runner):
        recipe = Recipe(
            name="cond_skip",
            steps=[
                Step(id="s1", primitive="echo", params={"text": "{{ input.text }}"}),
                Step(
                    id="s2",
                    primitive="upper",
                    params={"text": "{{ s1.result }}"},
                    when="{{ input.do_upper }}",
                ),
            ],
            output="{{ s2.result }}",
        )
        result = runner.run(recipe, text="hello", do_upper=False)
        assert result.ok
        assert result.steps[1].status == "skipped"
        assert result.output is None  # s2 was skipped, result is None

    def test_step_failure(self, runner):
        recipe = Recipe(
            name="fail_recipe",
            steps=[
                Step(id="s1", primitive="fail"),
            ],
        )
        result = runner.run(recipe)
        assert not result.ok
        assert result.status == "error"
        assert "boom" in result.error
        assert result.steps[0].status == "error"

    def test_step_failure_stops_execution(self, runner):
        recipe = Recipe(
            name="fail_stops",
            steps=[
                Step(id="s1", primitive="fail"),
                Step(id="s2", primitive="echo", params={"text": "never"}),
            ],
        )
        result = runner.run(recipe)
        assert not result.ok
        assert len(result.steps) == 1  # s2 never ran

    def test_duration_tracked(self, runner):
        recipe = Recipe(
            name="timed",
            steps=[Step(id="s1", primitive="echo", params={"text": "x"})],
        )
        result = runner.run(recipe, text="x")
        assert result.total_duration_ms >= 0
        assert result.steps[0].duration_ms >= 0

    def test_no_output_template(self, runner):
        recipe = Recipe(
            name="no_out",
            steps=[Step(id="s1", primitive="echo", params={"text": "x"})],
        )
        result = runner.run(recipe, text="x")
        assert result.ok
        assert result.output is None

    def test_validate_valid(self, runner):
        recipe = Recipe(
            name="valid",
            steps=[Step(id="s1", primitive="echo")],
        )
        errors = runner.validate(recipe)
        assert errors == []

    def test_validate_unknown_primitive(self, runner):
        recipe = Recipe(
            name="bad",
            steps=[Step(id="s1", primitive="nonexistent")],
        )
        errors = runner.validate(recipe)
        assert any("nonexistent" in e for e in errors)

    def test_validate_no_steps(self, runner):
        recipe = Recipe(name="empty", steps=[])
        errors = runner.validate(recipe)
        assert any("at least one step" in e for e in errors)

    def test_validate_duplicate_ids(self, runner):
        recipe = Recipe(
            name="dup",
            steps=[
                Step(id="s1", primitive="echo"),
                Step(id="s1", primitive="upper"),
            ],
        )
        errors = runner.validate(recipe)
        assert any("Duplicate" in e for e in errors)


# ==================================================================
# Integration: loader + runner
# ==================================================================

class TestLoaderRunnerIntegration:
    def test_parse_and_run(self):
        """Parse a recipe from dict and run it with mock primitives."""
        reg = PrimitiveRegistry()
        reg.register("extract_facts", lambda text: [{"content": text, "category": "fact"}], category="analysis")
        reg.register("save_memory", lambda content, source="test", tags=None: f"saved:{content}", category="memory")

        data = {
            "name": "extract_save",
            "steps": [
                {"id": "extract", "primitive": "extract_facts", "params": {"text": "{{ input.text }}"}},
                {"id": "save", "primitive": "save_memory", "params": {"content": "{{ input.text }}", "source": "test"}},
            ],
            "output": "{{ save.result }}",
        }
        recipe = parse_recipe(data)
        runner = RecipeRunner(registry=reg)
        result = runner.run(recipe, text="We decided to use Python")

        assert result.ok
        assert result.output == "saved:We decided to use Python"
        assert len(result.steps) == 2
        assert all(s.status == "ok" for s in result.steps)
