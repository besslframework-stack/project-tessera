"""Knowledge graph: extract relationships between documents and render as Mermaid."""

from __future__ import annotations

import json
import logging
import re
from collections import Counter, defaultdict
from pathlib import Path

from src.config import settings
from src.embedding import embed_query

logger = logging.getLogger(__name__)

# Keywords that indicate document relationships
_LINK_PATTERNS = [
    r"\[\[([^\]]+)\]\]",  # wiki-links [[target]]
    r"see also[:\s]+([^\n,]+)",  # "see also: X"
    r"related to[:\s]+([^\n,]+)",  # "related to: X"
    r"depends on[:\s]+([^\n,]+)",  # "depends on: X"
    r"references?[:\s]+([^\n,]+)",  # "reference: X"
]


def _extract_topics(text: str) -> list[str]:
    """Extract key topics from text using simple keyword extraction."""
    # Remove markdown formatting
    clean = re.sub(r"[#*_`\[\]()]", " ", text)
    clean = re.sub(r"\s+", " ", clean).strip().lower()

    # Split into words, filter short/common ones
    stop_words = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "shall", "can", "need", "must", "to", "of",
        "in", "for", "on", "with", "at", "by", "from", "as", "into", "about",
        "that", "this", "it", "its", "not", "no", "or", "and", "but", "if",
        "then", "than", "so", "up", "out", "all", "also", "just", "only",
        "very", "more", "most", "other", "some", "any", "each", "every",
        "such", "like", "through", "after", "before", "between", "under",
        "above", "below", "over", "both", "same", "different", "new", "old",
        "when", "where", "how", "what", "which", "who", "whom", "why",
        "here", "there", "now", "then", "still", "already", "yet",
    }

    words = clean.split()
    word_counts = Counter(
        w for w in words if len(w) > 3 and w not in stop_words and w.isalpha()
    )

    return [w for w, _ in word_counts.most_common(10)]


def _extract_links(text: str) -> list[str]:
    """Extract explicit document links/references from text."""
    links = []
    for pattern in _LINK_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            link = match.group(1).strip()
            if link and len(link) < 100:
                links.append(link)
    return links


def _sanitize_mermaid_id(s: str) -> str:
    """Make a string safe for Mermaid node IDs."""
    safe = re.sub(r"[^a-zA-Z0-9_]", "_", s)
    if safe and safe[0].isdigit():
        safe = "n_" + safe
    return safe[:40]


def _truncate_label(s: str, max_len: int = 30) -> str:
    """Truncate label for display."""
    if len(s) <= max_len:
        return s
    return s[: max_len - 3] + "..."


def build_knowledge_graph(
    query: str | None = None,
    project: str | None = None,
    scope: str = "all",
    max_nodes: int = 30,
) -> str:
    """Build a knowledge graph from indexed documents.

    Returns a Mermaid diagram string showing document relationships.
    """
    import lancedb

    db_path = str(settings.data.lancedb_path)
    if not Path(db_path).exists():
        return "No indexed documents. Run ingest_documents first."

    db = lancedb.connect(db_path)
    table_names = db.table_names()

    if "documents" not in table_names:
        return "No indexed documents. Run ingest_documents first."

    table = db.open_table("documents")

    # Get documents — either by query similarity or all
    if query:
        vector = embed_query(query)
        try:
            rows = table.search(vector).limit(max_nodes * 2).to_list()
        except Exception as exc:
            logger.warning("Knowledge graph search failed: %s", exc)
            return f"Search failed: {exc}"
    else:
        try:
            rows = table.to_pandas().head(max_nodes * 3).to_dict("records")
        except Exception:
            rows = table.search(embed_query("document")).limit(max_nodes * 3).to_list()

    if not rows:
        return "No documents found to build a graph."

    # Filter by project if specified
    if project:
        filtered = []
        for r in rows:
            meta = r.get("metadata", "{}")
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except (json.JSONDecodeError, TypeError):
                    meta = {}
            if meta.get("project", "") == project:
                filtered.append(r)
        rows = filtered or rows  # fallback to unfiltered if no matches

    # Build nodes: group chunks by source file
    file_nodes: dict[str, dict] = {}
    file_topics: dict[str, list[str]] = defaultdict(list)
    file_links: dict[str, list[str]] = defaultdict(list)

    for r in rows:
        meta = r.get("metadata", "{}")
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except (json.JSONDecodeError, TypeError):
                meta = {}

        source = meta.get("source_path", r.get("source_path", "unknown"))
        doc_type = meta.get("doc_type", "document")
        text = r.get("text", "")

        if source not in file_nodes:
            name = Path(source).stem if source != "unknown" else "unknown"
            file_nodes[source] = {
                "name": name,
                "doc_type": doc_type,
                "source": source,
            }

        # Extract topics and links
        topics = _extract_topics(text)
        file_topics[source].extend(topics)
        links = _extract_links(text)
        file_links[source].extend(links)

    # Limit nodes
    sources = list(file_nodes.keys())[:max_nodes]

    # Build edges based on shared topics
    edges: list[tuple[str, str, str]] = []
    topic_to_files: dict[str, list[str]] = defaultdict(list)

    for source in sources:
        top_topics = Counter(file_topics[source]).most_common(5)
        for topic, _ in top_topics:
            topic_to_files[topic].append(source)

    # Connect files that share topics
    seen_edges: set[tuple[str, str]] = set()
    for topic, files in topic_to_files.items():
        if len(files) < 2:
            continue
        for i, f1 in enumerate(files):
            for f2 in files[i + 1 :]:
                edge_key = (min(f1, f2), max(f1, f2))
                if edge_key not in seen_edges:
                    seen_edges.add(edge_key)
                    edges.append((f1, f2, topic))

    # Connect files that have explicit links
    for source in sources:
        for link in file_links[source]:
            link_lower = link.lower()
            for target in sources:
                target_name = file_nodes[target]["name"].lower()
                if target != source and (
                    link_lower in target_name or target_name in link_lower
                ):
                    edge_key = (min(source, target), max(source, target))
                    if edge_key not in seen_edges:
                        seen_edges.add(edge_key)
                        edges.append((source, target, "ref"))

    # Render Mermaid
    type_styles = {
        "prd": ":::prd",
        "session_log": ":::session",
        "decision_log": ":::decision",
        "document": ":::doc",
    }

    lines = ["graph LR"]
    lines.append("    classDef prd fill:#e1f5fe,stroke:#0288d1")
    lines.append("    classDef session fill:#f3e5f5,stroke:#7b1fa2")
    lines.append("    classDef decision fill:#fff3e0,stroke:#f57c00")
    lines.append("    classDef doc fill:#e8f5e9,stroke:#388e3c")

    # Add nodes
    node_ids: dict[str, str] = {}
    for source in sources:
        node = file_nodes[source]
        nid = _sanitize_mermaid_id(node["name"])
        node_ids[source] = nid
        label = _truncate_label(node["name"])
        style = type_styles.get(node["doc_type"], ":::doc")
        lines.append(f'    {nid}["{label}"]{style}')

    # Add edges
    for src, tgt, label in edges:
        if src in node_ids and tgt in node_ids:
            edge_label = _truncate_label(label, 15)
            lines.append(
                f"    {node_ids[src]} ---|{edge_label}| {node_ids[tgt]}"
            )

    mermaid = "\n".join(lines)

    # Summary
    summary = (
        f"Knowledge Graph: {len(sources)} documents, {len(edges)} connections\n\n"
        f"```mermaid\n{mermaid}\n```"
    )

    # Add isolated nodes warning
    connected = set()
    for src, tgt, _ in edges:
        connected.add(src)
        connected.add(tgt)
    isolated = [s for s in sources if s not in connected]
    if isolated:
        summary += f"\n\nIsolated documents ({len(isolated)}): "
        summary += ", ".join(file_nodes[s]["name"] for s in isolated[:10])
        if len(isolated) > 10:
            summary += f" ...and {len(isolated) - 10} more"

    return summary


def explore_connections(query: str, top_k: int = 10) -> str:
    """Explore connections around a specific topic or document.

    Returns related documents and a focused Mermaid subgraph.
    """
    import lancedb

    db_path = str(settings.data.lancedb_path)
    if not Path(db_path).exists():
        return "No indexed documents."

    db = lancedb.connect(db_path)
    if "documents" not in db.table_names():
        return "No indexed documents."

    table = db.open_table("documents")
    vector = embed_query(query)

    try:
        rows = table.search(vector).limit(top_k * 3).to_list()
    except Exception as exc:
        return f"Search failed: {exc}"

    if not rows:
        return f"No documents found related to '{query}'."

    # Group by source file
    file_groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        meta = r.get("metadata", "{}")
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except (json.JSONDecodeError, TypeError):
                meta = {}
        source = meta.get("source_path", "unknown")
        sim = max(0.0, min(1.0, 1.0 - float(r.get("_distance", 1.0))))
        file_groups[source].append({
            "text": r.get("text", ""),
            "similarity": sim,
            "doc_type": meta.get("doc_type", "document"),
            "section": meta.get("section", ""),
        })

    # Take top files by max similarity
    ranked = sorted(
        file_groups.items(),
        key=lambda x: max(c["similarity"] for c in x[1]),
        reverse=True,
    )[:top_k]

    # Find shared topics between center and each related doc
    center_source, center_chunks = ranked[0]
    center_text = " ".join(c["text"] for c in center_chunks)
    center_topics = set(_extract_topics(center_text))
    center_name = Path(center_source).stem

    # Build output
    parts = [f"## Connections for: {center_name}\n"]

    # Mermaid subgraph
    mermaid_lines = ["graph TD"]
    center_id = _sanitize_mermaid_id(center_name)
    mermaid_lines.append(f'    {center_id}["{_truncate_label(center_name)}"]:::center')
    mermaid_lines.append("    classDef center fill:#ffeb3b,stroke:#f57f17,stroke-width:3px")

    for source, chunks in ranked[1:]:
        name = Path(source).stem
        nid = _sanitize_mermaid_id(name)
        max_sim = max(c["similarity"] for c in chunks)
        doc_type = chunks[0]["doc_type"]

        chunk_text = " ".join(c["text"] for c in chunks)
        topics = set(_extract_topics(chunk_text))
        shared = center_topics & topics

        label = _truncate_label(name)
        mermaid_lines.append(f'    {nid}["{label}"]')

        edge_label = ", ".join(list(shared)[:2]) if shared else f"{max_sim*100:.0f}%"
        mermaid_lines.append(
            f"    {center_id} ---|{_truncate_label(edge_label, 15)}| {nid}"
        )

        parts.append(
            f"- **{name}** ({doc_type}, {max_sim*100:.1f}% similar)"
            + (f" — shared topics: {', '.join(list(shared)[:5])}" if shared else "")
        )

    mermaid = "\n".join(mermaid_lines)
    parts.insert(1, f"\n```mermaid\n{mermaid}\n```\n")

    return "\n".join(parts)
