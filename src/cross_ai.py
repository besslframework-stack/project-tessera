"""Cross-AI memory format converters.

Export Tessera memories to ChatGPT/Gemini formats and import from them.
Enables users to move their knowledge between AI tools seamlessly.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tessera → ChatGPT
# ---------------------------------------------------------------------------

def export_for_chatgpt(memories: list[dict]) -> str:
    """Export memories as ChatGPT-compatible memory JSON.

    ChatGPT memory format:
    [{"id": "...", "content": "...", "created_at": "..."}]
    """
    if not memories:
        return "[]"

    items = []
    for i, mem in enumerate(memories):
        content = mem.get("content", "").strip()
        category = mem.get("category", "general")
        tags = mem.get("tags", [])

        # ChatGPT memories are plain text with optional context
        text = content
        if tags:
            text += f" (tags: {', '.join(tags)})"
        if category != "general":
            text += f" [{category}]"

        items.append({
            "id": mem.get("id", f"tessera-{i}"),
            "content": text,
            "created_at": _normalize_date(mem.get("date", "")),
        })

    return json.dumps(items, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# ChatGPT → Tessera
# ---------------------------------------------------------------------------

def import_from_chatgpt(data: str) -> list[dict]:
    """Convert ChatGPT memory JSON to Tessera format.

    Accepts ChatGPT's memory export format and returns Tessera-compatible dicts.
    """
    try:
        items = json.loads(data)
    except (json.JSONDecodeError, TypeError):
        return []

    if not isinstance(items, list):
        return []

    memories = []
    for item in items:
        if not isinstance(item, dict):
            continue
        content = item.get("content", "").strip()
        if not content:
            continue

        # Extract category hint from [category] suffix
        category = "fact"
        tags = []
        if content.endswith("]") and "[" in content:
            bracket_start = content.rfind("[")
            cat_hint = content[bracket_start + 1:-1].strip().lower()
            if cat_hint in ("decision", "preference", "fact", "procedure", "reference"):
                category = cat_hint
                content = content[:bracket_start].strip()

        # Extract tags from (tags: ...) suffix
        if content.endswith(")") and "(tags:" in content:
            paren_start = content.rfind("(tags:")
            tag_str = content[paren_start + 6:-1].strip()
            tags = [t.strip() for t in tag_str.split(",") if t.strip()]
            content = content[:paren_start].strip()

        memories.append({
            "content": content,
            "category": category,
            "tags": tags,
            "date": item.get("created_at", ""),
            "source": "chatgpt-import",
        })

    return memories


# ---------------------------------------------------------------------------
# Tessera → Gemini
# ---------------------------------------------------------------------------

def export_for_gemini(memories: list[dict]) -> str:
    """Export memories as Gemini-compatible context format.

    Gemini uses a structured context format with facts and preferences.
    """
    if not memories:
        return json.dumps({"facts": [], "preferences": []}, indent=2)

    facts = []
    preferences = []

    for mem in memories:
        content = mem.get("content", "").strip()
        category = mem.get("category", "general")
        tags = mem.get("tags", [])
        date = _normalize_date(mem.get("date", ""))[:10]

        entry = {
            "text": content,
            "source": "tessera",
            "date": date,
        }
        if tags:
            entry["topics"] = tags

        if category == "preference":
            preferences.append(entry)
        else:
            facts.append(entry)

    return json.dumps(
        {"facts": facts, "preferences": preferences},
        indent=2,
        ensure_ascii=False,
    )


# ---------------------------------------------------------------------------
# Gemini → Tessera
# ---------------------------------------------------------------------------

def import_from_gemini(data: str) -> list[dict]:
    """Convert Gemini context JSON to Tessera format."""
    try:
        parsed = json.loads(data)
    except (json.JSONDecodeError, TypeError):
        return []

    if not isinstance(parsed, dict):
        return []

    memories = []

    for item in parsed.get("preferences", []):
        if not isinstance(item, dict):
            continue
        content = item.get("text", "").strip()
        if not content:
            continue
        memories.append({
            "content": content,
            "category": "preference",
            "tags": item.get("topics", []),
            "date": item.get("date", ""),
            "source": "gemini-import",
        })

    for item in parsed.get("facts", []):
        if not isinstance(item, dict):
            continue
        content = item.get("text", "").strip()
        if not content:
            continue
        memories.append({
            "content": content,
            "category": "fact",
            "tags": item.get("topics", []),
            "date": item.get("date", ""),
            "source": "gemini-import",
        })

    return memories


# ---------------------------------------------------------------------------
# Universal Tessera export (standard format)
# ---------------------------------------------------------------------------

def export_standard(memories: list[dict]) -> str:
    """Export as Tessera standard JSON — the canonical interchange format.

    Other tools can import this directly.
    """
    if not memories:
        return json.dumps({"version": "1.0", "memories": []}, indent=2)

    clean = []
    for mem in memories:
        clean.append({
            "content": mem.get("content", "").strip(),
            "category": mem.get("category", "general"),
            "tags": mem.get("tags", []),
            "date": _normalize_date(mem.get("date", "")),
            "source": mem.get("source", ""),
        })

    return json.dumps(
        {"version": "1.0", "source": "tessera", "memories": clean},
        indent=2,
        ensure_ascii=False,
    )


def import_standard(data: str) -> list[dict]:
    """Import from Tessera standard JSON format."""
    try:
        parsed = json.loads(data)
    except (json.JSONDecodeError, TypeError):
        return []

    if not isinstance(parsed, dict):
        return []

    memories = []
    for item in parsed.get("memories", []):
        if not isinstance(item, dict):
            continue
        content = item.get("content", "").strip()
        if not content:
            continue
        memories.append({
            "content": content,
            "category": item.get("category", "fact"),
            "tags": item.get("tags", []),
            "date": item.get("date", ""),
            "source": item.get("source", "tessera-import"),
        })

    return memories


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_date(date_str: str) -> str:
    """Normalize date string to ISO format."""
    if not date_str:
        return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    # Already ISO-like
    if "T" in str(date_str):
        return str(date_str)[:19]
    # Date only
    return str(date_str)[:10] + "T00:00:00"
