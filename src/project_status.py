"""Project status tracking and decision extraction."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from pathlib import Path

from src.config import workspace

logger = logging.getLogger(__name__)

_SKIP_DIRS = frozenset({
    "node_modules", ".next", ".venv", "__pycache__", ".git",
    "data", ".cache", "dist", "build", ".nuxt",
})


def _walk_project(root: Path):
    """Walk project tree, skipping heavy directories."""
    try:
        for item in root.iterdir():
            if item.is_dir():
                if item.name in _SKIP_DIRS or item.name.startswith("."):
                    continue
                yield item
                yield from _walk_project(item)
            else:
                yield item
    except PermissionError:
        pass


def get_project_status(project_id: str) -> str:
    """Get status for a specific project.

    Reads HANDOFF.md, lists recent files, and counts files by type.

    Args:
        project_id: Project identifier from workspace.yaml.

    Returns:
        Formatted project status.
    """
    proj = workspace.projects.get(project_id)
    if proj is None:
        available = ", ".join(workspace.projects.keys())
        return f"Unknown project: {project_id}. Available: {available}"

    project_root = workspace.root / proj.root
    if not project_root.exists():
        return f"Project directory not found: {project_root}"

    lines = [f"# {proj.display_name} ({project_id})", ""]

    # HANDOFF.md
    handoff = project_root / "HANDOFF.md"
    if handoff.exists():
        content = handoff.read_text(encoding="utf-8")
        # Truncate if too long
        if len(content) > 3000:
            content = content[:3000] + "\n... (truncated)"
        lines.append("## Current State (HANDOFF.md)")
        lines.append(content)
        lines.append("")
    else:
        lines.append("## Current State")
        lines.append("No HANDOFF.md found.")
        lines.append("")

    # Recent files (modified within 7 days)
    cutoff = datetime.now() - timedelta(days=7)
    recent = []
    for f in _walk_project(project_root):
        if not f.is_file():
            continue
        if f.suffix.lower() not in (".md", ".csv", ".txt", ".py", ".tsx", ".ts"):
            continue
        try:
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            if mtime > cutoff:
                rel = f.relative_to(project_root)
                recent.append((rel, mtime))
        except OSError:
            continue

    if recent:
        recent.sort(key=lambda x: x[1], reverse=True)
        lines.append("## Recent Changes (7 days)")
        for rel, mtime in recent[:15]:
            lines.append(f"- {rel} ({mtime.strftime('%m-%d %H:%M')})")
        if len(recent) > 15:
            lines.append(f"  ... and {len(recent) - 15} more files")
        lines.append("")

    # File counts by type
    type_counts: dict[str, int] = {}
    for f in _walk_project(project_root):
        if f.is_file():
            ext = f.suffix.lower() or "(no ext)"
            type_counts[ext] = type_counts.get(ext, 0) + 1

    if type_counts:
        lines.append("## File Counts")
        for ext, count in sorted(type_counts.items(), key=lambda x: -x[1]):
            lines.append(f"- {ext}: {count}")
        lines.append("")

    return "\n".join(lines)


def get_all_projects_summary() -> str:
    """Get a brief summary of all projects.

    Returns:
        Formatted summary of all projects.
    """
    lines = ["# Workspace Status", f"Root: {workspace.root}", ""]

    for pid, proj in workspace.projects.items():
        project_root = workspace.root / proj.root
        exists = project_root.exists()

        status_icon = "+" if exists else "-"
        line = f"[{status_icon}] {proj.display_name} ({pid})"

        if exists:
            handoff = project_root / "HANDOFF.md"
            if handoff.exists():
                # Read first non-empty, non-header line for a quick summary
                try:
                    for text_line in handoff.read_text(encoding="utf-8").splitlines():
                        stripped = text_line.strip()
                        if stripped and not stripped.startswith("#") and stripped != "---":
                            line += f" — {stripped[:80]}"
                            break
                except OSError:
                    pass

            # Count recently modified files
            cutoff = datetime.now() - timedelta(days=7)
            recent_count = 0
            for f in _walk_project(project_root):
                if f.is_file():
                    try:
                        if datetime.fromtimestamp(f.stat().st_mtime) > cutoff:
                            recent_count += 1
                    except OSError:
                        continue
            if recent_count:
                line += f" [{recent_count} files changed in 7d]"

        lines.append(line)

    return "\n".join(lines)


def extract_decisions(project_id: str | None = None, since: str | None = None) -> str:
    """Extract decisions from session logs and decision logs.

    Args:
        project_id: Filter by project. If None, searches all.
        since: Date string (YYYY-MM-DD) to filter from.

    Returns:
        Formatted list of decisions.
    """
    search_dirs = []

    if project_id:
        proj = workspace.projects.get(project_id)
        if proj is None:
            return f"Unknown project: {project_id}"
        proj_root = workspace.root / proj.root
        # Check session_logs and decision_log dirs
        for sub in ("session_logs", "00_decision_log"):
            d = proj_root / sub
            if d.exists():
                search_dirs.append(d)
    else:
        # Search all sources of type session_log or decision_log
        for source in workspace.sources:
            if source.type in ("session_log", "decision_log"):
                d = workspace.resolve_source_path(source)
                if d.exists():
                    search_dirs.append(d)

    since_date = None
    if since:
        try:
            since_date = datetime.strptime(since, "%Y-%m-%d")
        except ValueError:
            return f"Invalid date format: {since}. Use YYYY-MM-DD."

    decisions = []
    decision_patterns = [
        re.compile(r"^[-*]\s*(?:\*\*)?결정[:：]?\s*(?:\*\*)?\s*(.+)", re.IGNORECASE),
        re.compile(r"^[-*]\s*(?:\*\*)?Decision[:：]?\s*(?:\*\*)?\s*(.+)", re.IGNORECASE),
        re.compile(r"^[-*]\s*(?:\*\*)?합의[:：]?\s*(?:\*\*)?\s*(.+)", re.IGNORECASE),
    ]

    for search_dir in search_dirs:
        for md_file in sorted(search_dir.rglob("*.md")):
            # Filter by date if specified
            if since_date:
                # Try to extract date from filename (YYYYMMDD or YYYY-MM-DD pattern)
                date_match = re.search(r"(\d{4})[-_]?(\d{2})[-_]?(\d{2})", md_file.name)
                if date_match:
                    try:
                        file_date = datetime(
                            int(date_match.group(1)),
                            int(date_match.group(2)),
                            int(date_match.group(3)),
                        )
                        if file_date < since_date:
                            continue
                    except ValueError:
                        pass

            try:
                content = md_file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            in_decision_section = False
            for line in content.splitlines():
                stripped = line.strip()

                # Check if we're entering a decision-related section
                if stripped.startswith("#") and any(
                    kw in stripped.lower()
                    for kw in ("결정", "decision", "의사결정", "합의", "주요 변경")
                ):
                    in_decision_section = True
                    continue
                elif stripped.startswith("#"):
                    in_decision_section = False
                    continue

                # Pattern matching for decision lines
                for pattern in decision_patterns:
                    match = pattern.match(stripped)
                    if match:
                        decisions.append({
                            "text": match.group(1).strip(),
                            "source": str(md_file.relative_to(workspace.root)),
                        })
                        break

                # In decision section, capture bullet points
                if in_decision_section and stripped.startswith(("-", "*")) and len(stripped) > 3:
                    text = stripped.lstrip("-* ").strip()
                    if text and not any(d["text"] == text for d in decisions):
                        decisions.append({
                            "text": text,
                            "source": str(md_file.relative_to(workspace.root)),
                        })

    if not decisions:
        return "No decisions found."

    lines = [f"# Extracted Decisions ({len(decisions)})", ""]
    current_source = None
    for d in decisions:
        if d["source"] != current_source:
            current_source = d["source"]
            lines.append(f"## {current_source}")
        lines.append(f"- {d['text']}")

    return "\n".join(lines)
