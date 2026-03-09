"""Smart suggest: recommend related queries based on past interactions.

Analyzes search history and memory patterns to suggest what the user
might want to explore next. No LLM calls.
"""

from __future__ import annotations

import logging
import re
from collections import Counter

logger = logging.getLogger(__name__)


def _extract_keywords(text: str) -> list[str]:
    """Extract meaningful keywords from text."""
    stop_words = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "have",
        "has", "had", "do", "does", "did", "will", "would", "could", "should",
        "may", "might", "can", "to", "of", "in", "for", "on", "with", "at",
        "by", "from", "as", "into", "about", "we", "i", "they", "it", "this",
        "that", "and", "or", "but", "if", "then", "so", "because", "not", "no",
        "what", "how", "when", "where", "who", "which", "my", "your", "our",
    }
    words = re.findall(r"[a-zA-Z]+|[가-힣]+", text.lower())
    return [w for w in words if len(w) >= 2 and w not in stop_words]


def suggest_from_history(
    past_queries: list[str],
    memories: list[dict] | None = None,
    max_suggestions: int = 5,
) -> list[dict]:
    """Generate query suggestions from past search history and memories.

    Args:
        past_queries: List of past search query strings.
        memories: Optional list of memory dicts with 'content', 'tags', 'category'.
        max_suggestions: Maximum number of suggestions to return.

    Returns:
        List of suggestion dicts with 'query', 'reason', 'score'.
    """
    if not past_queries and not memories:
        return []

    # Count keyword frequency across all queries
    keyword_counts: Counter = Counter()
    for q in past_queries:
        for kw in _extract_keywords(q):
            keyword_counts[kw] += 1

    # Extract topics from memories
    memory_topics: Counter = Counter()
    memory_tags: Counter = Counter()
    if memories:
        for mem in memories:
            content = mem.get("content", "")
            for kw in _extract_keywords(content):
                memory_topics[kw] += 1
            for tag in mem.get("tags", []):
                memory_tags[tag.lower()] += 1

    suggestions: list[dict] = []

    # Strategy 1: Frequent keywords not recently searched
    recent_keywords = set()
    if past_queries:
        for kw in _extract_keywords(past_queries[-1]):
            recent_keywords.add(kw)

    for kw, count in keyword_counts.most_common(20):
        if kw not in recent_keywords and count >= 2:
            suggestions.append({
                "query": kw,
                "reason": f"frequently searched ({count} times)",
                "score": count * 0.5,
            })

    # Strategy 2: Memory topics not yet searched
    searched_keywords = set()
    for q in past_queries:
        searched_keywords.update(_extract_keywords(q))

    for topic, count in memory_topics.most_common(20):
        if topic not in searched_keywords and count >= 2:
            suggestions.append({
                "query": topic,
                "reason": f"appears in {count} memories but not searched",
                "score": count * 0.4,
            })

    # Strategy 3: Popular tags
    for tag, count in memory_tags.most_common(10):
        if tag not in searched_keywords:
            suggestions.append({
                "query": f"#{tag}",
                "reason": f"tag used {count} times",
                "score": count * 0.3,
            })

    # Deduplicate by query text
    seen = set()
    unique: list[dict] = []
    for s in suggestions:
        key = s["query"].lower()
        if key not in seen:
            seen.add(key)
            unique.append(s)

    # Sort by score descending
    unique.sort(key=lambda s: s["score"], reverse=True)
    return unique[:max_suggestions]


def format_suggestions(suggestions: list[dict]) -> str:
    """Format suggestions into readable text."""
    if not suggestions:
        return "No suggestions available yet. Use Tessera more to get personalized suggestions."

    lines = [f"# Suggested Queries ({len(suggestions)})", ""]
    for s in suggestions:
        lines.append(f"- **{s['query']}** — {s['reason']}")
    return "\n".join(lines)
