"""Tests for image parser."""

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

import importlib
import src.ingestion.image_parser
importlib.reload(src.ingestion.image_parser)

from src.ingestion.image_parser import (
    SUPPORTED_EXTENSIONS,
    _get_image_metadata,
    parse_image_file,
)


@pytest.fixture(autouse=True)
def _clear_mocks():
    _mock_doc_instances.clear()
    yield


class TestSupportedExtensions:
    def test_common_formats(self):
        for ext in [".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff"]:
            assert ext in SUPPORTED_EXTENSIONS


class TestGetImageMetadata:
    def test_basic_metadata(self, tmp_path):
        f = tmp_path / "test.png"
        f.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        meta = _get_image_metadata(f)
        assert meta["file_name"] == "test.png"
        assert meta["file_type"] == "image"
        assert meta["doc_type"] == "image"
        assert meta["file_size_bytes"] > 0


class TestParseImageFile:
    def test_without_ocr(self, tmp_path):
        f = tmp_path / "test.png"
        f.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        with patch("src.ingestion.image_parser._try_ocr", return_value=None):
            docs = parse_image_file(f)
            assert len(docs) == 1
            assert "test.png" in docs[0].text
            assert docs[0].metadata["ocr"] is False

    def test_with_ocr_text(self, tmp_path):
        f = tmp_path / "screenshot.png"
        f.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        with patch("src.ingestion.image_parser._try_ocr", return_value="Hello World from OCR"):
            docs = parse_image_file(f)
            assert len(docs) == 1
            assert "Hello World from OCR" in docs[0].text
            assert docs[0].metadata["ocr"] is True
