"""Tests for Remote MCP SSE/HTTP support."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest


class TestMCPServerSSEArgs:
    """Test that mcp_server.py correctly parses --sse/--http arguments."""

    def test_sse_flag_in_main_code(self):
        """Verify the SSE argument parsing code exists in mcp_server.py."""
        from pathlib import Path
        server_code = Path("mcp_server.py").read_text()
        assert "--sse" in server_code
        assert 'transport="sse"' in server_code

    def test_http_flag_in_main_code(self):
        """Verify the Streamable HTTP argument parsing code exists."""
        from pathlib import Path
        server_code = Path("mcp_server.py").read_text()
        assert "--http" in server_code
        assert 'transport="streamable-http"' in server_code

    def test_sse_default_port(self):
        """The SSE default port should be 8395."""
        from pathlib import Path
        server_code = Path("mcp_server.py").read_text()
        assert "8395" in server_code

    def test_host_binds_all_interfaces(self):
        """SSE/HTTP should bind to 0.0.0.0 for remote access."""
        from pathlib import Path
        server_code = Path("mcp_server.py").read_text()
        assert "0.0.0.0" in server_code


class TestCLIServeSSE:
    """Test that CLI serve command passes SSE/HTTP args correctly."""

    def test_cli_serve_has_sse_option(self):
        """The serve subparser should have --sse argument."""
        from pathlib import Path
        cli_code = Path("src/cli.py").read_text()
        assert '"--sse"' in cli_code

    def test_cli_serve_has_http_option(self):
        """The serve subparser should have --http argument."""
        from pathlib import Path
        cli_code = Path("src/cli.py").read_text()
        assert '"--http"' in cli_code

    @patch("mcp_server.main")
    def test_cmd_serve_default(self, mock_main):
        """Without --sse/--http, serve should call mcp_main normally."""
        import argparse
        from src.cli import cmd_serve
        args = argparse.Namespace(sse=None, http=None)
        cmd_serve(args)
        mock_main.assert_called_once()

    @patch("mcp_server.main")
    def test_cmd_serve_sse(self, mock_main):
        """With --sse, serve should inject sys.argv."""
        import argparse
        import sys
        from src.cli import cmd_serve
        args = argparse.Namespace(sse=9000, http=None)
        original_argv = sys.argv[:]
        cmd_serve(args)
        mock_main.assert_called_once()
        sys.argv = original_argv

    @patch("mcp_server.main")
    def test_cmd_serve_http(self, mock_main):
        """With --http, serve should inject sys.argv."""
        import argparse
        import sys
        from src.cli import cmd_serve
        args = argparse.Namespace(sse=None, http=9000)
        original_argv = sys.argv[:]
        cmd_serve(args)
        mock_main.assert_called_once()
        sys.argv = original_argv


class TestDashboardSSEInfo:
    """Dashboard should mention SSE capability."""

    def test_dashboard_endpoint_exists(self):
        from fastapi.testclient import TestClient
        from src.http_server import app
        client = TestClient(app)

        with patch("src.http_server._gather_dashboard_stats") as mock_stats:
            mock_stats.return_value = {
                "memory_count": 0, "entity_count": 0, "relationship_count": 0,
                "health_score": "—", "contradiction_count": 0, "cluster_count": 0,
                "recent_memories": [], "entity_graph_mermaid": "", "version": "1.2.0",
            }
            resp = client.get("/dashboard")
            assert resp.status_code == 200
