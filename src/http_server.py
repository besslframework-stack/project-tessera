"""HTTP API server for Tessera — enables ChatGPT, Gemini, extensions to use Tessera.

FastAPI-based REST API exposing the same core.py functions as the MCP server.
Run with: uvicorn src.http_server:app --port 8394
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from pydantic import BaseModel

from src import core
from src.api_auth import init_auth, is_auth_required, validate_key
from src.chatgpt_actions import get_gpt_instructions, get_openapi_spec, get_setup_guide

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Tessera API",
    description="Personal Knowledge Layer for AI — REST API",
    version="1.4.0",
    openapi_tags=[
        {"name": "search", "description": "Document and memory search"},
        {"name": "memory", "description": "Cross-session memory management"},
        {"name": "intelligence", "description": "Proactive knowledge intelligence"},
        {"name": "workspace", "description": "Workspace management and diagnostics"},
    ],
)

# CORS — allow local and common AI tool origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:*",
        "http://127.0.0.1:*",
        "https://chat.openai.com",
        "https://chatgpt.com",
        "https://gemini.google.com",
        "https://claude.ai",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize auth on import
init_auth()

# API key header (optional — only enforced when TESSERA_API_KEY is set)
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str | None = Depends(_api_key_header)):
    """Verify API key if auth is required."""
    if not is_auth_required():
        return  # No auth needed
    if not api_key or not validate_key(api_key):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


# ---------------------------------------------------------------------------
# Request/Response models
# ---------------------------------------------------------------------------

class SearchRequest(BaseModel):
    query: str
    top_k: int = 5

    @classmethod
    def __init_subclass__(cls, **kwargs): ...

    model_config = {"str_max_length": 2000}


class RememberRequest(BaseModel):
    content: str
    tags: list[str] | None = None

    model_config = {"str_max_length": 10000}


class RecallRequest(BaseModel):
    query: str
    top_k: int = 5
    since: str | None = None
    until: str | None = None
    category: str | None = None
    include_superseded: bool = False

    model_config = {"str_max_length": 2000}


class LearnRequest(BaseModel):
    content: str
    tags: list[str] | None = None

    model_config = {"str_max_length": 10000}


class ContextWindowRequest(BaseModel):
    query: str
    token_budget: int = 4000
    include_documents: bool = True

    model_config = {"str_max_length": 2000}


class ApiResponse(BaseModel):
    status: str = "ok"
    data: Any = None


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok", "service": "tessera"}


@app.get("/version")
def version():
    try:
        from importlib.metadata import version as pkg_version
        v = pkg_version("project-tessera")
    except Exception:
        v = "dev"
    return {"version": v}


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

@app.post("/search", response_model=ApiResponse, dependencies=[Depends(verify_api_key)])
def search_documents(req: SearchRequest):
    result = core.search_documents(req.query, req.top_k)
    return ApiResponse(data=result)


@app.post("/unified-search", response_model=ApiResponse, dependencies=[Depends(verify_api_key)])
def unified_search(req: SearchRequest):
    result = core.unified_search(req.query, req.top_k)
    return ApiResponse(data=result)


# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------

@app.post("/remember", response_model=ApiResponse, dependencies=[Depends(verify_api_key)])
def remember(req: RememberRequest):
    result = core.remember(req.content, req.tags)
    return ApiResponse(data=result)


@app.post("/recall", response_model=ApiResponse, dependencies=[Depends(verify_api_key)])
def recall(req: RecallRequest):
    result = core.recall(
        req.query, req.top_k,
        since=req.since, until=req.until, category=req.category,
        include_superseded=req.include_superseded,
    )
    return ApiResponse(data=result)


@app.post("/learn", response_model=ApiResponse, dependencies=[Depends(verify_api_key)])
def learn(req: LearnRequest):
    result = core.learn(req.content, req.tags)
    return ApiResponse(data=result)


@app.get("/memories", response_model=ApiResponse, dependencies=[Depends(verify_api_key)])
def list_memories(limit: int = Query(default=20, ge=1, le=100)):
    result = core.list_memories(limit)
    return ApiResponse(data=result)


@app.delete("/memories/{memory_id}", response_model=ApiResponse, dependencies=[Depends(verify_api_key)])
def forget_memory(memory_id: str):
    result = core.forget_memory(memory_id)
    return ApiResponse(data=result)


@app.get("/memories/categories", response_model=ApiResponse, dependencies=[Depends(verify_api_key)])
def memory_categories():
    result = core.memory_categories()
    return ApiResponse(data=result)


@app.get("/memories/search-by-category", response_model=ApiResponse, dependencies=[Depends(verify_api_key)])
def search_by_category(category: str = Query(...)):
    result = core.search_by_category(category)
    return ApiResponse(data=result)


@app.get("/memories/tags", response_model=ApiResponse, dependencies=[Depends(verify_api_key)])
def memory_tags():
    result = core.memory_tags()
    return ApiResponse(data=result)


@app.get("/memories/search-by-tag", response_model=ApiResponse, dependencies=[Depends(verify_api_key)])
def search_by_tag(tag: str = Query(...)):
    result = core.search_by_tag(tag)
    return ApiResponse(data=result)


# ---------------------------------------------------------------------------
# Intelligence
# ---------------------------------------------------------------------------

@app.post("/context-window", response_model=ApiResponse, dependencies=[Depends(verify_api_key)])
def context_window(req: ContextWindowRequest):
    result = core.context_window(req.query, req.token_budget, req.include_documents)
    return ApiResponse(data=result)


@app.get("/decision-timeline", response_model=ApiResponse, dependencies=[Depends(verify_api_key)])
def decision_timeline():
    result = core.decision_timeline()
    return ApiResponse(data=result)


@app.get("/smart-suggest", response_model=ApiResponse, dependencies=[Depends(verify_api_key)])
def smart_suggest(max_suggestions: int = Query(default=5, ge=1, le=20)):
    result = core.smart_suggest(max_suggestions)
    return ApiResponse(data=result)


@app.get("/topic-map", response_model=ApiResponse, dependencies=[Depends(verify_api_key)])
def topic_map(output_format: str = Query(default="text")):
    result = core.topic_map(output_format)
    return ApiResponse(data=result)


@app.get("/knowledge-stats", response_model=ApiResponse, dependencies=[Depends(verify_api_key)])
def knowledge_stats():
    result = core.knowledge_stats()
    return ApiResponse(data=result)


# ---------------------------------------------------------------------------
# Batch
# ---------------------------------------------------------------------------

class BatchOperation(BaseModel):
    method: str  # "search", "remember", "recall", "learn", "context_window"
    params: dict = {}


class BatchRequest(BaseModel):
    operations: list[BatchOperation]


@app.post("/batch", response_model=ApiResponse, dependencies=[Depends(verify_api_key)])
def batch(req: BatchRequest):
    """Execute multiple operations in a single request."""
    _BATCH_HANDLERS = {
        "search": lambda p: core.search_documents(p.get("query", ""), p.get("top_k", 5)),
        "unified_search": lambda p: core.unified_search(p.get("query", ""), p.get("top_k", 5)),
        "remember": lambda p: core.remember(p.get("content", ""), p.get("tags")),
        "recall": lambda p: core.recall(
            p.get("query", ""), p.get("top_k", 5),
            since=p.get("since"), until=p.get("until"), category=p.get("category"),
        ),
        "learn": lambda p: core.learn(p.get("content", ""), p.get("tags")),
        "context_window": lambda p: core.context_window(
            p.get("query", ""), p.get("token_budget", 4000), p.get("include_documents", True),
        ),
        "decision_timeline": lambda p: core.decision_timeline(),
        "smart_suggest": lambda p: core.smart_suggest(p.get("max_suggestions", 5)),
        "topic_map": lambda p: core.topic_map(p.get("output_format", "text")),
        "knowledge_stats": lambda p: core.knowledge_stats(),
    }

    results = []
    for op in req.operations[:20]:  # Max 20 operations per batch
        handler = _BATCH_HANDLERS.get(op.method)
        if handler is None:
            results.append({"method": op.method, "status": "error", "data": f"Unknown method: {op.method}"})
            continue
        try:
            data = handler(op.params)
            results.append({"method": op.method, "status": "ok", "data": data})
        except Exception as e:
            results.append({"method": op.method, "status": "error", "data": str(e)})

    return ApiResponse(data=results)


# ---------------------------------------------------------------------------
# Workspace
# ---------------------------------------------------------------------------

@app.get("/export", response_model=ApiResponse, dependencies=[Depends(verify_api_key)])
def export_knowledge(format: str = Query(default="markdown")):
    result = core.export_knowledge(format)
    return ApiResponse(data=result)


class ImportConversationsRequest(BaseModel):
    data: str
    source: str = "chatgpt"


class ImportFromAIRequest(BaseModel):
    data: str
    source: str = "chatgpt"


@app.get("/export-for-ai", response_model=ApiResponse, dependencies=[Depends(verify_api_key)])
def export_for_ai(target: str = Query(default="chatgpt")):
    result = core.export_for_ai(target)
    return ApiResponse(data=result)


@app.post("/import-from-ai", response_model=ApiResponse, dependencies=[Depends(verify_api_key)])
def import_from_ai(req: ImportFromAIRequest):
    result = core.import_from_ai(req.data, req.source)
    return ApiResponse(data=result)


@app.post("/import-conversations", response_model=ApiResponse, dependencies=[Depends(verify_api_key)])
def import_conversations(req: ImportConversationsRequest):
    result = core.import_conversations(req.data, req.source)
    return ApiResponse(data=result)


@app.post("/migrate", response_model=ApiResponse, dependencies=[Depends(verify_api_key)])
def migrate_data(dry_run: bool = Query(default=False)):
    result = core.migrate_data(dry_run)
    return ApiResponse(data=result)


@app.get("/vault-status", response_model=ApiResponse, dependencies=[Depends(verify_api_key)])
def vault_status_endpoint():
    result = core.vault_status_info()
    return ApiResponse(data=result)


@app.get("/user-profile", response_model=ApiResponse, dependencies=[Depends(verify_api_key)])
def user_profile():
    result = core.user_profile()
    return ApiResponse(data=result)


@app.get("/status", response_model=ApiResponse, dependencies=[Depends(verify_api_key)])
def tessera_status():
    result = core.tessera_status()
    return ApiResponse(data=result)


@app.get("/health-check", response_model=ApiResponse, dependencies=[Depends(verify_api_key)])
def health_check():
    result = core.health_check()
    return ApiResponse(data=result)


# ---------------------------------------------------------------------------
# Insight Phase (v1.1.0)
# ---------------------------------------------------------------------------


class DeepSearchRequest(BaseModel):
    query: str
    top_k: int = 5
    project: str | None = None
    doc_type: str | None = None


class DeepRecallRequest(BaseModel):
    query: str
    top_k: int = 5
    since: str | None = None
    until: str | None = None
    category: str | None = None


@app.post("/deep-search", response_model=ApiResponse, tags=["search"], dependencies=[Depends(verify_api_key)])
def deep_search_endpoint(req: DeepSearchRequest):
    result = core.multi_angle_search_documents(req.query, top_k=req.top_k, project=req.project, doc_type=req.doc_type)
    return ApiResponse(data=result)


@app.post("/deep-recall", response_model=ApiResponse, tags=["memory"], dependencies=[Depends(verify_api_key)])
def deep_recall_endpoint(req: DeepRecallRequest):
    result = core.multi_angle_recall(req.query, top_k=req.top_k, since=req.since, until=req.until, category=req.category)
    return ApiResponse(data=result)


@app.get("/memory-confidence", response_model=ApiResponse, tags=["intelligence"], dependencies=[Depends(verify_api_key)])
def memory_confidence_endpoint():
    result = core.memory_confidence()
    return ApiResponse(data=result)


@app.get("/memory-health", response_model=ApiResponse, tags=["intelligence"], dependencies=[Depends(verify_api_key)])
def memory_health_endpoint():
    result = core.memory_health()
    return ApiResponse(data=result)


@app.get("/hooks", response_model=ApiResponse, tags=["workspace"], dependencies=[Depends(verify_api_key)])
def hooks_endpoint():
    result = core.list_plugin_hooks()
    return ApiResponse(data=result)


@app.get("/contradictions", response_model=ApiResponse, tags=["intelligence"], dependencies=[Depends(verify_api_key)])
def contradictions_endpoint():
    result = core.detect_contradictions()
    return ApiResponse(data=result)


@app.get("/entity-search", response_model=ApiResponse, tags=["intelligence"], dependencies=[Depends(verify_api_key)])
def entity_search_endpoint(query: str = Query(...), limit: int = Query(default=10, ge=1, le=50)):
    result = core.entity_search(query, limit)
    return ApiResponse(data=result)


class EntityGraphRequest(BaseModel):
    query: str | None = None
    max_nodes: int = 30


@app.post("/entity-graph", response_model=ApiResponse, tags=["intelligence"], dependencies=[Depends(verify_api_key)])
def entity_graph_endpoint(req: EntityGraphRequest):
    result = core.entity_graph(req.query, req.max_nodes)
    return ApiResponse(data=result)


@app.get("/consolidation-candidates", response_model=ApiResponse, tags=["intelligence"], dependencies=[Depends(verify_api_key)])
def consolidation_candidates_endpoint(
    threshold: float = Query(default=0.85, ge=0.5, le=0.99),
    max_clusters: int = Query(default=20, ge=1, le=50),
):
    result = core.find_consolidation_candidates(threshold, max_clusters)
    return ApiResponse(data=result)


@app.post("/consolidate", response_model=ApiResponse, tags=["intelligence"], dependencies=[Depends(verify_api_key)])
def consolidate_endpoint(
    cluster_index: int = Query(default=1, ge=1),
    threshold: float = Query(default=0.85, ge=0.5, le=0.99),
):
    result = core.consolidate_memories(cluster_index, threshold)
    return ApiResponse(data=result)


# ---------------------------------------------------------------------------
# Phase 8: Cortex II
# ---------------------------------------------------------------------------


@app.post("/sleep-consolidate", response_model=ApiResponse, tags=["intelligence"], dependencies=[Depends(verify_api_key)])
def sleep_consolidate_endpoint():
    result = core.sleep_consolidate()
    return ApiResponse(data=result)


class RetentionPolicyRequest(BaseModel):
    max_age_days: int = 180
    min_confidence: float = 0.3
    dry_run: bool = True


@app.post("/retention-policy", response_model=ApiResponse, tags=["intelligence"], dependencies=[Depends(verify_api_key)])
def retention_policy_endpoint(
    max_age_days: int = Query(default=180, ge=1, le=3650),
    min_confidence: float = Query(default=0.3, ge=0.0, le=1.0),
    dry_run: bool = Query(default=True),
):
    result = core.retention_policy(max_age_days, min_confidence, dry_run)
    return ApiResponse(data=result)


@app.get("/retention-summary", response_model=ApiResponse, tags=["intelligence"], dependencies=[Depends(verify_api_key)])
def retention_summary_endpoint():
    result = core.retention_summary()
    return ApiResponse(data=result)


@app.get("/adapters/{framework}", response_model=ApiResponse, tags=["workspace"], dependencies=[Depends(verify_api_key)])
def adapters_endpoint(framework: str):
    result = core.get_agent_adapter(framework)
    return ApiResponse(data=result)


@app.post("/auto-curate", response_model=ApiResponse, tags=["intelligence"], dependencies=[Depends(verify_api_key)])
def auto_curate_endpoint():
    result = core.auto_curate()
    return ApiResponse(data=result)


# ---------------------------------------------------------------------------
# ChatGPT Custom GPT Actions
# ---------------------------------------------------------------------------

@app.get("/chatgpt-actions/openapi.json", tags=["workspace"])
def chatgpt_openapi(server_url: str = Query(default=None)):
    """Serve OpenAPI spec for ChatGPT Custom GPT Actions.

    Pass ?server_url=https://your-tunnel.ngrok-free.app to set the server URL.
    Defaults to the current request's base URL.
    """
    from starlette.responses import JSONResponse
    if not server_url:
        server_url = "http://localhost:8394"
    spec = get_openapi_spec(server_url)
    return JSONResponse(content=spec, headers={"Access-Control-Allow-Origin": "*"})


@app.get("/chatgpt-actions/instructions", tags=["workspace"])
def chatgpt_instructions():
    """Return the GPT instruction template to paste into your Custom GPT."""
    return {"instructions": get_gpt_instructions()}


@app.get("/chatgpt-actions/setup", tags=["workspace"])
def chatgpt_setup(tunnel_url: str = Query(default=None)):
    """Return the full setup guide for connecting ChatGPT to Tessera."""
    return {"guide": get_setup_guide(tunnel_url)}


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@app.get("/dashboard", tags=["workspace"], include_in_schema=False)
def dashboard():
    """Web dashboard — visual overview of Tessera's knowledge state."""
    from starlette.responses import HTMLResponse

    from src.dashboard import render_dashboard

    stats = _gather_dashboard_stats()
    html = render_dashboard(stats)
    return HTMLResponse(content=html)


def _gather_dashboard_stats() -> dict:
    """Collect stats from various core modules for the dashboard."""
    stats: dict = {"version": "dev"}

    # Version
    try:
        from importlib.metadata import version as pkg_version
        stats["version"] = pkg_version("project-tessera")
    except Exception:
        pass

    # Memory count
    try:
        from src.memory import _memory_dir
        mem_dir = _memory_dir()
        stats["memory_count"] = len(list(mem_dir.glob("*.md")))
    except Exception:
        stats["memory_count"] = 0

    # Entity count
    try:
        from src.entity_store import EntityStore
        store = EntityStore()
        stats["entity_count"] = store.entity_count()
        stats["relationship_count"] = store.relationship_count()
    except Exception:
        stats["entity_count"] = 0
        stats["relationship_count"] = 0

    # Health score
    try:
        health_text = core.memory_health()
        # Extract score from text like "Health Score: 85/100"
        import re
        m = re.search(r"(?:score|Score)[:\s]+(\d+)", health_text)
        stats["health_score"] = f"{m.group(1)}/100" if m else "—"
    except Exception:
        stats["health_score"] = "—"

    # Contradictions
    try:
        contra_text = core.detect_contradictions()
        import re
        m = re.search(r"(\d+)\s+contradiction", contra_text)
        stats["contradiction_count"] = int(m.group(1)) if m else 0
    except Exception:
        stats["contradiction_count"] = 0

    # Consolidation clusters
    try:
        from src.consolidation import find_similar_clusters
        clusters = find_similar_clusters(threshold=0.85, max_clusters=10)
        stats["cluster_count"] = len(clusters)
    except Exception:
        stats["cluster_count"] = 0

    # Recent memories
    try:
        memories_text = core.list_memories(10)
        # Parse the text output into structured data
        stats["recent_memories"] = _parse_memories_text(memories_text)
    except Exception:
        stats["recent_memories"] = []

    # Entity graph mermaid
    try:
        graph_text = core.entity_graph(max_nodes=20)
        import re
        m = re.search(r"```mermaid\n(.*?)```", graph_text, re.DOTALL)
        stats["entity_graph_mermaid"] = m.group(1).strip() if m else ""
    except Exception:
        stats["entity_graph_mermaid"] = ""

    return stats


def _parse_memories_text(text: str) -> list[dict]:
    """Parse the text output from list_memories into structured dicts."""
    if not text or "no memories" in text.lower():
        return []

    memories = []
    for block in text.split("\n\n---\n\n"):
        block = block.strip()
        if not block:
            continue
        lines = block.split("\n", 1)
        header = lines[0] if lines else ""
        content = lines[1].strip() if len(lines) > 1 else ""

        import re
        date_m = re.search(r"date:\s*(\S+)", header)
        cat_m = re.search(r"\[([a-zA-Z]\w+)\]", header)
        tags_m = re.search(r"tags:\s*(.+?)(?:\s*$|\s+date:)", header)

        memories.append({
            "date": date_m.group(1) if date_m else "",
            "category": cat_m.group(1) if cat_m else "",
            "tags": tags_m.group(1).strip() if tags_m else "",
            "content": content[:200],
        })

    return memories


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8394)


if __name__ == "__main__":
    main()
