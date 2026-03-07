"""File and folder organization tools for the workspace."""

from __future__ import annotations

import logging
import shutil
from datetime import datetime
from pathlib import Path

from src.config import workspace

logger = logging.getLogger(__name__)

# Directories to always skip when scanning
_SKIP_DIRS = frozenset({
    "node_modules", ".next", ".venv", "__pycache__", ".git",
    "data", ".cache", "dist", "build", ".nuxt",
})


def _validate_within_workspace(path: Path) -> Path:
    """Resolve and validate that a path is within the workspace root."""
    resolved = path.resolve()
    root = workspace.root.resolve()
    if not str(resolved).startswith(str(root)):
        raise ValueError(f"Path is outside workspace: {path}")
    return resolved


def move_file(src: str, dst: str) -> str:
    """Move a file within the workspace.

    Args:
        src: Source path (absolute or relative to workspace root).
        dst: Destination path (absolute or relative to workspace root).

    Returns:
        Result message.
    """
    src_path = _resolve_path(src)
    dst_path = _resolve_path(dst)

    _validate_within_workspace(src_path)
    _validate_within_workspace(dst_path)

    if not src_path.exists():
        return f"Source not found: {src_path}"

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src_path), str(dst_path))
    logger.info("Moved: %s -> %s", src_path, dst_path)
    return f"Moved: {src_path} -> {dst_path}"


def archive_file(path: str) -> str:
    """Move a file to the archive directory (_archive/YYYY-MM/).

    Args:
        path: File path (absolute or relative to workspace root).

    Returns:
        Result message.
    """
    file_path = _resolve_path(path)
    _validate_within_workspace(file_path)

    if not file_path.exists():
        return f"File not found: {file_path}"

    now = datetime.now()
    archive_dir = workspace.root / workspace.archive_dir / now.strftime("%Y-%m")
    archive_dir.mkdir(parents=True, exist_ok=True)

    dst = archive_dir / file_path.name
    # Avoid overwrite
    if dst.exists():
        stem = dst.stem
        suffix = dst.suffix
        counter = 1
        while dst.exists():
            dst = archive_dir / f"{stem}_{counter}{suffix}"
            counter += 1

    shutil.move(str(file_path), str(dst))
    logger.info("Archived: %s -> %s", file_path, dst)
    return f"Archived: {file_path} -> {dst}"


def rename_file(path: str, new_name: str) -> str:
    """Rename a file in the same directory.

    Args:
        path: File path (absolute or relative to workspace root).
        new_name: New file name (not a path).

    Returns:
        Result message.
    """
    file_path = _resolve_path(path)
    _validate_within_workspace(file_path)

    if not file_path.exists():
        return f"File not found: {file_path}"

    if "/" in new_name or "\\" in new_name:
        return "new_name should be a file name, not a path."

    dst = file_path.parent / new_name
    if dst.exists():
        return f"Target already exists: {dst}"

    file_path.rename(dst)
    logger.info("Renamed: %s -> %s", file_path, dst)
    return f"Renamed: {file_path.name} -> {new_name}"


def suggest_organization(path: str | None = None) -> str:
    """Analyze a directory and suggest cleanup actions.

    Args:
        path: Directory to analyze (default: workspace root).

    Returns:
        Formatted suggestions.
    """
    target = _resolve_path(path) if path else workspace.root
    _validate_within_workspace(target)

    if not target.exists():
        return f"Path not found: {target}"

    suggestions = []

    if target.is_file():
        return f"{target} is a file, not a directory."

    # Check for root-level files that might belong in project folders
    for f in sorted(target.iterdir()):
        if f.is_file() and f.suffix.lower() in (".md", ".csv", ".txt"):
            # Check if it matches a project
            matched = False
            for pid, proj in workspace.projects.items():
                if pid.lower() in f.name.lower():
                    suggestions.append(
                        f"  MOVE: {f.name} -> {proj.root}/ (matches project '{proj.display_name}')"
                    )
                    matched = True
                    break
            if not matched and f.name not in ("CLAUDE.md", "HANDOFF.md", "README.md"):
                suggestions.append(f"  REVIEW: {f.name} (root-level file, consider organizing)")

    # Walk tree once, skipping heavy directories
    all_files = []
    all_dirs = []
    for item in _walk_filtered(target):
        if item.is_file():
            all_files.append(item)
        elif item.is_dir():
            all_dirs.append(item)

    # Check for backup/restored files
    for f in all_files:
        name = f.name.lower()
        if any(pat in name for pat in ("_backup", "_restored", "_old", "_copy")):
            rel = f.relative_to(workspace.root)
            suggestions.append(f"  ARCHIVE: {rel} (backup/temporary file)")

    # Check for large files (>1MB)
    for f in all_files:
        try:
            size = f.stat().st_size
        except OSError:
            continue
        if size > 1_000_000:
            rel = f.relative_to(workspace.root)
            size_mb = size / 1_000_000
            suggestions.append(f"  LARGE: {rel} ({size_mb:.1f}MB)")

    # Check for empty directories
    for d in sorted(all_dirs):
        try:
            if not any(d.iterdir()):
                rel = d.relative_to(workspace.root)
                suggestions.append(f"  EMPTY DIR: {rel}/")
        except OSError:
            continue

    if not suggestions:
        return "No cleanup suggestions. Workspace looks organized."

    return "Cleanup suggestions:\n" + "\n".join(suggestions)


def list_directory(path: str | None = None, recursive: bool = False) -> str:
    """List files in a directory with size and date info.

    Args:
        path: Directory path (default: workspace root).
        recursive: Whether to recurse into subdirectories.

    Returns:
        Formatted file listing.
    """
    target = _resolve_path(path) if path else workspace.root
    _validate_within_workspace(target)

    if not target.exists():
        return f"Path not found: {target}"

    if target.is_file():
        stat = target.stat()
        return f"{target.name}  {_fmt_size(stat.st_size)}  {_fmt_date(stat.st_mtime)}"

    lines = [f"Directory: {target}", ""]
    iterator = sorted(target.rglob("*")) if recursive else sorted(target.iterdir())

    for item in iterator:
        rel = item.relative_to(target)
        if item.is_dir():
            lines.append(f"  {rel}/")
        else:
            stat = item.stat()
            lines.append(f"  {rel}  ({_fmt_size(stat.st_size)}, {_fmt_date(stat.st_mtime)})")

    return "\n".join(lines)


def _walk_filtered(root: Path) -> list[Path]:
    """Walk directory tree, skipping heavy/irrelevant directories."""
    results = []
    try:
        for item in sorted(root.iterdir()):
            if item.is_dir():
                if item.name in _SKIP_DIRS or item.name.startswith("."):
                    continue
                results.append(item)
                results.extend(_walk_filtered(item))
            else:
                results.append(item)
    except PermissionError:
        pass
    return results


def _resolve_path(path: str) -> Path:
    """Resolve a path: absolute paths stay as-is, relative paths are joined to workspace root."""
    p = Path(path)
    if p.is_absolute():
        return p
    return workspace.root / p


def _fmt_size(size: int) -> str:
    if size < 1024:
        return f"{size}B"
    if size < 1_048_576:
        return f"{size / 1024:.1f}KB"
    return f"{size / 1_048_576:.1f}MB"


def _fmt_date(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")
