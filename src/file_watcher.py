"""File watcher for auto-sync on document changes."""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)


class FileWatcher:
    """Watch workspace directories for file changes and trigger sync.

    Uses polling (no external dependency like watchdog) to detect
    new, modified, or deleted files. Runs in a background thread.
    """

    def __init__(
        self,
        watch_dirs: list[Path],
        extensions: list[str],
        on_change: Callable[[], None],
        poll_interval: float = 30.0,
        debounce: float = 5.0,
    ) -> None:
        self._watch_dirs = watch_dirs
        self._extensions = set(ext.lower() for ext in extensions)
        self._on_change = on_change
        self._poll_interval = poll_interval
        self._debounce = debounce
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._snapshot: dict[str, float] = {}

    def _scan(self) -> dict[str, float]:
        """Build a snapshot of file paths -> mtime."""
        snapshot = {}
        for d in self._watch_dirs:
            if not d.exists():
                continue
            for ext in self._extensions:
                for f in d.rglob(f"*{ext}"):
                    try:
                        snapshot[str(f)] = f.stat().st_mtime
                    except (OSError, PermissionError):
                        continue
        return snapshot

    def _has_changes(self, new_snapshot: dict[str, float]) -> bool:
        """Compare snapshots to detect changes."""
        if set(new_snapshot.keys()) != set(self._snapshot.keys()):
            return True
        for path, mtime in new_snapshot.items():
            if self._snapshot.get(path) != mtime:
                return True
        return False

    def _run(self) -> None:
        """Polling loop."""
        self._snapshot = self._scan()
        logger.info(
            "File watcher started: %d files across %d dirs (poll every %.0fs)",
            len(self._snapshot),
            len(self._watch_dirs),
            self._poll_interval,
        )

        while not self._stop_event.is_set():
            self._stop_event.wait(self._poll_interval)
            if self._stop_event.is_set():
                break

            new_snapshot = self._scan()
            if self._has_changes(new_snapshot):
                logger.info("File changes detected, waiting %.0fs debounce...", self._debounce)
                self._stop_event.wait(self._debounce)
                if self._stop_event.is_set():
                    break

                # Re-scan after debounce to catch rapid successive saves
                new_snapshot = self._scan()
                self._snapshot = new_snapshot

                try:
                    self._on_change()
                    logger.info("Auto-sync triggered by file watcher")
                except Exception as exc:
                    logger.warning("Auto-sync failed: %s", exc)

    def start(self) -> None:
        """Start watching in a background thread."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="tessera-watcher")
        self._thread.start()

    def stop(self) -> None:
        """Stop the watcher."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None
        logger.info("File watcher stopped")
