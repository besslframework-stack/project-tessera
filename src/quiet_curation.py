"""Quiet curation: invisible background maintenance for the knowledge base.

Runs automatically on server startup. No user action required.
The knowledge base gets cleaner every time you use any AI tool.

Pipeline:
1. Classify uncategorized memories
2. Tag untagged memories
3. Extract entities from un-processed memories
4. Auto-supersede high-severity contradictions
5. Merge near-duplicate memories (92%+ similarity)
6. Flag stale memories for retention review

Produces a compact summary for the next session's health pulse.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# Store the last curation result for session health pulse
_last_result: dict | None = None


def run_quiet_curation() -> dict:
    """Run the full quiet curation pipeline.

    Each step is independent and failure-isolated.
    Returns a summary dict with counts and timing.
    """
    global _last_result
    start = time.monotonic()

    result = {
        "classified": 0,
        "tagged": 0,
        "entities_extracted": 0,
        "contradictions_resolved": 0,
        "consolidated": 0,
        "retention_flagged": 0,
        "errors": [],
        "duration_ms": 0,
    }

    # 1-2. Classify + tag
    try:
        from src.auto_curator import _curate_metadata
        c, t = _curate_metadata()
        result["classified"] = c
        result["tagged"] = t
    except Exception as e:
        logger.debug("Quiet curation: metadata failed: %s", e)
        result["errors"].append(f"metadata: {e}")

    # 3. Entity extraction
    try:
        from src.auto_curator import _curate_entities
        result["entities_extracted"] = _curate_entities()
    except Exception as e:
        logger.debug("Quiet curation: entities failed: %s", e)
        result["errors"].append(f"entities: {e}")

    # 4. Contradiction resolution
    try:
        from src.auto_curator import _curate_contradictions
        result["contradictions_resolved"] = _curate_contradictions()
    except Exception as e:
        logger.debug("Quiet curation: contradictions failed: %s", e)
        result["errors"].append(f"contradictions: {e}")

    # 5. Near-duplicate consolidation
    try:
        from src.auto_curator import _curate_consolidation
        result["consolidated"] = _curate_consolidation()
    except Exception as e:
        logger.debug("Quiet curation: consolidation failed: %s", e)
        result["errors"].append(f"consolidation: {e}")

    # 6. Retention flagging
    try:
        from src.auto_curator import _curate_retention
        result["retention_flagged"] = _curate_retention()
    except Exception as e:
        logger.debug("Quiet curation: retention failed: %s", e)
        result["errors"].append(f"retention: {e}")

    result["duration_ms"] = round((time.monotonic() - start) * 1000)
    _last_result = result

    total = (
        result["classified"] + result["tagged"]
        + result["entities_extracted"] + result["contradictions_resolved"]
        + result["consolidated"]
    )
    if total > 0:
        logger.info(
            "Quiet curation complete: %d actions in %dms "
            "(classified=%d, tagged=%d, entities=%d, contradictions=%d, consolidated=%d)",
            total, result["duration_ms"],
            result["classified"], result["tagged"],
            result["entities_extracted"], result["contradictions_resolved"],
            result["consolidated"],
        )
    else:
        logger.debug("Quiet curation: knowledge base is clean (%dms)", result["duration_ms"])

    return result


def get_health_pulse() -> str | None:
    """Get a one-line health pulse from the last curation run.

    Returns None if no curation has run yet, or if nothing happened.
    Used by session primer to show "Last maintenance: ..." at session start.
    """
    if _last_result is None:
        return None

    r = _last_result
    total = (
        r["classified"] + r["tagged"]
        + r["entities_extracted"] + r["contradictions_resolved"]
        + r["consolidated"]
    )

    if total == 0:
        return None

    parts = []
    if r["classified"]:
        parts.append(f"{r['classified']} classified")
    if r["tagged"]:
        parts.append(f"{r['tagged']} tagged")
    if r["entities_extracted"]:
        parts.append(f"{r['entities_extracted']} entities")
    if r["contradictions_resolved"]:
        parts.append(f"{r['contradictions_resolved']} contradictions fixed")
    if r["consolidated"]:
        parts.append(f"{r['consolidated']} duplicates merged")
    if r["retention_flagged"]:
        parts.append(f"{r['retention_flagged']} at-risk")

    return f"Background maintenance: {', '.join(parts)}"
