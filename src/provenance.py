"""Provenance chain: track the origin and lineage of every memory.

Each memory carries provenance metadata showing where it came from,
which session created it, and what parent memories it was derived from
(e.g., when consolidated or superseded).

No LLM calls — metadata bookkeeping only.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def build_provenance(
    source: str = "conversation",
    session_id: str | None = None,
    parent_ids: list[str] | None = None,
    source_document: str | None = None,
    tool_name: str | None = None,
) -> dict:
    """Build a provenance record for a new memory.

    Args:
        source: Origin type (conversation, auto-learn, consolidation, etc.).
        session_id: The session that created this memory.
        parent_ids: IDs of parent memories (for consolidation/supersede).
        source_document: Path of source document (for doc-extracted memories).
        tool_name: The MCP tool that triggered creation.

    Returns:
        Dict with provenance fields.
    """
    if session_id is None:
        try:
            from src.interaction_log import SESSION_ID
            session_id = SESSION_ID
        except Exception:
            session_id = "unknown"

    prov: dict = {
        "created_by": source,
        "session_id": session_id,
        "created_at": datetime.now().isoformat(),
    }

    if parent_ids:
        prov["derived_from"] = parent_ids
    if source_document:
        prov["source_document"] = source_document
    if tool_name:
        prov["tool"] = tool_name

    return prov


def format_provenance_yaml(prov: dict) -> str:
    """Format provenance dict as YAML-compatible frontmatter string."""
    lines = ["provenance:"]
    for key, value in prov.items():
        if isinstance(value, list):
            lines.append(f"  {key}:")
            for item in value:
                lines.append(f"    - {item}")
        else:
            lines.append(f"  {key}: {value}")
    return "\n".join(lines)


def extract_provenance(file_path: Path | str) -> dict | None:
    """Extract provenance metadata from a memory file's frontmatter.

    Returns:
        Dict with provenance fields, or None if no provenance found.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        return None

    text = file_path.read_text(encoding="utf-8")

    # Parse YAML frontmatter
    m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return None

    frontmatter = m.group(1)

    # Look for provenance block — capture all indented lines after "provenance:"
    prov_match = re.search(
        r"provenance:\n((?:[ ]{2,}.+\n?)*)", frontmatter
    )
    if not prov_match:
        return None

    prov_lines = prov_match.group(1)
    prov: dict = {}

    current_key = None
    current_list: list[str] = []

    for line in prov_lines.split("\n"):
        line = line.rstrip()
        if not line:
            continue
        # List item (4+ spaces + "- ")
        if re.match(r"^\s{4,}- ", line):
            item = line.strip().lstrip("- ")
            current_list.append(item)
        # Key-value or key-only (2 spaces + word + ":")
        elif re.match(r"^\s{2}\w+:", line):
            # Save pending list from previous key
            if current_key and current_list:
                prov[current_key] = current_list
                current_list = []
            stripped = line.strip()
            if ": " in stripped:
                key, val = stripped.split(": ", 1)
                current_key = key
                prov[current_key] = val
            else:
                # Key with no value (e.g. "derived_from:") — next lines are list items
                current_key = stripped.rstrip(":")
                current_list = []

    if current_key and current_list:
        prov[current_key] = current_list

    return prov if prov else None


def trace_lineage(memory_id: str, max_depth: int = 10) -> list[dict]:
    """Trace the lineage of a memory back through its parent chain.

    Args:
        memory_id: The memory filename stem to trace.
        max_depth: Maximum depth to traverse.

    Returns:
        List of provenance records from newest to oldest.
    """
    from src.memory import _memory_dir

    mem_dir = _memory_dir()
    chain: list[dict] = []
    visited: set[str] = set()
    current_ids = [memory_id]

    for _ in range(max_depth):
        if not current_ids:
            break

        next_ids: list[str] = []
        for mid in current_ids:
            if mid in visited:
                continue
            visited.add(mid)

            # Find the file
            candidates = list(mem_dir.glob(f"{mid}*"))
            if not candidates:
                chain.append({"id": mid, "status": "not_found"})
                continue

            prov = extract_provenance(candidates[0])
            entry = {"id": mid, "file": candidates[0].name}
            if prov:
                entry.update(prov)
                parents = prov.get("derived_from", [])
                if isinstance(parents, list):
                    next_ids.extend(parents)
            chain.append(entry)

        current_ids = next_ids

    return chain


def get_provenance_stats() -> dict:
    """Get aggregate provenance statistics across all memories."""
    from src.memory import _memory_dir

    mem_dir = _memory_dir()
    stats: dict = {
        "total_memories": 0,
        "with_provenance": 0,
        "without_provenance": 0,
        "by_source": {},
        "by_session": {},
        "derived_count": 0,
    }

    for f in mem_dir.glob("*.md"):
        stats["total_memories"] += 1
        prov = extract_provenance(f)
        if prov:
            stats["with_provenance"] += 1
            source = prov.get("created_by", "unknown")
            stats["by_source"][source] = stats["by_source"].get(source, 0) + 1
            session = prov.get("session_id", "unknown")
            stats["by_session"][session] = stats["by_session"].get(session, 0) + 1
            if prov.get("derived_from"):
                stats["derived_count"] += 1
        else:
            stats["without_provenance"] += 1

    return stats


def format_lineage(chain: list[dict]) -> str:
    """Format a lineage chain as readable text."""
    if not chain:
        return "No lineage information available."

    parts: list[str] = []
    for i, entry in enumerate(chain):
        prefix = "  " * i + ("└─ " if i > 0 else "")
        mid = entry.get("id", "unknown")
        source = entry.get("created_by", "?")
        session = entry.get("session_id", "?")
        created = entry.get("created_at", "")[:16]
        status = entry.get("status", "")

        if status == "not_found":
            parts.append(f"{prefix}[{mid}] (file not found)")
        else:
            line = f"{prefix}[{mid}] via {source} (session: {session}"
            if created:
                line += f", {created}"
            line += ")"
            parents = entry.get("derived_from", [])
            if parents:
                line += f" ← derived from {', '.join(parents)}"
            parts.append(line)

    return "\n".join(parts)
