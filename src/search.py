"""Hybrid search: vector + FTS with metadata filters, version ranking, and dedup."""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path

import lancedb
from lancedb.rerankers import LinearCombinationReranker

from src.config import settings, workspace

logger = logging.getLogger(__name__)

_TABLE_NAME = "ontology_chunks"
_FTS_READY = False  # Module-level cache for FTS index status

# Simple TTL cache for search results
_search_cache: dict[str, tuple[float, list[dict]]] = {}
_CACHE_TTL = 60.0  # seconds
_CACHE_MAX = 64


def _cache_key(query: str, top_k: int, project: str | None, doc_type: str | None) -> str:
    return f"{query}|{top_k}|{project}|{doc_type}"


def _get_cached(key: str) -> list[dict] | None:
    entry = _search_cache.get(key)
    if entry is None:
        return None
    ts, results = entry
    if time.monotonic() - ts > _CACHE_TTL:
        del _search_cache[key]
        return None
    return results


def _put_cache(key: str, results: list[dict]) -> None:
    # Evict oldest if full
    if len(_search_cache) >= _CACHE_MAX:
        oldest_key = min(_search_cache, key=lambda k: _search_cache[k][0])
        del _search_cache[oldest_key]
    _search_cache[key] = (time.monotonic(), results)


def invalidate_search_cache() -> None:
    """Clear the search cache. Called after sync operations."""
    _search_cache.clear()


def _clean_query(text: str) -> str:
    """Preprocess query text for better search quality.

    - Strip markdown formatting
    - Normalize whitespace
    - Remove common filler phrases
    """
    # Remove markdown syntax
    text = re.sub(r"[#*`\[\]()>~_]", " ", text)
    # Remove URLs
    text = re.sub(r"https?://\S+", "", text)
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _embed_query(text: str) -> list[float]:
    """Get embedding vector using the configured embedding model."""
    from src.embedding import embed_query as _cached_embed
    return _cached_embed(text)


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
    """Remove duplicate chunks by (source_path, section) and content_hash.

    Uses two-pass dedup:
    1. Content hash: identical text across files → keep highest similarity
    2. Source+section: same section from same file → keep highest similarity
    """
    # Pass 1: content hash dedup (cross-file identical text)
    by_hash: dict[str, dict] = {}
    no_hash: list[dict] = []
    for row in rows:
        chash = row.get("content_hash")
        if chash:
            existing = by_hash.get(chash)
            if existing is None or row.get("similarity", 0) > existing.get("similarity", 0):
                by_hash[chash] = row
        else:
            no_hash.append(row)

    deduped = list(by_hash.values()) + no_hash

    # Pass 2: source+section dedup
    seen: dict[tuple[str, str], dict] = {}
    for row in deduped:
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
    # Check cache first
    ck = _cache_key(query, top_k, project, doc_type)
    cached = _get_cached(ck)
    if cached is not None:
        logger.debug("Search cache hit for: %s", query[:50])
        return cached

    db_path = str(settings.data.lancedb_path)
    if not Path(db_path).exists():
        return []

    db = lancedb.connect(db_path)

    if _TABLE_NAME not in db.table_names():
        return []

    table = db.open_table(_TABLE_NAME)
    cleaned = _clean_query(query)
    vector = _embed_query(cleaned or query)
    sc = workspace.search
    fetch_k = top_k * sc.fetch_multiplier

    # Try hybrid search, fallback to vector-only
    fts_ok = _ensure_fts_index(table)

    if fts_ok:
        try:
            reranker = LinearCombinationReranker(weight=sc.reranker_weight)
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

    result = rows[:top_k]
    _put_cache(ck, result)
    return result


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


def suggest_alternative_queries(query: str, top_k: int = 3) -> list[str]:
    """Generate alternative query suggestions when a search returns zero results.

    Strategies:
    1. Remove stop words and try core terms
    2. Try individual significant words from the query
    3. Try broader terms by removing specifics (numbers, versions)

    Returns up to top_k alternative query strings.
    """
    korean_stop_words: set[str] = {
        "에", "에서", "은", "는", "이", "가", "을", "를", "와", "과",
        "의", "로", "으로", "에게", "한", "된", "하는", "있는", "대한", "위한",
    }
    english_stop_words: set[str] = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "shall",
        "should", "may", "might", "can", "could", "must", "about", "for",
        "with", "from", "this", "that", "these", "those", "what", "how",
        "when", "where", "which", "who", "why",
    }
    all_stop_words = korean_stop_words | english_stop_words

    original_cleaned = re.sub(r"\s+", " ", query.strip())
    suggestions: list[str] = []
    seen: set[str] = {original_cleaned.lower()}

    def _add(candidate: str) -> None:
        normalized = re.sub(r"\s+", " ", candidate.strip())
        if normalized and normalized.lower() not in seen:
            seen.add(normalized.lower())
            suggestions.append(normalized)

    # Strategy 1: Remove stop words and try core terms
    words = original_cleaned.split()
    core_words = [w for w in words if w.lower() not in all_stop_words]
    if core_words:
        core_query = " ".join(core_words)
        _add(core_query)

    # Strategy 2: Try individual significant words (>= 3 chars)
    significant = [w for w in core_words if len(w) >= 3]
    for word in significant:
        if len(suggestions) >= top_k:
            break
        _add(word)

    # Strategy 3: Remove numbers/versions (e.g. v1.0, 3.2) from query
    stripped = re.sub(r"\bv?\d+(?:\.\d+)+\b", "", original_cleaned, flags=re.IGNORECASE)
    stripped = re.sub(r"\s+", " ", stripped).strip()
    if stripped:
        _add(stripped)

    return suggestions[:top_k]


def highlight_matches(text: str, query: str, context_chars: int = 80) -> str:
    """Extract and highlight the most relevant snippets from text matching the query.

    Finds occurrences of query words in the text and returns snippets
    with surrounding context, with matched words wrapped in **bold**.

    Args:
        text: The full text to search within.
        query: The search query (words will be searched individually).
        context_chars: Number of chars to show before/after each match.

    Returns:
        Formatted string with highlighted snippets, separated by "...".
        Returns first 200 chars of text if no word matches found.
    """
    cleaned = _clean_query(query)
    words = [w for w in cleaned.split() if len(w) >= 3]

    if not words or not text:
        return text[:200]

    # Collect match spans: (start, end) of snippets
    snippet_spans: list[tuple[int, int]] = []
    matched_positions: list[tuple[int, int, str]] = []  # (start, end, word)

    for word in words:
        for m in re.finditer(re.escape(word), text, re.IGNORECASE):
            matched_positions.append((m.start(), m.end(), word))
            snip_start = max(0, m.start() - context_chars)
            snip_end = min(len(text), m.end() + context_chars)
            snippet_spans.append((snip_start, snip_end))

    if not snippet_spans:
        return text[:200]

    # Merge overlapping spans
    snippet_spans.sort()
    merged: list[tuple[int, int]] = [snippet_spans[0]]
    for start, end in snippet_spans[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))

    # Build snippets with bold highlighting
    snippets: list[str] = []
    for span_start, span_end in merged:
        snippet = text[span_start:span_end]
        # Bold all matched words within this snippet
        for word in words:
            snippet = re.sub(
                re.escape(word),
                lambda m: f"**{m.group(0)}**",
                snippet,
                flags=re.IGNORECASE,
            )
        snippets.append(snippet.strip())

    result = " ... ".join(snippets)
    return result[:500]
