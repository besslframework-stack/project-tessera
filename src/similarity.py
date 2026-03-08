"""Find documents similar to a given document or text snippet."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np

import lancedb

from src.config import settings
from src.embedding import embed_query
from src.search import _parse_meta

logger = logging.getLogger(__name__)

_TABLE_NAME = "ontology_chunks"


def _build_result(meta: dict[str, Any], similarity: float, text: str) -> dict[str, Any]:
    """Build a standardised result dict from chunk metadata.

    Args:
        meta: Parsed metadata dict for the chunk.
        similarity: Similarity score (0-1, higher is better).
        text: Full chunk text.

    Returns:
        Dict with source_path, file_name, section, similarity, text_preview.
    """
    return {
        "source_path": meta.get("source_path", ""),
        "file_name": meta.get("file_name", ""),
        "section": meta.get("section", ""),
        "similarity": similarity,
        "text_preview": text[:200] if text else "",
    }


def _deduplicate_by_source(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Keep only the highest-similarity result per source_path.

    Args:
        rows: List of result dicts with 'source_path' and 'similarity'.

    Returns:
        Deduplicated list, one entry per unique source_path.
    """
    best: dict[str, dict[str, Any]] = {}
    for row in rows:
        sp = row["source_path"]
        existing = best.get(sp)
        if existing is None or row["similarity"] > existing["similarity"]:
            best[sp] = row
    return list(best.values())


def _open_table() -> Any | None:
    """Connect to LanceDB and open the ontology_chunks table.

    Returns:
        The LanceDB table object, or None if the database or table
        does not exist.
    """
    db_path = str(settings.data.lancedb_path)
    if not Path(db_path).exists():
        logger.debug("LanceDB path does not exist: %s", db_path)
        return None

    db = lancedb.connect(db_path)
    if _TABLE_NAME not in db.table_names():
        logger.debug("Table '%s' not found in LanceDB", _TABLE_NAME)
        return None

    return db.open_table(_TABLE_NAME)


def find_similar_documents(
    source_path: str,
    top_k: int = 5,
    exclude_same_file: bool = True,
) -> list[dict[str, Any]]:
    """Find documents similar to a given source file.

    Uses the average embedding of all chunks from the source file
    to find similar chunks from other files.

    Args:
        source_path: Path to the reference document.
        top_k: Number of similar documents to return.
        exclude_same_file: Whether to exclude chunks from the same file.

    Returns:
        List of dicts with 'source_path', 'file_name', 'section',
        'similarity', 'text_preview' (first 200 chars).
        Deduplicated by source_path (keeps highest similarity per file).
    """
    table = _open_table()
    if table is None:
        return []

    # Scan the table and filter chunks belonging to source_path
    all_rows = table.to_list()
    source_chunks: list[dict[str, Any]] = []
    for row in all_rows:
        meta = _parse_meta(row.get("metadata", {}))
        if meta.get("source_path") == source_path:
            source_chunks.append(row)

    if not source_chunks:
        logger.info("No chunks found for source_path: %s", source_path)
        return []

    # Compute average embedding vector from the file's chunks
    vectors = [row["vector"] for row in source_chunks if "vector" in row]
    if not vectors:
        logger.warning("No embedding vectors found for source_path: %s", source_path)
        return []

    avg_vector = np.mean(vectors, axis=0).tolist()

    # Search with the average vector
    fetch_k = top_k * 3
    raw_results = table.search(avg_vector).limit(fetch_k).to_list()

    # Filter and build results
    results: list[dict[str, Any]] = []
    for row in raw_results:
        meta = _parse_meta(row.get("metadata", {}))

        # Exclude same file if requested
        if exclude_same_file and meta.get("source_path") == source_path:
            continue

        # Exclude "full" section chunks (legacy data)
        if meta.get("section") == "full":
            continue

        # Compute similarity from distance
        dist = row.get("_distance")
        if dist is not None:
            similarity = max(0.0, min(1.0, 1.0 - float(dist)))
        else:
            similarity = 0.0

        results.append(_build_result(meta, similarity, row.get("text", "")))

    # Deduplicate by source_path (keep highest similarity per file)
    results = _deduplicate_by_source(results)

    # Sort by similarity descending and return top_k
    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results[:top_k]


def find_similar_to_text(
    text: str,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Find documents similar to a given text snippet.

    Args:
        text: Text to find similar documents for.
        top_k: Number of results.

    Returns:
        Same format as find_similar_documents: list of dicts with
        'source_path', 'file_name', 'section', 'similarity', 'text_preview'.
    """
    table = _open_table()
    if table is None:
        return []

    vector = embed_query(text)

    fetch_k = top_k * 3
    raw_results = table.search(vector).limit(fetch_k).to_list()

    results: list[dict[str, Any]] = []
    for row in raw_results:
        meta = _parse_meta(row.get("metadata", {}))

        # Exclude "full" section chunks (legacy data)
        if meta.get("section") == "full":
            continue

        dist = row.get("_distance")
        if dist is not None:
            similarity = max(0.0, min(1.0, 1.0 - float(dist)))
        else:
            similarity = 0.0

        results.append(_build_result(meta, similarity, row.get("text", "")))

    # Deduplicate by source_path (keep highest similarity per file)
    results = _deduplicate_by_source(results)

    # Sort by similarity descending and return top_k
    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results[:top_k]
