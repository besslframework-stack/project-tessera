"""Decision tracker: track how decisions on the same topic evolve over time.

Groups category=decision memories by topic similarity, then presents
a timeline of how decisions changed. No LLM calls.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from pathlib import Path

logger = logging.getLogger(__name__)


def _extract_topic_keywords(text: str) -> set[str]:
    """Extract meaningful keywords from text for topic grouping."""
    # Remove common stop words (English + Korean)
    stop_en = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "shall", "can", "to", "of", "in", "for",
        "on", "with", "at", "by", "from", "as", "into", "about", "we", "i",
        "they", "it", "this", "that", "use", "using", "go", "going", "went",
        "decided", "chose", "picked", "selected", "prefer", "like", "want",
        "not", "no", "and", "or", "but", "if", "then", "so", "because",
    }
    # Tokenize: split alphabetic and Korean separately to avoid "postgresql을" merging
    words = re.findall(r"[a-zA-Z]+|[가-힣]+", text.lower())
    return {w for w in words if len(w) >= 2 and w not in stop_en}


def _topic_similarity(keywords_a: set[str], keywords_b: set[str]) -> float:
    """Jaccard similarity between two keyword sets."""
    if not keywords_a or not keywords_b:
        return 0.0
    intersection = keywords_a & keywords_b
    union = keywords_a | keywords_b
    return len(intersection) / len(union)


def get_decision_timeline(memories: list[dict], topic_threshold: float = 0.3) -> list[dict]:
    """Group decision memories by topic and build timelines.

    Args:
        memories: List of memory dicts with 'content', 'date', 'category'.
        topic_threshold: Minimum Jaccard similarity to consider same topic.

    Returns:
        List of topic groups, each with 'topic_keywords', 'decisions' (sorted by date),
        and 'changed' flag (True if decisions differ).
    """
    # Filter to decisions only
    decisions = [m for m in memories if m.get("category", "").lower() == "decision"]
    if not decisions:
        return []

    # Sort by date ascending
    decisions.sort(key=lambda m: m.get("date", ""))

    # Group by topic using keyword overlap
    groups: list[dict] = []
    assigned = set()

    for i, dec in enumerate(decisions):
        if i in assigned:
            continue

        keywords_i = _extract_topic_keywords(dec.get("content", ""))
        group = {
            "topic_keywords": sorted(keywords_i)[:5],
            "decisions": [dec],
        }
        assigned.add(i)

        for j, other in enumerate(decisions):
            if j in assigned:
                continue
            keywords_j = _extract_topic_keywords(other.get("content", ""))
            if _topic_similarity(keywords_i, keywords_j) >= topic_threshold:
                group["decisions"].append(other)
                assigned.add(j)

        # Check if decisions in the group differ (evolution)
        contents = [d.get("content", "").strip().lower() for d in group["decisions"]]
        group["changed"] = len(set(contents)) > 1
        group["count"] = len(group["decisions"])
        groups.append(group)

    # Sort groups: changed ones first, then by count
    groups.sort(key=lambda g: (-int(g["changed"]), -g["count"]))
    return groups


def format_decision_timeline(groups: list[dict]) -> str:
    """Format decision groups into readable text."""
    if not groups:
        return "No decision memories found."

    lines = [f"# Decision Timeline ({len(groups)} topics)", ""]

    for g in groups:
        topic = ", ".join(g["topic_keywords"][:3]) if g["topic_keywords"] else "unknown"
        changed_marker = " (changed)" if g["changed"] else ""
        lines.append(f"## {topic}{changed_marker}")

        for dec in g["decisions"]:
            date = dec.get("date", "")[:10] if dec.get("date") else "?"
            content = dec.get("content", "").strip()
            if len(content) > 150:
                content = content[:147] + "..."
            lines.append(f"- [{date}] {content}")

        lines.append("")

    return "\n".join(lines)
