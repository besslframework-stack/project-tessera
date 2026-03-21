"""Analysis primitives: fact extraction, contradiction detection, entity extraction."""

from __future__ import annotations

from src.primitives.registry import PrimitiveRegistry


def register_analysis_primitives(reg: PrimitiveRegistry) -> None:
    from src.auto_extract import extract_facts
    from src.contradiction import detect_contradictions, format_contradictions
    from src.entity_extraction import extract_triples

    reg.register(
        "extract_facts",
        extract_facts,
        category="analysis",
        description="Extract decisions, preferences, and facts from text using pattern matching.",
    )
    reg.register(
        "detect_contradictions",
        detect_contradictions,
        category="analysis",
        description="Detect contradictions between a set of memories.",
    )
    reg.register(
        "format_contradictions",
        format_contradictions,
        category="analysis",
        description="Format contradiction results into human-readable text.",
    )
    reg.register(
        "extract_triples",
        extract_triples,
        category="analysis",
        description="Extract entity-relation triples (subject-predicate-object) from text.",
    )
