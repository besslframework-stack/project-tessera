"""Tests for auto-curator pipeline."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.auto_curator import (
    classify_memory,
    extract_tags,
    run_auto_curation,
)
from src.core import auto_curate


class TestClassifyMemory:
    def test_decision(self):
        assert classify_memory("We decided to use PostgreSQL") == "decision"

    def test_decision_korean(self):
        assert classify_memory("PostgreSQL을 사용하기로 결정했다") == "decision"

    def test_preference(self):
        assert classify_memory("I prefer dark mode for coding") == "preference"

    def test_fact(self):
        assert classify_memory("The API endpoint is /api/v2") == "fact"

    def test_process(self):
        assert classify_memory("Step 1: build the Docker image") == "process"

    def test_context(self):
        assert classify_memory("Currently working on the dashboard project") == "context"

    def test_default_to_fact(self):
        assert classify_memory("Something random here") == "fact"

    def test_empty_string(self):
        assert classify_memory("") == "fact"


class TestExtractTags:
    def test_database_tags(self):
        tags = extract_tags("We use PostgreSQL as our database")
        assert "db" in tags

    def test_api_tags(self):
        tags = extract_tags("The REST API endpoint returns JSON")
        assert "api" in tags

    def test_multiple_tags(self):
        tags = extract_tags("Deploy the React frontend with Docker")
        assert "deploy" in tags
        assert "frontend" in tags

    def test_no_tags(self):
        tags = extract_tags("Just a random note")
        assert tags == []

    def test_max_five_tags(self):
        text = "database api auth deploy react server model test security aws"
        tags = extract_tags(text)
        assert len(tags) <= 5


class TestRunAutoCuration:
    @patch("src.auto_curator._curate_retention", return_value=0)
    @patch("src.auto_curator._curate_consolidation", return_value=0)
    @patch("src.auto_curator._curate_contradictions", return_value=0)
    @patch("src.auto_curator._curate_entities", return_value=0)
    @patch("src.auto_curator._curate_metadata", return_value=(0, 0))
    def test_empty_run(self, *mocks):
        result = run_auto_curation()
        assert result["classified"] == 0
        assert result["tagged"] == 0
        assert result["entities_extracted"] == 0
        assert result["contradictions_resolved"] == 0
        assert result["consolidated"] == 0
        assert result["retention_flagged"] == 0
        assert result["errors"] == []

    @patch("src.auto_curator._curate_retention", return_value=2)
    @patch("src.auto_curator._curate_consolidation", return_value=1)
    @patch("src.auto_curator._curate_contradictions", return_value=1)
    @patch("src.auto_curator._curate_entities", return_value=5)
    @patch("src.auto_curator._curate_metadata", return_value=(3, 4))
    def test_full_run(self, *mocks):
        result = run_auto_curation()
        assert result["classified"] == 3
        assert result["tagged"] == 4
        assert result["entities_extracted"] == 5
        assert result["contradictions_resolved"] == 1
        assert result["consolidated"] == 1
        assert result["retention_flagged"] == 2

    @patch("src.auto_curator._curate_retention", side_effect=Exception("boom"))
    @patch("src.auto_curator._curate_consolidation", return_value=0)
    @patch("src.auto_curator._curate_contradictions", return_value=0)
    @patch("src.auto_curator._curate_entities", return_value=0)
    @patch("src.auto_curator._curate_metadata", return_value=(0, 0))
    def test_handles_errors(self, *mocks):
        result = run_auto_curation()
        assert len(result["errors"]) == 1
        assert "retention" in result["errors"][0]


class TestCoreAutoCurate:
    @patch("src.auto_curator.run_auto_curation")
    def test_formats_output(self, mock_run):
        mock_run.return_value = {
            "classified": 2,
            "tagged": 3,
            "entities_extracted": 5,
            "contradictions_resolved": 1,
            "consolidated": 0,
            "retention_flagged": 1,
            "errors": [],
        }
        result = auto_curate()
        assert "Auto-Curation Report" in result
        assert "Classified: 2" in result
        assert "Tagged: 3" in result

    @patch("src.auto_curator.run_auto_curation")
    def test_clean_message(self, mock_run):
        mock_run.return_value = {
            "classified": 0, "tagged": 0, "entities_extracted": 0,
            "contradictions_resolved": 0, "consolidated": 0,
            "retention_flagged": 0, "errors": [],
        }
        result = auto_curate()
        assert "clean" in result.lower() or "No curation" in result


class TestAutoCurateEndpoint:
    def setup_method(self):
        from fastapi.testclient import TestClient
        from src.http_server import app
        self.client = TestClient(app)

    @patch("src.core.auto_curate", return_value="Curation complete")
    def test_endpoint(self, mock_ac):
        resp = self.client.post("/auto-curate")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        mock_ac.assert_called_once()


class TestCurateMetadata:
    def test_classify_and_tag_file(self, tmp_path):
        mem_file = tmp_path / "test_mem.md"
        mem_file.write_text(
            "---\ndate: 2026-03-15\nsource: test\n---\n\n"
            "We decided to use PostgreSQL as our database\n",
            encoding="utf-8",
        )

        with patch("src.memory._memory_dir", return_value=tmp_path):
            from src.auto_curator import _curate_metadata
            classified, tagged = _curate_metadata()

        text = mem_file.read_text()
        assert "category: decision" in text
        assert "tags:" in text
        assert "db" in text
        assert classified == 1
        assert tagged == 1
