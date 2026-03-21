"""Memory primitives: CRUD operations on the Tessera memory store."""

from __future__ import annotations

from src.primitives.registry import PrimitiveRegistry


def register_memory_primitives(reg: PrimitiveRegistry) -> None:
    from src.memory import (
        save_memory,
        recall_memories,
        index_memory,
        supersede_memory,
        search_memories_by_tag,
        search_memories_by_category,
        list_memory_tags,
        list_memory_categories,
    )

    reg.register(
        "save_memory",
        save_memory,
        category="memory",
        description="Save content as a memory with optional tags, category, and source.",
    )
    reg.register(
        "recall_memories",
        recall_memories,
        category="memory",
        description="Recall memories matching a query with optional time and category filters.",
    )
    reg.register(
        "index_memory",
        index_memory,
        category="memory",
        description="Index a memory file into the vector store.",
    )
    reg.register(
        "supersede_memory",
        supersede_memory,
        category="memory",
        description="Mark a memory as superseded (outdated).",
    )
    reg.register(
        "search_memories_by_tag",
        search_memories_by_tag,
        category="memory",
        description="Find memories that have a specific tag.",
    )
    reg.register(
        "search_memories_by_category",
        search_memories_by_category,
        category="memory",
        description="Find memories in a specific category.",
    )
    reg.register(
        "list_memory_tags",
        list_memory_tags,
        category="memory",
        description="List all tags with their counts.",
    )
    reg.register(
        "list_memory_categories",
        list_memory_categories,
        category="memory",
        description="List all categories with their counts.",
    )
