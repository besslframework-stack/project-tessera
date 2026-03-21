"""Recipe and Step data models."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Step:
    """A single step in a recipe."""

    id: str
    primitive: str
    params: dict[str, str] = field(default_factory=dict)
    when: str | None = None  # Jinja-like condition; None = always run

    def __repr__(self) -> str:
        return f"Step({self.id!r}, primitive={self.primitive!r})"


@dataclass
class Recipe:
    """A composable workflow of steps that invoke primitives."""

    name: str
    description: str = ""
    version: int = 1
    steps: list[Step] = field(default_factory=list)
    output: str = ""  # template expression for final output

    def __repr__(self) -> str:
        return f"Recipe({self.name!r}, {len(self.steps)} steps)"
