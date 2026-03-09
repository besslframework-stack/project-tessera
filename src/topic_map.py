"""Topic map: cluster memories by topic and generate Mermaid diagram.

Groups all memories by keyword similarity, creating a topic map
that shows how knowledge is distributed. No LLM calls.
"""

from __future__ import annotations

import logging
import re
from collections import Counter

logger = logging.getLogger(__name__)


def _tokenize(text: str) -> list[str]:
    """Extract meaningful words from text."""
    stop_words = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "have",
        "has", "had", "do", "does", "did", "will", "would", "could", "should",
        "may", "might", "can", "to", "of", "in", "for", "on", "with", "at",
        "by", "from", "as", "into", "about", "we", "i", "they", "it", "this",
        "that", "and", "or", "but", "if", "then", "so", "because", "not", "no",
        "use", "using", "decided", "prefer", "like", "want",
    }
    words = re.findall(r"[a-zA-Z]+|[가-힣]+", text.lower())
    return [w for w in words if len(w) >= 2 and w not in stop_words]


def build_topic_map(
    memories: list[dict],
    min_topic_size: int = 2,
    max_topics: int = 15,
) -> list[dict]:
    """Cluster memories by shared keywords into topics.

    Args:
        memories: List of memory dicts with 'content'.
        min_topic_size: Minimum memories in a topic to include.
        max_topics: Maximum number of topics to return.

    Returns:
        List of topic dicts with 'label', 'keywords', 'count', 'memories'.
    """
    if not memories:
        return []

    # Count keyword frequency across all memories
    keyword_to_memories: dict[str, list[int]] = {}
    memory_keywords: list[set[str]] = []

    for i, mem in enumerate(memories):
        tokens = set(_tokenize(mem.get("content", "")))
        memory_keywords.append(tokens)
        for kw in tokens:
            keyword_to_memories.setdefault(kw, []).append(i)

    # Find topic keywords (appear in multiple memories)
    topic_keywords = {
        kw: indices
        for kw, indices in keyword_to_memories.items()
        if len(indices) >= min_topic_size
    }

    if not topic_keywords:
        return []

    # Greedy set-cover: pick keywords that cover the most uncovered memories
    covered: set[int] = set()
    topics: list[dict] = []

    # Sort by coverage (descending)
    sorted_keywords = sorted(topic_keywords.items(), key=lambda x: len(x[1]), reverse=True)

    for kw, indices in sorted_keywords:
        if len(topics) >= max_topics:
            break

        uncovered = [i for i in indices if i not in covered]
        if len(uncovered) < min_topic_size:
            continue

        # Find co-occurring keywords for this cluster
        cluster_indices = set(indices)
        co_keywords: Counter = Counter()
        for idx in cluster_indices:
            for other_kw in memory_keywords[idx]:
                if other_kw != kw:
                    co_keywords[other_kw] += 1

        # Top co-occurring keywords
        top_co = [k for k, c in co_keywords.most_common(3) if c >= 2]

        topic = {
            "label": kw,
            "keywords": [kw] + top_co,
            "count": len(cluster_indices),
            "memories": [memories[i] for i in sorted(cluster_indices)],
        }
        topics.append(topic)
        covered.update(cluster_indices)

    # Sort by count descending
    topics.sort(key=lambda t: t["count"], reverse=True)
    return topics


def format_topic_map_text(topics: list[dict]) -> str:
    """Format topic map as readable text."""
    if not topics:
        return "No topic clusters found. Add more memories to see patterns."

    total = sum(t["count"] for t in topics)
    lines = [f"# Topic Map ({len(topics)} topics, {total} memories)", ""]

    for t in topics:
        kw_str = ", ".join(t["keywords"][:4])
        lines.append(f"## {t['label']} ({t['count']} memories)")
        lines.append(f"   Keywords: {kw_str}")
        # Show up to 3 memory previews
        for mem in t["memories"][:3]:
            preview = mem.get("content", "")[:80].replace("\n", " ")
            if len(mem.get("content", "")) > 80:
                preview += "..."
            lines.append(f"   - {preview}")
        if t["count"] > 3:
            lines.append(f"   ... and {t['count'] - 3} more")
        lines.append("")

    return "\n".join(lines)


def format_topic_map_mermaid(topics: list[dict]) -> str:
    """Format topic map as Mermaid mindmap diagram."""
    if not topics:
        return "No topic clusters to visualize."

    lines = ["```mermaid", "mindmap", "  root((Knowledge))"]

    for t in topics:
        label = t["label"]
        count = t["count"]
        lines.append(f"    {label} [{label} ({count})]")
        for kw in t["keywords"][1:4]:
            lines.append(f"      {kw}")

    lines.append("```")
    return "\n".join(lines)
