"""Tests for the PDF parser module."""

from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest import mock

import pytest


def test_parse_pdf_file_is_callable() -> None:
    """parse_pdf_file should be importable and callable."""
    from src.ingestion.pdf_parser import parse_pdf_file

    assert callable(parse_pdf_file)


def test_format_pdf_as_text_is_callable() -> None:
    """format_pdf_as_text should be importable and callable."""
    from src.ingestion.pdf_parser import format_pdf_as_text

    assert callable(format_pdf_as_text)


def test_parse_pdf_file_missing_file(tmp_path: Path) -> None:
    """parse_pdf_file should return empty list for a non-existent file."""
    from src.ingestion.pdf_parser import parse_pdf_file

    result = parse_pdf_file(tmp_path / "nonexistent.pdf")
    # Either empty list (pymupdf installed, file open fails) or empty list (not installed)
    assert result == []


def test_format_pdf_as_text_missing_file(tmp_path: Path) -> None:
    """format_pdf_as_text should return an error/info string for a missing file."""
    from src.ingestion.pdf_parser import format_pdf_as_text

    result = format_pdf_as_text(tmp_path / "nonexistent.pdf")
    assert isinstance(result, str)
    # When pymupdf is not installed, returns install instruction
    # When pymupdf is installed, returns file-not-found error
    assert "nonexistent.pdf" in result or "pymupdf not installed" in result


def test_parse_pdf_graceful_degradation_no_pymupdf() -> None:
    """parse_pdf_file should return [] when pymupdf is not installed."""
    with mock.patch.dict(sys.modules, {"fitz": None}):
        import importlib

        from src.ingestion import pdf_parser

        importlib.reload(pdf_parser)

        result = pdf_parser.parse_pdf_file(Path("dummy.pdf"))
        assert result == []

    # Reload to restore normal state
    import importlib

    from src.ingestion import pdf_parser

    importlib.reload(pdf_parser)


def test_format_pdf_graceful_degradation_no_pymupdf() -> None:
    """format_pdf_as_text should return install message when pymupdf is not installed."""
    with mock.patch.dict(sys.modules, {"fitz": None}):
        import importlib

        from src.ingestion import pdf_parser

        importlib.reload(pdf_parser)

        result = pdf_parser.format_pdf_as_text(Path("dummy.pdf"))
        assert "pymupdf not installed" in result

    # Restore
    import importlib

    from src.ingestion import pdf_parser

    importlib.reload(pdf_parser)


def test_parse_pdf_file_with_mock_fitz(tmp_path: Path) -> None:
    """parse_pdf_file should call fitz correctly and produce one Document per page."""
    from dataclasses import dataclass, field

    @dataclass
    class FakeDocument:
        text: str = ""
        metadata: dict[str, object] = field(default_factory=dict)

    # Create a mock fitz module
    mock_fitz = types.ModuleType("fitz")

    mock_page = mock.MagicMock()
    mock_page.get_text.return_value = "Hello from page 1"

    mock_doc = mock.MagicMock()
    mock_doc.__len__ = mock.MagicMock(return_value=1)
    mock_doc.__getitem__ = mock.MagicMock(return_value=mock_page)

    mock_fitz.open = mock.MagicMock(return_value=mock_doc)

    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")

    # Also mock llama_index Document to use our FakeDocument
    mock_schema = mock.MagicMock()
    mock_schema.Document = FakeDocument

    with mock.patch.dict(sys.modules, {
        "fitz": mock_fitz,
        "llama_index.core.schema": mock_schema,
    }):
        import importlib

        from src.ingestion import pdf_parser

        importlib.reload(pdf_parser)

        result = pdf_parser.parse_pdf_file(pdf_path)

    assert len(result) == 1
    assert result[0].text == "Hello from page 1"
    assert result[0].metadata["file_type"] == "pdf"
    assert result[0].metadata["page_number"] == 1
    assert result[0].metadata["doc_type"] == "document"
    assert result[0].metadata["file_name"] == "test.pdf"

    # Restore
    import importlib

    from src.ingestion import pdf_parser

    importlib.reload(pdf_parser)


def test_format_pdf_as_text_with_mock_fitz(tmp_path: Path) -> None:
    """format_pdf_as_text should return page-separated text."""
    mock_fitz = types.ModuleType("fitz")

    mock_page = mock.MagicMock()
    mock_page.get_text.return_value = "Content on page one"

    mock_doc = mock.MagicMock()
    mock_doc.__len__ = mock.MagicMock(return_value=1)
    mock_doc.__getitem__ = mock.MagicMock(return_value=mock_page)

    mock_fitz.open = mock.MagicMock(return_value=mock_doc)

    pdf_path = tmp_path / "report.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")

    with mock.patch.dict(sys.modules, {"fitz": mock_fitz}):
        import importlib

        from src.ingestion import pdf_parser

        importlib.reload(pdf_parser)

        result = pdf_parser.format_pdf_as_text(pdf_path)

    assert "Page 1" in result
    assert "Content on page one" in result

    # Restore
    import importlib

    from src.ingestion import pdf_parser

    importlib.reload(pdf_parser)
