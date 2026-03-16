"""Tests for provenance chain."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.provenance import (
    build_provenance,
    extract_provenance,
    format_lineage,
    format_provenance_yaml,
    get_provenance_stats,
    trace_lineage,
)


class TestBuildProvenance:
    @patch("src.interaction_log.SESSION_ID", "test123")
    def test_basic(self):
        prov = build_provenance(source="conversation")
        assert prov["created_by"] == "conversation"
        assert prov["session_id"] == "test123"
        assert "created_at" in prov

    @patch("src.interaction_log.SESSION_ID", "sess456")
    def test_with_parents(self):
        prov = build_provenance(
            source="consolidation",
            parent_ids=["mem_a", "mem_b"],
        )
        assert prov["derived_from"] == ["mem_a", "mem_b"]

    @patch("src.interaction_log.SESSION_ID", "sess789")
    def test_with_source_document(self):
        prov = build_provenance(
            source="auto-learn",
            source_document="/docs/api.md",
        )
        assert prov["source_document"] == "/docs/api.md"

    @patch("src.interaction_log.SESSION_ID", "sess000")
    def test_with_tool(self):
        prov = build_provenance(
            source="conversation",
            tool_name="remember",
        )
        assert prov["tool"] == "remember"

    def test_explicit_session_id(self):
        prov = build_provenance(source="test", session_id="explicit")
        assert prov["session_id"] == "explicit"


class TestFormatProvenanceYaml:
    def test_simple(self):
        prov = {"created_by": "conversation", "session_id": "abc", "created_at": "2026-03-16"}
        yaml = format_provenance_yaml(prov)
        assert "provenance:" in yaml
        assert "created_by: conversation" in yaml
        assert "session_id: abc" in yaml

    def test_with_list(self):
        prov = {"created_by": "consolidation", "session_id": "x", "derived_from": ["a", "b"], "created_at": "2026-03-16"}
        yaml = format_provenance_yaml(prov)
        assert "derived_from:" in yaml
        assert "    - a" in yaml
        assert "    - b" in yaml


class TestExtractProvenance:
    def test_with_provenance(self, tmp_path):
        f = tmp_path / "mem.md"
        f.write_text(
            "---\n"
            "date: 2026-03-16\n"
            "source: conversation\n"
            "provenance:\n"
            "  created_by: conversation\n"
            "  session_id: abc123\n"
            "  created_at: 2026-03-16T10:00:00\n"
            "---\n\n"
            "Some content\n"
        )
        prov = extract_provenance(f)
        assert prov is not None
        assert prov["created_by"] == "conversation"
        assert prov["session_id"] == "abc123"

    def test_with_derived_from(self, tmp_path):
        f = tmp_path / "mem.md"
        f.write_text(
            "---\n"
            "date: 2026-03-16\n"
            "provenance:\n"
            "  created_by: consolidation\n"
            "  session_id: xyz\n"
            "  derived_from:\n"
            "    - parent_a\n"
            "    - parent_b\n"
            "  created_at: 2026-03-16T10:00:00\n"
            "---\n\n"
            "Merged content\n"
        )
        prov = extract_provenance(f)
        assert prov is not None
        assert prov["derived_from"] == ["parent_a", "parent_b"]

    def test_no_provenance(self, tmp_path):
        f = tmp_path / "old.md"
        f.write_text(
            "---\n"
            "date: 2026-03-16\n"
            "source: conversation\n"
            "---\n\n"
            "Old memory\n"
        )
        prov = extract_provenance(f)
        assert prov is None

    def test_nonexistent_file(self):
        prov = extract_provenance(Path("/nonexistent/file.md"))
        assert prov is None


class TestTraceLineage:
    @patch("src.memory._memory_dir")
    def test_single_memory(self, mock_dir, tmp_path):
        mock_dir.return_value = tmp_path
        f = tmp_path / "mem001_test.md"
        f.write_text(
            "---\n"
            "date: 2026-03-16\n"
            "provenance:\n"
            "  created_by: conversation\n"
            "  session_id: s1\n"
            "  created_at: 2026-03-16\n"
            "---\n\nContent\n"
        )
        chain = trace_lineage("mem001_test")
        assert len(chain) == 1
        assert chain[0]["created_by"] == "conversation"

    @patch("src.memory._memory_dir")
    def test_chain(self, mock_dir, tmp_path):
        mock_dir.return_value = tmp_path

        # Parent
        parent = tmp_path / "parent_a.md"
        parent.write_text(
            "---\n"
            "date: 2026-03-15\n"
            "provenance:\n"
            "  created_by: conversation\n"
            "  session_id: s0\n"
            "  created_at: 2026-03-15\n"
            "---\n\nOriginal\n"
        )

        # Child derived from parent
        child = tmp_path / "child_b.md"
        child.write_text(
            "---\n"
            "date: 2026-03-16\n"
            "provenance:\n"
            "  created_by: consolidation\n"
            "  session_id: s1\n"
            "  derived_from:\n"
            "    - parent_a\n"
            "  created_at: 2026-03-16\n"
            "---\n\nMerged\n"
        )

        chain = trace_lineage("child_b")
        assert len(chain) == 2
        assert chain[0]["id"] == "child_b"
        assert chain[1]["id"] == "parent_a"

    @patch("src.memory._memory_dir")
    def test_missing_parent(self, mock_dir, tmp_path):
        mock_dir.return_value = tmp_path

        child = tmp_path / "orphan.md"
        child.write_text(
            "---\n"
            "date: 2026-03-16\n"
            "provenance:\n"
            "  created_by: consolidation\n"
            "  session_id: s1\n"
            "  derived_from:\n"
            "    - missing_parent\n"
            "  created_at: 2026-03-16\n"
            "---\n\nOrphan\n"
        )

        chain = trace_lineage("orphan")
        assert len(chain) == 2
        assert chain[1]["status"] == "not_found"


class TestGetProvenanceStats:
    @patch("src.memory._memory_dir")
    def test_mixed(self, mock_dir, tmp_path):
        mock_dir.return_value = tmp_path

        # With provenance
        (tmp_path / "a.md").write_text(
            "---\ndate: 2026-03-16\nprovenance:\n  created_by: conversation\n  session_id: s1\n  created_at: 2026-03-16\n---\n\nA\n"
        )
        # Without provenance
        (tmp_path / "b.md").write_text(
            "---\ndate: 2026-03-16\n---\n\nB\n"
        )
        # With derived_from
        (tmp_path / "c.md").write_text(
            "---\ndate: 2026-03-16\nprovenance:\n  created_by: consolidation\n  session_id: s1\n  derived_from:\n    - a\n  created_at: 2026-03-16\n---\n\nC\n"
        )

        stats = get_provenance_stats()
        assert stats["total_memories"] == 3
        assert stats["with_provenance"] == 2
        assert stats["without_provenance"] == 1
        assert stats["derived_count"] == 1
        assert stats["by_source"]["conversation"] == 1
        assert stats["by_source"]["consolidation"] == 1

    @patch("src.memory._memory_dir")
    def test_empty(self, mock_dir, tmp_path):
        mock_dir.return_value = tmp_path
        stats = get_provenance_stats()
        assert stats["total_memories"] == 0


class TestFormatLineage:
    def test_empty(self):
        assert "No lineage" in format_lineage([])

    def test_single(self):
        chain = [{"id": "mem1", "created_by": "conversation", "session_id": "s1", "created_at": "2026-03-16T10:00"}]
        result = format_lineage(chain)
        assert "mem1" in result
        assert "conversation" in result

    def test_chain(self):
        chain = [
            {"id": "child", "created_by": "consolidation", "session_id": "s2", "created_at": "2026-03-16", "derived_from": ["parent"]},
            {"id": "parent", "created_by": "conversation", "session_id": "s1", "created_at": "2026-03-15"},
        ]
        result = format_lineage(chain)
        assert "child" in result
        assert "parent" in result
        assert "derived from" in result

    def test_not_found(self):
        chain = [{"id": "orphan", "status": "not_found"}]
        result = format_lineage(chain)
        assert "not found" in result


class TestProvenanceEndpoints:
    def setup_method(self):
        from fastapi.testclient import TestClient
        from src.http_server import app
        self.client = TestClient(app)

    def test_provenance_stats(self):
        resp = self.client.get("/provenance-stats")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_memory_lineage(self):
        resp = self.client.get("/provenance/nonexistent_memory")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
