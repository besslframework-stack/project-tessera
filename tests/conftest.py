"""Shared test fixtures for Tessera tests."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

# Mock external dependencies that may not be installed in test env
# Build a mock FastMCP whose .tool() and .resource() decorators pass through
_mock_fastmcp_mod = MagicMock()


class _PassthroughFastMCP:
    """Minimal stand-in for FastMCP that makes decorators transparent."""

    def __init__(self, **kwargs):
        pass

    def tool(self, **kwargs):
        def decorator(fn):
            return fn
        return decorator

    def resource(self, *args, **kwargs):
        def decorator(fn):
            return fn
        return decorator

    def run(self):
        pass


_mock_fastmcp_mod.FastMCP = _PassthroughFastMCP

_optional_deps = {
    "fastembed": MagicMock(),
    "lancedb": MagicMock(),
    "lancedb.rerankers": MagicMock(),
    "mcp": MagicMock(),
    "mcp.server": MagicMock(),
    "mcp.server.fastmcp": _mock_fastmcp_mod,
}
for _mod_name, _mock in _optional_deps.items():
    if _mod_name not in sys.modules:
        sys.modules[_mod_name] = _mock

import pytest
from pathlib import Path
from unittest.mock import patch
import numpy as np


@pytest.fixture
def tmp_workspace(tmp_path):
    """Create a minimal workspace structure for testing."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "test.md").write_text("# Test\n\nThis is a test document about auth flow.\n")
    (docs / "prd.md").write_text(
        "# PRD v1.0\n\n## 개요\nTest PRD\n\n## 문제 정의\nSome problem\n"
    )
    (docs / "data.csv").write_text("name,value\nalpha,1\nbeta,2\n")

    memories = tmp_path / "data" / "memories"
    memories.mkdir(parents=True)

    lancedb = tmp_path / "data" / "lancedb"
    lancedb.mkdir(parents=True)

    return tmp_path


@pytest.fixture
def workspace_yaml(tmp_workspace):
    """Create a workspace.yaml file."""
    yaml_content = f"""workspace:
  root: {tmp_workspace}
  name: test-workspace

sources:
  - path: docs
    type: document
    project: test_project

projects:
  test_project:
    display_name: Test Project
    root: docs
"""
    yaml_path = tmp_workspace / "workspace.yaml"
    yaml_path.write_text(yaml_content)
    return yaml_path


@pytest.fixture
def mock_embed_model():
    """Mock fastembed model to avoid downloading real models."""
    mock_model = MagicMock()
    mock_model.embed.return_value = iter([np.random.rand(384).astype(np.float32)])
    with patch("src.embedding.get_embed_model", return_value=mock_model):
        yield mock_model


@pytest.fixture
def mock_embed_query():
    """Mock embed_query to return random vectors."""
    def _mock_query(text):
        return np.random.rand(384).astype(np.float32).tolist()

    with patch("src.embedding.embed_query", side_effect=_mock_query):
        yield _mock_query
