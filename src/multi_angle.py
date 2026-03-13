"""Multi-angle search: decompose a query into multiple perspectives and merge results.

Inspired by channeltalk-mcp's _build_search_angles pattern. Instead of searching
once, generates 2-4 angle queries and merges the best results per source.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)


def build_search_angles(query: str, max_angles: int = 4) -> list[str]:
    """Decompose a query into multiple search angles.

    Strategies:
    1. Original query (always included)
    2. Core keywords only (stop words removed)
    3. Individual significant terms (for broad recall)
    4. Reversed emphasis (if query has A+B, try B+A)

    Args:
        query: Original search query.
        max_angles: Maximum number of angles to generate.

    Returns:
        List of query strings (always includes original first).
    """
    cleaned = re.sub(r"\s+", " ", query.strip())
    if not cleaned:
        return [query]

    angles = [cleaned]
    seen = {cleaned.lower()}

    def _add(candidate: str) -> None:
        normalized = re.sub(r"\s+", " ", candidate.strip())
        if normalized and normalized.lower() not in seen:
            seen.add(normalized.lower())
            angles.append(normalized)

    # Tokenize: separate English and Korean
    tokens = re.findall(r"[a-zA-Z]+|[가-힣]+", cleaned)

    # Stop words
    stop_words = {
        "the", "a", "an", "is", "are", "was", "were", "be", "have", "has",
        "do", "does", "for", "with", "from", "this", "that", "what", "how",
        "when", "where", "which", "who", "why", "about", "can", "will",
        "에", "에서", "은", "는", "이", "가", "을", "를", "와", "과",
        "의", "로", "으로", "에게", "한", "된", "하는", "있는", "대한", "위한",
    }

    # Strategy 2: core keywords
    core = [t for t in tokens if t.lower() not in stop_words and len(t) >= 2]
    if core and len(core) < len(tokens):
        _add(" ".join(core))

    # Strategy 3: significant individual terms (longest first, for recall)
    significant = sorted(
        [t for t in core if len(t) >= 3],
        key=len,
        reverse=True,
    )
    for term in significant:
        if len(angles) >= max_angles:
            break
        _add(term)

    # Strategy 4: reversed order (A B C → C B A)
    if len(core) >= 2 and len(angles) < max_angles:
        _add(" ".join(reversed(core)))

    return angles[:max_angles]


def merge_results(
    all_results: list[list[dict]],
    top_k: int = 5,
    key_field: str = "file_path",
    score_field: str = "similarity",
) -> list[dict]:
    """Merge results from multiple search angles, keeping best score per source.

    For document search, key_field is typically metadata.source_path.
    For memory search, key_field is file_path.

    Args:
        all_results: List of result lists (one per angle).
        top_k: Maximum results to return.
        key_field: Field to deduplicate on.
        score_field: Field containing the similarity score.

    Returns:
        Merged and deduplicated results, sorted by best score.
    """
    best: dict[str, dict] = {}

    for results in all_results:
        for r in results:
            # Extract key for deduplication
            if key_field == "source_path":
                meta = r.get("metadata", {})
                key = meta.get("source_path", "") + "|" + meta.get("section", "")
            else:
                key = r.get(key_field, str(id(r)))

            score = r.get(score_field, 0.0)
            existing = best.get(key)

            if existing is None or score > existing.get(score_field, 0.0):
                best[key] = r

    merged = sorted(best.values(), key=lambda x: x.get(score_field, 0.0), reverse=True)
    return merged[:top_k]


def multi_angle_search(
    query: str,
    search_fn,
    top_k: int = 5,
    max_angles: int = 3,
    **search_kwargs,
) -> list[dict]:
    """Execute multi-angle search using the provided search function.

    Args:
        query: Original search query.
        search_fn: Search function that takes (query, top_k, **kwargs) and returns list[dict].
        top_k: Number of final results.
        max_angles: Maximum search angles to generate.
        **search_kwargs: Additional kwargs passed to search_fn.

    Returns:
        Merged results from all angles.
    """
    angles = build_search_angles(query, max_angles=max_angles)
    logger.debug("Multi-angle search: %d angles for %r", len(angles), query[:50])

    all_results = []
    for angle in angles:
        try:
            results = search_fn(angle, top_k=top_k, **search_kwargs)
            all_results.append(results)
        except Exception as exc:
            logger.warning("Angle search failed for %r: %s", angle[:30], exc)

    if not all_results:
        return []

    # Detect key field based on result structure
    sample = all_results[0][0] if all_results[0] else {}
    if "metadata" in sample:
        key_field = "source_path"
    else:
        key_field = "file_path"

    return merge_results(all_results, top_k=top_k, key_field=key_field)


def multi_angle_recall(
    query: str,
    recall_fn,
    top_k: int = 5,
    max_angles: int = 3,
    **recall_kwargs,
) -> list[dict]:
    """Execute multi-angle recall for memories.

    Args:
        query: Original query.
        recall_fn: Recall function (query, top_k, **kwargs) -> list[dict].
        top_k: Number of final results.
        max_angles: Maximum angles.
        **recall_kwargs: Additional kwargs (since, until, category).

    Returns:
        Merged memory results.
    """
    angles = build_search_angles(query, max_angles=max_angles)

    all_results = []
    for angle in angles:
        try:
            results = recall_fn(angle, top_k=top_k, **recall_kwargs)
            all_results.append(results)
        except Exception as exc:
            logger.warning("Angle recall failed for %r: %s", angle[:30], exc)

    if not all_results:
        return []

    return merge_results(all_results, top_k=top_k, key_field="file_path")
