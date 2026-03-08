"""Detect stale/outdated documents in the Tessera workspace.

Checks file modification times against a configurable threshold and
produces structured reports grouped by project.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from src.config import workspace
from src.sync import FileMetaDB

logger = logging.getLogger(__name__)


def _extract_project(file_path: str) -> str:
    """Extract project ID from a file path using workspace project keys.

    Scans the path string for any known project root directory. Falls back
    to ``"other"`` when no project matches.

    Args:
        file_path: Absolute or relative file path string.

    Returns:
        Matching project ID or ``"other"``.
    """
    for project_id, project_cfg in workspace.projects.items():
        if project_cfg.root in file_path:
            return project_id
    return "other"


def _file_mtime_utc(file_path: str) -> datetime | None:
    """Return the file's mtime as a timezone-aware UTC datetime.

    Args:
        file_path: Path to the file on disk.

    Returns:
        UTC datetime of last modification, or ``None`` if the file is
        inaccessible.
    """
    try:
        mtime = Path(file_path).stat().st_mtime
        return datetime.fromtimestamp(mtime, tz=timezone.utc)
    except OSError:
        logger.debug("Cannot stat file: %s", file_path)
        return None


def check_freshness(days_threshold: int = 90) -> list[dict]:
    """Return a list of stale tracked files exceeding *days_threshold*.

    Opens its own :class:`FileMetaDB` connection, iterates every tracked
    file, and compares the current filesystem mtime against ``now``.

    Args:
        days_threshold: Number of days after which a file is considered
            stale.

    Returns:
        List of dicts sorted by ``days_ago`` descending (oldest first).
        Each dict contains:

        - ``file_path`` -- absolute path string
        - ``file_name`` -- basename of the file
        - ``last_modified`` -- ISO 8601 date string
        - ``days_ago`` -- integer days since last modification
        - ``status`` -- ``"stale"`` (always, since recent files are filtered)
    """
    db = FileMetaDB(workspace.meta_db_path)
    try:
        tracked_paths = db.all_tracked_paths()
    finally:
        db.close()

    now = datetime.now(timezone.utc)
    stale_files: list[dict] = []

    for file_path in tracked_paths:
        mtime_dt = _file_mtime_utc(file_path)
        if mtime_dt is None:
            continue

        delta = now - mtime_dt
        days_ago = delta.days

        if days_ago > days_threshold:
            stale_files.append({
                "file_path": file_path,
                "file_name": Path(file_path).name,
                "last_modified": mtime_dt.strftime("%Y-%m-%d"),
                "days_ago": days_ago,
                "status": "stale",
            })

    stale_files.sort(key=lambda f: f["days_ago"], reverse=True)
    return stale_files


def freshness_summary(days_threshold: int = 90) -> str:
    """Return a Markdown-formatted summary of stale documents.

    Groups stale files by project (derived from workspace project config)
    and lists each file with its name and days since last modification.

    Args:
        days_threshold: Number of days after which a file is considered
            stale.

    Returns:
        Markdown string. Returns ``"All documents are up to date."`` when
        no files exceed the threshold.
    """
    stale = check_freshness(days_threshold)

    if not stale:
        return "All documents are up to date."

    # Group by project
    by_project: dict[str, list[dict]] = defaultdict(list)
    for entry in stale:
        project = _extract_project(entry["file_path"])
        by_project[project].append(entry)

    lines: list[str] = [
        f"# Stale Documents ({len(stale)} files older than {days_threshold} days)",
        "",
    ]

    for project_id in sorted(by_project):
        display_name = project_id
        if project_id in workspace.projects:
            display_name = workspace.projects[project_id].display_name

        files = by_project[project_id]
        lines.append(f"## {display_name}")
        lines.append("")
        for entry in files:
            lines.append(
                f"- **{entry['file_name']}** -- {entry['days_ago']} days ago"
            )
        lines.append("")

    return "\n".join(lines)
