"""SQLite-based file metadata tracking and incremental sync."""

from __future__ import annotations

import fnmatch
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from src.config import WorkspaceConfig

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    new: list[Path]
    changed: list[Path]
    deleted: list[str]
    unchanged_count: int

    @property
    def has_changes(self) -> bool:
        return bool(self.new or self.changed or self.deleted)

    def summary(self) -> str:
        parts = []
        if self.new:
            parts.append(f"{len(self.new)} new")
        if self.changed:
            parts.append(f"{len(self.changed)} changed")
        if self.deleted:
            parts.append(f"{len(self.deleted)} deleted")
        parts.append(f"{self.unchanged_count} unchanged")
        return ", ".join(parts)


class FileMetaDB:
    """SQLite database for tracking file metadata (mtime, size)."""

    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS file_meta (
                file_path TEXT PRIMARY KEY,
                mtime REAL NOT NULL,
                size INTEGER NOT NULL,
                last_indexed_at TEXT NOT NULL,
                chunk_count INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS sync_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                new_count INTEGER DEFAULT 0,
                changed_count INTEGER DEFAULT 0,
                deleted_count INTEGER DEFAULT 0
            );
        """)
        self._conn.commit()

    def get_file_meta(self, file_path: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM file_meta WHERE file_path = ?", (file_path,)
        ).fetchone()
        return dict(row) if row else None

    def upsert_file(self, file_path: str, mtime: float, size: int, chunk_count: int = 0) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            """INSERT INTO file_meta (file_path, mtime, size, last_indexed_at, chunk_count)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(file_path) DO UPDATE SET
                   mtime = excluded.mtime,
                   size = excluded.size,
                   last_indexed_at = excluded.last_indexed_at,
                   chunk_count = excluded.chunk_count""",
            (file_path, mtime, size, now, chunk_count),
        )
        self._conn.commit()

    def delete_file(self, file_path: str) -> None:
        self._conn.execute("DELETE FROM file_meta WHERE file_path = ?", (file_path,))
        self._conn.commit()

    def all_tracked_paths(self) -> set[str]:
        rows = self._conn.execute("SELECT file_path FROM file_meta").fetchall()
        return {r["file_path"] for r in rows}

    def record_sync(self, result: SyncResult) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT INTO sync_history (timestamp, new_count, changed_count, deleted_count) VALUES (?, ?, ?, ?)",
            (now, len(result.new), len(result.changed), len(result.deleted)),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()


def _should_ignore(path: Path, ignore_patterns: list[str]) -> bool:
    """Check if a path matches any ignore pattern.

    Handles ** glob patterns by checking path segments instead of fnmatch
    (which doesn't match ** across directory boundaries).
    """
    path_str = str(path)
    path_parts = set(path.parts)
    for pat in ignore_patterns:
        if "**" in pat:
            # Extract literal directory/file segments from the pattern
            segments = [s for s in pat.split("/") if s and s != "**" and "*" not in s]
            if segments and all(seg in path_parts for seg in segments):
                return True
        else:
            if fnmatch.fnmatch(path_str, pat):
                return True
    return False


def _collect_source_files(ws: WorkspaceConfig) -> list[Path]:
    """Walk all source directories, filtering by extensions and ignore patterns."""
    files = []
    for source in ws.sources:
        source_path = ws.resolve_source_path(source)
        if not source_path.exists():
            continue
        if source_path.is_file():
            if source_path.suffix.lower() in ws.extensions:
                files.append(source_path)
            continue
        for ext in ws.extensions:
            for f in sorted(source_path.rglob(f"*{ext}")):
                if not _should_ignore(f, ws.ignore_patterns):
                    files.append(f)
    return files


def compute_sync_diff(ws: WorkspaceConfig, meta_db: FileMetaDB) -> SyncResult:
    """Compare filesystem state against DB to find new/changed/deleted files."""
    current_files = _collect_source_files(ws)
    tracked = meta_db.all_tracked_paths()

    new_files = []
    changed_files = []
    unchanged_count = 0

    seen_paths = set()
    for f in current_files:
        fstr = str(f)
        seen_paths.add(fstr)
        stat = f.stat()

        meta = meta_db.get_file_meta(fstr)
        if meta is None:
            new_files.append(f)
        elif stat.st_mtime > meta["mtime"] or stat.st_size != meta["size"]:
            changed_files.append(f)
        else:
            unchanged_count += 1

    deleted = sorted(tracked - seen_paths)

    return SyncResult(
        new=new_files,
        changed=changed_files,
        deleted=deleted,
        unchanged_count=unchanged_count,
    )


def run_incremental_sync(
    ws: WorkspaceConfig,
    meta_db: FileMetaDB,
    vector_store_delete_fn=None,
    ingest_fn=None,
) -> SyncResult:
    """Run incremental sync: delete stale vectors, re-ingest changed files, update DB.

    Args:
        ws: Workspace config.
        meta_db: File metadata DB.
        vector_store_delete_fn: Callable(source_path: str) -> int to delete vectors.
        ingest_fn: Callable(paths: list[Path]) -> int to ingest files.
    """
    diff = compute_sync_diff(ws, meta_db)

    if not diff.has_changes:
        logger.info("No changes detected. %s", diff.summary())
        meta_db.record_sync(diff)
        return diff

    logger.info("Sync diff: %s", diff.summary())

    # 1. Handle deleted files
    for deleted_path in diff.deleted:
        if vector_store_delete_fn:
            count = vector_store_delete_fn(deleted_path)
            logger.info("Deleted %d vectors for removed file: %s", count, deleted_path)
        meta_db.delete_file(deleted_path)

    # 2. Handle changed files (delete old vectors first)
    for changed_file in diff.changed:
        if vector_store_delete_fn:
            vector_store_delete_fn(str(changed_file))

    # 3. Ingest new + changed files
    files_to_ingest = diff.new + diff.changed
    per_file_counts: dict[str, int] = {}
    if files_to_ingest and ingest_fn:
        result = ingest_fn(files_to_ingest)
        if isinstance(result, tuple):
            count, per_file_counts = result
        else:
            count = result
        logger.info("Ingested %d documents from %d files", count, len(files_to_ingest))

    # 4. Update metadata DB with per-file chunk counts
    for f in files_to_ingest:
        stat = f.stat()
        chunk_count = per_file_counts.get(str(f), 0)
        meta_db.upsert_file(str(f), stat.st_mtime, stat.st_size, chunk_count=chunk_count)

    meta_db.record_sync(diff)
    return diff
