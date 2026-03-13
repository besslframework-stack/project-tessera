"""Contradiction detection: find memories that conflict with each other.

Extends decision_tracker's topic grouping with semantic contradiction detection.
Inspired by Tether's drift detection and Fleming's grounding validation.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime

from src.decision_tracker import _extract_topic_keywords, _topic_similarity

logger = logging.getLogger(__name__)

# Negation patterns (EN + KO) that indicate opposing decisions
_NEGATION_PATTERNS_EN = [
    (r"\bnot\b", None),
    (r"\bstop\b", r"\b(?:start|begin|continue)\b"),
    (r"\bremove\b", r"\b(?:add|keep|use)\b"),
    (r"\breplace\b", r"\b(?:keep|use)\b"),
    (r"\bswitch from\b", r"\bswitch to\b"),
    (r"\binstead of\b", None),
    (r"\bno longer\b", None),
    (r"\bdeprecate\b", r"\b(?:adopt|use)\b"),
]

_NEGATION_PATTERNS_KO = [
    ("안 쓰", "쓰기로"),
    ("중단", "시작"),
    ("중단", "계속"),
    ("제거", "추가"),
    ("대체", "유지"),
    ("전환", "유지"),
    ("폐기", "도입"),
    ("안 하", "하기로"),
    ("그만", "계속"),
    ("그만", "시작"),
]


def _normalize_content(text: str) -> str:
    """Normalize text for comparison."""
    return re.sub(r"\s+", " ", text.strip().lower())


def _has_negation_signal(text_a: str, text_b: str) -> bool:
    """Check if two texts show negation patterns suggesting contradiction.

    Looks for cases like:
    - "use PostgreSQL" vs "stop using PostgreSQL"
    - "React 쓰기로 했다" vs "React 안 쓰기로 했다"
    """
    a_lower = text_a.lower()
    b_lower = text_b.lower()

    # English patterns
    for neg, pos in _NEGATION_PATTERNS_EN:
        if pos:
            if re.search(neg, a_lower) and re.search(pos, b_lower):
                return True
            if re.search(pos, a_lower) and re.search(neg, b_lower):
                return True
        else:
            # Unidirectional negation
            if re.search(neg, a_lower) and not re.search(neg, b_lower):
                return True
            if re.search(neg, b_lower) and not re.search(neg, a_lower):
                return True

    # Korean patterns
    for neg, pos in _NEGATION_PATTERNS_KO:
        if neg in a_lower and pos in b_lower:
            return True
        if pos in a_lower and neg in b_lower:
            return True

    return False


def _extract_subject(text: str) -> set[str]:
    """Extract the subject/target of a decision (what it's about).

    Returns significant nouns/proper nouns that identify what the decision targets.
    """
    # Extract capitalized words (likely proper nouns: React, PostgreSQL, etc.)
    proper = set(re.findall(r"[A-Z][a-zA-Z]+", text))
    # Extract Korean nouns (2+ char sequences)
    korean = set(re.findall(r"[가-힣]{2,}", text))
    return proper | korean


def detect_contradictions(
    memories: list[dict],
    topic_threshold: float = 0.3,
    min_subject_overlap: int = 1,
) -> list[dict]:
    """Detect contradictions among memories.

    A contradiction is detected when:
    1. Two memories share the same topic (keyword overlap >= threshold)
    2. They have different content (not just rephrased)
    3. They show negation signals OR share subjects but differ in stance

    Args:
        memories: List of memory dicts with 'content', 'date', 'category'.
        topic_threshold: Minimum Jaccard similarity for same-topic grouping.
        min_subject_overlap: Minimum shared subjects to consider related.

    Returns:
        List of contradiction dicts with 'memory_a', 'memory_b', 'reason',
        'topic_keywords', and 'severity'.
    """
    # Focus on decisions and preferences (most likely to contradict)
    relevant = [
        m for m in memories
        if m.get("category", "").lower() in ("decision", "preference", "fact")
    ]

    if len(relevant) < 2:
        return []

    # Sort by date
    relevant.sort(key=lambda m: m.get("date", ""))

    contradictions = []
    checked = set()

    for i, mem_a in enumerate(relevant):
        kw_a = _extract_topic_keywords(mem_a.get("content", ""))
        subj_a = _extract_subject(mem_a.get("content", ""))
        content_a = _normalize_content(mem_a.get("content", ""))

        for j, mem_b in enumerate(relevant):
            if j <= i:
                continue

            pair_key = (id(mem_a), id(mem_b))
            if pair_key in checked:
                continue
            checked.add(pair_key)

            kw_b = _extract_topic_keywords(mem_b.get("content", ""))
            topic_sim = _topic_similarity(kw_a, kw_b)

            if topic_sim < topic_threshold:
                continue

            content_b = _normalize_content(mem_b.get("content", ""))

            # Same content = not a contradiction
            if content_a == content_b:
                continue

            subj_b = _extract_subject(mem_b.get("content", ""))
            shared_subjects = subj_a & subj_b

            # Check contradiction signals
            reason = None
            severity = "low"

            if _has_negation_signal(content_a, content_b):
                reason = "negation pattern detected"
                severity = "high"
            elif len(shared_subjects) >= min_subject_overlap and topic_sim >= 0.5:
                reason = f"same subject ({', '.join(list(shared_subjects)[:3])}) with different stance"
                severity = "medium"

            if reason:
                # Determine which is newer
                date_a = mem_a.get("date", "")
                date_b = mem_b.get("date", "")
                if date_a and date_b:
                    newer = mem_b if date_b > date_a else mem_a
                    older = mem_a if newer is mem_b else mem_b
                else:
                    newer, older = mem_b, mem_a

                shared_kw = kw_a & kw_b
                contradictions.append({
                    "memory_a": older,
                    "memory_b": newer,
                    "reason": reason,
                    "topic_keywords": sorted(shared_kw)[:5],
                    "severity": severity,
                    "newer_date": newer.get("date", "")[:10],
                    "older_date": older.get("date", "")[:10],
                })

    # Sort by severity (high first), then by newer_date (recent first)
    severity_order = {"high": 0, "medium": 1, "low": 2}
    contradictions.sort(
        key=lambda c: (severity_order.get(c["severity"], 3), c.get("newer_date", "")),
    )

    return contradictions


def format_contradictions(contradictions: list[dict]) -> str:
    """Format contradictions into readable text.

    Args:
        contradictions: List from detect_contradictions().

    Returns:
        Markdown-formatted contradiction report.
    """
    if not contradictions:
        return "No contradictions detected in your memories."

    lines = [
        f"# Contradiction Report ({len(contradictions)} found)",
        "",
    ]

    for i, c in enumerate(contradictions, 1):
        severity = c["severity"].upper()
        topic = ", ".join(c["topic_keywords"][:3]) if c["topic_keywords"] else "unknown"
        reason = c["reason"]

        lines.append(f"## [{severity}] #{i}: {topic}")
        lines.append(f"**Reason**: {reason}")
        lines.append("")

        # Older memory
        older = c["memory_a"]
        older_date = c["older_date"] or "?"
        older_content = older.get("content", "").strip()
        if len(older_content) > 200:
            older_content = older_content[:197] + "..."
        lines.append(f"**Earlier** [{older_date}]: {older_content}")

        # Newer memory
        newer = c["memory_b"]
        newer_date = c["newer_date"] or "?"
        newer_content = newer.get("content", "").strip()
        if len(newer_content) > 200:
            newer_content = newer_content[:197] + "..."
        lines.append(f"**Later** [{newer_date}]: {newer_content}")

        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)
