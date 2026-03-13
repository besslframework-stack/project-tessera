"""Memory confidence scoring: rate memory reliability based on repetition and recency.

Inspired by Fleming's cross-consistency pattern. Memories confirmed across
multiple sessions or sources get higher confidence scores.
"""

from __future__ import annotations

import logging
import re
from collections import Counter

from src.decision_tracker import _extract_topic_keywords, _topic_similarity

logger = logging.getLogger(__name__)


def _compute_repetition_score(memory: dict, all_memories: list[dict], threshold: float = 0.3) -> float:
    """Score based on how many other memories confirm the same topic.

    Returns 0.0-1.0 where 1.0 means many memories confirm this topic.
    """
    content = memory.get("content", "")
    keywords = _extract_topic_keywords(content)
    if not keywords:
        return 0.0

    confirmations = 0
    for other in all_memories:
        if other is memory:
            continue
        other_kw = _extract_topic_keywords(other.get("content", ""))
        if _topic_similarity(keywords, other_kw) >= threshold:
            confirmations += 1

    # Normalize: 0 confirmations = 0.0, 1 = 0.3, 2 = 0.5, 3+ = 0.7, 5+ = 1.0
    if confirmations == 0:
        return 0.0
    elif confirmations == 1:
        return 0.3
    elif confirmations == 2:
        return 0.5
    elif confirmations <= 4:
        return 0.7
    return 1.0


def _compute_source_diversity_score(memory: dict, all_memories: list[dict], threshold: float = 0.3) -> float:
    """Score based on how many different sources confirm the same topic.

    Multiple sources (user-request, auto-learn, conversation) = higher confidence.
    """
    content = memory.get("content", "")
    keywords = _extract_topic_keywords(content)
    if not keywords:
        return 0.0

    sources = {memory.get("source", "unknown")}
    for other in all_memories:
        if other is memory:
            continue
        other_kw = _extract_topic_keywords(other.get("content", ""))
        if _topic_similarity(keywords, other_kw) >= threshold:
            sources.add(other.get("source", "unknown"))

    # 1 source = 0.2, 2 = 0.6, 3+ = 1.0
    if len(sources) <= 1:
        return 0.2
    elif len(sources) == 2:
        return 0.6
    return 1.0


def _compute_recency_score(memory: dict) -> float:
    """Score based on how recent the memory is.

    Very recent = higher confidence (more likely still valid).
    """
    from datetime import datetime

    date_str = memory.get("date", "")
    if not date_str:
        return 0.3  # Unknown date = moderate

    try:
        mem_date = datetime.fromisoformat(date_str[:19])
        now = datetime.now()
        age_days = (now - mem_date).days

        if age_days <= 7:
            return 1.0
        elif age_days <= 30:
            return 0.8
        elif age_days <= 90:
            return 0.6
        elif age_days <= 180:
            return 0.4
        return 0.2
    except (ValueError, TypeError):
        return 0.3


def _compute_category_weight(memory: dict) -> float:
    """Category-based weight. Decisions and preferences are inherently more
    likely to change than facts."""
    category = memory.get("category", "general").lower()
    weights = {
        "fact": 0.9,        # Facts are stable
        "reference": 0.8,
        "preference": 0.6,  # Preferences can change
        "decision": 0.5,    # Decisions often evolve
        "context": 0.4,
        "general": 0.5,
    }
    return weights.get(category, 0.5)


def compute_confidence(
    memory: dict,
    all_memories: list[dict],
    weights: dict[str, float] | None = None,
) -> dict:
    """Compute confidence score for a single memory.

    Args:
        memory: The memory to score.
        all_memories: All memories for cross-reference.
        weights: Optional weight overrides for each factor.

    Returns:
        Dict with 'score' (0-1), 'label' (high/medium/low), and factor breakdown.
    """
    w = weights or {
        "repetition": 0.35,
        "source_diversity": 0.20,
        "recency": 0.25,
        "category": 0.20,
    }

    repetition = _compute_repetition_score(memory, all_memories)
    source_div = _compute_source_diversity_score(memory, all_memories)
    recency = _compute_recency_score(memory)
    category = _compute_category_weight(memory)

    score = (
        repetition * w["repetition"]
        + source_div * w["source_diversity"]
        + recency * w["recency"]
        + category * w["category"]
    )

    if score >= 0.65:
        label = "high"
    elif score >= 0.4:
        label = "medium"
    else:
        label = "low"

    return {
        "score": round(score, 3),
        "label": label,
        "factors": {
            "repetition": round(repetition, 2),
            "source_diversity": round(source_div, 2),
            "recency": round(recency, 2),
            "category_weight": round(category, 2),
        },
    }


def score_all_memories(memories: list[dict]) -> list[dict]:
    """Compute confidence scores for all memories.

    Args:
        memories: List of memory dicts.

    Returns:
        Same list with 'confidence' dict added to each memory.
        Sorted by confidence score descending.
    """
    for mem in memories:
        mem["confidence"] = compute_confidence(mem, memories)

    memories.sort(key=lambda m: m["confidence"]["score"], reverse=True)
    return memories


def format_confidence_report(memories: list[dict]) -> str:
    """Format a confidence report for scored memories.

    Args:
        memories: Memories with 'confidence' already computed.

    Returns:
        Markdown report.
    """
    if not memories:
        return "No memories to analyze."

    scored = [m for m in memories if "confidence" in m]
    if not scored:
        return "No confidence scores computed."

    high = [m for m in scored if m["confidence"]["label"] == "high"]
    medium = [m for m in scored if m["confidence"]["label"] == "medium"]
    low = [m for m in scored if m["confidence"]["label"] == "low"]

    lines = [
        f"# Memory Confidence Report",
        f"",
        f"**{len(scored)} memories analyzed**: "
        f"{len(high)} high, {len(medium)} medium, {len(low)} low confidence",
        "",
    ]

    if high:
        lines.append("## High Confidence")
        for m in high[:10]:
            c = m["confidence"]
            content = m.get("content", "")[:100]
            lines.append(f"- [{c['score']:.2f}] {content}")
        lines.append("")

    if low:
        lines.append("## Low Confidence (consider reviewing)")
        for m in low[:10]:
            c = m["confidence"]
            content = m.get("content", "")[:100]
            factors = c["factors"]
            reason = []
            if factors["repetition"] < 0.3:
                reason.append("unconfirmed")
            if factors["recency"] < 0.4:
                reason.append("old")
            if factors["source_diversity"] < 0.3:
                reason.append("single source")
            reason_str = f" ({', '.join(reason)})" if reason else ""
            lines.append(f"- [{c['score']:.2f}] {content}{reason_str}")
        lines.append("")

    return "\n".join(lines)
