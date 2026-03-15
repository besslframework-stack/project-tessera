"""Tests for sleep-time consolidation (Phase 8a)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.sleep_consolidation import run_sleep_cycle


class TestRunSleepCycle:
    @patch("src.memory.recall_memories", return_value=[])
    @patch("src.consolidation.find_similar_clusters", return_value=[])
    def test_no_clusters_no_memories(self, mock_fsc, mock_recall):
        result = run_sleep_cycle()
        assert result["clusters_found"] == 0
        assert result["consolidated"] == 0
        assert result["superseded"] == 0
        assert result["skipped"] == 0

    @patch("src.memory.recall_memories", return_value=[])
    @patch("src.consolidation.find_similar_clusters")
    def test_clusters_below_threshold_skipped(self, mock_fsc, mock_recall):
        mock_fsc.return_value = [
            {"memories": [{"content": "A"}, {"content": "B"}], "similarity": 0.89, "count": 2},
            {"memories": [{"content": "C"}, {"content": "D"}], "similarity": 0.90, "count": 2},
        ]
        result = run_sleep_cycle()
        assert result["clusters_found"] == 2
        assert result["consolidated"] == 0
        assert result["skipped"] == 2

    @patch("src.memory.recall_memories", return_value=[])
    @patch("src.consolidation.consolidate_cluster")
    @patch("src.consolidation.find_similar_clusters")
    def test_high_similarity_consolidated(self, mock_fsc, mock_cc, mock_recall):
        mock_fsc.return_value = [
            {"memories": [{"content": "A"}, {"content": "B"}], "similarity": 0.95, "count": 2},
        ]
        mock_cc.return_value = {"merged_content": "AB", "superseded_count": 1, "new_memory_path": "/tmp/new.md"}
        result = run_sleep_cycle()
        assert result["consolidated"] == 1
        assert result["superseded"] == 1
        assert result["skipped"] == 0
        mock_cc.assert_called_once()

    @patch("src.memory.recall_memories", return_value=[])
    @patch("src.consolidation.consolidate_cluster", side_effect=Exception("merge error"))
    @patch("src.consolidation.find_similar_clusters")
    def test_consolidation_error_skipped(self, mock_fsc, mock_cc, mock_recall):
        mock_fsc.return_value = [
            {"memories": [{"content": "A"}, {"content": "B"}], "similarity": 0.95, "count": 2},
        ]
        result = run_sleep_cycle()
        assert result["consolidated"] == 0
        assert result["skipped"] == 1

    @patch("src.memory.supersede_memory", return_value=True)
    @patch("src.contradiction.detect_contradictions")
    @patch("src.memory.recall_memories")
    @patch("src.consolidation.find_similar_clusters", return_value=[])
    def test_contradiction_auto_supersede(self, mock_fsc, mock_recall, mock_detect, mock_sup):
        mock_recall.return_value = [
            {"content": "Use React", "category": "decision", "date": "2026-01-01", "file_path": "/tmp/old.md"},
            {"content": "Stop using React", "category": "decision", "date": "2026-03-01", "file_path": "/tmp/new.md"},
        ]
        mock_detect.return_value = [
            {
                "severity": "high",
                "memory_a": {"content": "Use React", "file_path": "/tmp/old.md"},
                "memory_b": {"content": "Stop using React", "file_path": "/tmp/new.md"},
            }
        ]
        result = run_sleep_cycle()
        assert result["superseded"] >= 1
        mock_sup.assert_called_once()

    @patch("src.memory.recall_memories")
    @patch("src.consolidation.find_similar_clusters", return_value=[])
    def test_medium_severity_not_superseded(self, mock_fsc, mock_recall):
        mock_recall.return_value = [{"content": "A", "category": "decision"}]
        with patch("src.contradiction.detect_contradictions") as mock_detect:
            mock_detect.return_value = [
                {"severity": "medium", "memory_a": {"file_path": "/tmp/a.md"}, "memory_b": {"file_path": "/tmp/b.md"}}
            ]
            result = run_sleep_cycle()
        assert result["superseded"] == 0

    @patch("src.consolidation.find_similar_clusters", side_effect=Exception("db error"))
    def test_cluster_search_failure(self, mock_fsc):
        with patch("src.memory.recall_memories", return_value=[]):
            result = run_sleep_cycle()
        assert result["clusters_found"] == 0

    @patch("src.memory.recall_memories", return_value=[])
    @patch("src.consolidation.consolidate_cluster")
    @patch("src.consolidation.find_similar_clusters")
    def test_mixed_clusters(self, mock_fsc, mock_cc, mock_recall):
        mock_fsc.return_value = [
            {"memories": [{"content": "A"}, {"content": "B"}], "similarity": 0.95, "count": 2},
            {"memories": [{"content": "C"}, {"content": "D"}], "similarity": 0.89, "count": 2},
        ]
        mock_cc.return_value = {"merged_content": "AB", "superseded_count": 1, "new_memory_path": "/tmp/new.md"}
        result = run_sleep_cycle()
        assert result["clusters_found"] == 2
        assert result["consolidated"] == 1
        assert result["skipped"] == 1


class TestSleepConsolidateCore:
    @patch("src.sleep_consolidation.run_sleep_cycle")
    def test_core_wrapper(self, mock_cycle):
        from src.core import sleep_consolidate

        mock_cycle.return_value = {
            "consolidated": 2,
            "superseded": 3,
            "clusters_found": 5,
            "skipped": 3,
        }
        result = sleep_consolidate()
        assert "Sleep Consolidation Report" in result
        assert "Auto-consolidated: 2" in result
        assert "Memories superseded: 3" in result

    @patch("src.sleep_consolidation.run_sleep_cycle")
    def test_core_no_action(self, mock_cycle):
        from src.core import sleep_consolidate

        mock_cycle.return_value = {
            "consolidated": 0,
            "superseded": 0,
            "clusters_found": 0,
            "skipped": 0,
        }
        result = sleep_consolidate()
        assert "No action taken" in result


class TestSleepConsolidateHTTP:
    def setup_method(self):
        from fastapi.testclient import TestClient
        from src.http_server import app
        self.client = TestClient(app)

    @patch("src.core.sleep_consolidate", return_value="Sleep report")
    def test_endpoint(self, mock_sc):
        resp = self.client.post("/sleep-consolidate")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        assert resp.json()["data"] == "Sleep report"
        mock_sc.assert_called_once()
