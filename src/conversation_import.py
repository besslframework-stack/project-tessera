"""Import conversations from ChatGPT, Claude, and Gemini exports.

Extracts knowledge (decisions, preferences, facts) from past AI conversations
and converts them to Tessera memories.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)

# Patterns that indicate extractable knowledge
_PREFERENCE_PATTERNS = [
    r"(?:i prefer |i like |i always |i never |i want |my favorite )",
    r"(?:선호|좋아하|항상|싫어|원해)",
]

_DECISION_PATTERNS = [
    r"(?:decided to |going with |chose |choosing |will use |switched to |let's use )",
    r"(?:결정|선택|사용하기로|바꾸기로|전환)",
]

_FACT_PATTERNS = [
    r"(?:the .+ is |note that |remember that |important:|fyi |api .+ endpoint)",
    r"(?:참고|기억해|중요한|알아둘)",
]


def import_chatgpt_conversations(data: str) -> list[dict]:
    """Import from ChatGPT conversation export (conversations.json).

    ChatGPT export format:
    [{"title": "...", "create_time": ..., "mapping": {"id": {"message": ...}}}]
    """
    try:
        conversations = json.loads(data)
    except (json.JSONDecodeError, TypeError):
        return []

    if not isinstance(conversations, list):
        return []

    extracted = []
    for conv in conversations:
        if not isinstance(conv, dict):
            continue

        title = conv.get("title", "Untitled")
        create_time = conv.get("create_time")
        date = _timestamp_to_iso(create_time) if create_time else ""

        # Extract messages from mapping
        mapping = conv.get("mapping", {})
        messages = _extract_chatgpt_messages(mapping)

        # Only process user messages for knowledge extraction
        for msg in messages:
            if msg.get("role") != "user":
                continue
            content = msg.get("content", "").strip()
            if len(content) < 10 or len(content) > 500:
                continue

            category = _classify_content(content)
            if category:
                extracted.append({
                    "content": content,
                    "category": category,
                    "tags": [_sanitize_tag(title)],
                    "date": date,
                    "source": "chatgpt-conversation",
                })

    return extracted


def _extract_chatgpt_messages(mapping: dict) -> list[dict]:
    """Extract messages from ChatGPT mapping structure."""
    messages = []
    for node in mapping.values():
        if not isinstance(node, dict):
            continue
        msg = node.get("message")
        if not isinstance(msg, dict):
            continue
        author = msg.get("author", {})
        role = author.get("role", "") if isinstance(author, dict) else ""
        content_obj = msg.get("content", {})
        if isinstance(content_obj, dict):
            parts = content_obj.get("parts", [])
            text = " ".join(str(p) for p in parts if isinstance(p, str))
        elif isinstance(content_obj, str):
            text = content_obj
        else:
            text = ""
        if text.strip():
            messages.append({"role": role, "content": text.strip()})
    return messages


def import_claude_conversations(data: str) -> list[dict]:
    """Import from Claude conversation export (JSON).

    Claude export format:
    [{"uuid": "...", "name": "...", "created_at": "...", "chat_messages": [{"sender": "human", "text": "..."}]}]
    """
    try:
        conversations = json.loads(data)
    except (json.JSONDecodeError, TypeError):
        return []

    if not isinstance(conversations, list):
        return []

    extracted = []
    for conv in conversations:
        if not isinstance(conv, dict):
            continue

        title = conv.get("name", "Untitled")
        date = conv.get("created_at", "")[:10] if conv.get("created_at") else ""

        messages = conv.get("chat_messages", [])
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            if msg.get("sender") != "human":
                continue
            content = msg.get("text", "").strip()
            if len(content) < 10 or len(content) > 500:
                continue

            category = _classify_content(content)
            if category:
                extracted.append({
                    "content": content,
                    "category": category,
                    "tags": [_sanitize_tag(title)],
                    "date": date,
                    "source": "claude-conversation",
                })

    return extracted


def import_gemini_conversations(data: str) -> list[dict]:
    """Import from Gemini conversation export (JSON).

    Gemini export format:
    [{"title": "...", "messages": [{"role": "user", "content": "...", "timestamp": "..."}]}]
    """
    try:
        conversations = json.loads(data)
    except (json.JSONDecodeError, TypeError):
        return []

    if not isinstance(conversations, list):
        return []

    extracted = []
    for conv in conversations:
        if not isinstance(conv, dict):
            continue

        title = conv.get("title", "Untitled")

        messages = conv.get("messages", [])
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            if msg.get("role") != "user":
                continue
            content = msg.get("content", "").strip()
            if len(content) < 10 or len(content) > 500:
                continue

            date = msg.get("timestamp", "")[:10] if msg.get("timestamp") else ""

            category = _classify_content(content)
            if category:
                extracted.append({
                    "content": content,
                    "category": category,
                    "tags": [_sanitize_tag(title)],
                    "date": date,
                    "source": "gemini-conversation",
                })

    return extracted


def import_plain_text(data: str, source: str = "text") -> list[dict]:
    """Import from plain text — one memory per non-empty line."""
    lines = data.strip().split("\n")
    extracted = []
    for line in lines:
        line = line.strip()
        if len(line) < 10:
            continue
        category = _classify_content(line) or "fact"
        extracted.append({
            "content": line,
            "category": category,
            "tags": [],
            "date": datetime.now().strftime("%Y-%m-%d"),
            "source": source,
        })
    return extracted


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _classify_content(text: str) -> str | None:
    """Classify text as decision, preference, fact, or None (skip)."""
    lower = text.lower()

    for pattern in _PREFERENCE_PATTERNS:
        if re.search(pattern, lower):
            return "preference"

    for pattern in _DECISION_PATTERNS:
        if re.search(pattern, lower):
            return "decision"

    for pattern in _FACT_PATTERNS:
        if re.search(pattern, lower):
            return "fact"

    return None


def _sanitize_tag(title: str) -> str:
    """Convert a conversation title to a clean tag."""
    tag = re.sub(r"[^\w\s가-힣-]", "", title.lower())
    tag = re.sub(r"\s+", "-", tag.strip())
    return tag[:50] if tag else "conversation"


def _timestamp_to_iso(ts: float | int | None) -> str:
    """Convert Unix timestamp to ISO date string."""
    if ts is None:
        return ""
    try:
        return datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d")
    except (ValueError, OSError, OverflowError):
        return ""


def format_import_summary(memories: list[dict]) -> str:
    """Format a summary of imported memories."""
    if not memories:
        return "No extractable knowledge found in the conversation data."

    by_category: dict[str, int] = {}
    by_source: dict[str, int] = {}
    for m in memories:
        cat = m.get("category", "unknown")
        by_category[cat] = by_category.get(cat, 0) + 1
        src = m.get("source", "unknown")
        by_source[src] = by_source.get(src, 0) + 1

    lines = [f"## Conversation Import Summary", f"Extracted {len(memories)} memories:", ""]
    for cat, count in sorted(by_category.items()):
        lines.append(f"- **{cat.title()}**: {count}")
    lines.append("")
    for src, count in sorted(by_source.items()):
        lines.append(f"- Source: {src} ({count})")

    return "\n".join(lines)
