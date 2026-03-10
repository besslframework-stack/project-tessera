"""User profile: build and maintain a profile from interactions and memories.

Automatically tracks user preferences, frequently used tools, common topics,
and interaction patterns. No LLM calls.
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime

logger = logging.getLogger(__name__)


def build_profile(
    memories: list[dict],
    interactions: list[dict] | None = None,
) -> dict:
    """Build a user profile from memories and interaction history.

    Args:
        memories: List of memory dicts with 'content', 'category', 'tags', 'date'.
        interactions: Optional list of interaction dicts with 'tool_name', 'timestamp'.

    Returns:
        Profile dict with preferences, topics, patterns, and stats.
    """
    profile: dict = {
        "total_memories": len(memories),
        "preferences": [],
        "decisions": [],
        "top_topics": [],
        "active_hours": {},
        "tool_usage": {},
        "language_preference": "unknown",
        "knowledge_areas": [],
    }

    if not memories and not interactions:
        return profile

    # Extract preferences and decisions
    preference_counter: Counter = Counter()
    decision_counter: Counter = Counter()
    topic_counter: Counter = Counter()
    tag_counter: Counter = Counter()

    for mem in memories:
        category = mem.get("category", "general")
        content = mem.get("content", "")

        if category == "preference":
            profile["preferences"].append({
                "content": content[:200],
                "date": mem.get("date", ""),
            })

        if category == "decision":
            profile["decisions"].append({
                "content": content[:200],
                "date": mem.get("date", ""),
            })

        for tag in mem.get("tags", []):
            tag_counter[tag.lower()] += 1

    # Top topics from tags
    profile["top_topics"] = [
        {"topic": t, "count": c}
        for t, c in tag_counter.most_common(10)
    ]

    # Detect language preference from content
    korean_count = 0
    english_count = 0
    for mem in memories:
        content = mem.get("content", "")
        for ch in content:
            if "\uac00" <= ch <= "\ud7a3":
                korean_count += 1
            elif "a" <= ch.lower() <= "z":
                english_count += 1

    if korean_count > english_count * 2:
        profile["language_preference"] = "korean"
    elif english_count > korean_count * 2:
        profile["language_preference"] = "english"
    else:
        profile["language_preference"] = "bilingual"

    # Tool usage from interactions
    if interactions:
        tool_counter: Counter = Counter()
        hour_counter: Counter = Counter()

        for inter in interactions:
            tool = inter.get("tool_name", "unknown")
            tool_counter[tool] += 1

            ts = inter.get("timestamp", "")
            if ts and len(ts) >= 13:
                try:
                    hour = int(ts[11:13])
                    hour_counter[hour] += 1
                except ValueError:
                    pass

        profile["tool_usage"] = dict(tool_counter.most_common(10))
        profile["active_hours"] = dict(sorted(hour_counter.items()))

    # Knowledge areas (categories with counts)
    cat_counter: Counter = Counter()
    for mem in memories:
        cat_counter[mem.get("category", "general")] += 1

    profile["knowledge_areas"] = [
        {"area": area, "count": count}
        for area, count in cat_counter.most_common()
    ]

    return profile


def format_profile(profile: dict) -> str:
    """Format user profile into readable text."""
    if profile["total_memories"] == 0:
        return "No profile data yet. Use Tessera more to build your profile."

    lines = ["# User Profile", ""]

    # Overview
    lines.append(f"Memories: {profile['total_memories']}")
    lines.append(f"Language: {profile['language_preference']}")
    lines.append("")

    # Knowledge areas
    if profile["knowledge_areas"]:
        lines.append("## Knowledge Areas")
        for area in profile["knowledge_areas"]:
            lines.append(f"- {area['area']}: {area['count']}")
        lines.append("")

    # Preferences
    if profile["preferences"]:
        lines.append(f"## Preferences ({len(profile['preferences'])})")
        for p in profile["preferences"][:5]:
            date = p["date"][:10] if p["date"] else ""
            lines.append(f"- [{date}] {p['content'][:100]}")
        lines.append("")

    # Decisions
    if profile["decisions"]:
        lines.append(f"## Recent Decisions ({len(profile['decisions'])})")
        for d in profile["decisions"][:5]:
            date = d["date"][:10] if d["date"] else ""
            lines.append(f"- [{date}] {d['content'][:100]}")
        lines.append("")

    # Top topics
    if profile["top_topics"]:
        lines.append("## Top Topics")
        for t in profile["top_topics"][:5]:
            lines.append(f"- #{t['topic']}: {t['count']}")
        lines.append("")

    # Tool usage
    if profile["tool_usage"]:
        lines.append("## Most Used Tools")
        for tool, count in list(profile["tool_usage"].items())[:5]:
            lines.append(f"- {tool}: {count}")
        lines.append("")

    return "\n".join(lines)
