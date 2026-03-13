"""Memory health analytics: track access patterns and classify memory vitality.

Inspired by Claudel's EvolutionEngine which classifies tokens as
healthy/underused/orphaned based on usage patterns.
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime

logger = logging.getLogger(__name__)


def _parse_date(date_str: str) -> datetime | None:
    """Parse ISO date string, returns None on failure."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str[:19])
    except (ValueError, TypeError):
        return None


def classify_health(
    memories: list[dict],
    search_history: list[dict] | None = None,
    stale_days: int = 90,
) -> dict:
    """Classify each memory's health status.

    Health statuses:
    - healthy: accessed recently or created recently
    - stale: not accessed and older than stale_days
    - orphaned: no tags, no category, likely low value

    Args:
        memories: List of memory dicts.
        search_history: Optional list of past search queries with timestamps.
        stale_days: Days after which an unaccessed memory is considered stale.

    Returns:
        Dict with 'summary', 'by_status', and 'recommendations'.
    """
    now = datetime.now()
    healthy = []
    stale = []
    orphaned = []

    for mem in memories:
        date = _parse_date(mem.get("date", ""))
        category = mem.get("category", "").strip()
        tags = mem.get("tags", "")
        content = mem.get("content", "").strip()

        # Orphaned: no meaningful metadata
        if not category or category == "general":
            if not tags or tags in ("general", "[]", ""):
                if len(content) < 20:
                    orphaned.append(mem)
                    continue

        # Stale: older than threshold
        if date:
            age_days = (now - date).days
            if age_days > stale_days:
                stale.append(mem)
                continue

        healthy.append(mem)

    return {
        "summary": {
            "total": len(memories),
            "healthy": len(healthy),
            "stale": len(stale),
            "orphaned": len(orphaned),
            "health_score": round(len(healthy) / max(len(memories), 1), 2),
        },
        "by_status": {
            "healthy": healthy,
            "stale": stale,
            "orphaned": orphaned,
        },
        "recommendations": _build_recommendations(healthy, stale, orphaned),
    }


def _build_recommendations(
    healthy: list[dict],
    stale: list[dict],
    orphaned: list[dict],
) -> list[str]:
    """Generate actionable recommendations based on health analysis."""
    recs = []

    if orphaned:
        recs.append(
            f"{len(orphaned)} orphaned memories with minimal metadata. "
            "Consider adding tags or categories, or deleting if no longer relevant."
        )

    if stale:
        # Group stale by category
        cats = Counter(m.get("category", "general") for m in stale)
        top_cat = cats.most_common(1)[0] if cats else ("general", 0)
        recs.append(
            f"{len(stale)} stale memories (90+ days old). "
            f"Most are '{top_cat[0]}' ({top_cat[1]}). "
            "Review and archive or update outdated ones."
        )

    if len(healthy) < len(stale):
        recs.append(
            "More stale memories than healthy ones. "
            "Consider a knowledge cleanup session."
        )

    if not recs:
        recs.append("Memory health looks good. No action needed.")

    return recs


def compute_growth_stats(memories: list[dict]) -> dict:
    """Compute memory growth statistics over time.

    Returns:
        Dict with monthly counts, category distribution, source distribution.
    """
    monthly: Counter[str] = Counter()
    by_category: Counter[str] = Counter()
    by_source: Counter[str] = Counter()

    for mem in memories:
        date_str = mem.get("date", "")
        if date_str and len(date_str) >= 7:
            monthly[date_str[:7]] += 1

        category = mem.get("category", "general")
        by_category[category] += 1

        source = mem.get("source", "unknown")
        by_source[source] += 1

    return {
        "monthly_growth": dict(sorted(monthly.items())),
        "by_category": dict(by_category.most_common()),
        "by_source": dict(by_source.most_common()),
        "total": len(memories),
    }


def format_health_report(health: dict, growth: dict | None = None) -> str:
    """Format health analysis into readable report.

    Args:
        health: Result from classify_health().
        growth: Optional result from compute_growth_stats().

    Returns:
        Markdown report.
    """
    s = health["summary"]
    lines = [
        "# Memory Health Report",
        "",
        f"**{s['total']} memories** — Health Score: {s['health_score']:.0%}",
        "",
        f"| Status | Count |",
        f"|--------|-------|",
        f"| Healthy | {s['healthy']} |",
        f"| Stale (90+ days) | {s['stale']} |",
        f"| Orphaned | {s['orphaned']} |",
        "",
    ]

    # Recommendations
    recs = health.get("recommendations", [])
    if recs:
        lines.append("## Recommendations")
        for r in recs:
            lines.append(f"- {r}")
        lines.append("")

    # Growth stats
    if growth:
        lines.append("## Growth")
        monthly = growth.get("monthly_growth", {})
        if monthly:
            lines.append("### Monthly")
            for month, count in list(monthly.items())[-6:]:
                bar = "█" * min(count, 20)
                lines.append(f"  {month}: {bar} ({count})")
            lines.append("")

        cats = growth.get("by_category", {})
        if cats:
            lines.append("### By Category")
            for cat, count in cats.items():
                lines.append(f"  - {cat}: {count}")
            lines.append("")

    return "\n".join(lines)
