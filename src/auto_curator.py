"""Auto-curator: autonomous memory classification, curation, and cleanup.

Runs as a single pipeline that:
1. Classifies untagged/uncategorized memories
2. Extracts entities from memories missing entity relationships
3. Detects and resolves contradictions
4. Consolidates duplicate clusters
5. Flags stale memories for retention review
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


# Category detection patterns
_CATEGORY_PATTERNS: list[tuple[str, list[str]]] = [
    ("decision", [
        r"(?:chose|decided|selected|picked|went with|switched to)",
        r"(?:결정|선택|채택|확정)",
        r"(?:we'll use|going with|from now on)",
    ]),
    ("preference", [
        r"(?:prefer|like|better|favorite|rather)",
        r"(?:선호|좋아|싫어|편함|불편)",
        r"(?:always use|never use|avoid)",
    ]),
    ("fact", [
        r"(?:is a|are|was|located|founded|created|built|version)",
        r"(?:이다|있다|이란|이라|라는|하는)",
        r"(?:API key|password|endpoint|port|URL)",
    ]),
    ("process", [
        r"(?:step \d|first|then|after|before|deploy|build|run)",
        r"(?:순서|단계|절차|방법|프로세스)",
        r"(?:how to|in order to|workflow)",
    ]),
    ("context", [
        r"(?:working on|currently|project|sprint|team)",
        r"(?:작업 중|진행 중|프로젝트|팀)",
        r"(?:this week|today|right now|status)",
    ]),
]

# Tag extraction patterns
_TAG_KEYWORDS: dict[str, list[str]] = {
    "db": ["database", "postgresql", "mysql", "sqlite", "mongodb", "redis", "sql"],
    "api": ["api", "endpoint", "rest", "graphql", "http", "grpc"],
    "auth": ["auth", "login", "password", "token", "oauth", "jwt", "session"],
    "deploy": ["deploy", "ci/cd", "docker", "kubernetes", "k8s", "nginx"],
    "frontend": ["react", "vue", "angular", "css", "html", "tailwind", "ui"],
    "backend": ["server", "fastapi", "django", "flask", "express", "node"],
    "ml": ["model", "training", "inference", "embedding", "llm", "ai"],
    "testing": ["test", "pytest", "jest", "coverage", "mock", "fixture"],
    "security": ["security", "encryption", "vulnerability", "xss", "csrf"],
    "infra": ["aws", "gcp", "azure", "terraform", "cloud", "serverless"],
}


def classify_memory(content: str) -> str:
    """Detect the most likely category for a memory based on content patterns."""
    content_lower = content.lower()
    scores: dict[str, int] = {}

    for category, patterns in _CATEGORY_PATTERNS:
        score = 0
        for pattern in patterns:
            if re.search(pattern, content_lower):
                score += 1
        if score > 0:
            scores[category] = score

    if not scores:
        return "fact"  # default

    return max(scores, key=scores.get)


def extract_tags(content: str) -> list[str]:
    """Extract relevant tags from memory content."""
    content_lower = content.lower()
    found_tags: list[str] = []

    for tag, keywords in _TAG_KEYWORDS.items():
        for kw in keywords:
            if kw in content_lower:
                found_tags.append(tag)
                break

    return found_tags[:5]  # max 5 tags


def run_auto_curation() -> dict:
    """Run the full auto-curation pipeline.

    Returns:
        Dict with results: classified, tagged, entities_extracted,
        contradictions_resolved, consolidated, retention_flagged.
    """
    results = {
        "classified": 0,
        "tagged": 0,
        "entities_extracted": 0,
        "contradictions_resolved": 0,
        "consolidated": 0,
        "retention_flagged": 0,
        "errors": [],
    }

    # 1. Classify and tag untagged memories
    try:
        c, t = _curate_metadata()
        results["classified"] = c
        results["tagged"] = t
    except Exception as e:
        logger.warning("Metadata curation failed: %s", e)
        results["errors"].append(f"metadata: {e}")

    # 2. Extract entities from memories missing relationships
    try:
        results["entities_extracted"] = _curate_entities()
    except Exception as e:
        logger.warning("Entity extraction failed: %s", e)
        results["errors"].append(f"entities: {e}")

    # 3. Detect and resolve contradictions
    try:
        results["contradictions_resolved"] = _curate_contradictions()
    except Exception as e:
        logger.warning("Contradiction resolution failed: %s", e)
        results["errors"].append(f"contradictions: {e}")

    # 4. Consolidate duplicates
    try:
        results["consolidated"] = _curate_consolidation()
    except Exception as e:
        logger.warning("Consolidation failed: %s", e)
        results["errors"].append(f"consolidation: {e}")

    # 5. Flag stale memories
    try:
        results["retention_flagged"] = _curate_retention()
    except Exception as e:
        logger.warning("Retention check failed: %s", e)
        results["errors"].append(f"retention: {e}")

    return results


def _curate_metadata() -> tuple[int, int]:
    """Classify uncategorized memories and add tags to untagged ones."""
    from src.memory import _memory_dir

    mem_dir = _memory_dir()
    classified = 0
    tagged = 0

    for md_file in sorted(mem_dir.glob("*.md")):
        text = md_file.read_text(encoding="utf-8")

        # Parse frontmatter
        if not text.startswith("---"):
            continue

        end = text.find("---", 3)
        if end == -1:
            continue

        frontmatter = text[3:end]
        body = text[end + 3:].strip()
        modified = False

        # Check if category is missing or generic
        has_category = "category:" in frontmatter
        current_cat = ""
        if has_category:
            m = re.search(r"category:\s*(\S+)", frontmatter)
            current_cat = m.group(1) if m else ""

        if not current_cat or current_cat in ("", "uncategorized", "unknown"):
            new_cat = classify_memory(body)
            if has_category:
                frontmatter = re.sub(
                    r"category:\s*\S*",
                    f"category: {new_cat}",
                    frontmatter,
                )
            else:
                frontmatter += f"\ncategory: {new_cat}"
            classified += 1
            modified = True

        # Check if tags are missing
        has_tags = "tags:" in frontmatter
        if not has_tags:
            new_tags = extract_tags(body)
            if new_tags:
                tag_str = "[" + ", ".join(new_tags) + "]"
                frontmatter += f"\ntags: {tag_str}"
                tagged += 1
                modified = True
        else:
            m = re.search(r"tags:\s*\[?\s*\]?$", frontmatter, re.MULTILINE)
            if m:  # empty tags
                new_tags = extract_tags(body)
                if new_tags:
                    tag_str = "[" + ", ".join(new_tags) + "]"
                    frontmatter = re.sub(
                        r"tags:\s*\[?\s*\]?$",
                        f"tags: {tag_str}",
                        frontmatter,
                        flags=re.MULTILINE,
                    )
                    tagged += 1
                    modified = True

        if modified:
            new_text = f"---{frontmatter}---\n\n{body}\n"
            md_file.write_text(new_text, encoding="utf-8")

    return classified, tagged


def _curate_entities() -> int:
    """Extract entities from memories that don't have entity relationships."""
    from src.entity_extraction import extract_triples
    from src.entity_store import EntityStore
    from src.memory import _memory_dir

    store = EntityStore()
    mem_dir = _memory_dir()
    extracted = 0

    for md_file in sorted(mem_dir.glob("*.md")):
        memory_id = md_file.stem

        # Check if already has relationships
        existing = store.get_memory_entities(memory_id)
        if existing:
            continue

        text = md_file.read_text(encoding="utf-8")
        # Extract body (skip frontmatter)
        if text.startswith("---"):
            end = text.find("---", 3)
            if end != -1:
                text = text[end + 3:]

        triples = extract_triples(text.strip())
        if not triples:
            continue

        for triple in triples:
            try:
                subj_id = store.upsert_entity(
                    triple.subject.name, triple.subject.entity_type
                )
                obj_id = store.upsert_entity(
                    triple.object.name, triple.object.entity_type
                )
                store.add_relationship(
                    subj_id, triple.predicate, obj_id,
                    memory_id=memory_id, confidence=triple.confidence,
                )
                extracted += 1
            except Exception:
                continue

    return extracted


def _curate_contradictions() -> int:
    """Detect and auto-supersede high-severity contradictions."""
    from src.contradiction import detect_contradictions
    from src.memory import recall_memories, supersede_memory

    try:
        memories = recall_memories("", top_k=100, include_superseded=True)
    except Exception:
        return 0

    if len(memories) < 2:
        return 0

    contradictions = detect_contradictions(memories)
    resolved = 0

    for c in contradictions:
        if c.get("severity") != "high":
            continue

        older = c.get("memory_a", {})
        older_path = older.get("file_path", "")
        if older_path and Path(older_path).exists():
            newer = c.get("memory_b", {})
            newer_name = Path(newer.get("file_path", "")).stem if newer.get("file_path") else ""
            if supersede_memory(Path(older_path), superseded_by=newer_name):
                resolved += 1

    return resolved


def _curate_consolidation() -> int:
    """Find and merge highly similar memory clusters."""
    from src.consolidation import consolidate_cluster, find_similar_clusters

    clusters = find_similar_clusters(threshold=0.92, max_clusters=5)
    consolidated = 0

    for cluster in clusters:
        if cluster["similarity"] >= 0.92 and cluster["count"] >= 2:
            try:
                result = consolidate_cluster(cluster)
                consolidated += result.get("superseded_count", 0)
            except Exception:
                continue

    return consolidated


def _curate_retention() -> int:
    """Flag old or low-quality memories for review."""
    from src.retention import get_retention_summary

    summary = get_retention_summary()
    return summary.get("at_risk", 0)
