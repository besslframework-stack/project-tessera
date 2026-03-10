"""Cross-session memory and auto-learn: persist knowledge across Claude sessions."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from src.config import workspace
from src.embedding import embed_query

logger = logging.getLogger(__name__)

# Memory storage directory (inside Tessera's data folder)
_MEMORY_DIR_NAME = "memories"


def _memory_dir() -> Path:
    """Get or create the memories directory."""
    project_root = Path(__file__).parent.parent
    mem_dir = project_root / "data" / _MEMORY_DIR_NAME
    mem_dir.mkdir(parents=True, exist_ok=True)
    return mem_dir


def _check_duplicate(content: str, threshold: float = 0.92) -> dict | None:
    """Check if a similar memory already exists using cosine similarity.

    Args:
        content: The content to check for duplicates.
        threshold: Cosine similarity threshold (0.0-1.0). Above this = duplicate.

    Returns:
        Dict with 'file_path', 'content', 'similarity' if duplicate found, else None.
    """
    try:
        import lancedb
        from src.config import settings

        db_path = str(settings.data.lancedb_path)
        if not Path(db_path).exists():
            return None

        db = lancedb.connect(db_path)
        if "memories" not in db.table_names():
            return None

        table = db.open_table("memories")
        vector = embed_query(content)

        results = table.search(vector).limit(1).to_list()
        if not results:
            return None

        top = results[0]
        dist = float(top.get("_distance", 1.0))
        similarity = max(0.0, min(1.0, 1.0 - dist))

        if similarity >= threshold:
            return {
                "file_path": top.get("file_path", ""),
                "content": top.get("text", ""),
                "similarity": similarity,
            }
    except Exception as exc:
        logger.debug("Dedup check failed (proceeding with save): %s", exc)

    return None


def _detect_category(content: str) -> str:
    """Auto-detect memory category from content using pattern matching.

    Categories: decision, preference, fact, reference, context.
    Falls back to 'general' if no pattern matches.
    """
    try:
        from src.auto_extract import extract_facts

        facts = extract_facts(content)
        if facts:
            return facts[0].category
    except Exception as e:
        logger.debug("Category detection failed: %s", e)
    return "general"


def save_memory(
    content: str,
    tags: list[str] | None = None,
    source: str = "conversation",
    category: str | None = None,
    dedup: bool = True,
    dedup_threshold: float = 0.92,
) -> Path:
    """Save a memory as a timestamped markdown file.

    Checks for duplicate memories before saving (cosine similarity > threshold).
    If a duplicate is found, the save is skipped and the existing file path is returned.
    Auto-detects category (decision/preference/fact) from content if not provided.

    Args:
        content: The knowledge/fact/decision to remember.
        tags: Optional tags for categorization.
        source: Where this memory came from.
        category: Memory category. Auto-detected if None.
        dedup: Whether to check for duplicates before saving.
        dedup_threshold: Cosine similarity threshold for dedup (0.0-1.0).

    Returns:
        Path to the saved (or existing duplicate) file.
    """
    if dedup:
        existing = _check_duplicate(content, threshold=dedup_threshold)
        if existing:
            existing_path = Path(existing["file_path"])
            logger.info(
                "Memory dedup: skipped (%.1f%% similar to %s)",
                existing["similarity"] * 100,
                existing_path.name,
            )
            return existing_path

    # Auto-detect category if not provided
    if category is None:
        category = _detect_category(content)

    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    slug = content[:40].replace(" ", "_").replace("/", "_").replace("\n", "_")
    slug = "".join(c for c in slug if c.isalnum() or c == "_")
    filename = f"{timestamp}_{slug}.md"

    mem_dir = _memory_dir()
    file_path = mem_dir / filename

    tag_str = ", ".join(tags) if tags else "general"
    md_content = (
        f"---\n"
        f"date: {now.isoformat()}\n"
        f"source: {source}\n"
        f"category: {category}\n"
        f"tags: [{tag_str}]\n"
        f"---\n\n"
        f"{content}\n"
    )

    file_path.write_text(md_content, encoding="utf-8")
    logger.info("Saved memory [%s]: %s", category, file_path)
    return file_path


def recall_memories(
    query: str,
    top_k: int = 5,
    since: str | None = None,
    until: str | None = None,
    category: str | None = None,
) -> list[dict]:
    """Search memories using vector similarity with optional time and category filters.

    Args:
        query: Search query text.
        top_k: Maximum number of results.
        since: ISO date string (e.g. '2026-03-01'). Only return memories after this date.
        until: ISO date string (e.g. '2026-03-10'). Only return memories before this date.
        category: Filter by category (decision, preference, fact, etc.).

    Returns:
        List of dicts with 'content', 'date', 'category', 'tags', 'source', 'similarity'.
    """
    import lancedb

    from src.config import settings

    db_path = str(settings.data.lancedb_path)
    if not Path(db_path).exists():
        return []

    db = lancedb.connect(db_path)
    if "memories" not in db.table_names():
        return []

    table = db.open_table("memories")
    vector = embed_query(query)

    # Fetch more results when filtering, to compensate for post-filter reduction
    fetch_k = top_k * 3 if (since or until or category) else top_k

    try:
        results = table.search(vector).limit(fetch_k).to_list()
    except Exception as exc:
        logger.warning("Memory search failed: %s", exc)
        return []

    memories = []
    for row in results:
        date_val = row.get("date", "")
        cat_val = row.get("category", "")

        # Time filter
        if since and date_val and date_val[:10] < since[:10]:
            continue
        if until and date_val and date_val[:10] > until[:10]:
            continue

        # Category filter
        if category and cat_val.lower() != category.lower():
            continue

        dist = row.get("_distance", 1.0)
        similarity = max(0.0, min(1.0, 1.0 - float(dist)))

        memories.append({
            "content": row.get("text", ""),
            "date": date_val,
            "category": cat_val,
            "tags": row.get("tags", ""),
            "source": row.get("source", ""),
            "file_path": row.get("file_path", ""),
            "similarity": similarity,
        })

        if len(memories) >= top_k:
            break

    return memories


def index_memory(file_path: Path) -> int:
    """Index a single memory file into the memories LanceDB table.

    Returns number of records indexed.
    """
    import numpy as np
    import lancedb

    from src.config import settings
    from src.embedding import get_embed_model

    if not file_path.exists():
        return 0

    text = file_path.read_text(encoding="utf-8")

    # Parse frontmatter
    date_str = ""
    source = ""
    category = ""
    tags = ""
    body = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            frontmatter = parts[1]
            body = parts[2].strip()
            for line in frontmatter.strip().splitlines():
                if line.startswith("date:"):
                    date_str = line.split(":", 1)[1].strip()
                elif line.startswith("source:"):
                    source = line.split(":", 1)[1].strip()
                elif line.startswith("category:"):
                    category = line.split(":", 1)[1].strip()
                elif line.startswith("tags:"):
                    tags = line.split(":", 1)[1].strip()

    if not body.strip():
        return 0

    model = get_embed_model()
    embedding = list(model.embed([body]))[0]

    record = {
        "id": file_path.stem,
        "vector": np.array(embedding, dtype=np.float32),
        "text": body,
        "date": date_str,
        "source": source,
        "category": category,
        "tags": tags,
        "file_path": str(file_path),
    }

    db_path = str(settings.data.lancedb_path)
    db = lancedb.connect(db_path)

    if "memories" in db.table_names():
        table = db.open_table("memories")
        # Delete existing record for this file if re-indexing
        try:
            table.delete(f"id = '{file_path.stem}'")
        except Exception as e:
            logger.debug("Could not delete existing record %s: %s", file_path.stem, e)
        table.add([record])
    else:
        db.create_table("memories", [record])

    return 1


def index_all_memories() -> int:
    """Index all memory files in the memories directory."""
    mem_dir = _memory_dir()
    count = 0
    for md_file in sorted(mem_dir.glob("*.md")):
        count += index_memory(md_file)
    return count


def learn_and_index(content: str, tags: list[str] | None = None, source: str = "auto-learn") -> dict:
    """Save new knowledge and immediately index it for search.

    Dedup is enabled by default — if identical or near-identical content
    already exists, the save is skipped and the existing path is returned.

    Returns dict with file_path, index status, and whether it was a duplicate.
    """
    # Check dedup before saving
    existing = _check_duplicate(content)
    if existing:
        return {
            "file_path": existing["file_path"],
            "indexed": True,
            "deduplicated": True,
            "similarity": existing["similarity"],
        }

    file_path = save_memory(content, tags=tags, source=source, dedup=False)
    indexed = index_memory(file_path)
    return {
        "file_path": str(file_path),
        "indexed": indexed > 0,
        "deduplicated": False,
    }


def export_memories(format: str = "json") -> str:
    """Export all saved memories as a JSON string.

    Reads every .md file from the memories directory, parses frontmatter
    (date, source, tags) and body, and returns a serialised list.

    Args:
        format: Export format. Only ``"json"`` is supported.

    Returns:
        A JSON string containing a list of memory dicts, each with keys
        ``content``, ``date``, ``source``, ``tags``, and ``filename``.

    Raises:
        ValueError: If an unsupported format is requested.
    """
    if format != "json":
        raise ValueError(f"Unsupported export format: {format!r}. Only 'json' is supported.")

    mem_dir = _memory_dir()
    memories: list[dict] = []

    for md_file in sorted(mem_dir.glob("*.md")):
        text = md_file.read_text(encoding="utf-8")

        date_str = ""
        source = ""
        tags = ""
        body = text

        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                frontmatter = parts[1]
                body = parts[2].strip()
                for line in frontmatter.strip().splitlines():
                    if line.startswith("date:"):
                        date_str = line.split(":", 1)[1].strip()
                    elif line.startswith("source:"):
                        source = line.split(":", 1)[1].strip()
                    elif line.startswith("tags:"):
                        tags = line.split(":", 1)[1].strip()

        memories.append({
            "content": body,
            "date": date_str,
            "source": source,
            "tags": tags,
            "filename": md_file.name,
        })

    return json.dumps(memories, ensure_ascii=False, indent=2)


def import_memories(data: str, format: str = "json") -> dict:
    """Batch-import memories from a JSON string.

    Each entry in the JSON list must contain at least a ``content`` key.
    Optional keys: ``tags`` (list of strings) and ``source`` (string).

    Entries with empty or missing ``content`` are silently skipped.
    Errors on individual entries are collected without aborting the batch.

    Args:
        data: A JSON string representing a list of memory dicts.
        format: Import format. Only ``"json"`` is supported.

    Returns:
        A dict with ``imported`` (int), ``indexed`` (int), and
        ``errors`` (list of error description strings).

    Raises:
        ValueError: If an unsupported format is requested or *data*
            cannot be parsed as a JSON list.
    """
    if format != "json":
        raise ValueError(f"Unsupported import format: {format!r}. Only 'json' is supported.")

    try:
        entries = json.loads(data)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON data: {exc}") from exc

    if not isinstance(entries, list):
        raise ValueError("Expected a JSON list of memory objects.")

    imported = 0
    indexed = 0
    errors: list[str] = []

    for idx, entry in enumerate(entries):
        try:
            if not isinstance(entry, dict):
                errors.append(f"Entry {idx}: not a dict, skipped.")
                continue

            content = (entry.get("content") or "").strip()
            if not content:
                continue

            tags = entry.get("tags")
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",") if t.strip()]
            source = entry.get("source", "import")

            file_path = save_memory(content, tags=tags, source=source)
            imported += 1

            try:
                indexed += index_memory(file_path)
            except Exception as index_exc:
                errors.append(f"Entry {idx}: saved but indexing failed — {index_exc}")
        except Exception as exc:
            errors.append(f"Entry {idx}: {exc}")

    return {"imported": imported, "indexed": indexed, "errors": errors}


def _parse_tags_bracket(raw: str) -> list[str]:
    """Parse a bracket-style tags string like ``[tag1, tag2]`` into a list.

    Args:
        raw: The raw tags value from frontmatter (may include brackets).

    Returns:
        List of stripped, non-empty tag strings.
    """
    stripped = raw.strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        stripped = stripped[1:-1]
    return [t.strip() for t in stripped.split(",") if t.strip()]


def list_memory_tags() -> dict[str, int]:
    """List all unique tags across saved memories with their counts.

    Returns:
        Dict mapping tag name to count of memories with that tag.
        Sorted by count descending.
    """
    from collections import Counter

    mem_dir = _memory_dir()
    counter: Counter[str] = Counter()

    for md_file in mem_dir.glob("*.md"):
        text = md_file.read_text(encoding="utf-8")

        if not text.startswith("---"):
            continue

        parts = text.split("---", 2)
        if len(parts) < 3:
            continue

        frontmatter = parts[1]
        for line in frontmatter.strip().splitlines():
            if line.startswith("tags:"):
                raw_tags = line.split(":", 1)[1].strip()
                tags = _parse_tags_bracket(raw_tags)
                counter.update(tags)
                break

    return dict(counter.most_common())


def search_memories_by_tag(tag: str) -> list[dict]:
    """Find all memories that have a specific tag.

    Args:
        tag: Tag to filter by (case-insensitive).

    Returns:
        List of dicts with 'filename', 'content', 'date', 'tags', 'source'.
        Sorted by date descending (newest first).
    """
    mem_dir = _memory_dir()
    results: list[dict] = []

    for md_file in mem_dir.glob("*.md"):
        text = md_file.read_text(encoding="utf-8")

        date_str = ""
        source = ""
        tags_raw = ""
        body = text

        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                frontmatter = parts[1]
                body = parts[2].strip()
                for line in frontmatter.strip().splitlines():
                    if line.startswith("date:"):
                        date_str = line.split(":", 1)[1].strip()
                    elif line.startswith("source:"):
                        source = line.split(":", 1)[1].strip()
                    elif line.startswith("tags:"):
                        tags_raw = line.split(":", 1)[1].strip()

        parsed_tags = _parse_tags_bracket(tags_raw)
        if not any(t.lower() == tag.lower() for t in parsed_tags):
            continue

        results.append({
            "filename": md_file.stem,
            "content": body,
            "date": date_str,
            "tags": tags_raw,
            "source": source,
        })

    results.sort(key=lambda m: m["date"], reverse=True)
    return results


def list_memory_categories() -> dict[str, int]:
    """List all unique categories across saved memories with their counts.

    Returns:
        Dict mapping category name to count. Sorted by count descending.
    """
    from collections import Counter

    mem_dir = _memory_dir()
    counter: Counter[str] = Counter()

    for md_file in mem_dir.glob("*.md"):
        text = md_file.read_text(encoding="utf-8")
        if not text.startswith("---"):
            continue

        parts = text.split("---", 2)
        if len(parts) < 3:
            continue

        frontmatter = parts[1]
        for line in frontmatter.strip().splitlines():
            if line.startswith("category:"):
                cat = line.split(":", 1)[1].strip()
                if cat:
                    counter[cat] += 1
                break

    return dict(counter.most_common())


def search_memories_by_category(category: str) -> list[dict]:
    """Find all memories with a specific category.

    Args:
        category: Category to filter by (e.g. 'decision', 'preference', 'fact').

    Returns:
        List of dicts with 'filename', 'content', 'date', 'category', 'tags', 'source'.
        Sorted by date descending (newest first).
    """
    mem_dir = _memory_dir()
    results: list[dict] = []

    for md_file in mem_dir.glob("*.md"):
        text = md_file.read_text(encoding="utf-8")

        date_str = ""
        source = ""
        cat = ""
        tags_raw = ""
        body = text

        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                frontmatter = parts[1]
                body = parts[2].strip()
                for line in frontmatter.strip().splitlines():
                    if line.startswith("date:"):
                        date_str = line.split(":", 1)[1].strip()
                    elif line.startswith("source:"):
                        source = line.split(":", 1)[1].strip()
                    elif line.startswith("category:"):
                        cat = line.split(":", 1)[1].strip()
                    elif line.startswith("tags:"):
                        tags_raw = line.split(":", 1)[1].strip()

        if cat.lower() != category.lower():
            continue

        results.append({
            "filename": md_file.stem,
            "content": body,
            "date": date_str,
            "category": cat,
            "tags": tags_raw,
            "source": source,
        })

    results.sort(key=lambda m: m["date"], reverse=True)
    return results
