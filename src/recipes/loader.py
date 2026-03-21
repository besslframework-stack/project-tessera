"""Recipe loader: parse YAML files into Recipe objects."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from src.recipes.models import Recipe, Step

logger = logging.getLogger(__name__)


def load_recipe(path: str | Path) -> Recipe:
    """Load a recipe from a YAML file.

    Args:
        path: Path to the YAML recipe file.

    Returns:
        Parsed Recipe object.

    Raises:
        FileNotFoundError: If file does not exist.
        ValueError: If YAML structure is invalid.
    """
    import yaml

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Recipe not found: {path}")

    with open(path) as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Recipe must be a YAML mapping, got {type(data).__name__}")

    return parse_recipe(data, source=str(path))


def parse_recipe(data: dict[str, Any], source: str = "<inline>") -> Recipe:
    """Parse a recipe dict into a Recipe object.

    Args:
        data: Recipe data (typically from YAML).
        source: Source identifier for error messages.

    Returns:
        Parsed Recipe object.
    """
    name = data.get("name")
    if not name:
        raise ValueError(f"Recipe from {source} must have a 'name' field")

    steps_data = data.get("steps", [])
    if not isinstance(steps_data, list):
        raise ValueError(f"Recipe {name}: 'steps' must be a list")

    steps = []
    seen_ids: set[str] = set()
    for i, step_data in enumerate(steps_data):
        if not isinstance(step_data, dict):
            raise ValueError(f"Recipe {name}, step {i}: must be a mapping")

        step_id = step_data.get("id")
        if not step_id:
            raise ValueError(f"Recipe {name}, step {i}: must have an 'id'")
        if step_id in seen_ids:
            raise ValueError(f"Recipe {name}: duplicate step id '{step_id}'")
        seen_ids.add(step_id)

        primitive = step_data.get("primitive")
        if not primitive:
            raise ValueError(f"Recipe {name}, step '{step_id}': must have a 'primitive'")

        steps.append(Step(
            id=step_id,
            primitive=primitive,
            params=step_data.get("params", {}),
            when=step_data.get("when"),
        ))

    return Recipe(
        name=name,
        description=data.get("description", ""),
        version=data.get("version", 1),
        steps=steps,
        output=data.get("output", ""),
    )


def discover_recipes(directory: str | Path | None = None) -> list[Path]:
    """Find all .yaml recipe files in a directory.

    Args:
        directory: Directory to scan. Defaults to project recipes/ dir.

    Returns:
        List of recipe file paths.
    """
    if directory is None:
        directory = Path(__file__).parent.parent.parent / "recipes"

    directory = Path(directory)
    if not directory.is_dir():
        return []

    return sorted(directory.glob("*.yaml"))
