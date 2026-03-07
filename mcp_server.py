"""Tessera MCP server — exposes document search tools to Claude Desktop."""

from __future__ import annotations

import json
import logging
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
from src.search import list_indexed_sources, search

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """Run auto-sync on server startup."""
    ctx = {}
    if workspace.sync_auto:
        try:
            from llama_index.embeddings.ollama import OllamaEmbedding

            from src.graph.vector_store import OntologyVectorStore
            from src.ingestion.pipeline import IngestionPipeline
            from src.sync import FileMetaDB, run_incremental_sync

            meta_db = FileMetaDB(workspace.meta_db_path)
            embed_model = OllamaEmbedding(
                model_name=workspace.embed_model,
                base_url=workspace.ollama_base_url,
            )
            vector_store = OntologyVectorStore(embed_model=embed_model)
            pipeline = IngestionPipeline(vector_store=vector_store)

            def _ingest(paths: list[Path]) -> tuple[int, dict[str, int]]:
                return pipeline.run(source_paths=paths)

            result = run_incremental_sync(
                ws=workspace,
                meta_db=meta_db,
                vector_store_delete_fn=vector_store.delete_by_source,
                ingest_fn=_ingest,
            )
            logger.info("Auto-sync complete: %s", result.summary())
            ctx["meta_db"] = meta_db
        except Exception as exc:
            logger.warning("Auto-sync failed (non-fatal): %s", exc)

    yield ctx


mcp = FastMCP(
    name="tessera",
    lifespan=lifespan,
    instructions=(
        "This server provides access to the user's local workspace documents.\n\n"
        "## Auto-use rules\n"
        "When the user asks about topics that may be in their indexed documents, "
        "**call search_documents first** before answering:\n"
        "- Project-related content (PRDs, specs, requirements)\n"
        "- Past decisions, meeting notes, session logs\n"
        "- Feature specs, wireframes, data requirements\n\n"
        "## Workspace management\n"
        "- Cleanup requests: call suggest_cleanup first, then organize_files after user confirmation\n"
        "- Project status questions: call project_status automatically\n"
        "- Decision questions: call extract_decisions automatically\n\n"
        "## Workflow\n"
        "1. Extract keywords from user's question and call search_documents\n"
        "2. If results are insufficient, retry with different keywords\n"
        "3. Use read_file for full document contents when needed\n"
        "4. Answer based on search results\n\n"
        "Always cite source document names in your answers."
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
    results = search(query, top_k=top_k, project=project, doc_type=doc_type)

    if not results:
        return "No results found. Run `python main.py ingest` to index documents first."

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
        if len(text) > 1500:
            text = text[:1500] + "…"

        output_parts.append(f"{header}\n{text}")

    return "\n\n---\n\n".join(output_parts)


@mcp.tool(description="List all indexed source files.")
def list_sources() -> str:
    """List all indexed source files."""
    sources = list_indexed_sources()

    if not sources:
        return "No indexed files. Run `python main.py ingest` to index documents first."

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

    if len(content) > 50000:
        content = content[:50000] + "\n\n… (50,000자에서 잘림)"

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
            output += "\n\n## 버전 스프롤 감지"
            for s in sprawl:
                output += f"\n\n{s['base_name']}:"
                for v in s["versions"]:
                    marker = " ← 최신" if v["path"] == s["latest"] else " ← 아카이브 후보"
                    output += f"\n  v{v['version']}: {Path(v['path']).name}{marker}"
        else:
            output += "\n\n버전 스프롤 없음."

    if check_consistency:
        parent = Path(file_path).parent
        issues = audit_cross_prd_consistency(parent)
        if issues:
            output += "\n\n## 일관성 이슈"
            for issue in issues:
                output += f"\n  - {issue}"
        else:
            output += "\n\nPRD 간 일관성 이슈 없음."

    return output


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
