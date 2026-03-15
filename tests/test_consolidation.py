"""Tests for memory consolidation (Phase 6d)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.consolidation import consolidate_cluster, find_similar_clusters
from src.core import consolidate_memories, find_consolidation_candidates


class TestFindSimilarClusters:
    def test_no_db(self):
        with patch("src.config.settings") as ms:
            ms.data.lancedb_path = "/tmp/nonexistent_db_path_xyz"
            result = find_similar_clusters()
        assert result == []

    def test_empty_table(self):
        mock_df = MagicMock()
        mock_df.to_dict.return_value = []
        mock_table = MagicMock()
        mock_table.to_pandas.return_value = mock_df
        mock_db = MagicMock()
        mock_db.table_names.return_value = ["memories"]
        mock_db.open_table.return_value = mock_table

        with patch("lancedb.connect", return_value=mock_db), \
             patch("src.config.settings") as ms, \
             patch.object(Path, "exists", return_value=True):
            ms.data.lancedb_path = "/tmp/db"
            result = find_similar_clusters()
        assert result == []

    def test_single_memory(self):
        mock_df = MagicMock()
        mock_df.to_dict.return_value = [
            {"text": "Only one memory", "file_path": "/tmp/m1.md", "superseded_at": ""}
        ]
        mock_table = MagicMock()
        mock_table.to_pandas.return_value = mock_df
        mock_db = MagicMock()
        mock_db.table_names.return_value = ["memories"]
        mock_db.open_table.return_value = mock_table

        with patch("lancedb.connect", return_value=mock_db), \
             patch("src.config.settings") as ms, \
             patch.object(Path, "exists", return_value=True):
            ms.data.lancedb_path = "/tmp/db"
            result = find_similar_clusters()
        assert result == []


class TestConsolidateCluster:
    def test_too_few_memories(self):
        result = consolidate_cluster({"memories": [{"content": "one"}]})
        assert result["superseded_count"] == 0

    def test_empty_cluster(self):
        result = consolidate_cluster({"memories": []})
        assert result["superseded_count"] == 0

    def test_merge_two_memories(self, tmp_path):
        mem1 = tmp_path / "mem1.md"
        mem1.write_text(
            "---\ndate: 2026-03-15\nvalid_from: 2026-03-15\n"
            "source: test\ncategory: fact\ntags: [db]\n---\n\nUse PostgreSQL for the project\n"
        )
        mem2 = tmp_path / "mem2.md"
        mem2.write_text(
            "---\ndate: 2026-03-15\nvalid_from: 2026-03-15\n"
            "source: test\ncategory: fact\ntags: [db]\n---\n\nPostgreSQL is our database\n"
        )

        cluster = {
            "memories": [
                {
                    "content": "Use PostgreSQL for the project",
                    "date": "2026-03-15",
                    "category": "fact",
                    "tags": "db",
                    "file_path": str(mem1),
                },
                {
                    "content": "PostgreSQL is our database",
                    "date": "2026-03-15",
                    "category": "fact",
                    "tags": "db",
                    "file_path": str(mem2),
                },
            ],
            "similarity": 0.9,
            "count": 2,
        }

        with patch("src.memory.save_memory") as mock_save, \
             patch("src.memory.supersede_memory", return_value=True) as mock_sup:
            mock_save.return_value = tmp_path / "merged.md"
            result = consolidate_cluster(cluster)

        assert result["superseded_count"] == 2
        mock_save.assert_called_once()


class TestCoreConsolidation:
    @patch("src.consolidation.find_similar_clusters", return_value=[])
    def test_no_clusters(self, mock_fsc):
        result = find_consolidation_candidates()
        assert "well-differentiated" in result.lower() or "No similar" in result

    @patch("src.consolidation.find_similar_clusters")
    def test_found_clusters(self, mock_fsc):
        mock_fsc.return_value = [
            {
                "memories": [
                    {"content": "Use PostgreSQL", "date": "2026-03-15", "category": "fact", "tags": "db"},
                    {"content": "PostgreSQL is good", "date": "2026-03-15", "category": "fact", "tags": "db"},
                ],
                "similarity": 0.92,
                "count": 2,
            }
        ]
        result = find_consolidation_candidates()
        assert "1 clusters" in result or "Found 1" in result
        assert "PostgreSQL" in result

    @patch("src.consolidation.find_similar_clusters", return_value=[])
    def test_consolidate_no_clusters(self, mock_fsc):
        result = consolidate_memories(1)
        assert "No similar" in result

    @patch("src.consolidation.consolidate_cluster")
    @patch("src.consolidation.find_similar_clusters")
    def test_consolidate_success(self, mock_fsc, mock_cc):
        mock_fsc.return_value = [
            {
                "memories": [
                    {"content": "A", "date": "", "category": "", "tags": ""},
                    {"content": "B", "date": "", "category": "", "tags": ""},
                ],
                "similarity": 0.9,
                "count": 2,
            }
        ]
        mock_cc.return_value = {
            "merged_content": "Consolidated A and B",
            "superseded_count": 1,
            "new_memory_path": "/tmp/new.md",
        }
        result = consolidate_memories(1)
        assert "Consolidated" in result
        assert "Superseded: 1" in result

    @patch("src.consolidation.find_similar_clusters")
    def test_consolidate_invalid_index(self, mock_fsc):
        mock_fsc.return_value = [{"memories": [], "similarity": 0.9, "count": 0}]
        result = consolidate_memories(99)
        assert "not found" in result.lower()


class TestConsolidationHTTPEndpoints:
    def setup_method(self):
        from fastapi.testclient import TestClient
        from src.http_server import app
        self.client = TestClient(app)

    @patch("src.core.find_consolidation_candidates", return_value="Found 2 clusters")
    def test_candidates_endpoint(self, mock_fc):
        resp = self.client.get("/consolidation-candidates")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        mock_fc.assert_called_once_with(0.85, 20)

    @patch("src.core.consolidate_memories", return_value="Consolidated 3 memories")
    def test_consolidate_endpoint(self, mock_cm):
        resp = self.client.post("/consolidate?cluster_index=1")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        mock_cm.assert_called_once_with(1, 0.85)
