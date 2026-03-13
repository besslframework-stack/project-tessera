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
    _get_analytics().log_query(
        query.strip(), top_k, len(results), _elapsed, project, doc_type, "search"
    )
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


def project_status(project_id: str | None = None) -> str:
    """Get project status. If no project_id, returns all projects summary."""
    from src.project_status import get_all_projects_summary, get_project_status

    if project_id:
        return get_project_status(project_id)
    return get_all_projects_summary()


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
    return build_knowledge_graph(query=query, project=project, scope=scope, max_nodes=max_nodes)


def explore_connections(query: str, top_k: int = 10) -> str:
    """Explore connections around a specific topic or document."""
    if not query or not query.strip():
        return "Please provide a topic or document name to explore."
    from src.config import workspace
    from src.knowledge_graph import explore_connections as _explore

    top_k = max(1, min(top_k, workspace.search.max_top_k))

    return _explore(query=query.strip(), top_k=top_k)


# --- Unified Search ---


# --- Indexing Tools ---


# --- Operations Tools ---


# --- Freshness Tools ---


# --- Analytics Tools ---


# --- Batch Memory Tools ---


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


# --- MCP Resources ---


# --- Auto-Learn Tools ---


# --- Interaction Log Tools ---
