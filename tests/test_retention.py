"""Tests for retention policy (Phase 8b)."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.retention import apply_retention_policy, get_retention_summary


class TestApplyRetentionPolicy:
    @patch("src.memory.recall_memories", return_value=[])
    def test_no_memories(self, mock_recall):
        result = apply_retention_policy()
        assert result["candidates"] == 0
        assert result["archived"] == 0
        assert result["reasons"] == []

    @patch("src.memory_confidence.compute_confidence")
    @patch("src.memory.recall_memories")
    def test_old_memory_detected(self, mock_recall, mock_conf):
        old_date = (datetime.now() - timedelta(days=200)).isoformat()
        mock_recall.return_value = [
            {"content": "Old memory about databases", "date": old_date, "category": "fact", "tags": "db", "file_path": "/tmp/old.md"},
        ]
        mock_conf.return_value = {"score": 0.5}
        result = apply_retention_policy(max_age_days=180, dry_run=True)
        assert result["candidates"] == 1
        assert result["archived"] == 0
        assert result["reasons"][0]["reason"] == "exceeded_max_age"

    @patch("src.memory_confidence.compute_confidence")
    @patch("src.memory.recall_memories")
    def test_low_confidence_detected(self, mock_recall, mock_conf):
        recent_date = datetime.now().isoformat()
        mock_recall.return_value = [
            {"content": "Some content with enough length to pass orphan check", "date": recent_date, "category": "fact", "tags": "test", "file_path": "/tmp/low.md"},
        ]
        mock_conf.return_value = {"score": 0.1}
        result = apply_retention_policy(min_confidence=0.3, dry_run=True)
        assert result["candidates"] == 1
        assert result["reasons"][0]["reason"] == "low_confidence"

    @patch("src.memory_confidence.compute_confidence")
    @patch("src.memory.recall_memories")
    def test_orphaned_detected(self, mock_recall, mock_conf):
        recent_date = datetime.now().isoformat()
        mock_recall.return_value = [
            {"content": "short", "date": recent_date, "category": "", "tags": "", "file_path": "/tmp/orphan.md"},
        ]
        mock_conf.return_value = {"score": 0.5}
        result = apply_retention_policy(dry_run=True)
        assert result["candidates"] == 1
        assert result["reasons"][0]["reason"] == "orphaned"

    @patch("src.memory_confidence.compute_confidence")
    @patch("src.memory.recall_memories")
    def test_healthy_memory_not_flagged(self, mock_recall, mock_conf):
        recent_date = datetime.now().isoformat()
        mock_recall.return_value = [
            {"content": "This is a healthy memory with enough content and good metadata", "date": recent_date, "category": "fact", "tags": "important", "file_path": "/tmp/good.md"},
        ]
        mock_conf.return_value = {"score": 0.7}
        result = apply_retention_policy(dry_run=True)
        assert result["candidates"] == 0

    @patch("src.memory.supersede_memory", return_value=True)
    @patch("src.memory._memory_dir")
    @patch("src.memory_confidence.compute_confidence")
    @patch("src.memory.recall_memories")
    def test_non_dry_run_archives(self, mock_recall, mock_conf, mock_memdir, mock_sup, tmp_path):
        old_date = (datetime.now() - timedelta(days=200)).isoformat()
        mem_file = tmp_path / "old.md"
        mem_file.write_text("old content")

        mock_recall.return_value = [
            {"content": "Old memory content", "date": old_date, "category": "fact", "tags": "db", "file_path": str(mem_file)},
        ]
        mock_conf.return_value = {"score": 0.5}
        mock_memdir.return_value = tmp_path

        result = apply_retention_policy(max_age_days=180, dry_run=False)
        assert result["candidates"] == 1
        assert result["archived"] == 1

    @patch("src.memory.recall_memories", side_effect=Exception("db error"))
    def test_recall_failure(self, mock_recall):
        result = apply_retention_policy()
        assert result["candidates"] == 0

    @patch("src.memory_confidence.compute_confidence", side_effect=Exception("scoring error"))
    @patch("src.memory.recall_memories")
    def test_confidence_error_defaults(self, mock_recall, mock_conf):
        recent_date = datetime.now().isoformat()
        mock_recall.return_value = [
            {"content": "Some content with enough length to pass orphan check", "date": recent_date, "category": "fact", "tags": "test", "file_path": "/tmp/mem.md"},
        ]
        result = apply_retention_policy(dry_run=True)
        # With default confidence 0.5, should not be flagged
        assert result["candidates"] == 0


class TestGetRetentionSummary:
    @patch("src.memory.recall_memories", return_value=[])
    def test_no_memories(self, mock_recall):
        result = get_retention_summary()
        assert result["total"] == 0

    @patch("src.memory.recall_memories")
    def test_age_distribution(self, mock_recall):
        now = datetime.now()
        mock_recall.return_value = [
            {"content": "Recent", "date": now.isoformat(), "category": "fact", "tags": "a"},
            {"content": "Month old", "date": (now - timedelta(days=45)).isoformat(), "category": "fact", "tags": "b"},
            {"content": "Old", "date": (now - timedelta(days=200)).isoformat(), "category": "fact", "tags": "c"},
        ]
        result = get_retention_summary()
        assert result["total"] == 3
        assert result["age_distribution"]["0-30d"] == 1
        assert result["age_distribution"]["31-90d"] == 1
        assert result["age_distribution"]["180d+"] == 1
        assert result["at_risk"] == 1

    @patch("src.memory.recall_memories")
    def test_orphaned_count(self, mock_recall):
        mock_recall.return_value = [
            {"content": "x", "date": datetime.now().isoformat(), "category": "", "tags": ""},
        ]
        result = get_retention_summary()
        assert result["orphaned"] == 1

    @patch("src.memory.recall_memories", side_effect=Exception("fail"))
    def test_recall_failure(self, mock_recall):
        result = get_retention_summary()
        assert result["total"] == 0


class TestRetentionCore:
    @patch("src.retention.apply_retention_policy")
    def test_core_retention_policy(self, mock_apply):
        from src.core import retention_policy

        mock_apply.return_value = {
            "candidates": 3,
            "archived": 0,
            "reasons": [
                {"file": "/tmp/old.md", "reason": "exceeded_max_age", "age_days": 200, "confidence": 0.4},
            ],
        }
        result = retention_policy(dry_run=True)
        assert "Retention Policy Report" in result
        assert "DRY RUN" in result
        assert "Candidates: 3" in result

    @patch("src.retention.get_retention_summary")
    def test_core_retention_summary(self, mock_summary):
        from src.core import retention_summary

        mock_summary.return_value = {
            "total": 10,
            "age_distribution": {"0-30d": 5, "31-90d": 3, "91-180d": 1, "180d+": 1, "unknown": 0},
            "at_risk": 1,
            "orphaned": 2,
        }
        result = retention_summary()
        assert "Retention Summary" in result
        assert "10 total memories" in result
        assert "At risk (180d+): 1" in result


class TestRetentionHTTP:
    def setup_method(self):
        from fastapi.testclient import TestClient
        from src.http_server import app
        self.client = TestClient(app)

    @patch("src.core.retention_policy", return_value="Retention report")
    def test_retention_policy_endpoint(self, mock_rp):
        resp = self.client.post("/retention-policy?max_age_days=90&dry_run=true")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        mock_rp.assert_called_once_with(90, 0.3, True)

    @patch("src.core.retention_summary", return_value="Summary report")
    def test_retention_summary_endpoint(self, mock_rs):
        resp = self.client.get("/retention-summary")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        mock_rs.assert_called_once()
