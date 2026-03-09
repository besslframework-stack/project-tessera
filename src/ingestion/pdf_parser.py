"""Parse PDF files into LlamaIndex Documents."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from llama_index.core.schema import Document

logger = logging.getLogger(__name__)


def parse_pdf_file(file_path: Path) -> list["Document"]:
    """Parse a PDF file into Documents. Each page becomes a Document.

    Args:
        file_path: Path to the PDF file.

    Returns:
        List of Documents, one per page with non-empty text.
    """
    try:
        import fitz  # pymupdf
    except ImportError:
        logger.warning("pymupdf not installed, skipping PDF: %s", file_path)
        return []

    from llama_index.core.schema import Document

    try:
        doc = fitz.open(str(file_path))
    except Exception as exc:
        logger.error("Failed to open PDF %s: %s", file_path, exc)
        return []

    documents: list[Document] = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text().strip()
        if not text:
            continue

        documents.append(
            Document(
                text=text,
                metadata={
                    "source_path": str(file_path),
                    "file_name": file_path.name,
                    "file_type": "pdf",
                    "page_number": page_num + 1,
                    "doc_type": "document",
                },
            )
        )

    doc.close()
    return documents


def format_pdf_as_text(file_path: Path) -> str:
    """Read a PDF file and return its full contents as plain text.

    Each page is separated by a header line showing the page number.

    Args:
        file_path: Path to the PDF file.

    Returns:
        Full text content of the PDF, or an error message.
    """
    try:
        import fitz  # pymupdf
    except ImportError:
        return "pymupdf not installed. Run: pip install pymupdf"

    try:
        doc = fitz.open(str(file_path))
    except Exception as exc:
        return f"Failed to open {file_path.name}: {exc}"

    parts: list[str] = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text().strip()
        if text:
            parts.append(f"### Page {page_num + 1}\n\n{text}")

    doc.close()
    return "\n\n".join(parts) if parts else f"No text found in {file_path.name}"
