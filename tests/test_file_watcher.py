"""Tests for FileWatcher polling-based file change detection."""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from src.file_watcher import FileWatcher


class TestFileWatcherScan:
    def test_scan_empty_dir(self, tmp_path):
        watcher = FileWatcher(
            watch_dirs=[tmp_path],
            extensions=[".md"],
            on_change=lambda: None,
        )
        snapshot = watcher._scan()
        assert snapshot == {}

    def test_scan_finds_matching_files(self, tmp_path):
        (tmp_path / "a.md").write_text("hello")
        (tmp_path / "b.txt").write_text("world")

        watcher = FileWatcher(
            watch_dirs=[tmp_path],
            extensions=[".md"],
            on_change=lambda: None,
        )
        snapshot = watcher._scan()
        assert len(snapshot) == 1
        assert str(tmp_path / "a.md") in snapshot

    def test_scan_multiple_extensions(self, tmp_path):
        (tmp_path / "a.md").write_text("a")
        (tmp_path / "b.csv").write_text("b")
        (tmp_path / "c.py").write_text("c")

        watcher = FileWatcher(
            watch_dirs=[tmp_path],
            extensions=[".md", ".csv"],
            on_change=lambda: None,
        )
        snapshot = watcher._scan()
        assert len(snapshot) == 2

    def test_scan_nonexistent_dir(self, tmp_path):
        watcher = FileWatcher(
            watch_dirs=[tmp_path / "nonexistent"],
            extensions=[".md"],
            on_change=lambda: None,
        )
        snapshot = watcher._scan()
        assert snapshot == {}

    def test_scan_recursive(self, tmp_path):
        sub = tmp_path / "sub" / "deep"
        sub.mkdir(parents=True)
        (sub / "nested.md").write_text("nested")

        watcher = FileWatcher(
            watch_dirs=[tmp_path],
            extensions=[".md"],
            on_change=lambda: None,
        )
        snapshot = watcher._scan()
        assert len(snapshot) == 1


class TestFileWatcherChanges:
    def test_has_changes_new_file(self, tmp_path):
        watcher = FileWatcher(
            watch_dirs=[tmp_path],
            extensions=[".md"],
            on_change=lambda: None,
        )
        watcher._snapshot = {}
        new_snapshot = {str(tmp_path / "new.md"): 1000.0}
        assert watcher._has_changes(new_snapshot)

    def test_has_changes_deleted_file(self, tmp_path):
        watcher = FileWatcher(
            watch_dirs=[tmp_path],
            extensions=[".md"],
            on_change=lambda: None,
        )
        watcher._snapshot = {str(tmp_path / "old.md"): 1000.0}
        assert watcher._has_changes({})

    def test_has_changes_modified_file(self, tmp_path):
        path = str(tmp_path / "file.md")
        watcher = FileWatcher(
            watch_dirs=[tmp_path],
            extensions=[".md"],
            on_change=lambda: None,
        )
        watcher._snapshot = {path: 1000.0}
        assert watcher._has_changes({path: 2000.0})

    def test_no_changes(self, tmp_path):
        path = str(tmp_path / "file.md")
        watcher = FileWatcher(
            watch_dirs=[tmp_path],
            extensions=[".md"],
            on_change=lambda: None,
        )
        watcher._snapshot = {path: 1000.0}
        assert not watcher._has_changes({path: 1000.0})


class TestFileWatcherLifecycle:
    def test_start_stop(self, tmp_path):
        watcher = FileWatcher(
            watch_dirs=[tmp_path],
            extensions=[".md"],
            on_change=lambda: None,
            poll_interval=0.1,
        )
        watcher.start()
        assert watcher._thread is not None
        assert watcher._thread.is_alive()

        watcher.stop()
        assert watcher._thread is None

    def test_double_start_no_duplicate(self, tmp_path):
        watcher = FileWatcher(
            watch_dirs=[tmp_path],
            extensions=[".md"],
            on_change=lambda: None,
            poll_interval=0.1,
        )
        watcher.start()
        thread1 = watcher._thread
        watcher.start()  # Should not create new thread
        assert watcher._thread is thread1
        watcher.stop()

    def test_double_stop_safe(self, tmp_path):
        watcher = FileWatcher(
            watch_dirs=[tmp_path],
            extensions=[".md"],
            on_change=lambda: None,
            poll_interval=0.1,
        )
        watcher.start()
        watcher.stop()
        watcher.stop()  # Should not raise

    def test_callback_on_change(self, tmp_path):
        callback_count = {"n": 0}

        def on_change():
            callback_count["n"] += 1

        (tmp_path / "initial.md").write_text("hello")

        watcher = FileWatcher(
            watch_dirs=[tmp_path],
            extensions=[".md"],
            on_change=on_change,
            poll_interval=0.1,
            debounce=0.05,
        )
        watcher.start()
        time.sleep(0.15)  # Let initial scan complete

        # Create a new file to trigger change
        (tmp_path / "new.md").write_text("new content")
        time.sleep(0.5)  # Wait for poll + debounce + callback

        watcher.stop()
        assert callback_count["n"] >= 1
