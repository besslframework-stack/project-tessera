"""Tessera MCP server — exposes document search tools to Claude Desktop."""

from __future__ import annotations

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
from src.search import invalidate_search_cache

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
    logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
)
_file_handler.setLevel(logging.DEBUG)

_stderr_handler = logging.StreamHandler(sys.stderr)
_stderr_handler.setLevel(logging.WARNING)
_stderr_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))

logging.basicConfig(level=logging.DEBUG, handlers=[_file_handler, _stderr_handler])

logger = logging.getLogger(__name__)

from src.search import search  # noqa: E402  — kept so tests can patch mcp_server.search

from src import core  # noqa: E402


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

        # Save session summary on shutdown
        try:
            from src.interaction_log import SESSION_ID
            from src.session_summary import save_session_summary

            il = core._get_interaction_log()
            interactions = il.get_session_interactions(SESSION_ID, limit=200)
            if interactions:
                result = save_session_summary(SESSION_ID, interactions)
                if result:
                    logger.info("Session summary saved: %s", result["file_path"])
        except Exception as exc:
            logger.debug("Session summary failed (non-fatal): %s", exc)


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


# --- Tools (thin wrappers delegating to core) ---


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
    # Sync the module-level `search` reference so tests patching
    # ``mcp_server.search`` propagate into core.
    core.search = search
    return core.search_documents(query, top_k=top_k, project=project, doc_type=doc_type)


@mcp.tool(
    description=(
        "Return full contents of a file as a structured view. "
        "CSV → markdown table, XLSX → tables per sheet, MD → raw text, DOCX → paragraphs. "
        "Use when the user wants to see the complete file, not just search results."
    )
)
def view_file_full(file_path: str) -> str:
    """Return full contents of any supported file as structured text."""
    return core.view_file_full(file_path)


@mcp.tool(description="List all indexed source files.")
def list_sources() -> str:
    """List all indexed source files."""
    return core.list_sources()


@mcp.tool(description="Read file contents by absolute path.")
def read_file(file_path: str) -> str:
    """Read file contents by path."""
    return core.read_file(file_path)


# TODO: Remove?
# @mcp.tool(
#     description=(
#         "Get project status including HANDOFF.md, recent changes, and file statistics. "
#         "Call automatically when asked about project status."
#     )
# )
def project_status(project_id: str | None = None) -> str:
    """Get project status. If no project_id, returns all projects summary."""
    return core.project_status(project_id)


# TODO: Remove?
# @mcp.tool(
#     description=(
#         "Audit a PRD file for quality and completeness against a 13-section structure. "
#         "Checks section coverage, Mermaid syntax, wireframes, versioning, and changelog.\n\n"
#         "check_sprawl=True: Detect multiple versions of the same PRD (suggest archiving old ones)\n"
#         "check_consistency=True: Check cross-PRD consistency for period selectors and tiers"
#     )
# )
def audit_prd(
    file_path: str,
    check_sprawl: bool = False,
    check_consistency: bool = False,
) -> str:
    """Audit a PRD file for quality and completeness."""
    return core.audit_prd(file_path, check_sprawl=check_sprawl, check_consistency=check_consistency)


# --- Memory Tools ---


# --- Knowledge Graph Tools ---


# TODO: Remove?
# @mcp.tool(
#     description=(
#         "Build a knowledge graph from indexed documents showing relationships "
#         "between concepts, decisions, and entities. "
#         "Returns a Mermaid diagram of the document relationships.\n\n"
#         "scope: 'project' (single project) or 'all' (entire workspace)\n"
#         "max_nodes: limit the number of nodes in the graph (default 30)"
#     )
# )
# def knowledge_graph(
#     query: str | None = None,
#     project: str | None = None,
#     scope: str = "all",
#     max_nodes: int = 30,
# ) -> str:
#     """Build and return a knowledge graph as Mermaid diagram."""
#     return core.knowledge_graph(query=query, project=project, scope=scope, max_nodes=max_nodes)
#
#
# @mcp.tool(
#     description=(
#         "Show connections for a specific document or concept in the knowledge graph. "
#         "Returns related documents, shared topics, and a focused Mermaid subgraph."
#     )
# )
# def explore_connections(query: str, top_k: int = 10) -> str:
#     """Explore connections around a specific topic or document."""
#     return core.explore_connections(query, top_k=top_k)


# --- Unified Search ---


# --- Indexing Tools ---


# --- Operations Tools ---


# --- Freshness Tools ---


# --- Analytics Tools ---

# --- Batch Memory Tools ---


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
    return core.find_similar(source_path, top_k=top_k)


# --- Tag Tools ---


# --- MCP Resources ---


# TODO: Remove?
# @mcp.resource("docs://index")
# def document_index() -> str:
#     """Provide a browsable index of all indexed documents."""
#     return core.document_index()
#
#
# @mcp.resource("workspace://status")
# def workspace_status() -> str:
#     """Provide current workspace status across all projects."""
#     return core.workspace_status()


# --- Auto-Learn Tools ---


# --- Interaction Log Tools ---


def main() -> None:
    """Entry point for the MCP server."""
    mcp.run(
        transport="streamable-http",
    )


if __name__ == "__main__":
    main()
