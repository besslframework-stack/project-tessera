"""Tests for universal text/code parser."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch
import sys

import pytest


# Mock llama_index before importing parser
_mock_doc_instances = []

class _MockDocument:
    def __init__(self, text="", metadata=None):
        self.text = text
        self.metadata = metadata or {}
        _mock_doc_instances.append(self)

_mock_schema = MagicMock()
_mock_schema.Document = _MockDocument
sys.modules["llama_index"] = MagicMock()
sys.modules["llama_index.core"] = MagicMock()
sys.modules["llama_index.core.schema"] = _mock_schema

# Force reimport with our mock
import importlib
import src.ingestion.text_parser
importlib.reload(src.ingestion.text_parser)

from src.ingestion.text_parser import (
    SUPPORTED_EXTENSIONS,
    _detect_language,
    _strip_html_tags,
    parse_text_file,
)


@pytest.fixture(autouse=True)
def _clear_mocks():
    _mock_doc_instances.clear()
    yield


class TestDetectLanguage:
    def test_python(self, tmp_path):
        assert _detect_language(tmp_path / "main.py") == "python"

    def test_typescript(self, tmp_path):
        assert _detect_language(tmp_path / "app.ts") == "typescript"

    def test_tsx(self, tmp_path):
        assert _detect_language(tmp_path / "Component.tsx") == "typescript-react"

    def test_go(self, tmp_path):
        assert _detect_language(tmp_path / "main.go") == "go"

    def test_rust(self, tmp_path):
        assert _detect_language(tmp_path / "lib.rs") == "rust"

    def test_json(self, tmp_path):
        assert _detect_language(tmp_path / "config.json") == "json"

    def test_yaml(self, tmp_path):
        assert _detect_language(tmp_path / "deploy.yaml") == "yaml"

    def test_html(self, tmp_path):
        assert _detect_language(tmp_path / "index.html") == "html"

    def test_dockerfile(self, tmp_path):
        assert _detect_language(tmp_path / "Dockerfile") == "dockerfile"

    def test_unknown(self, tmp_path):
        assert _detect_language(tmp_path / "file.xyz") == "text"


class TestStripHtmlTags:
    def test_basic(self):
        assert _strip_html_tags("<p>Hello</p>") == "Hello"

    def test_nested(self):
        result = _strip_html_tags("<div><p>Hello <b>World</b></p></div>")
        assert "Hello" in result
        assert "World" in result

    def test_script_removal(self):
        html = "<p>Text</p><script>alert('xss')</script><p>More</p>"
        result = _strip_html_tags(html)
        assert "alert" not in result
        assert "Text" in result

    def test_entities(self):
        result = _strip_html_tags("A &amp; B")
        assert "A & B" in result


class TestParseTextFile:
    def test_python_file(self, tmp_path):
        f = tmp_path / "hello.py"
        f.write_text("def hello():\n    print('Hello, world!')\n")
        docs = parse_text_file(f)
        assert len(docs) == 1
        assert docs[0].metadata["language"] == "python"
        assert docs[0].metadata["doc_type"] == "code"
        assert "def hello" in docs[0].text

    def test_json_file(self, tmp_path):
        f = tmp_path / "config.json"
        f.write_text('{"key": "value"}')
        docs = parse_text_file(f)
        assert len(docs) == 1
        assert docs[0].metadata["language"] == "json"

    def test_html_strips_tags(self, tmp_path):
        f = tmp_path / "page.html"
        f.write_text("<html><body><h1>Title</h1><p>Content</p></body></html>")
        docs = parse_text_file(f)
        assert len(docs) == 1
        assert "<h1>" not in docs[0].text
        assert "Title" in docs[0].text

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.py"
        f.write_text("")
        docs = parse_text_file(f)
        assert len(docs) == 0

    def test_yaml_file(self, tmp_path):
        f = tmp_path / "config.yaml"
        f.write_text("server:\n  port: 8080\n")
        docs = parse_text_file(f)
        assert len(docs) == 1
        assert docs[0].metadata["language"] == "yaml"

    def test_shell_script(self, tmp_path):
        f = tmp_path / "deploy.sh"
        f.write_text("#!/bin/bash\necho 'hi'\n")
        docs = parse_text_file(f)
        assert len(docs) == 1
        assert docs[0].metadata["language"] == "shell"

    def test_line_count(self, tmp_path):
        f = tmp_path / "multi.py"
        f.write_text("line1\nline2\nline3\n")
        docs = parse_text_file(f)
        assert docs[0].metadata["line_count"] == 4

    def test_nonexistent_file(self, tmp_path):
        f = tmp_path / "nope.py"
        docs = parse_text_file(f)
        assert len(docs) == 0


class TestSupportedExtensions:
    def test_common_languages(self):
        for ext in [".py", ".js", ".ts", ".go", ".rs", ".java", ".c", ".cpp"]:
            assert ext in SUPPORTED_EXTENSIONS

    def test_config_formats(self):
        for ext in [".json", ".yaml", ".yml", ".toml", ".xml"]:
            assert ext in SUPPORTED_EXTENSIONS

    def test_web_formats(self):
        for ext in [".html", ".css", ".scss"]:
            assert ext in SUPPORTED_EXTENSIONS
