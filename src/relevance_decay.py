"""Relevance decay: time-based score adjustment for memories.

Older memories get a lower relevance score, so recent knowledge
is prioritized. Uses exponential decay with configurable half-life.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Default half-life in days: after this many days, score is halved
DEFAULT_HALF_LIFE_DAYS = 30


def compute_decay_factor(
    memory_date: str | datetime,
    reference_date: str | datetime | None = None,
    half_life_days: float = DEFAULT_HALF_LIFE_DAYS,
) -> float:
    """Compute exponential decay factor based on age.

    Args:
        memory_date: When the memory was created (ISO date string or datetime).
        reference_date: Reference point (default: now). ISO string or datetime.
        half_life_days: Days after which relevance halves.

    Returns:
        Decay factor between 0.0 and 1.0. Recent = close to 1.0.
    """
    mem_dt = _parse_date(memory_date)
    ref_dt = _parse_date(reference_date) if reference_date else datetime.now(timezone.utc)

    if mem_dt is None or ref_dt is None:
        return 1.0  # Can't compute, no penalty

    age_days = (ref_dt - mem_dt).total_seconds() / 86400
    if age_days <= 0:
        return 1.0  # Future or same day

    if half_life_days <= 0:
        return 1.0  # No decay

    # Exponential decay: 0.5^(age / half_life)
    return math.pow(0.5, age_days / half_life_days)


def apply_decay(
    memories: list[dict],
    reference_date: str | datetime | None = None,
    half_life_days: float = DEFAULT_HALF_LIFE_DAYS,
    min_factor: float = 0.1,
) -> list[dict]:
    """Apply time-based decay to memory scores and re-sort.

    Args:
        memories: List of memory dicts with 'score' and 'date'.
        reference_date: Reference point for age calculation.
        half_life_days: Days after which relevance halves.
        min_factor: Minimum decay factor (floor).

    Returns:
        Same list with 'score' adjusted and 'decay_factor' added, sorted by new score.
    """
    for mem in memories:
        date = mem.get("date", "")
        factor = compute_decay_factor(date, reference_date, half_life_days)
        factor = max(factor, min_factor)  # Apply floor
        original_score = mem.get("score", 1.0)
        mem["original_score"] = original_score
        mem["score"] = original_score * factor
        mem["decay_factor"] = round(factor, 4)

    # Re-sort by adjusted score
    memories.sort(key=lambda m: m.get("score", 0), reverse=True)
    return memories


def _parse_date(value: str | datetime | None) -> datetime | None:
    """Parse a date string or datetime to datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    # Try ISO format variants
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            dt = datetime.strptime(value.strip()[:19], fmt[:min(len(fmt), 19)])
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None
