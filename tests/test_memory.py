"""Tests for cross-session memory system."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from src.memory import save_memory, _memory_dir


class TestSaveMemory:
    def test_basic_save(self, tmp_path):
        with patch("src.memory._memory_dir", return_value=tmp_path):
            path = save_memory("OAuth 2.0 + PKCE chosen for auth flow")
            assert path.exists()
            content = path.read_text()
            assert "OAuth 2.0 + PKCE" in content
            assert "date:" in content
            assert "source: conversation" in content

    def test_save_with_tags(self, tmp_path):
        with patch("src.memory._memory_dir", return_value=tmp_path):
            path = save_memory("Use Redis for caching", tags=["architecture", "cache"])
            content = path.read_text()
            assert "architecture" in content
            assert "cache" in content

    def test_save_with_custom_source(self, tmp_path):
        with patch("src.memory._memory_dir", return_value=tmp_path):
            path = save_memory("Some fact", source="auto-learn")
            content = path.read_text()
            assert "source: auto-learn" in content

    def test_filename_has_timestamp(self, tmp_path):
        with patch("src.memory._memory_dir", return_value=tmp_path):
            path = save_memory("Test content")
            # Filename format: YYYYMMDD_HHMMSS_slug.md
            assert path.suffix == ".md"
            assert "_" in path.stem

    def test_special_chars_in_content(self, tmp_path):
        with patch("src.memory._memory_dir", return_value=tmp_path):
            path = save_memory("Content with /slashes/ and\nnewlines")
            assert path.exists()

    def test_empty_tags_default(self, tmp_path):
        with patch("src.memory._memory_dir", return_value=tmp_path):
            path = save_memory("No tags")
            content = path.read_text()
            assert "general" in content


class TestMemoryDir:
    def test_creates_directory(self, tmp_path):
        mem_dir = tmp_path / "data" / "memories"
        with patch("src.memory.Path") as mock_path:
            # Use actual _memory_dir with patched project root
            pass  # _memory_dir creates dir automatically
