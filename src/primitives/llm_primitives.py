"""LLM primitives: AI-powered classification, summarization, and connection.

Phase 0: interface stubs only (raise NotImplementedError).
Phase 1: on-device LLM via llama.cpp / MLX + cloud LLM via Anthropic API.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from src.primitives.registry import PrimitiveRegistry

logger = logging.getLogger(__name__)


@dataclass
class ClassifyResult:
    category: str  # decision, preference, fact, emotion, relationship
    tags: list[str]
    confidence: float


@dataclass
class SummaryResult:
    summary: str
    key_points: list[str]


@dataclass
class ConnectionResult:
    connections: list[dict]  # [{from, to, relation, strength}]


def llm_classify(
    text: str,
    *,
    model: str = "local",
    categories: list[str] | None = None,
) -> ClassifyResult:
    """Classify text into a category using LLM.

    Args:
        text: Text to classify.
        model: "local" for on-device LLM, or a cloud model identifier.
        categories: Allowed categories. Defaults to standard set.

    Returns:
        ClassifyResult with category, suggested tags, and confidence.

    Raises:
        NotImplementedError: Until Phase 1 implementation.
    """
    raise NotImplementedError(
        "llm_classify requires Phase 1 (LLM Intelligence Layer). "
        "Use extract_facts for regex-based classification."
    )


def llm_summarize(
    memories: list[dict],
    *,
    model: str = "local",
    max_length: int = 200,
) -> SummaryResult:
    """Summarize a group of memories into a structured summary.

    Args:
        memories: List of memory dicts to summarize.
        model: "local" for on-device LLM, or a cloud model identifier.
        max_length: Maximum summary length in characters.

    Returns:
        SummaryResult with summary text and key points.

    Raises:
        NotImplementedError: Until Phase 1 implementation.
    """
    raise NotImplementedError(
        "llm_summarize requires Phase 1 (LLM Intelligence Layer)."
    )


def llm_connect(
    memories: list[dict],
    *,
    model: str = "local",
    min_strength: float = 0.5,
) -> ConnectionResult:
    """Discover semantic connections between memories.

    Args:
        memories: List of memory dicts to analyze.
        model: "local" for on-device LLM, or a cloud model identifier.
        min_strength: Minimum connection strength to include.

    Returns:
        ConnectionResult with discovered connections.

    Raises:
        NotImplementedError: Until Phase 1 implementation.
    """
    raise NotImplementedError(
        "llm_connect requires Phase 1 (LLM Intelligence Layer)."
    )


def register_llm_primitives(reg: PrimitiveRegistry) -> None:
    reg.register(
        "llm_classify",
        llm_classify,
        category="llm",
        description="Classify text into a category using LLM (Phase 1).",
    )
    reg.register(
        "llm_summarize",
        llm_summarize,
        category="llm",
        description="Summarize a group of memories using LLM (Phase 1).",
    )
    reg.register(
        "llm_connect",
        llm_connect,
        category="llm",
        description="Discover semantic connections between memories using LLM (Phase 1).",
    )
