"""Hybrid search: vector + FTS with metadata filters, version ranking, and dedup."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import lancedb
from lancedb.rerankers import LinearCombinationReranker

from src.config import settings
from src.embedding import get_embed_model

logger = logging.getLogger(__name__)

_TABLE_NAME = "ontology_chunks"
_FTS_READY = False  # Module-level cache for FTS index status


def _embed_query(text: str) -> list[float]:
    """Get embedding vector using the configured embedding model."""
    model = get_embed_model()
    embeddings = list(model.embed([text]))
    return embeddings[0].tolist()


def _ensure_fts_index(table) -> bool:
    """Create FTS index on text column if not already present (idempotent)."""
    global _FTS_READY
    if _FTS_READY:
        return True
    try:
        table.create_fts_index("text", replace=True)
        _FTS_READY = True
        logger.info("FTS index created/verified on '%s'", _TABLE_NAME)
        return True
    except Exception as exc:
        logger.warning("FTS index creation failed (will use vector-only): %s", exc)
        return False


def _extract_version(filename: str) -> tuple[int, ...]:
    """Extract version tuple from filename like PRD_xxx_v3.19.md -> (3, 19)."""
    m = re.search(r"_v(\d+(?:\.\d+)*)", filename, re.IGNORECASE)
    if m:
        return tuple(int(x) for x in m.group(1).split("."))
    return (0,)


def _rank_prefer_latest_version(rows: list[dict]) -> list[dict]:
    """Among rows from the same PRD (base filename), prefer the latest version."""
    # Group by base filename (without version suffix)
    groups: dict[str, list[dict]] = {}
    for row in rows:
        meta = row.get("metadata", {})
        fname = meta.get("file_name", "")
        # Normalize: strip version to get base name
        base = re.sub(r"_v\d+(?:\.\d+)*", "", fname, flags=re.IGNORECASE)
        groups.setdefault(base, []).append(row)

    result = []
    for base, group_rows in groups.items():
        if len(group_rows) <= 1:
            result.extend(group_rows)
            continue

        # Find the max version in this group
        max_version = max(
            _extract_version(r.get("metadata", {}).get("file_name", ""))
            for r in group_rows
        )

        for r in group_rows:
            ver = _extract_version(r.get("metadata", {}).get("file_name", ""))
            if ver == max_version:
                result.append(r)
            else:
                # Penalize older versions by reducing similarity
                r["similarity"] = r.get("similarity", 0.0) * 0.5
                result.append(r)

    return result


def _deduplicate_chunks(rows: list[dict]) -> list[dict]:
    """Remove duplicate chunks by (source_path, section), keeping highest similarity."""
    seen: dict[tuple[str, str], dict] = {}
    for row in rows:
        meta = row.get("metadata", {})
        key = (meta.get("source_path", ""), meta.get("section", ""))
        existing = seen.get(key)
        if existing is None or row.get("similarity", 0) > existing.get("similarity", 0):
            seen[key] = row
    return list(seen.values())


def _parse_meta(meta) -> dict:
    """Ensure metadata is a dict."""
    if isinstance(meta, dict):
        return meta
    if isinstance(meta, str):
        try:
            return json.loads(meta)
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def search(
    query: str,
    top_k: int = 5,
    project: str | None = None,
    doc_type: str | None = None,
) -> list[dict]:
    """Search LanceDB with hybrid vector+FTS, metadata filters, version ranking, and dedup.

    Args:
        query: Search query text.
        top_k: Number of results to return.
        project: Filter by project name (e.g. 'valley_llm').
        doc_type: Filter by document type (e.g. 'prd', 'session_log').

    Returns:
        List of dicts with 'text', 'metadata', 'similarity' keys.
        similarity is normalized 0-1 (higher = more relevant).
    """
    db_path = str(settings.data.lancedb_path)
    if not Path(db_path).exists():
        return []

    db = lancedb.connect(db_path)

    if _TABLE_NAME not in db.table_names():
        return []

    table = db.open_table(_TABLE_NAME)
    vector = _embed_query(query)
    fetch_k = top_k * 6  # Over-fetch for filtering/reranking

    # Try hybrid search, fallback to vector-only
    fts_ok = _ensure_fts_index(table)

    if fts_ok:
        try:
            reranker = LinearCombinationReranker(weight=0.7)
            raw_results = (
                table.search(vector, query_type="hybrid")
                .text(query)
                .limit(fetch_k)
                .rerank(reranker=reranker)
                .to_list()
            )
        except Exception as exc:
            logger.warning("Hybrid search failed, falling back to vector: %s", exc)
            raw_results = table.search(vector).limit(fetch_k).to_list()
    else:
        raw_results = table.search(vector).limit(fetch_k).to_list()

    # Normalize into output dicts with similarity scores
    rows = []
    for row in raw_results:
        meta = _parse_meta(row.get("metadata", {}))

        # Filter out "full" section chunks (v2 legacy data)
        if meta.get("section") == "full":
            continue

        # Metadata filters (Python-side to avoid LanceDB hybrid+prefilter 0-result bug)
        if project and meta.get("project") != project:
            continue
        if doc_type and meta.get("doc_type") != doc_type:
            continue

        # Compute similarity from distance
        dist = row.get("_distance")
        relevance = row.get("_relevance_score")
        if relevance is not None:
            similarity = float(relevance)
        elif dist is not None:
            # Cosine distance -> similarity: sim = 1 - dist (clamped)
            similarity = max(0.0, min(1.0, 1.0 - float(dist)))
        else:
            similarity = 0.0

        rows.append({
            "text": row.get("text", ""),
            "metadata": meta,
            "similarity": similarity,
        })

    # Version-aware ranking
    rows = _rank_prefer_latest_version(rows)

    # Deduplicate by (source_path, section)
    rows = _deduplicate_chunks(rows)

    # Sort by similarity descending
    rows.sort(key=lambda x: x["similarity"], reverse=True)

    return rows[:top_k]


def list_indexed_sources() -> list[str]:
    """Return unique source file paths from the vector store."""
    db_path = str(settings.data.lancedb_path)
    if not Path(db_path).exists():
        return []

    db = lancedb.connect(db_path)

    if _TABLE_NAME not in db.table_names():
        return []

    table = db.open_table(_TABLE_NAME)
    df = table.to_pandas()

    if "metadata" not in df.columns:
        return []

    sources = set()
    for meta in df["metadata"]:
        m = _parse_meta(meta)
        if "source_path" in m:
            sources.add(m["source_path"])

    return sorted(sources)
