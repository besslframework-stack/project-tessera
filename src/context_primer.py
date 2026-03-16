"""Context primer: assemble a session-start briefing from recent knowledge.

Combines recent decisions, active topics, user preferences, health pulse,
and last session summary into a compact context that gets injected at
the beginning of each new session.

No LLM calls — composes from existing data.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def prime_context(days: int = 7, max_items: int = 5) -> dict:
    """Build a session-start context briefing.

    Args:
        days: How many days back to look for recent context.
        max_items: Max items per section (decisions, preferences, etc.).

    Returns:
        Dict with sections: health_pulse, recent_decisions, recent_preferences,
        active_topics, last_session, stats.
    """
    result: dict = {
        "health_pulse": None,
        "recent_decisions": [],
        "recent_preferences": [],
        "active_topics": [],
        "last_session": None,
        "stats": {"total_memories": 0, "language": "unknown"},
        "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
    }

    # 1. Health pulse from quiet curation
    try:
        from src.quiet_curation import get_health_pulse
        result["health_pulse"] = get_health_pulse()
    except Exception as exc:
        logger.debug("Health pulse unavailable: %s", exc)

    # 2. Recent decisions and preferences
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    try:
        from src.memory import recall_memories

        decisions = recall_memories(
            "decision", top_k=max_items, since=cutoff, category="decision",
        )
        result["recent_decisions"] = [
            {"content": m["content"][:200], "date": m.get("date", "")[:10]}
            for m in decisions
        ]

        preferences = recall_memories(
            "preference", top_k=max_items, since=cutoff, category="preference",
        )
        result["recent_preferences"] = [
            {"content": m["content"][:200], "date": m.get("date", "")[:10]}
            for m in preferences
        ]
    except Exception as exc:
        logger.debug("Memory recall unavailable: %s", exc)

    # 3. Active topics from all recent memories
    try:
        from collections import Counter
        from src.memory import recall_memories

        all_recent = recall_memories("", top_k=100, since=cutoff)
        result["stats"]["total_memories"] = len(all_recent)

        tag_counter: Counter = Counter()
        for m in all_recent:
            tags = m.get("tags") or ""
            if isinstance(tags, str):
                for t in tags.split(","):
                    t = t.strip()
                    if t:
                        tag_counter[t.lower()] += 1
            elif isinstance(tags, list):
                for t in tags:
                    if t:
                        tag_counter[t.strip().lower()] += 1
        result["active_topics"] = [
            {"topic": t, "count": c}
            for t, c in tag_counter.most_common(max_items)
        ]
    except Exception as exc:
        logger.debug("Topic extraction failed: %s", exc)

    # 4. Last session summary
    try:
        from src.interaction_log import InteractionLog
        log = InteractionLog()
        sessions = log.get_recent_sessions(limit=2)
        # Skip current session (first one), get last completed session
        for sess in sessions:
            if sess.get("interaction_count", 0) >= 3:
                result["last_session"] = {
                    "session_id": sess.get("session_id", ""),
                    "interactions": sess.get("interaction_count", 0),
                    "top_tools": sess.get("top_tools", ""),
                    "started": sess.get("first_ts", "")[:16],
                    "ended": sess.get("last_ts", "")[:16],
                }
                break
    except Exception as exc:
        logger.debug("Session history unavailable: %s", exc)

    # 5. Language detection
    try:
        from src.memory import recall_memories
        sample = recall_memories("", top_k=20)
        ko = en = 0
        for m in sample:
            for ch in m.get("content", ""):
                if "\uac00" <= ch <= "\ud7a3":
                    ko += 1
                elif "a" <= ch.lower() <= "z":
                    en += 1
        if ko > en * 2:
            result["stats"]["language"] = "korean"
        elif en > ko * 2:
            result["stats"]["language"] = "english"
        else:
            result["stats"]["language"] = "bilingual"
    except Exception:
        pass

    return result


def format_primer(ctx: dict) -> str:
    """Format context primer as a readable briefing string."""
    parts: list[str] = []
    parts.append("## Session Context Briefing")

    # Health pulse
    if ctx.get("health_pulse"):
        parts.append(f"\n{ctx['health_pulse']}")

    # Recent decisions
    decisions = ctx.get("recent_decisions", [])
    if decisions:
        parts.append(f"\n### Recent Decisions ({len(decisions)})")
        for d in decisions:
            date = d.get("date", "")
            parts.append(f"- [{date}] {d['content']}")

    # Recent preferences
    prefs = ctx.get("recent_preferences", [])
    if prefs:
        parts.append(f"\n### Active Preferences ({len(prefs)})")
        for p in prefs:
            date = p.get("date", "")
            parts.append(f"- [{date}] {p['content']}")

    # Active topics
    topics = ctx.get("active_topics", [])
    if topics:
        topic_str = ", ".join(f"{t['topic']} ({t['count']})" for t in topics)
        parts.append(f"\n### Active Topics: {topic_str}")

    # Last session
    last = ctx.get("last_session")
    if last:
        parts.append(
            f"\n### Last Session: {last.get('interactions', 0)} interactions "
            f"({last.get('started', '')} ~ {last.get('ended', '')})"
        )
        if last.get("top_tools"):
            parts.append(f"Top tools: {last['top_tools']}")

    # Stats
    stats = ctx.get("stats", {})
    total = stats.get("total_memories", 0)
    lang = stats.get("language", "unknown")
    if total > 0:
        parts.append(f"\n---\n{total} memories in knowledge base | Language: {lang}")

    if not any([decisions, prefs, topics, last]):
        parts.append("\nNo recent context available. This looks like a fresh start.")

    return "\n".join(parts)
