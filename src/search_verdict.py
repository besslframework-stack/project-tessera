"""Search verdict: classify search results as found/weak/none based on similarity.

Provides confidence labels so AI tools can distinguish reliable results
from uncertain ones. Thresholds derived from channeltalk-mcp patterns.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Similarity thresholds (cosine similarity 0-1)
THRESHOLD_FOUND = 0.45  # Strong match
THRESHOLD_WEAK = 0.25   # Possible match


def classify_verdict(similarity: float) -> str:
    """Classify a single similarity score into a verdict label.

    Args:
        similarity: Cosine similarity score (0.0-1.0).

    Returns:
        "found" (>= 0.45), "weak" (0.25-0.45), or "none" (< 0.25).
    """
    if similarity >= THRESHOLD_FOUND:
        return "found"
    elif similarity >= THRESHOLD_WEAK:
        return "weak"
    return "none"


def add_verdicts(results: list[dict], score_key: str = "similarity") -> list[dict]:
    """Add verdict labels to a list of search/recall results.

    Mutates each dict in-place by adding a 'verdict' key.

    Args:
        results: List of result dicts, each with a similarity score.
        score_key: Key name for the similarity score field.

    Returns:
        The same list with 'verdict' added to each dict.
    """
    for r in results:
        score = r.get(score_key, 0.0)
        r["verdict"] = classify_verdict(score)
    return results


def compute_overall_verdict(results: list[dict]) -> str:
    """Compute an overall verdict for a set of results.

    Returns:
        "found" if any result is found, "weak" if any is weak, else "none".
    """
    if not results:
        return "none"

    verdicts = {r.get("verdict", classify_verdict(r.get("similarity", 0.0))) for r in results}

    if "found" in verdicts:
        return "found"
    if "weak" in verdicts:
        return "weak"
    return "none"


def format_verdict_label(verdict: str) -> str:
    """Format verdict for display in search output.

    Args:
        verdict: "found", "weak", or "none".

    Returns:
        Human-readable label string.
    """
    labels = {
        "found": "confident match",
        "weak": "possible match",
        "none": "low relevance",
    }
    return labels.get(verdict, verdict)
