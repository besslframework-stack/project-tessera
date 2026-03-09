"""Tessera MCP server — exposes document search tools to Claude Desktop."""

from __future__ import annotations

import json
import logging
import logging.handlers
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

# Ensure project root is on sys.path so `src` package resolves
_project_root = str(Path(__file__).parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from mcp.server.fastmcp import FastMCP

from src.config import workspace
from src.search import highlight_matches, invalidate_search_cache, list_indexed_sources, search, suggest_alternative_queries
from src.search_analytics import SearchAnalyticsDB

# Configure logging: file + stderr
_log_dir = Path(_project_root) / "data" / "logs"
_log_dir.mkdir(parents=True, exist_ok=True)
_file_handler = logging.handlers.RotatingFileHandler(
    _log_dir / "tessera.log",
    maxBytes=5 * 1024 * 1024,  # 5MB
    backupCount=3,
    encoding="utf-8",
)
_file_handler.setFormatter(
    logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
)
_file_handler.setLevel(logging.DEBUG)

_stderr_handler = logging.StreamHandler(sys.stderr)
_stderr_handler.setLevel(logging.WARNING)
_stderr_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))

logging.basicConfig(level=logging.DEBUG, handlers=[_file_handler, _stderr_handler])

logger = logging.getLogger(__name__)

# Search analytics (singleton)
_analytics = SearchAnalyticsDB()


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """Run auto-sync on server startup, then watch for file changes."""
    ctx = {}
    watcher = None

    if workspace.sync_auto:
        try:
            from src.graph.vector_store import OntologyVectorStore
            from src.ingestion.pipeline import IngestionPipeline
            from src.sync import FileMetaDB, run_incremental_sync

            meta_db = FileMetaDB(workspace.meta_db_path)
            vector_store = OntologyVectorStore()
            pipeline = IngestionPipeline(vector_store=vector_store)

            def _ingest(paths: list[Path]) -> tuple[int, dict[str, int]]:
                return pipeline.run(source_paths=paths)

            def _do_background_sync() -> None:
                """Run sync in background so server starts immediately."""
                try:
                    result = run_incremental_sync(
                        ws=workspace,
                        meta_db=meta_db,
                        vector_store_delete_fn=vector_store.delete_by_source,
                        ingest_fn=_ingest,
                    )
                    if result.has_changes:
                        invalidate_search_cache()
                    logger.info("Background auto-sync complete: %s", result.summary())
                except Exception as exc:
                    logger.warning("Background auto-sync failed: %s", exc)

            # Run sync in background thread — server starts immediately
            import asyncio

            loop = asyncio.get_event_loop()
            loop.run_in_executor(None, _do_background_sync)
            logger.info("Auto-sync started in background")

            ctx["meta_db"] = meta_db

            # Start file watcher for continuous auto-sync
            from src.file_watcher import FileWatcher

            def _on_file_change() -> None:
                """Callback: re-run incremental sync when files change."""
                try:
                    sync_result = run_incremental_sync(
                        ws=workspace,
                        meta_db=meta_db,
                        vector_store_delete_fn=vector_store.delete_by_source,
                        ingest_fn=_ingest,
                    )
                    if sync_result.has_changes:
                        invalidate_search_cache()
                        logger.info("File watcher sync: %s", sync_result.summary())
                except Exception as exc:
                    logger.warning("File watcher sync failed: %s", exc)

            watch_dirs = workspace.all_source_paths()
            watcher = FileWatcher(
                watch_dirs=watch_dirs,
                extensions=workspace.extensions,
                on_change=_on_file_change,
                poll_interval=workspace.watcher.poll_interval,
                debounce=workspace.watcher.debounce,
            )
            watcher.start()
            ctx["watcher"] = watcher
            logger.info("File watcher started for %d directories", len(watch_dirs))

        except Exception as exc:
            logger.warning("Auto-sync failed (non-fatal): %s", exc)

    try:
        yield ctx
    finally:
        if watcher:
            watcher.stop()
            logger.info("File watcher stopped")


mcp = FastMCP(
    name="tessera",
    lifespan=lifespan,
    instructions=(
        "Tessera provides semantic search across the user's local workspace documents "
        "and cross-session memory.\n\n"
        "## Auto-use rules\n"
        "When the user asks about topics that may be in their workspace, "
        "**call unified_search first** (searches documents AND memories together):\n"
        "- Project-related content (PRDs, specs, requirements)\n"
        "- Past decisions, meeting notes, session logs\n"
        "- Previously remembered facts or preferences\n\n"
        "## Memory\n"
        "- 'Remember this' → call remember\n"
        "- 'What did I say about...' → call recall\n"
        "- 'What have I saved?' → call list_memories\n"
        "- 'Forget that memory' → call forget_memory\n\n"
        "## Workspace management\n"
        "- Cleanup requests: call suggest_cleanup first, then organize_files after confirmation\n"
        "- Project status: call project_status automatically\n"
        "- Decision questions: call extract_decisions automatically\n"
        "- Server health: call tessera_status\n\n"
        "## Workflow\n"
        "1. Call unified_search with keywords from the user's question\n"
        "2. If results are insufficient, retry with different keywords or use search_documents\n"
        "3. Use read_file for full document contents when needed\n"
        "4. Answer based on search results, citing source document names\n"
    ),
)


# --- Existing Tools ---


@mcp.tool(
    description=(
        "Hybrid (semantic + keyword) search across indexed workspace documents "
        "(PRDs, decision logs, session logs, etc.). "
        "Call this tool first when the user asks about project-related content.\n\n"
        "Filter by project ID or doc_type (prd, session_log, decision_log, document)."
    )
)
def search_documents(
    query: str,
    top_k: int = 5,
    project: str | None = None,
    doc_type: str | None = None,
) -> str:
    """Search indexed documents with hybrid vector+keyword search."""
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
        return f"Search error: {exc}. Try running `ingest_documents` first."
    _elapsed = (_time.monotonic() - _t0) * 1000
    _analytics.log_query(query.strip(), top_k, len(results), _elapsed, project, doc_type, "search")

    if not results:
        msg = "No results found."
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
        if len(text) > text_limit:
            text = text[:text_limit] + "…"

        output_parts.append(f"{header}\n{text}")

    return "\n\n---\n\n".join(output_parts)


@mcp.tool(
    description=(
        "Return full contents of a file as a structured view. "
        "CSV → markdown table, XLSX → tables per sheet, MD → raw text, DOCX → paragraphs. "
        "Use when the user wants to see the complete file, not just search results."
    )
)
def view_file_full(file_path: str) -> str:
    """Return full contents of any supported file as structured text."""
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
    elif suffix == ".md":
        return read_file(str(p))
    elif suffix == ".docx":
        return read_file(str(p))
    else:
        return read_file(str(p))


@mcp.tool(description="List all indexed source files.")
def list_sources() -> str:
    """List all indexed source files."""
    sources = list_indexed_sources()

    if not sources:
        return "No indexed files. Try the `ingest_documents` tool to index your documents first."

    lines = [f"Indexed files ({len(sources)}):", ""]
    for s in sources:
        lines.append(f"  - {s}")

    return "\n".join(lines)


@mcp.tool(description="Read file contents by absolute path.")
def read_file(file_path: str) -> str:
    """Read file contents by path."""
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


# --- New Tools ---


@mcp.tool(
    description=(
        "Organize files in the workspace. "
        "action: 'move', 'archive', 'rename', 'list'. "
        "Always call suggest_cleanup first and get user confirmation before organizing."
    )
)
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


@mcp.tool(
    description=(
        "Generate cleanup suggestions for the workspace. "
        "Detects root-level files, backup files, large files, empty directories. "
        "Call this tool first when cleanup is requested."
    )
)
def suggest_cleanup(path: str | None = None) -> str:
    """Suggest cleanup actions for the workspace."""
    from src.organizer import suggest_organization

    return suggest_organization(path)


@mcp.tool(
    description=(
        "Get project status including HANDOFF.md, recent changes, and file statistics. "
        "Call automatically when asked about project status."
    )
)
def project_status(project_id: str | None = None) -> str:
    """Get project status. If no project_id, returns all projects summary."""
    from src.project_status import get_all_projects_summary, get_project_status

    if project_id:
        return get_project_status(project_id)
    return get_all_projects_summary()


@mcp.tool(
    description=(
        "Extract decisions from session logs and decision logs. "
        "Call automatically when asked about past decisions."
    )
)
def extract_decisions(project_id: str | None = None, since: str | None = None) -> str:
    """Extract decisions from session/decision logs."""
    from src.project_status import extract_decisions as _extract

    return _extract(project_id=project_id, since=since)


@mcp.tool(
    description=(
        "Audit a PRD file for quality and completeness against a 13-section structure. "
        "Checks section coverage, Mermaid syntax, wireframes, versioning, and changelog.\n\n"
        "check_sprawl=True: Detect multiple versions of the same PRD (suggest archiving old ones)\n"
        "check_consistency=True: Check cross-PRD consistency for period selectors and tiers"
    )
)
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


@mcp.tool(
    description=(
        "Save a piece of knowledge for cross-session persistence. "
        "Use this when the user says 'remember this' or when important decisions, "
        "preferences, or facts should be preserved across conversations."
    )
)
def remember(content: str, tags: list[str] | None = None) -> str:
    """Save a memory for cross-session persistence."""
    if not content or not content.strip():
        return "Please provide content to remember."
    from src.memory import learn_and_index

    result = learn_and_index(content.strip(), tags=tags, source="user-request")
    status = "indexed" if result["indexed"] else "saved (not yet indexed)"
    return f"Remembered and {status}:\n{content}"


@mcp.tool(
    description=(
        "Search past memories from previous sessions. "
        "Call this when the user asks 'what did I say about...', "
        "'do you remember...', or references past conversations."
    )
)
def recall(query: str, top_k: int = 5) -> str:
    """Search past memories using semantic similarity."""
    if not query or not query.strip():
        return "Please provide a search query."
    top_k = max(1, min(top_k, workspace.search.max_top_k))
    from src.memory import recall_memories

    memories = recall_memories(query.strip(), top_k=top_k)

    if not memories:
        return "No memories found. Nothing has been saved yet."

    parts = []
    for i, m in enumerate(memories, 1):
        sim = m["similarity"] * 100
        header = f"[{i}] (similarity: {sim:.1f}%)"
        if m["date"]:
            header += f"  date: {m['date']}"
        if m["tags"]:
            header += f"  tags: {m['tags']}"
        parts.append(f"{header}\n{m['content']}")

    return "\n\n---\n\n".join(parts)


@mcp.tool(
    description=(
        "Auto-learn: save new knowledge and immediately index it for search. "
        "Use this to capture insights, patterns, or facts discovered during conversation."
    )
)
def learn(content: str, tags: list[str] | None = None, source: str = "auto-learn") -> str:
    """Save and immediately index new knowledge."""
    if not content or not content.strip():
        return "Please provide content to learn."
    from src.memory import learn_and_index

    result = learn_and_index(content.strip(), tags=tags, source=source)
    status = "indexed" if result["indexed"] else "saved (indexing failed)"
    return f"Learned and {status}:\n{content}"


# --- Knowledge Graph Tools ---


@mcp.tool(
    description=(
        "Build a knowledge graph from indexed documents showing relationships "
        "between concepts, decisions, and entities. "
        "Returns a Mermaid diagram of the document relationships.\n\n"
        "scope: 'project' (single project) or 'all' (entire workspace)\n"
        "max_nodes: limit the number of nodes in the graph (default 30)"
    )
)
def knowledge_graph(
    query: str | None = None,
    project: str | None = None,
    scope: str = "all",
    max_nodes: int = 30,
) -> str:
    """Build and return a knowledge graph as Mermaid diagram."""
    from src.knowledge_graph import build_knowledge_graph

    kg = workspace.knowledge_graph
    max_nodes = max(1, min(max_nodes, kg.max_max_nodes))
    if scope not in ("all", "project"):
        scope = "all"
    return build_knowledge_graph(
        query=query, project=project, scope=scope, max_nodes=max_nodes
    )


@mcp.tool(
    description=(
        "Show connections for a specific document or concept in the knowledge graph. "
        "Returns related documents, shared topics, and a focused Mermaid subgraph."
    )
)
def explore_connections(query: str, top_k: int = 10) -> str:
    """Explore connections around a specific topic or document."""
    if not query or not query.strip():
        return "Please provide a topic or document name to explore."
    top_k = max(1, min(top_k, workspace.search.max_top_k))
    from src.knowledge_graph import explore_connections as _explore

    return _explore(query=query.strip(), top_k=top_k)


# --- Unified Search ---


@mcp.tool(
    description=(
        "Search across BOTH indexed documents AND past memories in one call. "
        "Returns combined results ranked by similarity. "
        "Use this instead of calling search_documents + recall separately."
    )
)
def unified_search(
    query: str,
    top_k: int = 5,
    project: str | None = None,
    doc_type: str | None = None,
) -> str:
    """Search documents and memories together."""
    if not query or not query.strip():
        return "Please provide a search query."
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
            text = r["text"][:text_limit] + "…" if len(r["text"]) > text_limit else r["text"]
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
    _analytics.log_query(query, top_k, len(doc_results) + mem_count, _elapsed, project, doc_type, "unified")

    if not parts:
        return "No results found in documents or memories."

    return "\n\n---\n\n".join(parts)


# --- Indexing Tools ---


@mcp.tool(
    description=(
        "Index (or re-index) all workspace documents into the vector store. "
        "Run this when setting up Tessera for the first time, or when you want to "
        "rebuild the entire index from scratch. "
        "Optionally pass specific directory paths to index only those."
    )
)
def ingest_documents(paths: list[str] | None = None) -> str:
    """Full ingestion of workspace documents."""
    from src.graph.vector_store import OntologyVectorStore
    from src.ingestion.pipeline import IngestionPipeline

    vector_store = OntologyVectorStore()
    pipeline = IngestionPipeline(vector_store=vector_store)

    source_paths = [Path(p) for p in paths] if paths else None
    count, per_file = pipeline.run(source_paths=source_paths)
    invalidate_search_cache()

    return (
        f"Indexing complete: {count} documents from {len(per_file)} files.\n"
        f"You can now use search_documents to search across them."
    )


@mcp.tool(
    description=(
        "Incrementally sync the index with your workspace. "
        "Only processes new, changed, or deleted files since the last sync. "
        "Much faster than full ingestion. Run this when you've updated some documents."
    )
)
def sync_documents() -> str:
    """Incremental sync — only new/changed/deleted files."""
    from src.graph.vector_store import OntologyVectorStore
    from src.ingestion.pipeline import IngestionPipeline
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


@mcp.tool(
    description=(
        "Show Tessera server health: tracked files, sync history, "
        "index size, cache stats, and watcher status. "
        "Call this when asked about server status or troubleshooting."
    )
)
def tessera_status() -> str:
    """Return server health and operational status."""
    from src.embedding import embed_query
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
    from src.search import _search_cache

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


@mcp.tool(
    description=(
        "List saved memories with optional filtering. "
        "Use to browse what Tessera has remembered across sessions."
    )
)
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


@mcp.tool(
    description=(
        "Delete a specific memory by filename (without .md extension). "
        "Use list_memories first to find the memory to delete."
    )
)
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


@mcp.tool(
    description=(
        "Check for stale/outdated documents that haven't been modified recently. "
        "Returns a list grouped by project showing file names and days since last update. "
        "Use this proactively to suggest document reviews."
    )
)
def check_document_freshness(days_threshold: int = 90) -> str:
    """Check for stale documents exceeding the age threshold."""
    days_threshold = max(1, min(days_threshold, 365))
    from src.freshness import freshness_summary

    return freshness_summary(days_threshold=days_threshold)


@mcp.tool(
    description=(
        "Run a comprehensive health check on the Tessera workspace. "
        "Checks: config validity, dependencies, index status, stale documents, "
        "zero-result query patterns. Returns actionable recommendations."
    )
)
def health_check() -> str:
    """Run workspace health diagnostics."""
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
        stats = _analytics.get_stats(days=30)
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


@mcp.tool(
    description=(
        "Show search usage analytics: total queries, top queries, zero-result queries, "
        "response times, and daily trends. Use for understanding search patterns."
    )
)
def search_analytics(days: int = 30) -> str:
    """Return search analytics summary."""
    days = max(1, min(days, 365))
    stats = _analytics.get_stats(days=days)

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


@mcp.tool(
    description=(
        "Export all saved memories as JSON for backup or transfer. "
        "Returns a JSON string with all memories and their metadata."
    )
)
def export_memories() -> str:
    """Export all memories as JSON."""
    from src.memory import export_memories as _export

    data = _export(format="json")
    count = data.count('"content"')
    return f"Exported {count} memories:\n\n{data}"


@mcp.tool(
    description=(
        "Import memories from a JSON string (batch import). "
        "Format: [{\"content\": \"...\", \"tags\": [\"...\"], \"source\": \"...\"}]. "
        "Use export_memories to get the expected format."
    )
)
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


@mcp.tool(
    description=(
        "Find documents similar to a given document. "
        "Returns related documents ranked by similarity. "
        "Use this when users ask 'what else is related to this document'."
    )
)
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


@mcp.tool(
    description=(
        "List all unique tags across saved memories with their counts. "
        "Useful for browsing memory categories."
    )
)
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


@mcp.tool(
    description=(
        "Search memories by a specific tag. "
        "Use memory_tags first to see available tags."
    )
)
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


# --- MCP Resources ---


@mcp.resource("docs://index")
def document_index() -> str:
    """Provide a browsable index of all indexed documents."""
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


@mcp.resource("workspace://status")
def workspace_status() -> str:
    """Provide current workspace status across all projects."""
    from src.project_status import get_all_projects_summary

    return get_all_projects_summary()


if __name__ == "__main__":
    mcp.run()
