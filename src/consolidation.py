"""Memory consolidation: find similar memory clusters and merge them."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def find_similar_clusters(
    threshold: float = 0.85,
    max_clusters: int = 20,
) -> list[dict]:
    """Find clusters of similar memories that could be consolidated.

    Args:
        threshold: Cosine similarity threshold (0.0-1.0). Higher = stricter.
        max_clusters: Maximum number of clusters to return.

    Returns:
        List of cluster dicts with 'memories' (list of memory dicts) and 'similarity'.
    """
    import lancedb

    from src.config import settings
    from src.embedding import embed_query

    db_path = str(settings.data.lancedb_path)
    if not Path(db_path).exists():
        return []

    db = lancedb.connect(db_path)
    if "memories" not in db.table_names():
        return []

    table = db.open_table("memories")

    # Get all memories
    try:
        all_rows = table.to_pandas().to_dict("records")
    except Exception:
        try:
            all_rows = table.search(embed_query("memory")).limit(500).to_list()
        except Exception as exc:
            logger.warning("Failed to load memories for consolidation: %s", exc)
            return []

    if len(all_rows) < 2:
        return []

    # Filter out superseded memories
    active = [r for r in all_rows if not r.get("superseded_at", "")]

    # Compare each pair using vector distance
    clusters: list[dict] = []
    used: set[str] = set()

    for i, mem_a in enumerate(active):
        path_a = mem_a.get("file_path", "")
        if path_a in used:
            continue

        cluster_members = [mem_a]
        text_a = mem_a.get("text", "")
        if not text_a:
            continue

        try:
            vec_a = embed_query(text_a)
        except Exception:
            continue

        # Search for similar
        try:
            similar = table.search(vec_a).limit(10).to_list()
        except Exception:
            continue

        for candidate in similar:
            path_c = candidate.get("file_path", "")
            if path_c == path_a or path_c in used:
                continue
            if candidate.get("superseded_at", ""):
                continue

            dist = candidate.get("_distance", 1.0)
            similarity = max(0.0, min(1.0, 1.0 - float(dist)))

            if similarity >= threshold:
                cluster_members.append(candidate)
                used.add(path_c)

        if len(cluster_members) > 1:
            used.add(path_a)
            # Calculate average similarity within cluster
            avg_sim = sum(
                max(0.0, min(1.0, 1.0 - float(m.get("_distance", 1.0))))
                for m in cluster_members[1:]
            ) / max(1, len(cluster_members) - 1)

            clusters.append({
                "memories": [
                    {
                        "content": m.get("text", ""),
                        "date": m.get("date", ""),
                        "category": m.get("category", ""),
                        "tags": m.get("tags", ""),
                        "file_path": m.get("file_path", ""),
                    }
                    for m in cluster_members
                ],
                "similarity": round(avg_sim, 3),
                "count": len(cluster_members),
            })

            if len(clusters) >= max_clusters:
                break

    # Sort by cluster size (largest first), then similarity
    clusters.sort(key=lambda c: (-c["count"], -c["similarity"]))
    return clusters


def consolidate_cluster(cluster: dict) -> dict:
    """Merge a cluster of similar memories into one, superseding the others.

    Args:
        cluster: A cluster dict from find_similar_clusters().

    Returns:
        Dict with 'merged_content', 'superseded_count', 'new_memory_path'.
    """
    from src.memory import save_memory, supersede_memory

    memories = cluster.get("memories", [])
    if len(memories) < 2:
        return {"merged_content": "", "superseded_count": 0, "new_memory_path": ""}

    # Merge content: take the longest/most detailed one as base,
    # append unique info from others
    sorted_mems = sorted(memories, key=lambda m: len(m.get("content", "")), reverse=True)
    base = sorted_mems[0]
    base_content = base.get("content", "")

    # Collect unique tags
    all_tags: set[str] = set()
    for m in memories:
        tags = m.get("tags", "")
        if isinstance(tags, str) and tags:
            for t in tags.split(","):
                t = t.strip()
                if t:
                    all_tags.add(t)
        elif isinstance(tags, list):
            all_tags.update(t for t in tags if t)

    # Collect additional content from other memories (only if substantially different)
    additions = []
    for m in sorted_mems[1:]:
        other = m.get("content", "")
        # Only add if the other memory has meaningful unique content
        if other and other not in base_content and len(other) > 20:
            # Check word overlap
            base_words = set(base_content.lower().split())
            other_words = set(other.lower().split())
            unique_ratio = len(other_words - base_words) / max(1, len(other_words))
            if unique_ratio > 0.3:
                additions.append(other.strip())

    merged = base_content
    if additions:
        merged += "\n\n---\n(Consolidated from related memories)\n" + "\n".join(additions)

    # Save new consolidated memory
    tags_list = sorted(all_tags) if all_tags else None
    new_path = save_memory(merged, tags=tags_list)

    # Supersede old memories
    superseded = 0
    new_name = new_path.stem if new_path else ""
    for m in memories:
        fp = m.get("file_path", "")
        if fp:
            p = Path(fp)
            if p.exists() and (not new_path or p != new_path):
                if supersede_memory(p, superseded_by=new_name):
                    superseded += 1

    return {
        "merged_content": merged[:500],
        "superseded_count": superseded,
        "new_memory_path": str(new_path) if new_path else "",
    }
