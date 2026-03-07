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


def save_memory(content: str, tags: list[str] | None = None, source: str = "conversation") -> Path:
    """Save a memory as a timestamped markdown file.

    Args:
        content: The knowledge/fact/decision to remember.
        tags: Optional tags for categorization.
        source: Where this memory came from.

    Returns:
        Path to the saved file.
    """
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
        f"tags: [{tag_str}]\n"
        f"---\n\n"
        f"{content}\n"
    )

    file_path.write_text(md_content, encoding="utf-8")
    logger.info("Saved memory: %s", file_path)
    return file_path


def recall_memories(query: str, top_k: int = 5) -> list[dict]:
    """Search memories using vector similarity.

    Returns list of dicts with 'content', 'date', 'tags', 'source', 'similarity'.
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

    try:
        results = table.search(vector).limit(top_k).to_list()
    except Exception as exc:
        logger.warning("Memory search failed: %s", exc)
        return []

    memories = []
    for row in results:
        dist = row.get("_distance", 1.0)
        similarity = max(0.0, min(1.0, 1.0 - float(dist)))

        memories.append({
            "content": row.get("text", ""),
            "date": row.get("date", ""),
            "tags": row.get("tags", ""),
            "source": row.get("source", ""),
            "file_path": row.get("file_path", ""),
            "similarity": similarity,
        })

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
        except Exception:
            pass
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

    Returns dict with file_path and index status.
    """
    file_path = save_memory(content, tags=tags, source=source)
    indexed = index_memory(file_path)
    return {
        "file_path": str(file_path),
        "indexed": indexed > 0,
    }
