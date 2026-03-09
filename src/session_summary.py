"""Session summary: generate a summary of a session's interactions.

When a session ends, this module analyzes the interaction log and produces
a concise summary that gets saved as a memory for cross-session continuity.
No LLM calls — uses heuristics and pattern matching.
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime

logger = logging.getLogger(__name__)


def generate_session_summary(interactions: list[dict]) -> str | None:
    """Generate a text summary from a list of session interactions.

    Args:
        interactions: List of dicts with 'tool_name', 'input_summary',
                      'output_summary', 'timestamp'.

    Returns:
        A summary string, or None if the session is too short to summarize.
    """
    if not interactions or len(interactions) < 3:
        return None

    # Count tool usage
    tool_counts: Counter[str] = Counter()
    for ix in interactions:
        tool_counts[ix.get("tool_name", "unknown")] += 1

    # Extract time range
    timestamps = [ix.get("timestamp", "") for ix in interactions if ix.get("timestamp")]
    if timestamps:
        first = timestamps[-1][:19]  # interactions are DESC order
        last = timestamps[0][:19]
    else:
        first = last = "unknown"

    # Extract search queries
    queries: list[str] = []
    for ix in interactions:
        inp = ix.get("input_summary", "")
        if "query=" in inp:
            # Extract query value from input_summary like "query='some query'"
            start = inp.find("query=")
            if start >= 0:
                rest = inp[start + 6:]
                # Handle quoted strings
                if rest.startswith("'") or rest.startswith('"'):
                    quote = rest[0]
                    end = rest.find(quote, 1)
                    if end > 0:
                        queries.append(rest[1:end])
                else:
                    # Unquoted, take until space
                    end = rest.find(" ")
                    queries.append(rest[:end] if end > 0 else rest)

    # Extract remembered content
    remembered: list[str] = []
    for ix in interactions:
        if ix.get("tool_name") in ("remember", "learn"):
            inp = ix.get("input_summary", "")
            if "content=" in inp:
                start = inp.find("content=")
                rest = inp[start + 8:]
                if rest.startswith("'") or rest.startswith('"'):
                    quote = rest[0]
                    end = rest.find(quote, 1)
                    if end > 0:
                        remembered.append(rest[1:end])

    # Build summary
    parts: list[str] = []
    parts.append(f"Session ({first} ~ {last}): {len(interactions)} interactions")

    # Tool usage
    top_tools = tool_counts.most_common(5)
    tool_str = ", ".join(f"{name} x{count}" for name, count in top_tools)
    parts.append(f"Tools used: {tool_str}")

    # Search queries
    if queries:
        unique_queries = list(dict.fromkeys(queries))[:5]
        parts.append(f"Searched: {', '.join(unique_queries)}")

    # Remembered items
    if remembered:
        for item in remembered[:3]:
            parts.append(f"Remembered: {item[:100]}")

    return "\n".join(parts)


def save_session_summary(session_id: str, interactions: list[dict]) -> dict | None:
    """Generate and save a session summary as a memory.

    Args:
        session_id: The session ID to summarize.
        interactions: List of interaction dicts from the session.

    Returns:
        Dict with file_path and indexed status, or None if too short.
    """
    summary = generate_session_summary(interactions)
    if not summary:
        logger.debug("Session %s too short to summarize (%d interactions)", session_id, len(interactions))
        return None

    from src.memory import save_memory, index_memory

    file_path = save_memory(
        content=summary,
        tags=["session-summary", session_id],
        source="session-end",
        category="context",
        dedup=False,  # Session summaries are unique
    )

    try:
        indexed = index_memory(file_path)
    except Exception as exc:
        logger.warning("Failed to index session summary: %s", exc)
        indexed = 0

    logger.info("Session summary saved: %s", file_path)
    return {"file_path": str(file_path), "indexed": indexed > 0}
