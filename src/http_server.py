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

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Tessera API",
    description="Personal Knowledge Layer for AI — REST API",
    version="0.8.3",
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


class RememberRequest(BaseModel):
    content: str
    tags: list[str] | None = None


class RecallRequest(BaseModel):
    query: str
    top_k: int = 5
    since: str | None = None
    until: str | None = None
    category: str | None = None


class LearnRequest(BaseModel):
    content: str
    tags: list[str] | None = None


class ContextWindowRequest(BaseModel):
    query: str
    token_budget: int = 4000
    include_documents: bool = True


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
# Entry point
# ---------------------------------------------------------------------------

def main():
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8394)


if __name__ == "__main__":
    main()
