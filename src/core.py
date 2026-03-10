"""Core business logic extracted from mcp_server.py.

All tool/resource functions live here. mcp_server.py is a thin MCP wrapper
that delegates every call to the corresponding function in this module.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.interaction_log import InteractionLog
    from src.search_analytics import SearchAnalyticsDB

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level imports used by tool functions.
# Keeping them at module level allows tests to patch e.g.
# ``mcp_server.search`` (which reassigns ``core.search``).
# ---------------------------------------------------------------------------

from src.search import (  # noqa: E402
    highlight_matches as highlight_matches,
    search as search,
    suggest_alternative_queries as suggest_alternative_queries,
)

# ---------------------------------------------------------------------------
# Lazy singletons
# ---------------------------------------------------------------------------

_analytics: SearchAnalyticsDB | None = None
_interaction_log: InteractionLog | None = None


def _get_analytics() -> SearchAnalyticsDB:
    global _analytics
    if _analytics is None:
        from src.search_analytics import SearchAnalyticsDB
        _analytics = SearchAnalyticsDB()
    return _analytics


def _get_interaction_log() -> InteractionLog:
    global _interaction_log
    if _interaction_log is None:
        from src.interaction_log import InteractionLog
        _interaction_log = InteractionLog()
    return _interaction_log


def _log_interaction(
    tool_name: str,
    input_summary: str,
    output_summary: str,
    duration_ms: int | None = None,
) -> None:
    """Helper: log an interaction via the singleton InteractionLog."""
    if duration_ms is not None:
        _get_interaction_log().log(tool_name, input_summary, output_summary, duration_ms)
    else:
        _get_interaction_log().log(tool_name, input_summary, output_summary)


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def search_documents(
    query: str,
    top_k: int = 5,
    project: str | None = None,
    doc_type: str | None = None,
) -> str:
    """Search indexed documents with hybrid vector+keyword search."""
    from src.config import workspace

    if not query or not query.strip():
        return "Please provide a search query."
    max_k = workspace.search.max_top_k
    top_k = max(1, min(top_k, max_k))
    import time as _time
    _t0 = _time.monotonic()
    try:
        results = search(query.strip(), top_k=top_k, project=project, doc_type=doc_type)
    except Exception as exc:
        logger.error("Search failed: %s", exc)
        return "Couldn't search yet — your documents haven't been indexed. Try asking me to 'index my documents' first."
    _elapsed = (_time.monotonic() - _t0) * 1000
    _get_analytics().log_query(query.strip(), top_k, len(results), _elapsed, project, doc_type, "search")
    _log_interaction(
        "search_documents",
        f"query={query.strip()!r} top_k={top_k} project={project}",
        f"{len(results)} results in {_elapsed:.0f}ms",
        int(_elapsed),
    )

    if not results:
        msg = "I couldn't find anything matching that."
        suggestions = suggest_alternative_queries(query.strip())
        if suggestions:
            msg += "\n\nTry these alternative queries:\n"
            for s in suggestions:
                msg += f"  - {s}\n"
        else:
            msg += " Try the `ingest_documents` tool to index your documents first."
        return msg

    text_limit = workspace.search.result_text_limit
    output_parts = []
    for i, r in enumerate(results, 1):
        meta = r["metadata"]
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except (json.JSONDecodeError, TypeError):
                meta = {}

        source = meta.get("source_path", "unknown")
        section = meta.get("section", "")
        doc_type_val = meta.get("doc_type", "")
        version = meta.get("version", "")
        similarity = r.get("similarity", 0.0)

        header = f"[{i}] {source}"
        if section:
            header += f" > {section}"
        if doc_type_val:
            header += f" ({doc_type_val})"
        if version:
            header += f" [v{version}]"
        header += f"  (similarity: {similarity * 100:.1f}%)"

        text = r["text"]
        text = highlight_matches(text, query.strip())
        if len(text) > text_limit:
            text = text[:text_limit] + "…"

        output_parts.append(f"{header}\n{text}")

    return "\n\n---\n\n".join(output_parts)


def view_file_full(file_path: str) -> str:
    """Return full contents of any supported file as structured text."""
    from src.search import list_indexed_sources

    p = Path(file_path)

    # Try to find by partial filename if not absolute
    if not p.exists() and not p.is_absolute():
        try:
            sources = list_indexed_sources()
            for s in sources:
                if file_path.lower() in s.lower():
                    p = Path(s)
                    break
        except Exception:
            pass

    if not p.exists():
        return f"File not found: {file_path}"

    suffix = p.suffix.lower()
    if suffix == ".csv":
        from src.ingestion.csv_parser import format_csv_as_table
        return format_csv_as_table(p)
    elif suffix in (".xlsx", ".xls"):
        from src.ingestion.xlsx_parser import format_xlsx_as_table
        return format_xlsx_as_table(p)
    elif suffix == ".pdf":
        from src.ingestion.pdf_parser import format_pdf_as_text
        return format_pdf_as_text(p)
    elif suffix == ".md":
        return read_file(str(p))
    elif suffix == ".docx":
        return read_file(str(p))
    else:
        return read_file(str(p))


def list_sources() -> str:
    """List all indexed source files."""
    from src.search import list_indexed_sources

    sources = list_indexed_sources()

    if not sources:
        return "No files indexed yet. Ask me to 'index my documents' or run `tessera setup` to get started."

    lines = [f"Indexed files ({len(sources)}):", ""]
    for s in sources:
        lines.append(f"  - {s}")

    return "\n".join(lines)


def read_file(file_path: str) -> str:
    """Read file contents by path."""
    from src.config import workspace

    p = Path(file_path)

    if not p.exists():
        return f"File not found: {file_path}"

    if not p.is_file():
        return f"Not a file: {file_path}"

    try:
        content = p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return f"Not a text file: {file_path}"

    max_read = workspace.limits.max_file_read
    if len(content) > max_read:
        content = content[:max_read] + f"\n\n… (truncated at {max_read:,} chars)"

    return content


def organize_files(
    action: str,
    path: str,
    destination: str | None = None,
    new_name: str | None = None,
    recursive: bool = False,
) -> str:
    """Organize files in the workspace."""
    from src.organizer import archive_file, list_directory, move_file, rename_file

    if action == "move":
        if not destination:
            return "destination is required for 'move' action."
        return move_file(path, destination)
    elif action == "archive":
        return archive_file(path)
    elif action == "rename":
        if not new_name:
            return "new_name is required for 'rename' action."
        return rename_file(path, new_name)
    elif action == "list":
        return list_directory(path, recursive=recursive)
    else:
        return f"Unknown action: {action}. Use 'move', 'archive', 'rename', or 'list'."


def suggest_cleanup(path: str | None = None) -> str:
    """Suggest cleanup actions for the workspace."""
    from src.organizer import suggest_organization

    return suggest_organization(path)


def project_status(project_id: str | None = None) -> str:
    """Get project status. If no project_id, returns all projects summary."""
    from src.project_status import get_all_projects_summary, get_project_status

    if project_id:
        return get_project_status(project_id)
    return get_all_projects_summary()


def extract_decisions(project_id: str | None = None, since: str | None = None) -> str:
    """Extract decisions from session/decision logs."""
    from src.project_status import extract_decisions as _extract

    return _extract(project_id=project_id, since=since)


def audit_prd(
    file_path: str,
    check_sprawl: bool = False,
    check_consistency: bool = False,
) -> str:
    """Audit a PRD file for quality and completeness."""
    from src.prd_auditor import (
        audit_cross_prd_consistency,
        audit_prd_file,
        find_prd_version_sprawl,
    )

    result = audit_prd_file(file_path)
    output = result.summary()

    if check_sprawl:
        parent = Path(file_path).parent
        sprawl = find_prd_version_sprawl(parent)
        if sprawl:
            output += "\n\n## Version Sprawl Detected"
            for s in sprawl:
                output += f"\n\n{s['base_name']}:"
                for v in s["versions"]:
                    marker = " <- latest" if v["path"] == s["latest"] else " <- archive candidate"
                    output += f"\n  v{v['version']}: {Path(v['path']).name}{marker}"
        else:
            output += "\n\nNo version sprawl detected."

    if check_consistency:
        parent = Path(file_path).parent
        issues = audit_cross_prd_consistency(parent)
        if issues:
            output += "\n\n## Consistency Issues"
            for issue in issues:
                output += f"\n  - {issue}"
        else:
            output += "\n\nNo cross-PRD consistency issues."

    return output


# --- Memory Tools ---


def remember(content: str, tags: list[str] | None = None) -> str:
    """Save a memory for cross-session persistence."""
    if not content or not content.strip():
        return "What should I remember? Tell me what you'd like to save."
    from src.auto_extract import should_auto_learn
    from src.memory import learn_and_index

    # Auto-detect category from content
    extracted = should_auto_learn(content.strip())
    if extracted and not tags:
        tags = [extracted[0].category]
    result = learn_and_index(content.strip(), tags=tags, source="user-request")
    if result.get("deduplicated"):
        sim = result.get("similarity", 0) * 100
        _log_interaction("remember", f"content={content.strip()[:100]!r} tags={tags}", f"dedup ({sim:.0f}%)")
        return f"Already remembered (similar memory exists, {sim:.0f}% match). Skipped duplicate."
    status = "indexed" if result["indexed"] else "saved (not yet indexed)"
    _log_interaction("remember", f"content={content.strip()[:100]!r} tags={tags}", status)
    return f"Remembered and {status}:\n{content}"


def recall(
    query: str,
    top_k: int = 5,
    since: str | None = None,
    until: str | None = None,
    category: str | None = None,
) -> str:
    """Search past memories using semantic similarity with optional filters.

    Args:
        query: Search query.
        top_k: Max results.
        since: Only memories after this date (e.g. '2026-03-01').
        until: Only memories before this date (e.g. '2026-03-10').
        category: Filter by category (decision, preference, fact).
    """
    if not query or not query.strip():
        return "Please provide a search query."
    from src.config import workspace
    from src.memory import recall_memories

    top_k = max(1, min(top_k, workspace.search.max_top_k))

    memories = recall_memories(
        query.strip(), top_k=top_k, since=since, until=until, category=category,
    )
    filters = []
    if since:
        filters.append(f"since={since}")
    if until:
        filters.append(f"until={until}")
    if category:
        filters.append(f"category={category}")
    filter_str = f" [{', '.join(filters)}]" if filters else ""
    _log_interaction("recall", f"query={query.strip()!r} top_k={top_k}{filter_str}", f"{len(memories)} memories found")

    if not memories:
        if filters:
            return f"No memories found matching your filters{filter_str}."
        return "I don't have any memories yet. You can ask me to remember something first."

    parts = []
    for i, m in enumerate(memories, 1):
        sim = m["similarity"] * 100
        header = f"[{i}] (similarity: {sim:.1f}%)"
        if m.get("category"):
            header += f"  [{m['category']}]"
        if m["date"]:
            header += f"  date: {m['date']}"
        if m["tags"]:
            header += f"  tags: {m['tags']}"
        parts.append(f"{header}\n{m['content']}")

    return "\n\n---\n\n".join(parts)


def learn(content: str, tags: list[str] | None = None, source: str = "auto-learn") -> str:
    """Save and immediately index new knowledge."""
    if not content or not content.strip():
        return "Please provide content to learn."
    from src.memory import learn_and_index

    result = learn_and_index(content.strip(), tags=tags, source=source)
    if result.get("deduplicated"):
        sim = result.get("similarity", 0) * 100
        _log_interaction("learn", f"content={content.strip()[:100]!r} tags={tags}", f"dedup ({sim:.0f}%)")
        return f"Already known (similar memory exists, {sim:.0f}% match). Skipped duplicate."
    status = "indexed" if result["indexed"] else "saved (indexing failed)"
    _log_interaction("learn", f"content={content.strip()[:100]!r} tags={tags}", status)
    return f"Learned and {status}:\n{content}"


# --- Knowledge Graph Tools ---


def knowledge_graph(
    query: str | None = None,
    project: str | None = None,
    scope: str = "all",
    max_nodes: int = 30,
) -> str:
    """Build and return a knowledge graph as Mermaid diagram."""
    from src.config import workspace
    from src.knowledge_graph import build_knowledge_graph

    kg = workspace.knowledge_graph
    max_nodes = max(1, min(max_nodes, kg.max_max_nodes))
    if scope not in ("all", "project"):
        scope = "all"
    return build_knowledge_graph(
        query=query, project=project, scope=scope, max_nodes=max_nodes
    )


def explore_connections(query: str, top_k: int = 10) -> str:
    """Explore connections around a specific topic or document."""
    if not query or not query.strip():
        return "Please provide a topic or document name to explore."
    from src.config import workspace
    from src.knowledge_graph import explore_connections as _explore

    top_k = max(1, min(top_k, workspace.search.max_top_k))

    return _explore(query=query.strip(), top_k=top_k)


# --- Unified Search ---


def unified_search(
    query: str,
    top_k: int = 5,
    project: str | None = None,
    doc_type: str | None = None,
) -> str:
    """Search documents and memories together."""
    if not query or not query.strip():
        return "Please provide a search query."
    from src.config import workspace

    max_k = workspace.search.max_top_k
    top_k = max(1, min(top_k, max_k))
    query = query.strip()
    text_limit = workspace.search.unified_text_limit
    import time as _time
    _t0 = _time.monotonic()

    parts = []
    mem_count = 0

    # 1. Document search
    try:
        doc_results = search(query, top_k=top_k, project=project, doc_type=doc_type)
    except Exception as exc:
        logger.error("Document search failed: %s", exc)
        doc_results = []
    if doc_results:
        parts.append(f"## Documents ({len(doc_results)} results)")
        for i, r in enumerate(doc_results, 1):
            meta = r["metadata"]
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except (json.JSONDecodeError, TypeError):
                    meta = {}
            source = meta.get("source_path", "unknown")
            similarity = r.get("similarity", 0.0)
            raw_text = r["text"]
            text = highlight_matches(raw_text, query)
            if len(text) > text_limit:
                text = text[:text_limit] + "…"
            parts.append(f"[D{i}] {source} ({similarity * 100:.0f}%)\n{text}")

    # 2. Memory search
    try:
        from src.memory import recall_memories

        memories = recall_memories(query, top_k=min(top_k, 5))
        if memories:
            mem_count = len(memories)
            parts.append(f"\n## Memories ({mem_count} results)")
            for i, m in enumerate(memories, 1):
                sim = m["similarity"] * 100
                date = m.get("date", "")
                tags = m.get("tags", "")
                header = f"[M{i}] ({sim:.0f}%)"
                if date:
                    header += f" {date[:10]}"
                if tags:
                    header += f" [{tags}]"
                parts.append(f"{header}\n{m['content']}")
    except Exception as exc:
        logger.debug("Memory search skipped: %s", exc)

    _elapsed = (_time.monotonic() - _t0) * 1000
    _get_analytics().log_query(query, top_k, len(doc_results) + mem_count, _elapsed, project, doc_type, "unified")
    _log_interaction(
        "unified_search",
        f"query={query!r} top_k={top_k} project={project}",
        f"{len(doc_results)} docs + {mem_count} memories in {_elapsed:.0f}ms",
        int(_elapsed),
    )

    if not parts:
        return "No results found in documents or memories."

    return "\n\n---\n\n".join(parts)


# --- Indexing Tools ---


def ingest_documents(paths: list[str] | None = None) -> str:
    """Full ingestion of workspace documents."""
    from src.graph.vector_store import OntologyVectorStore
    from src.ingestion.pipeline import IngestionPipeline
    from src.search import invalidate_search_cache

    vector_store = OntologyVectorStore()
    pipeline = IngestionPipeline(vector_store=vector_store)

    source_paths = [Path(p) for p in paths] if paths else None
    try:
        count, per_file = pipeline.run(source_paths=source_paths)
    except Exception as exc:
        logger.error("Ingestion failed: %s", exc)
        return (
            "Something went wrong while indexing. Make sure your workspace folder "
            "exists and contains supported files (.md, .csv, .xlsx, .docx, .pdf)."
        )
    invalidate_search_cache()

    return (
        f"Indexing complete: {count} documents from {len(per_file)} files.\n"
        f"You can now use search_documents to search across them."
    )


def sync_documents() -> str:
    """Incremental sync -- only new/changed/deleted files."""
    from src.config import workspace
    from src.graph.vector_store import OntologyVectorStore
    from src.ingestion.pipeline import IngestionPipeline
    from src.search import invalidate_search_cache
    from src.sync import FileMetaDB, run_incremental_sync

    meta_db = FileMetaDB(workspace.meta_db_path)
    vector_store = OntologyVectorStore()
    pipeline = IngestionPipeline(vector_store=vector_store)

    def _ingest(file_paths: list[Path]) -> tuple[int, dict[str, int]]:
        return pipeline.run(source_paths=file_paths)

    result = run_incremental_sync(
        ws=workspace,
        meta_db=meta_db,
        vector_store_delete_fn=vector_store.delete_by_source,
        ingest_fn=_ingest,
    )
    meta_db.close()
    if result.has_changes:
        invalidate_search_cache()

    parts = [f"Sync complete: {result.summary()}"]
    if result.new:
        parts.append(f"New: {', '.join(p.name for p in result.new[:10])}")
        if len(result.new) > 10:
            parts.append(f"  ...and {len(result.new) - 10} more")
    if result.changed:
        parts.append(f"Changed: {', '.join(p.name for p in result.changed[:10])}")
    if result.deleted:
        parts.append(f"Deleted: {', '.join(Path(p).name for p in result.deleted[:10])}")

    return "\n".join(parts)


# --- Operations Tools ---


def tessera_status() -> str:
    """Return server health and operational status."""
    from src.config import workspace
    from src.embedding import embed_query
    from src.search import _search_cache, list_indexed_sources
    from src.sync import FileMetaDB

    lines = ["# Tessera Status", ""]

    # Tracked files
    try:
        meta_db = FileMetaDB(workspace.meta_db_path)
        tracked = meta_db.file_count()
        lines.append(f"**Tracked files:** {tracked}")

        # Recent sync history
        history = meta_db.sync_history(limit=5)
        if history:
            lines.append("")
            lines.append("## Recent Syncs")
            for h in history:
                ts = h.get("timestamp", "?")[:19]
                new = h.get("new_count", 0)
                changed = h.get("changed_count", 0)
                deleted = h.get("deleted_count", 0)
                lines.append(f"- {ts}: +{new} ~{changed} -{deleted}")
        meta_db.close()
    except Exception as exc:
        lines.append(f"**DB error:** {exc}")

    # Index stats
    try:
        sources = list_indexed_sources()
        lines.append(f"\n**Indexed sources:** {len(sources)}")
    except Exception:
        lines.append("\n**Index:** not available")

    # Cache stats
    lines.append(f"**Search cache entries:** {len(_search_cache)}")

    cache_info = embed_query.cache_info()
    lines.append(
        f"**Embed cache:** {cache_info.hits} hits / {cache_info.misses} misses "
        f"({cache_info.currsize}/{cache_info.maxsize})"
    )

    # Config summary
    lines.append("")
    lines.append("## Config")
    lines.append(f"- Workspace: {workspace.name} ({workspace.root})")
    lines.append(f"- Extensions: {', '.join(workspace.extensions)}")
    lines.append(f"- Auto-sync: {workspace.sync_auto}")
    lines.append(f"- Poll interval: {workspace.watcher.poll_interval}s")
    lines.append(f"- Chunk size: {workspace.ingestion.chunk_size}")
    lines.append(f"- Reranker weight: {workspace.search.reranker_weight}")

    return "\n".join(lines)


def list_memories(limit: int = 20) -> str:
    """List saved memory files."""
    from src.memory import _memory_dir

    mem_dir = _memory_dir()
    files = sorted(mem_dir.glob("*.md"), reverse=True)

    if not files:
        return "No memories saved yet. Use the `remember` tool to save knowledge."

    limit = max(1, min(limit, 100))
    files = files[:limit]

    lines = [f"# Saved Memories ({len(files)})", ""]
    for f in files:
        # Parse frontmatter for tags
        text = f.read_text(encoding="utf-8")
        tags = ""
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                for line in parts[1].strip().splitlines():
                    if line.startswith("tags:"):
                        tags = line.split(":", 1)[1].strip()
                        break

        # First line of body as preview
        body = text.split("---", 2)[-1].strip() if "---" in text else text.strip()
        preview = body[:80].replace("\n", " ")
        if len(body) > 80:
            preview += "…"

        tag_str = f" {tags}" if tags else ""
        lines.append(f"- **{f.stem}**{tag_str}")
        lines.append(f"  {preview}")

    return "\n".join(lines)


def forget_memory(memory_name: str) -> str:
    """Delete a saved memory file."""
    if not memory_name or not memory_name.strip():
        return "Please provide a memory name."

    from src.memory import _memory_dir

    mem_dir = _memory_dir()
    target = mem_dir / f"{memory_name.strip()}.md"

    if not target.exists():
        return f"Memory not found: {memory_name}"

    # Safety: ensure it's within the memories directory
    if not str(target.resolve()).startswith(str(mem_dir.resolve())):
        return "Invalid memory path."

    target.unlink()
    return f"Deleted memory: {memory_name}"


# --- Freshness Tools ---


def check_document_freshness(days_threshold: int = 90) -> str:
    """Check for stale documents exceeding the age threshold."""
    days_threshold = max(1, min(days_threshold, 365))
    from src.freshness import freshness_summary

    return freshness_summary(days_threshold=days_threshold)


def health_check() -> str:
    """Run workspace health diagnostics."""
    from src.search import list_indexed_sources

    lines = ["# Tessera Health Check", ""]
    issues = []
    ok = []

    # 1. Config
    try:
        from src.config import load_workspace_config
        ws = load_workspace_config()
        ok.append(f"Config valid ({len(ws.sources)} sources, {len(ws.projects)} projects)")
    except Exception as exc:
        issues.append(f"Config error: {exc}")

    # 2. Index
    try:
        sources = list_indexed_sources()
        ok.append(f"Index: {len(sources)} sources indexed")
    except Exception:
        issues.append("Index not available")

    # 3. Dependencies
    deps = {"fastembed": "Embedding", "lancedb": "Vector store", "mcp": "MCP server"}
    for mod, desc in deps.items():
        try:
            __import__(mod)
            ok.append(f"{desc} ({mod}) installed")
        except ImportError:
            issues.append(f"{desc} ({mod}) not installed")

    # 4. Stale documents
    try:
        from src.freshness import check_freshness
        stale = check_freshness(days_threshold=90)
        if stale:
            issues.append(f"{len(stale)} documents older than 90 days")
        else:
            ok.append("All documents recently updated")
    except Exception:
        pass

    # 5. Zero-result queries
    try:
        stats = _get_analytics().get_stats(days=30)
        zero = stats.get("zero_result_queries", [])
        if zero:
            issues.append(f"{len(zero)} queries returned zero results in last 30 days")
        else:
            ok.append("No zero-result queries")
    except Exception:
        pass

    for item in ok:
        lines.append(f"- [OK] {item}")
    if issues:
        lines.append("")
        for item in issues:
            lines.append(f"- [!!] {item}")
        lines.append(f"\n{len(issues)} issue(s) found.")
    else:
        lines.append("\nAll checks passed.")

    return "\n".join(lines)


# --- Analytics Tools ---


def search_analytics(days: int = 30) -> str:
    """Return search analytics summary."""
    days = max(1, min(days, 365))
    stats = _get_analytics().get_stats(days=days)

    lines = [f"# Search Analytics (last {days} days)", ""]
    lines.append(f"**Total queries:** {stats['total_queries']}")
    lines.append(f"**Avg response time:** {stats['avg_response_ms']:.1f}ms")

    if stats["queries_by_source"]:
        lines.append("\n## By Source")
        for src, cnt in stats["queries_by_source"].items():
            lines.append(f"- {src}: {cnt}")

    if stats["top_queries"]:
        lines.append("\n## Top Queries")
        for q in stats["top_queries"]:
            lines.append(f"- \"{q['query']}\" ({q['count']}x, avg {q['avg_response_ms']:.0f}ms)")

    if stats["zero_result_queries"]:
        lines.append("\n## Zero-Result Queries")
        for q in stats["zero_result_queries"]:
            lines.append(f"- \"{q['query']}\" ({q['count']}x)")

    if stats["queries_per_day"]:
        lines.append("\n## Daily Trend")
        for d in stats["queries_per_day"][-14:]:  # Last 2 weeks
            lines.append(f"- {d['date']}: {d['count']}")

    return "\n".join(lines)


# --- Batch Memory Tools ---


def export_memories() -> str:
    """Export all memories as JSON."""
    from src.memory import export_memories as _export

    data = _export(format="json")
    count = data.count('"content"')
    return f"Exported {count} memories:\n\n{data}"


def import_memories(data: str) -> str:
    """Import memories from JSON."""
    if not data or not data.strip():
        return "Please provide JSON data to import."
    from src.memory import import_memories as _import

    try:
        result = _import(data.strip(), format="json")
    except ValueError as exc:
        return f"Import error: {exc}"

    lines = [f"Imported {result['imported']} memories, indexed {result['indexed']}."]
    if result["errors"]:
        lines.append(f"\nErrors ({len(result['errors'])}):")
        for err in result["errors"][:10]:
            lines.append(f"  - {err}")
    return "\n".join(lines)


# --- Similarity Tools ---


def find_similar(source_path: str, top_k: int = 5) -> str:
    """Find documents similar to the given source file."""
    if not source_path or not source_path.strip():
        return "Please provide a source file path."
    top_k = max(1, min(top_k, 20))
    from src.similarity import find_similar_documents

    try:
        results = find_similar_documents(source_path.strip(), top_k=top_k)
    except Exception as exc:
        logger.error("Similarity search failed: %s", exc)
        return f"Error: {exc}"

    if not results:
        return "No similar documents found."

    lines = [f"Documents similar to `{Path(source_path).name}`:", ""]
    for i, r in enumerate(results, 1):
        sim = r["similarity"] * 100
        section = f" > {r['section']}" if r.get("section") else ""
        lines.append(f"[{i}] {r['file_name']}{section} ({sim:.0f}%)")
        lines.append(f"    {r['text_preview']}")
    return "\n".join(lines)


# --- Tag Tools ---


def memory_tags() -> str:
    """List all memory tags with counts."""
    from src.memory import list_memory_tags

    tags = list_memory_tags()
    if not tags:
        return "No tags found. Save memories with tags using the `remember` tool."

    lines = [f"# Memory Tags ({len(tags)})", ""]
    for tag, count in tags.items():
        lines.append(f"- **{tag}** ({count})")
    return "\n".join(lines)


def search_by_tag(tag: str) -> str:
    """Find all memories with a specific tag."""
    if not tag or not tag.strip():
        return "Please provide a tag to search for."
    from src.memory import search_memories_by_tag

    results = search_memories_by_tag(tag.strip())
    if not results:
        return f"No memories found with tag '{tag}'."

    lines = [f"# Memories tagged '{tag}' ({len(results)})", ""]
    for r in results:
        date = r.get("date", "")[:10] if r.get("date") else ""
        header = f"- **{r['filename']}**"
        if date:
            header += f" ({date})"
        lines.append(header)
        preview = r["content"][:100].replace("\n", " ")
        if len(r["content"]) > 100:
            preview += "…"
        lines.append(f"  {preview}")
    return "\n".join(lines)


def memory_categories() -> str:
    """List all memory categories with counts."""
    from src.memory import list_memory_categories

    cats = list_memory_categories()
    if not cats:
        return "No categories found. Categories are auto-detected when saving memories."

    lines = [f"# Memory Categories ({len(cats)})", ""]
    for cat, count in cats.items():
        lines.append(f"- **{cat}** ({count})")
    return "\n".join(lines)


def search_by_category(category: str) -> str:
    """Find all memories with a specific category (decision, preference, fact, etc.)."""
    if not category or not category.strip():
        return "Please provide a category (e.g. 'decision', 'preference', 'fact')."
    from src.memory import search_memories_by_category

    results = search_memories_by_category(category.strip())
    if not results:
        return f"No memories found with category '{category}'."

    lines = [f"# {category.title()} memories ({len(results)})", ""]
    for r in results:
        date = r.get("date", "")[:10] if r.get("date") else ""
        header = f"- **{r['filename']}**"
        if date:
            header += f" ({date})"
        lines.append(header)
        preview = r["content"][:100].replace("\n", " ")
        if len(r["content"]) > 100:
            preview += "..."
        lines.append(f"  {preview}")
    return "\n".join(lines)


# --- MCP Resources ---


def document_index() -> str:
    """Provide a browsable index of all indexed documents."""
    from src.search import list_indexed_sources

    sources = list_indexed_sources()

    if not sources:
        return "No indexed documents."

    # Group by project directory
    groups: dict[str, list[str]] = {}
    for s in sources:
        parts = Path(s).parts
        # Try to extract a meaningful group name from the path
        key = "Other"
        for i, part in enumerate(parts):
            if part in ("products", "internal", "memory", "docs"):
                if i + 1 < len(parts):
                    key = parts[i + 1]
                else:
                    key = part
                break
        groups.setdefault(key, []).append(s)

    lines = [f"# Indexed Documents ({len(sources)})", ""]
    for group, files in sorted(groups.items()):
        lines.append(f"## {group} ({len(files)})")
        for f in files:
            name = Path(f).name
            lines.append(f"- {name}")
            lines.append(f"  `{f}`")
        lines.append("")

    return "\n".join(lines)


def workspace_status() -> str:
    """Provide current workspace status across all projects."""
    from src.project_status import get_all_projects_summary

    return get_all_projects_summary()


# --- Auto-Learn Tools ---


def digest_conversation(summary: str = "") -> str:
    """Extract and save knowledge from the current session."""
    from src.auto_extract import should_auto_learn
    from src.memory import learn_and_index

    facts_saved = 0
    all_text = summary

    # If no summary provided, gather from interaction log
    if not all_text.strip():
        interactions = _get_interaction_log().get_session_interactions(limit=50)
        text_parts = []
        for ix in interactions:
            text_parts.append(f"{ix['input_summary']} {ix['output_summary']}")
        all_text = "\n".join(text_parts)

    if not all_text.strip():
        return "Nothing to digest — no interactions in this session yet."

    extracted = should_auto_learn(all_text)
    if not extracted:
        return "No decisions, preferences, or facts detected in this session."

    results = []
    for fact in extracted:
        try:
            learn_and_index(
                fact.content,
                tags=[fact.category],
                source=f"auto-digest-{fact.category}",
            )
            facts_saved += 1
            results.append(f"- [{fact.category}] {fact.content[:80]}")
        except Exception as exc:
            logger.warning("Failed to save extracted fact: %s", exc)

    _log_interaction(
        "digest_conversation",
        f"input_length={len(all_text)}",
        f"extracted={len(extracted)} saved={facts_saved}",
    )

    header = f"Digested {facts_saved} facts from this session:"
    return f"{header}\n" + "\n".join(results)


def decision_timeline() -> str:
    """Show how decisions have evolved over time, grouped by topic."""
    from src.decision_tracker import format_decision_timeline, get_decision_timeline
    from src.memory import search_memories_by_category

    decisions = search_memories_by_category("decision")
    if not decisions:
        return "No decision memories found. Decisions are auto-detected when you say things like 'we decided to use X'."

    groups = get_decision_timeline(decisions)
    _log_interaction("decision_timeline", "", f"{len(groups)} topics, {len(decisions)} decisions")
    return format_decision_timeline(groups)


def toggle_auto_learn(enabled: bool | None = None) -> str:
    """Toggle or check auto-learning status.

    If enabled is None, returns current status.
    Otherwise, sets auto-learning on or off.
    """
    from src.config import workspace

    if enabled is None:
        status = "ON" if workspace.auto_learn.enabled else "OFF"
        return (
            f"Auto-learn is {status}\n"
            f"Min confidence: {workspace.auto_learn.min_confidence}\n"
            f"Min interactions for summary: {workspace.auto_learn.min_interactions_for_summary}"
        )

    # WorkspaceConfig is not frozen, so we can replace the auto_learn field
    from src.config import AutoLearnConfig

    workspace.auto_learn = AutoLearnConfig(
        enabled=enabled,
        min_confidence=workspace.auto_learn.min_confidence,
        min_interactions_for_summary=workspace.auto_learn.min_interactions_for_summary,
    )
    status = "ON" if enabled else "OFF"
    _log_interaction("toggle_auto_learn", f"enabled={enabled}", status)
    return f"Auto-learn is now {status}."


def review_learned(limit: int = 20) -> str:
    """Review recently auto-learned memories.

    Shows memories with source containing 'auto' — these are the ones
    created by auto-extract, digest, or session summary.
    """
    from src.memory import _memory_dir

    mem_dir = _memory_dir()
    auto_memories: list[dict] = []

    for md_file in sorted(mem_dir.glob("*.md"), reverse=True):
        text = md_file.read_text(encoding="utf-8")
        if not text.startswith("---"):
            continue

        parts = text.split("---", 2)
        if len(parts) < 3:
            continue

        frontmatter = parts[1]
        body = parts[2].strip()
        source = ""
        category = ""
        date_str = ""

        for line in frontmatter.strip().splitlines():
            if line.startswith("source:"):
                source = line.split(":", 1)[1].strip()
            elif line.startswith("category:"):
                category = line.split(":", 1)[1].strip()
            elif line.startswith("date:"):
                date_str = line.split(":", 1)[1].strip()

        if "auto" in source or "session" in source or "digest" in source:
            auto_memories.append({
                "filename": md_file.stem,
                "content": body,
                "source": source,
                "category": category,
                "date": date_str,
            })

        if len(auto_memories) >= limit:
            break

    if not auto_memories:
        return "No auto-learned memories found yet."

    lines = [f"# Auto-learned memories ({len(auto_memories)})", ""]
    for m in auto_memories:
        date = m["date"][:10] if m["date"] else ""
        cat = f"[{m['category']}]" if m["category"] else ""
        lines.append(f"- **{m['filename']}** {cat} ({date})")
        preview = m["content"][:120].replace("\n", " ")
        if len(m["content"]) > 120:
            preview += "..."
        lines.append(f"  {preview}")
        lines.append(f"  source: {m['source']}")
    return "\n".join(lines)


def context_window(
    query: str,
    token_budget: int = 4000,
    include_documents: bool = True,
) -> str:
    """Build an optimal context window for a query within a token budget.

    Retrieves relevant memories (and optionally documents), assembles them
    in priority order, and truncates to fit the budget.

    Args:
        query: What context to assemble for.
        token_budget: Max tokens for the context window.
        include_documents: Whether to also search documents.
    """
    from src.context_window import build_context_window, format_context_summary
    from src.memory import recall_memories

    memories = recall_memories(query.strip(), top_k=20)

    documents = []
    if include_documents:
        try:
            results = search(query.strip(), top_k=10)
            documents = [
                {"content": r.get("text", ""), "score": r.get("score", 0), "source": r.get("source", "")}
                for r in results
                if r.get("text")
            ]
        except Exception:
            logger.debug("Document search failed for context window, continuing with memories only")

    result = build_context_window(
        memories=memories,
        documents=documents,
        token_budget=token_budget,
    )

    _log_interaction(
        "context_window",
        f"query={query!r} budget={token_budget}",
        f"{result['included_memories']}mem + {result['included_documents']}doc, ~{result['token_count']}tok",
    )
    return format_context_summary(result)


def smart_suggest(max_suggestions: int = 5) -> str:
    """Get personalized query suggestions based on past interactions and memories.

    Analyzes search history and memory patterns to recommend what to explore next.
    """
    from src.smart_suggest import format_suggestions, suggest_from_history

    # Get past queries from search analytics
    past_queries: list[str] = []
    try:
        analytics = _get_analytics()
        recent = analytics.get_recent_queries(limit=50)
        past_queries = [r["query"] for r in recent if r.get("query")]
    except Exception:
        logger.debug("Could not load search analytics for suggestions")

    # Get memories for topic analysis
    memories: list[dict] = []
    try:
        from src.memory import list_memories
        memories = list_memories(limit=50)
    except Exception:
        logger.debug("Could not load memories for suggestions")

    suggestions = suggest_from_history(
        past_queries, memories=memories, max_suggestions=max_suggestions,
    )
    _log_interaction("smart_suggest", f"max={max_suggestions}", f"{len(suggestions)} suggestions")
    return format_suggestions(suggestions)


def topic_map(output_format: str = "text") -> str:
    """Generate a topic map of all memories.

    Args:
        output_format: 'text' for readable text, 'mermaid' for Mermaid diagram.
    """
    from src.topic_map import build_topic_map, format_topic_map_mermaid, format_topic_map_text

    # Get all memories
    memories: list[dict] = []
    try:
        from src.memory import list_memories
        memories = list_memories(limit=200)
    except Exception:
        logger.debug("Could not load memories for topic map")

    topics = build_topic_map(memories)
    _log_interaction("topic_map", f"format={output_format}", f"{len(topics)} topics")

    if output_format == "mermaid":
        return format_topic_map_mermaid(topics)
    return format_topic_map_text(topics)


def knowledge_stats() -> str:
    """Get aggregate statistics about stored knowledge."""
    from src.knowledge_stats import compute_stats, format_stats

    memories: list[dict] = []
    try:
        from src.memory import list_memories
        memories = list_memories(limit=500)
    except Exception:
        logger.debug("Could not load memories for stats")

    documents: list[dict] = []
    try:
        from src.ingestion.pipeline import get_indexed_count
        documents = [{}] * get_indexed_count()
    except Exception:
        pass

    stats = compute_stats(memories, documents)
    _log_interaction("knowledge_stats", "", f"{stats['total_memories']} memories, {stats['total_documents']} docs")
    return format_stats(stats)


def user_profile() -> str:
    """Build and display a user profile from memories and interactions."""
    from src.user_profile import build_profile, format_profile

    memories: list[dict] = []
    try:
        from src.memory import list_memories
        memories = list_memories(limit=200)
    except Exception:
        logger.debug("Could not load memories for profile")

    interactions: list[dict] = []
    try:
        log = _get_interaction_log()
        interactions = log.get_recent(limit=200)
    except Exception:
        logger.debug("Could not load interactions for profile")

    profile = build_profile(memories, interactions)
    _log_interaction("user_profile", "", f"{profile['total_memories']} memories")
    return format_profile(profile)


# --- Interaction Log Tools ---


def session_interactions(session_id: str | None = None, limit: int = 20) -> str:
    """List tool interactions from a session."""
    interactions = _get_interaction_log().get_session_interactions(session_id, limit)
    if not interactions:
        return "No interactions recorded yet in this session."

    lines = [f"## Session Interactions (latest {len(interactions)})"]
    for ix in interactions:
        lines.append(
            f"- **{ix['tool_name']}** ({ix['timestamp'][:19]})\n"
            f"  Input: {ix['input_summary']}\n"
            f"  Output: {ix['output_summary']}"
        )
    return "\n".join(lines)


def recent_sessions(limit: int = 10) -> str:
    """List recent session summaries."""
    sessions = _get_interaction_log().get_recent_sessions(limit)
    if not sessions:
        return "No sessions recorded yet."

    lines = ["## Recent Sessions"]
    for s in sessions:
        started = s["started"][:19] if s["started"] else "?"
        ended = s["ended"][:19] if s["ended"] else "?"
        lines.append(
            f"- **{s['session_id']}**: {started} → {ended} "
            f"({s['interaction_count']} interactions)"
        )
    return "\n".join(lines)
