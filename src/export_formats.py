"""Export memories to various formats: Obsidian, Markdown, JSON, CSV.

Enables users to take their knowledge out of Tessera into other tools.
"""

from __future__ import annotations

import csv
import io
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def export_obsidian(memories: list[dict], vault_name: str = "Tessera") -> str:
    """Export memories as Obsidian-compatible markdown with wikilinks.

    Each memory becomes a note with YAML frontmatter and wikilinks
    to tags and categories.

    Returns:
        Multi-file markdown content separated by file markers.
    """
    if not memories:
        return "No memories to export."

    parts = []
    for mem in memories:
        content = mem.get("content", "").strip()
        date = mem.get("date", "")[:10] if mem.get("date") else ""
        category = mem.get("category", "general")
        tags = mem.get("tags", [])
        name = mem.get("name", mem.get("filename", f"memory-{date}"))

        lines = [
            "---",
            f"date: {date}" if date else "date:",
            f"category: {category}",
            f"tags: [{', '.join(tags)}]" if tags else "tags: []",
            f"source: tessera",
            "---",
            "",
            content,
            "",
        ]

        # Add wikilinks
        if tags:
            lines.append("## Links")
            for tag in tags:
                lines.append(f"- [[{tag}]]")
            lines.append(f"- [[{category}]]")

        parts.append(f"=== {name}.md ===\n" + "\n".join(lines))

    header = f"# Tessera Export ({len(memories)} memories)\n"
    header += f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
    return header + "\n\n".join(parts)


def export_markdown(memories: list[dict]) -> str:
    """Export memories as a single markdown document."""
    if not memories:
        return "No memories to export."

    lines = [
        f"# Tessera Knowledge Export",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Total: {len(memories)} memories",
        "",
    ]

    # Group by category
    by_category: dict[str, list[dict]] = {}
    for mem in memories:
        cat = mem.get("category", "general")
        by_category.setdefault(cat, []).append(mem)

    for cat, mems in sorted(by_category.items()):
        lines.append(f"## {cat.title()} ({len(mems)})")
        lines.append("")
        for mem in mems:
            date = mem.get("date", "")[:10] if mem.get("date") else ""
            content = mem.get("content", "").strip().replace("\n", " ")
            if len(content) > 200:
                content = content[:197] + "..."
            tags = mem.get("tags", [])
            tag_str = f" #{' #'.join(tags)}" if tags else ""
            lines.append(f"- [{date}] {content}{tag_str}")
        lines.append("")

    return "\n".join(lines)


def export_csv(memories: list[dict]) -> str:
    """Export memories as CSV."""
    if not memories:
        return "No memories to export."

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["date", "category", "content", "tags", "source"])

    for mem in memories:
        writer.writerow([
            mem.get("date", "")[:10] if mem.get("date") else "",
            mem.get("category", "general"),
            mem.get("content", "").strip(),
            ",".join(mem.get("tags", [])),
            mem.get("source", ""),
        ])

    return output.getvalue()


def export_json_pretty(memories: list[dict]) -> str:
    """Export memories as formatted JSON."""
    if not memories:
        return "[]"

    clean = []
    for mem in memories:
        clean.append({
            "date": mem.get("date", "")[:10] if mem.get("date") else "",
            "category": mem.get("category", "general"),
            "content": mem.get("content", "").strip(),
            "tags": mem.get("tags", []),
            "source": mem.get("source", ""),
        })

    return json.dumps(clean, indent=2, ensure_ascii=False)
