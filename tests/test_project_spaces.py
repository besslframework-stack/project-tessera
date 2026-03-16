"""Tests for project spaces."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.project_spaces import assign_project, format_project_spaces, list_project_spaces


class TestListProjectSpaces:
    @patch("src.memory._memory_dir")
    def test_empty(self, mock_dir, tmp_path):
        mock_dir.return_value = tmp_path
        spaces = list_project_spaces()
        assert spaces == []

    @patch("src.memory._memory_dir")
    def test_single_project(self, mock_dir, tmp_path):
        mock_dir.return_value = tmp_path
        (tmp_path / "a.md").write_text(
            "---\ndate: 2026-03-16\nproject: tessera\ntags: [api, python]\n---\n\nSome memory\n"
        )
        (tmp_path / "b.md").write_text(
            "---\ndate: 2026-03-15\nproject: tessera\ntags: [database]\n---\n\nAnother\n"
        )
        spaces = list_project_spaces()
        assert len(spaces) == 1
        assert spaces[0]["project"] == "tessera"
        assert spaces[0]["memory_count"] == 2
        assert spaces[0]["latest_date"] == "2026-03-16"

    @patch("src.memory._memory_dir")
    def test_multiple_projects(self, mock_dir, tmp_path):
        mock_dir.return_value = tmp_path
        (tmp_path / "a.md").write_text(
            "---\ndate: 2026-03-16\nproject: tessera\ntags: [api]\n---\n\nA\n"
        )
        (tmp_path / "b.md").write_text(
            "---\ndate: 2026-03-15\nproject: frontend\ntags: [react]\n---\n\nB\n"
        )
        (tmp_path / "c.md").write_text(
            "---\ndate: 2026-03-14\ntags: [misc]\n---\n\nC (no project)\n"
        )
        spaces = list_project_spaces()
        names = [s["project"] for s in spaces]
        assert "tessera" in names
        assert "frontend" in names
        assert "(unassigned)" in names

    @patch("src.memory._memory_dir")
    def test_sorted_by_count(self, mock_dir, tmp_path):
        mock_dir.return_value = tmp_path
        for i in range(5):
            (tmp_path / f"a{i}.md").write_text(
                f"---\ndate: 2026-03-{10+i}\nproject: big\ntags: [general]\n---\n\nMem {i}\n"
            )
        (tmp_path / "small.md").write_text(
            "---\ndate: 2026-03-16\nproject: small\ntags: [general]\n---\n\nSmall\n"
        )
        spaces = list_project_spaces()
        assert spaces[0]["project"] == "big"
        assert spaces[0]["memory_count"] == 5


class TestAssignProject:
    @patch("src.memory._memory_dir")
    def test_assign(self, mock_dir, tmp_path):
        mock_dir.return_value = tmp_path
        f = tmp_path / "mem001.md"
        f.write_text("---\ndate: 2026-03-16\ntags: [api]\n---\n\nContent\n")

        result = assign_project("mem001", "tessera")
        assert result is True

        text = f.read_text()
        assert "project: tessera" in text

    @patch("src.memory._memory_dir")
    def test_reassign(self, mock_dir, tmp_path):
        mock_dir.return_value = tmp_path
        f = tmp_path / "mem002.md"
        f.write_text("---\ndate: 2026-03-16\nproject: old\ntags: [api]\n---\n\nContent\n")

        result = assign_project("mem002", "new")
        assert result is True

        text = f.read_text()
        assert "project: new" in text
        assert "project: old" not in text

    @patch("src.memory._memory_dir")
    def test_not_found(self, mock_dir, tmp_path):
        mock_dir.return_value = tmp_path
        result = assign_project("nonexistent", "whatever")
        assert result is False


class TestFormatProjectSpaces:
    def test_empty(self):
        result = format_project_spaces([])
        assert "No project spaces" in result

    def test_with_spaces(self):
        spaces = [
            {"project": "tessera", "memory_count": 10, "latest_date": "2026-03-16", "top_tags": ["api", "python"]},
            {"project": "frontend", "memory_count": 5, "latest_date": "2026-03-15", "top_tags": ["react"]},
        ]
        result = format_project_spaces(spaces)
        assert "tessera" in result
        assert "10 memories" in result
        assert "frontend" in result


class TestProjectSpacesEndpoints:
    def setup_method(self):
        from fastapi.testclient import TestClient
        from src.http_server import app
        self.client = TestClient(app)

    def test_list_projects(self):
        resp = self.client.get("/projects")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_assign_project(self):
        resp = self.client.post("/assign-project?memory_id=test&project=demo")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
