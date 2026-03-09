"""Knowledge stats: aggregate statistics about memories and documents.

Provides a dashboard-style overview of knowledge distribution,
growth trends, and category breakdown. No LLM calls.
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime

logger = logging.getLogger(__name__)


def compute_stats(
    memories: list[dict],
    documents: list[dict] | None = None,
) -> dict:
    """Compute aggregate knowledge statistics.

    Args:
        memories: List of memory dicts with 'content', 'date', 'category', 'tags'.
        documents: Optional list of document dicts.

    Returns:
        Dict with stats: total counts, category breakdown, tag distribution,
        growth by month, average content length.
    """
    stats: dict = {
        "total_memories": len(memories),
        "total_documents": len(documents) if documents else 0,
        "categories": {},
        "top_tags": [],
        "growth_by_month": {},
        "avg_memory_length": 0,
        "oldest_memory": None,
        "newest_memory": None,
    }

    if not memories:
        return stats

    # Category breakdown
    category_counter: Counter = Counter()
    tag_counter: Counter = Counter()
    lengths: list[int] = []
    dates: list[str] = []
    monthly: Counter = Counter()

    for mem in memories:
        cat = mem.get("category", "general")
        category_counter[cat] += 1

        for tag in mem.get("tags", []):
            tag_counter[tag.lower()] += 1

        content = mem.get("content", "")
        lengths.append(len(content))

        date = mem.get("date", "")
        if date and len(date) >= 7:
            dates.append(date[:10])
            monthly[date[:7]] += 1  # YYYY-MM

    stats["categories"] = dict(category_counter.most_common())
    stats["top_tags"] = [{"tag": t, "count": c} for t, c in tag_counter.most_common(10)]
    stats["growth_by_month"] = dict(sorted(monthly.items()))
    stats["avg_memory_length"] = round(sum(lengths) / len(lengths)) if lengths else 0

    if dates:
        sorted_dates = sorted(dates)
        stats["oldest_memory"] = sorted_dates[0]
        stats["newest_memory"] = sorted_dates[-1]

    return stats


def format_stats(stats: dict) -> str:
    """Format knowledge stats into readable text."""
    if stats["total_memories"] == 0 and stats["total_documents"] == 0:
        return "No knowledge stored yet."

    lines = ["# Knowledge Statistics", ""]

    # Overview
    lines.append("## Overview")
    lines.append(f"- Memories: {stats['total_memories']}")
    lines.append(f"- Documents: {stats['total_documents']}")
    if stats["avg_memory_length"]:
        lines.append(f"- Avg memory length: {stats['avg_memory_length']} chars")
    if stats["oldest_memory"]:
        lines.append(f"- Date range: {stats['oldest_memory']} to {stats['newest_memory']}")
    lines.append("")

    # Categories
    if stats["categories"]:
        lines.append("## Categories")
        for cat, count in stats["categories"].items():
            pct = round(100 * count / stats["total_memories"])
            lines.append(f"- {cat}: {count} ({pct}%)")
        lines.append("")

    # Tags
    if stats["top_tags"]:
        lines.append("## Top Tags")
        for t in stats["top_tags"][:10]:
            lines.append(f"- #{t['tag']}: {t['count']}")
        lines.append("")

    # Growth
    if stats["growth_by_month"]:
        lines.append("## Growth by Month")
        for month, count in stats["growth_by_month"].items():
            bar = "#" * min(count, 30)
            lines.append(f"- {month}: {bar} ({count})")
        lines.append("")

    return "\n".join(lines)
