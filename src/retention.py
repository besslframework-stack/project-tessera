"""Retention policy: manage memory lifecycle and archival.

Identifies old, low-confidence, and orphaned memories for archival.
Supports dry-run mode for safe preview before taking action.
"""

from __future__ import annotations

import logging
import shutil
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def _parse_date(date_str: str) -> datetime | None:
    """Parse ISO date string, returns None on failure."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str[:19])
    except (ValueError, TypeError):
        return None


def _is_orphaned(mem: dict) -> bool:
    """Check if a memory is orphaned (no meaningful metadata, short content)."""
    category = (mem.get("category") or "").strip()
    tags = mem.get("tags") or ""
    content = (mem.get("content") or "").strip()

    no_category = not category or category in ("general", "")
    if isinstance(tags, list):
        no_tags = len(tags) == 0
    else:
        no_tags = not tags or tags in ("general", "[]", "")
    short_content = len(content) < 30

    return no_category and no_tags and short_content


def apply_retention_policy(
    max_age_days: int = 180,
    min_confidence: float = 0.3,
    dry_run: bool = True,
) -> dict:
    """Apply retention policy to memories.

    Identifies candidates for archival based on:
    1. Age exceeding max_age_days
    2. Confidence score below min_confidence
    3. Orphaned status (no tags, no category, short content)

    Args:
        max_age_days: Maximum age in days before a memory is a candidate.
        min_confidence: Minimum confidence score threshold.
        dry_run: If True, only report candidates. If False, archive them.

    Returns:
        Dict with candidates count, archived count, and reasons list.
    """
    from src.memory import _memory_dir, recall_memories, supersede_memory
    from src.memory_confidence import compute_confidence

    now = datetime.now()
    reasons: list[dict] = []
    archived = 0

    # Get all active memories
    try:
        memories = recall_memories("", top_k=500, include_superseded=False)
    except Exception as exc:
        logger.warning("Retention policy: recall failed: %s", exc)
        return {"candidates": 0, "archived": 0, "reasons": []}

    if not memories:
        return {"candidates": 0, "archived": 0, "reasons": []}

    for mem in memories:
        reason = None
        age_days = 0
        confidence = 0.0

        # Check age
        date = _parse_date(mem.get("date", ""))
        if date:
            age_days = (now - date).days
        else:
            age_days = 0

        # Compute confidence
        try:
            conf_result = compute_confidence(mem, memories)
            confidence = conf_result.get("score", 0.5)
        except Exception:
            confidence = 0.5

        # Determine reason
        if age_days > max_age_days:
            reason = "exceeded_max_age"
        elif confidence < min_confidence:
            reason = "low_confidence"
        elif _is_orphaned(mem):
            reason = "orphaned"

        if reason:
            file_path = mem.get("file_path", "")
            reasons.append({
                "file": file_path,
                "reason": reason,
                "age_days": age_days,
                "confidence": round(confidence, 3),
            })

            if not dry_run and file_path:
                try:
                    src_path = Path(file_path)
                    if src_path.exists():
                        # Move to archive directory
                        archive_dir = _memory_dir().parent / "archive"
                        archive_dir.mkdir(parents=True, exist_ok=True)
                        dest = archive_dir / src_path.name
                        shutil.move(str(src_path), str(dest))

                        # Supersede in index
                        supersede_memory(src_path, superseded_by="retention_policy")
                        archived += 1
                except Exception as exc:
                    logger.warning("Retention: archive failed for %s: %s", file_path, exc)

    return {
        "candidates": len(reasons),
        "archived": archived,
        "reasons": reasons,
    }


def get_retention_summary() -> dict:
    """Get a quick summary of retention status without taking action.

    Returns:
        Dict with total memories, age distribution, and at-risk counts.
    """
    from src.memory import recall_memories

    now = datetime.now()

    try:
        memories = recall_memories("", top_k=500, include_superseded=False)
    except Exception:
        return {
            "total": 0,
            "age_distribution": {},
            "at_risk": 0,
            "orphaned": 0,
        }

    if not memories:
        return {
            "total": 0,
            "age_distribution": {},
            "at_risk": 0,
            "orphaned": 0,
        }

    age_buckets = {
        "0-30d": 0,
        "31-90d": 0,
        "91-180d": 0,
        "180d+": 0,
        "unknown": 0,
    }
    at_risk = 0
    orphaned_count = 0

    for mem in memories:
        date = _parse_date(mem.get("date", ""))
        if date:
            age = (now - date).days
            if age <= 30:
                age_buckets["0-30d"] += 1
            elif age <= 90:
                age_buckets["31-90d"] += 1
            elif age <= 180:
                age_buckets["91-180d"] += 1
            else:
                age_buckets["180d+"] += 1
                at_risk += 1
        else:
            age_buckets["unknown"] += 1

        if _is_orphaned(mem):
            orphaned_count += 1

    return {
        "total": len(memories),
        "age_distribution": age_buckets,
        "at_risk": at_risk,
        "orphaned": orphaned_count,
    }
