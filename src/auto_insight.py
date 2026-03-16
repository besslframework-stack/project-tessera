"""Auto-insight: generate insights from accumulated memories.

Analyzes memory patterns over time to produce:
1. Trending topics -- what you've been thinking about most recently
2. Decision patterns -- recurring types of decisions
3. Hidden connections -- topics that co-occur but aren't obviously linked
4. Weekly digest -- summary of what was learned this week
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


def generate_insights(days: int = 7) -> dict:
    """Generate insights from memories within the given time window.

    Args:
        days: Look back this many days (default 7).

    Returns:
        Dict with trending_topics, decision_patterns, connections,
        digest, and period metadata.
    """
    from src.memory import recall_memories

    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    try:
        all_mems = recall_memories("", top_k=500)
    except Exception:
        all_mems = []

    recent = [m for m in all_mems if m.get("date", "") >= cutoff]
    older = [m for m in all_mems if m.get("date", "") < cutoff]

    return {
        "period": f"Last {days} days (since {cutoff})",
        "total_memories": len(all_mems),
        "recent_count": len(recent),
        "trending_topics": _find_trending_topics(recent, older),
        "decision_patterns": _find_decision_patterns(recent),
        "connections": _find_hidden_connections(recent),
        "digest": _build_digest(recent, days),
    }


def _find_trending_topics(
    recent: list[dict], older: list[dict], top_n: int = 5
) -> list[dict]:
    """Find topics that appear more in recent memories than in older ones."""
    recent_tags = Counter()
    older_tags = Counter()

    for m in recent:
        for tag in (m.get("tags") or []):
            recent_tags[tag.lower()] += 1
        cat = m.get("category", "")
        if cat:
            recent_tags[f"cat:{cat}"] += 1

    for m in older:
        for tag in (m.get("tags") or []):
            older_tags[tag.lower()] += 1

    # Score by recent frequency, boosted if it wasn't common before
    scored: list[tuple[str, float]] = []
    for topic, count in recent_tags.items():
        if topic.startswith("cat:"):
            continue
        old_count = older_tags.get(topic, 0)
        # New or growing topics get higher scores
        if old_count == 0:
            score = count * 2.0  # brand new topic
        else:
            score = count / (old_count + 1)  # growth ratio
        scored.append((topic, round(score, 2)))

    scored.sort(key=lambda x: x[1], reverse=True)
    return [{"topic": t, "score": s, "recent_count": recent_tags[t]}
            for t, s in scored[:top_n]]


def _find_decision_patterns(memories: list[dict]) -> list[dict]:
    """Find recurring decision themes."""
    decisions = [
        m for m in memories
        if m.get("category") == "decision"
    ]

    if not decisions:
        return []

    # Extract common subjects from decision content
    subjects: Counter = Counter()
    for d in decisions:
        content = d.get("content", "").lower()
        # Pull out noun-like words (3+ chars, not stop words)
        words = re.findall(r'\b[a-z가-힣]{3,}\b', content)
        stop = {"the", "and", "for", "that", "this", "with", "use", "our",
                "was", "are", "from", "have", "will", "but", "not", "been",
                "하기로", "했다", "대해", "것을", "하는", "있는"}
        for w in words:
            if w not in stop:
                subjects[w] += 1

    top_subjects = subjects.most_common(5)
    patterns = []
    for subject, count in top_subjects:
        if count >= 2:
            related = [
                d.get("content", "")[:80]
                for d in decisions
                if subject in d.get("content", "").lower()
            ][:3]
            patterns.append({
                "subject": subject,
                "decision_count": count,
                "examples": related,
            })

    return patterns


def _find_hidden_connections(memories: list[dict], min_overlap: int = 2) -> list[dict]:
    """Find tag pairs that co-occur in memories, suggesting hidden links."""
    pair_counts: Counter = Counter()
    pair_mems: dict[tuple, list[str]] = {}

    for m in memories:
        tags = sorted(set(t.lower() for t in (m.get("tags") or [])))
        for i in range(len(tags)):
            for j in range(i + 1, len(tags)):
                pair = (tags[i], tags[j])
                pair_counts[pair] += 1
                if pair not in pair_mems:
                    pair_mems[pair] = []
                preview = m.get("content", "")[:60]
                if len(pair_mems[pair]) < 3:
                    pair_mems[pair].append(preview)

    connections = []
    for pair, count in pair_counts.most_common(5):
        if count >= min_overlap:
            connections.append({
                "topics": list(pair),
                "co_occurrences": count,
                "examples": pair_mems[pair],
            })

    return connections


def _build_digest(memories: list[dict], days: int) -> str:
    """Build a human-readable weekly digest."""
    if not memories:
        return f"No new memories in the last {days} days."

    # Count by category
    cats = Counter(m.get("category", "general") for m in memories)

    lines = [f"{len(memories)} memories in the last {days} days:"]

    for cat, count in cats.most_common():
        lines.append(f"  {cat}: {count}")

    # Most recent 5
    sorted_mems = sorted(memories, key=lambda m: m.get("date", ""), reverse=True)
    lines.append("")
    lines.append("Most recent:")
    for m in sorted_mems[:5]:
        date = m.get("date", "?")
        content = m.get("content", "")[:70]
        lines.append(f"  [{date}] {content}")

    return "\n".join(lines)


def format_insights(insights: dict) -> str:
    """Format insights dict into readable markdown."""
    lines = [f"# Auto-Insights ({insights['period']})", ""]
    lines.append(f"Total memories: {insights['total_memories']}, "
                 f"recent: {insights['recent_count']}")
    lines.append("")

    # Trending
    trends = insights.get("trending_topics", [])
    if trends:
        lines.append("## Trending topics")
        for t in trends:
            lines.append(f"- **{t['topic']}** (score: {t['score']}, "
                         f"mentioned {t['recent_count']}x recently)")
        lines.append("")
    else:
        lines.append("## Trending topics")
        lines.append("No clear trends detected.")
        lines.append("")

    # Decision patterns
    patterns = insights.get("decision_patterns", [])
    if patterns:
        lines.append("## Decision patterns")
        for p in patterns:
            lines.append(f"- **{p['subject']}** ({p['decision_count']} decisions)")
            for ex in p["examples"]:
                lines.append(f"  - {ex}")
        lines.append("")

    # Connections
    conns = insights.get("connections", [])
    if conns:
        lines.append("## Hidden connections")
        for c in conns:
            lines.append(f"- **{c['topics'][0]}** + **{c['topics'][1]}** "
                         f"(co-occur {c['co_occurrences']}x)")
            for ex in c["examples"]:
                lines.append(f"  - {ex}")
        lines.append("")

    # Digest
    lines.append("## Digest")
    lines.append(insights.get("digest", "No data."))

    return "\n".join(lines)
