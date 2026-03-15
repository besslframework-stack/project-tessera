"""Sleep-time consolidation: autonomous memory maintenance cycle.

Runs conservative memory consolidation and contradiction resolution
in a single "sleep" cycle, meant to be called periodically (e.g., nightly).
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def run_sleep_cycle() -> dict:
    """Run a full sleep consolidation cycle.

    1. Find similar memory clusters (threshold=0.88, conservative).
    2. Auto-consolidate clusters with similarity >= 0.92 (very high confidence only).
    3. Run contradiction detection and auto-supersede high-severity ones.
    4. Return a summary dict.

    Returns:
        Dict with consolidated, superseded, clusters_found, skipped counts.
    """
    from pathlib import Path

    from src.consolidation import consolidate_cluster, find_similar_clusters
    from src.contradiction import detect_contradictions
    from src.memory import recall_memories, supersede_memory

    summary = {
        "consolidated": 0,
        "superseded": 0,
        "clusters_found": 0,
        "skipped": 0,
    }

    # Step 1: Find similar clusters (conservative threshold)
    try:
        clusters = find_similar_clusters(threshold=0.88, max_clusters=50)
    except Exception as exc:
        logger.warning("Sleep cycle: cluster search failed: %s", exc)
        clusters = []

    summary["clusters_found"] = len(clusters)

    # Step 2: Auto-consolidate only very high confidence clusters (>= 0.92)
    for cluster in clusters:
        sim = cluster.get("similarity", 0.0)
        if sim >= 0.92:
            try:
                result = consolidate_cluster(cluster)
                summary["consolidated"] += 1
                summary["superseded"] += result.get("superseded_count", 0)
            except Exception as exc:
                logger.warning("Sleep cycle: consolidation failed: %s", exc)
                summary["skipped"] += 1
        else:
            summary["skipped"] += 1

    # Step 3: Contradiction detection and auto-supersede high-severity
    try:
        memories = recall_memories("", top_k=200, include_superseded=False)
    except Exception as exc:
        logger.warning("Sleep cycle: recall failed: %s", exc)
        memories = []

    if memories:
        try:
            contradictions = detect_contradictions(memories)
        except Exception as exc:
            logger.warning("Sleep cycle: contradiction detection failed: %s", exc)
            contradictions = []

        for c in contradictions:
            if c.get("severity") == "high":
                older = c.get("memory_a", {})
                newer = c.get("memory_b", {})
                older_path = older.get("file_path", "")
                newer_name = (
                    Path(newer.get("file_path", "")).stem
                    if newer.get("file_path")
                    else ""
                )
                if older_path:
                    try:
                        if supersede_memory(Path(older_path), superseded_by=newer_name):
                            summary["superseded"] += 1
                    except Exception as exc:
                        logger.warning("Sleep cycle: supersede failed: %s", exc)

    return summary
