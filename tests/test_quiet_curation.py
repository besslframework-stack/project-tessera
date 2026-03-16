"""Tests for quiet curation pipeline."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.quiet_curation import get_health_pulse, run_quiet_curation


class TestRunQuietCuration:
    @patch("src.auto_curator._curate_retention", return_value=0)
    @patch("src.auto_curator._curate_consolidation", return_value=0)
    @patch("src.auto_curator._curate_contradictions", return_value=0)
    @patch("src.auto_curator._curate_entities", return_value=0)
    @patch("src.auto_curator._curate_metadata", return_value=(0, 0))
    def test_clean_run(self, *mocks):
        result = run_quiet_curation()
        assert result["classified"] == 0
        assert result["tagged"] == 0
        assert result["entities_extracted"] == 0
        assert result["contradictions_resolved"] == 0
        assert result["consolidated"] == 0
        assert result["retention_flagged"] == 0
        assert result["errors"] == []
        assert result["duration_ms"] >= 0

    @patch("src.auto_curator._curate_retention", return_value=2)
    @patch("src.auto_curator._curate_consolidation", return_value=1)
    @patch("src.auto_curator._curate_contradictions", return_value=3)
    @patch("src.auto_curator._curate_entities", return_value=5)
    @patch("src.auto_curator._curate_metadata", return_value=(4, 6))
    def test_active_run(self, *mocks):
        result = run_quiet_curation()
        assert result["classified"] == 4
        assert result["tagged"] == 6
        assert result["entities_extracted"] == 5
        assert result["contradictions_resolved"] == 3
        assert result["consolidated"] == 1
        assert result["retention_flagged"] == 2

    @patch("src.auto_curator._curate_retention", side_effect=Exception("fail"))
    @patch("src.auto_curator._curate_consolidation", return_value=0)
    @patch("src.auto_curator._curate_contradictions", return_value=0)
    @patch("src.auto_curator._curate_entities", return_value=0)
    @patch("src.auto_curator._curate_metadata", return_value=(0, 0))
    def test_handles_errors(self, *mocks):
        result = run_quiet_curation()
        assert len(result["errors"]) == 1
        assert "retention" in result["errors"][0]

    @patch("src.auto_curator._curate_retention", side_effect=Exception("a"))
    @patch("src.auto_curator._curate_consolidation", side_effect=Exception("b"))
    @patch("src.auto_curator._curate_contradictions", side_effect=Exception("c"))
    @patch("src.auto_curator._curate_entities", side_effect=Exception("d"))
    @patch("src.auto_curator._curate_metadata", side_effect=Exception("e"))
    def test_all_fail_gracefully(self, *mocks):
        result = run_quiet_curation()
        assert len(result["errors"]) == 5
        assert result["classified"] == 0


class TestGetHealthPulse:
    @patch("src.auto_curator._curate_retention", return_value=0)
    @patch("src.auto_curator._curate_consolidation", return_value=0)
    @patch("src.auto_curator._curate_contradictions", return_value=0)
    @patch("src.auto_curator._curate_entities", return_value=0)
    @patch("src.auto_curator._curate_metadata", return_value=(0, 0))
    def test_clean_returns_none(self, *mocks):
        run_quiet_curation()
        assert get_health_pulse() is None

    @patch("src.auto_curator._curate_retention", return_value=1)
    @patch("src.auto_curator._curate_consolidation", return_value=2)
    @patch("src.auto_curator._curate_contradictions", return_value=1)
    @patch("src.auto_curator._curate_entities", return_value=3)
    @patch("src.auto_curator._curate_metadata", return_value=(2, 4))
    def test_active_returns_summary(self, *mocks):
        run_quiet_curation()
        pulse = get_health_pulse()
        assert pulse is not None
        assert "Background maintenance" in pulse
        assert "classified" in pulse
        assert "contradictions fixed" in pulse
        assert "duplicates merged" in pulse


class TestHealthPulseEndpoint:
    def setup_method(self):
        from fastapi.testclient import TestClient
        from src.http_server import app
        self.client = TestClient(app)

    def test_endpoint(self):
        resp = self.client.get("/health-pulse")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
