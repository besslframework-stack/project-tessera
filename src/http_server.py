"""HTTP API server for Tessera — enables ChatGPT, Gemini, extensions to use Tessera.

FastAPI-based REST API exposing the same core.py functions as the MCP server.
Run with: uvicorn src.http_server:app --port 8394
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from src import core

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Tessera API",
    description="Personal Knowledge Layer for AI — REST API",
    version="0.8.1",
)


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

@app.post("/search", response_model=ApiResponse)
def search_documents(req: SearchRequest):
    result = core.search_documents(req.query, req.top_k)
    return ApiResponse(data=result)


@app.post("/unified-search", response_model=ApiResponse)
def unified_search(req: SearchRequest):
    result = core.unified_search(req.query, req.top_k)
    return ApiResponse(data=result)


# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------

@app.post("/remember", response_model=ApiResponse)
def remember(req: RememberRequest):
    result = core.remember(req.content, req.tags)
    return ApiResponse(data=result)


@app.post("/recall", response_model=ApiResponse)
def recall(req: RecallRequest):
    result = core.recall(
        req.query, req.top_k,
        since=req.since, until=req.until, category=req.category,
    )
    return ApiResponse(data=result)


@app.post("/learn", response_model=ApiResponse)
def learn(req: LearnRequest):
    result = core.learn(req.content, req.tags)
    return ApiResponse(data=result)


@app.get("/memories", response_model=ApiResponse)
def list_memories(limit: int = Query(default=20, ge=1, le=100)):
    result = core.list_memories(limit)
    return ApiResponse(data=result)


@app.delete("/memories/{memory_id}", response_model=ApiResponse)
def forget_memory(memory_id: str):
    result = core.forget_memory(memory_id)
    return ApiResponse(data=result)


@app.get("/memories/categories", response_model=ApiResponse)
def memory_categories():
    result = core.memory_categories()
    return ApiResponse(data=result)


@app.get("/memories/search-by-category", response_model=ApiResponse)
def search_by_category(category: str = Query(...)):
    result = core.search_by_category(category)
    return ApiResponse(data=result)


@app.get("/memories/tags", response_model=ApiResponse)
def memory_tags():
    result = core.memory_tags()
    return ApiResponse(data=result)


@app.get("/memories/search-by-tag", response_model=ApiResponse)
def search_by_tag(tag: str = Query(...)):
    result = core.search_by_tag(tag)
    return ApiResponse(data=result)


# ---------------------------------------------------------------------------
# Intelligence
# ---------------------------------------------------------------------------

@app.post("/context-window", response_model=ApiResponse)
def context_window(req: ContextWindowRequest):
    result = core.context_window(req.query, req.token_budget, req.include_documents)
    return ApiResponse(data=result)


@app.get("/decision-timeline", response_model=ApiResponse)
def decision_timeline():
    result = core.decision_timeline()
    return ApiResponse(data=result)


@app.get("/smart-suggest", response_model=ApiResponse)
def smart_suggest(max_suggestions: int = Query(default=5, ge=1, le=20)):
    result = core.smart_suggest(max_suggestions)
    return ApiResponse(data=result)


@app.get("/topic-map", response_model=ApiResponse)
def topic_map(output_format: str = Query(default="text")):
    result = core.topic_map(output_format)
    return ApiResponse(data=result)


@app.get("/knowledge-stats", response_model=ApiResponse)
def knowledge_stats():
    result = core.knowledge_stats()
    return ApiResponse(data=result)


# ---------------------------------------------------------------------------
# Workspace
# ---------------------------------------------------------------------------

@app.get("/status", response_model=ApiResponse)
def tessera_status():
    result = core.tessera_status()
    return ApiResponse(data=result)


@app.get("/health-check", response_model=ApiResponse)
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
