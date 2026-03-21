"""Search primitives: query, highlight, and multi-angle search."""

from __future__ import annotations

from src.primitives.registry import PrimitiveRegistry


def register_search_primitives(reg: PrimitiveRegistry) -> None:
    from src.search import search, highlight_matches
    from src.multi_angle import build_search_angles, merge_results
    from src.time_parser import parse_time_expression
    from src.knowledge_graph import build_knowledge_graph

    reg.register(
        "search",
        search,
        category="search",
        description="Hybrid vector + FTS search across indexed documents.",
    )
    reg.register(
        "highlight_matches",
        highlight_matches,
        category="search",
        description="Highlight query matches in text with context.",
    )
    reg.register(
        "build_search_angles",
        build_search_angles,
        category="search",
        description="Generate alternative query angles for multi-perspective search.",
    )
    reg.register(
        "merge_results",
        merge_results,
        category="search",
        description="Merge and deduplicate results from multiple searches.",
    )
    reg.register(
        "parse_time_expression",
        parse_time_expression,
        category="search",
        description="Parse natural language time expressions into date ranges.",
    )
    reg.register(
        "build_knowledge_graph",
        build_knowledge_graph,
        category="search",
        description="Build a Mermaid knowledge graph from memories and documents.",
    )
