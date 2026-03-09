"""Tests for auto-learn toggle and review (v0.7.0)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from src.config import AutoLearnConfig


class TestAutoLearnConfig:
    def test_defaults(self):
        cfg = AutoLearnConfig()
        assert cfg.enabled is True
        assert cfg.min_confidence == 0.75
        assert cfg.min_interactions_for_summary == 3

    def test_custom_values(self):
        cfg = AutoLearnConfig(enabled=False, min_confidence=0.9, min_interactions_for_summary=5)
        assert cfg.enabled is False
        assert cfg.min_confidence == 0.9
        assert cfg.min_interactions_for_summary == 5


class TestToggleAutoLearn:
    def test_check_status(self):
        from src.core import toggle_auto_learn
        result = toggle_auto_learn(None)
        assert "Auto-learn is" in result
        assert "Min confidence" in result

    def test_toggle_off(self):
        from src.core import toggle_auto_learn
        from src.config import workspace

        original = workspace.auto_learn.enabled
        try:
            result = toggle_auto_learn(False)
            assert "OFF" in result
            assert workspace.auto_learn.enabled is False
        finally:
            # Restore
            workspace.auto_learn = AutoLearnConfig(enabled=original)

    def test_toggle_on(self):
        from src.core import toggle_auto_learn
        from src.config import workspace

        workspace.auto_learn = AutoLearnConfig(enabled=False)
        try:
            result = toggle_auto_learn(True)
            assert "ON" in result
            assert workspace.auto_learn.enabled is True
        finally:
            workspace.auto_learn = AutoLearnConfig(enabled=True)


class TestReviewLearned:
    def test_no_auto_memories(self, tmp_path):
        from src.core import review_learned
        with patch("src.core._memory_dir" if hasattr(__import__("src.core", fromlist=["_memory_dir"]), "_memory_dir") else "src.memory._memory_dir", return_value=tmp_path):
            result = review_learned()
            assert "No auto-learned" in result

    def test_finds_auto_memories(self, tmp_path):
        from src.core import review_learned

        (tmp_path / "auto_mem.md").write_text(
            "---\ndate: 2026-03-10\nsource: auto-digest-decision\ncategory: decision\n---\n\nUse PostgreSQL"
        )
        (tmp_path / "manual_mem.md").write_text(
            "---\ndate: 2026-03-10\nsource: user-request\ncategory: fact\n---\n\nManual memory"
        )
        with patch("src.memory._memory_dir", return_value=tmp_path):
            result = review_learned()
            assert "auto_mem" in result
            assert "PostgreSQL" in result
            # Manual memory should not appear
            assert "Manual memory" not in result

    def test_respects_limit(self, tmp_path):
        from src.core import review_learned

        for i in range(5):
            (tmp_path / f"auto_{i}.md").write_text(
                f"---\ndate: 2026-03-{10+i}\nsource: auto-digest\ncategory: fact\n---\n\nFact {i}"
            )
        with patch("src.memory._memory_dir", return_value=tmp_path):
            result = review_learned(limit=2)
            # Should only show 2
            assert result.count("auto_") <= 3  # 2 entries + header

    def test_shows_session_summary(self, tmp_path):
        from src.core import review_learned

        (tmp_path / "session.md").write_text(
            "---\ndate: 2026-03-10\nsource: session-end\ncategory: context\n---\n\nSession summary"
        )
        with patch("src.memory._memory_dir", return_value=tmp_path):
            result = review_learned()
            assert "Session summary" in result
