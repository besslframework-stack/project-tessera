"""Auto-extract: detect decisions, preferences, and facts from text.

Uses regex + heuristic patterns (no LLM calls) to identify knowledge
worth remembering from tool interactions. This is the core of the
Sponge auto-learning pipeline.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ExtractedFact:
    """A piece of knowledge extracted from text."""

    content: str
    category: str  # decision, preference, fact, reference, context
    confidence: float  # 0.0 - 1.0
    source_text: str  # original text this was extracted from


# --- Pattern definitions ---

# Decision patterns: "we decided", "let's go with", "결정", "하기로"
_DECISION_PATTERNS = [
    re.compile(r"(?:we |I )?(?:decided|chose|picked|selected|went with|going with)\s+(.{10,200})", re.IGNORECASE),
    re.compile(r"(?:let'?s |we should |I'?ll )?(?:go with|use|stick with|switch to)\s+(.{10,200})", re.IGNORECASE),
    re.compile(r"(?:결정|선택|채택|확정)(?:했|하기로|함|했다|합니다|하겠습니다)[:\s]*(.{10,200})"),
    re.compile(r"(.{10,100})(?:으로|를|을)\s*(?:결정|선택|확정|채택)(?:했|합니다|함)", re.IGNORECASE),
    re.compile(r"(.{10,100})(?:하기로|하는 것으로)\s*(?:결정|합의|확정)", re.IGNORECASE),
]

# Preference patterns: "I prefer", "always use", "선호", "항상"
_PREFERENCE_PATTERNS = [
    re.compile(r"(?:I |we )?(?:prefer|like|want|favor|always use)\s+(.{10,200})", re.IGNORECASE),
    re.compile(r"(?:don'?t |never |avoid |hate )(?:use|like|want)\s+(.{10,200})", re.IGNORECASE),
    re.compile(r"(?:선호|좋아|싫어|기피|항상|매번|늘)\s*(.{10,200})"),
    re.compile(r"(.{10,100})(?:를|을)\s*(?:선호|기피|싫어)(?:합니다|해|함|한다)", re.IGNORECASE),
]

# Fact/definition patterns: "X is Y", "X means Y"
_FACT_PATTERNS = [
    re.compile(r"(?:note(?:\s+that)?|remember(?:\s+that)?|important|key point)[:\s]+(.{10,300})", re.IGNORECASE),
    re.compile(r"(?:잊지 ?마|기억해|중요한 ?것은|핵심은|참고)[:\s]*(.{10,300})"),
    re.compile(r"(?:the |a )?(?:rule|policy|standard|convention) is[:\s]+(.{10,200})", re.IGNORECASE),
]

# Explicit remember signals: "remember this", "이거 기억해"
_SIGNAL_PATTERNS = [
    re.compile(r"(?:remember this|don'?t forget|keep in mind|save this)[:\s]*(.{5,300})", re.IGNORECASE),
    re.compile(r"(?:이거 기억|기억해 ?둬|저장해 ?둬|잊지 ?마)[:\s]*(.{5,300})"),
]


def extract_facts(text: str) -> list[ExtractedFact]:
    """Extract learnable facts from text using pattern matching.

    Args:
        text: Input text (typically from a tool's input or output).

    Returns:
        List of extracted facts with categories and confidence scores.
    """
    if not text or len(text.strip()) < 20:
        return []

    facts: list[ExtractedFact] = []
    seen_contents: set[str] = set()

    def _add(content: str, category: str, confidence: float) -> None:
        clean = content.strip().rstrip(".")
        if len(clean) < 10 or clean.lower() in seen_contents:
            return
        seen_contents.add(clean.lower())
        facts.append(ExtractedFact(
            content=clean,
            category=category,
            confidence=confidence,
            source_text=text[:500],
        ))

    # Check explicit signals first (highest confidence)
    for pat in _SIGNAL_PATTERNS:
        for match in pat.finditer(text):
            _add(match.group(1), "fact", 0.95)

    # Decision patterns
    for pat in _DECISION_PATTERNS:
        for match in pat.finditer(text):
            _add(match.group(1), "decision", 0.85)

    # Preference patterns
    for pat in _PREFERENCE_PATTERNS:
        for match in pat.finditer(text):
            _add(match.group(1), "preference", 0.80)

    # Fact patterns
    for pat in _FACT_PATTERNS:
        for match in pat.finditer(text):
            _add(match.group(1), "fact", 0.75)

    return facts


def should_auto_learn(text: str, min_confidence: float = 0.75) -> list[ExtractedFact]:
    """Check if text contains facts worth auto-learning.

    Filters extracted facts by minimum confidence threshold.

    Args:
        text: Text to analyze.
        min_confidence: Minimum confidence to include a fact.

    Returns:
        List of facts above the confidence threshold.
    """
    return [f for f in extract_facts(text) if f.confidence >= min_confidence]
