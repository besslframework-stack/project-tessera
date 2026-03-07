"""Extract structured metadata from documents using regex patterns."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from llama_index.core.schema import Document


# Regex patterns for common document metadata
PATTERNS = {
    "version": re.compile(r"(?:버전|version)[:\s]+v?(\d+(?:\.\d+)?)", re.IGNORECASE),
    "date": re.compile(r"(?:작성일|날짜|일자|date|created)[:\s]+([\d\-\.]+)", re.IGNORECASE),
    "priority": re.compile(r"\b(P[012])\b"),
    "phase": re.compile(r"Phase\s*(\d+)", re.IGNORECASE),
    # Requirement IDs (e.g. REQ-001, TR-01, AI-01)
    "req_id": re.compile(r"\b([A-Z]{2,4}-\d{2,3})\b"),
}

# Max chars for any single metadata value (prevents bloat from false-positive regex matches)
_MAX_META_VALUE_LEN = 200


def enrich_metadata(document: "Document") -> "Document":
    """Add extracted metadata fields to a document using regex patterns.

    This runs before LLM-based entity extraction to provide hints.
    Existing metadata keys are not overwritten.
    """
    text = document.text

    for key, pattern in PATTERNS.items():
        # Skip if already set from parsing
        if f"detected_{key}" in document.metadata:
            continue
        matches = pattern.findall(text)
        if matches:
            # Deduplicate while preserving order
            seen: set = set()
            unique = [m for m in matches if not (m in seen or seen.add(m))]  # type: ignore[func-returns-value]
            if len(unique) == 1:
                value = unique[0]
            else:
                value = ", ".join(unique)

            # Truncate to prevent metadata bloat
            if len(value) > _MAX_META_VALUE_LEN:
                value = value[:_MAX_META_VALUE_LEN]

            document.metadata[f"detected_{key}"] = value

    return document


def enrich_documents(documents: "list[Document]") -> "list[Document]":
    """Enrich a list of documents with extracted metadata."""
    return [enrich_metadata(doc) for doc in documents]
