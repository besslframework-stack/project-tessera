"""ChatGPT Custom GPT Actions integration.

Serves an OpenAPI spec optimized for ChatGPT Actions and provides
a GPT instruction template. This enables real cross-AI integration:
ChatGPT calls Tessera's HTTP API directly instead of one-time memory exports.
"""

from __future__ import annotations

import json

# ---------------------------------------------------------------------------
# OpenAPI spec for ChatGPT Actions
# ---------------------------------------------------------------------------

def get_openapi_spec(server_url: str = "http://localhost:8394") -> dict:
    """Return an OpenAPI 3.1.0 spec optimized for ChatGPT Custom GPT Actions.

    Only exposes the endpoints a GPT would actually use during conversation.
    Descriptions are written for the GPT to understand when/how to call them.
    """
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "Tessera — Personal Knowledge Layer",
            "description": (
                "Tessera stores your documents and memories locally. "
                "Use these endpoints to search the user's knowledge base, "
                "save new memories, and recall past decisions."
            ),
            "version": "1.1.1",
        },
        "servers": [{"url": server_url}],
        "paths": {
            "/search": {
                "post": {
                    "operationId": "searchDocuments",
                    "summary": "Search the user's local documents",
                    "description": (
                        "Search through the user's indexed documents (markdown, PDF, DOCX, code, etc). "
                        "Use this when the user asks about something that might be in their files."
                    ),
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["query"],
                                    "properties": {
                                        "query": {
                                            "type": "string",
                                            "description": "Natural language search query",
                                        },
                                        "top_k": {
                                            "type": "integer",
                                            "default": 5,
                                            "description": "Number of results to return",
                                        },
                                    },
                                },
                            },
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Search results with relevance scores",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ApiResponse"},
                                },
                            },
                        },
                    },
                },
            },
            "/remember": {
                "post": {
                    "operationId": "rememberFact",
                    "summary": "Save a memory for the user",
                    "description": (
                        "Store a piece of knowledge the user wants to remember across sessions. "
                        "Use this when the user says 'remember that...', makes a decision, "
                        "states a preference, or shares a fact worth keeping."
                    ),
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["content"],
                                    "properties": {
                                        "content": {
                                            "type": "string",
                                            "description": "The memory to store (decision, preference, fact, etc)",
                                        },
                                        "tags": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                            "description": "Optional tags for organization",
                                        },
                                    },
                                },
                            },
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Confirmation with memory ID",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ApiResponse"},
                                },
                            },
                        },
                    },
                },
            },
            "/recall": {
                "post": {
                    "operationId": "recallMemories",
                    "summary": "Recall the user's saved memories",
                    "description": (
                        "Search through the user's saved memories (decisions, preferences, facts). "
                        "Use this at the start of conversations to check what the user has previously "
                        "told you, or when they ask 'do you remember...'."
                    ),
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["query"],
                                    "properties": {
                                        "query": {
                                            "type": "string",
                                            "description": "What to search for in memories",
                                        },
                                        "top_k": {
                                            "type": "integer",
                                            "default": 5,
                                            "description": "Number of memories to return",
                                        },
                                        "category": {
                                            "type": "string",
                                            "enum": ["decision", "preference", "fact", "procedure", "reference"],
                                            "description": "Filter by memory category",
                                        },
                                    },
                                },
                            },
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Matching memories with relevance scores",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ApiResponse"},
                                },
                            },
                        },
                    },
                },
            },
            "/unified-search": {
                "post": {
                    "operationId": "unifiedSearch",
                    "summary": "Search both documents and memories at once",
                    "description": (
                        "Searches documents and memories together, returning combined results. "
                        "Use this when you want the broadest possible answer from the user's knowledge base."
                    ),
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["query"],
                                    "properties": {
                                        "query": {"type": "string"},
                                        "top_k": {"type": "integer", "default": 5},
                                    },
                                },
                            },
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Combined document and memory results",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ApiResponse"},
                                },
                            },
                        },
                    },
                },
            },
            "/deep-search": {
                "post": {
                    "operationId": "deepSearch",
                    "summary": "Multi-angle deep search with confidence scoring",
                    "description": (
                        "Decomposes the query into multiple search angles, runs parallel searches, "
                        "and merges results with a confidence verdict (found/weak/none). "
                        "Use this for complex questions where a simple search might miss relevant results."
                    ),
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["query"],
                                    "properties": {
                                        "query": {"type": "string"},
                                        "top_k": {"type": "integer", "default": 5},
                                    },
                                },
                            },
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Multi-angle results with verdict",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ApiResponse"},
                                },
                            },
                        },
                    },
                },
            },
            "/memories": {
                "get": {
                    "operationId": "listMemories",
                    "summary": "List all saved memories",
                    "description": (
                        "Returns the user's saved memories, most recent first. "
                        "Use this to get an overview of what the user has stored."
                    ),
                    "parameters": [
                        {
                            "name": "limit",
                            "in": "query",
                            "schema": {"type": "integer", "default": 20, "minimum": 1, "maximum": 100},
                            "description": "Maximum number of memories to return",
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "List of memories",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ApiResponse"},
                                },
                            },
                        },
                    },
                },
            },
            "/memories/{memory_id}": {
                "delete": {
                    "operationId": "forgetMemory",
                    "summary": "Delete a specific memory",
                    "description": "Remove a memory by its ID. Use when the user asks to forget something.",
                    "parameters": [
                        {
                            "name": "memory_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "Confirmation of deletion",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ApiResponse"},
                                },
                            },
                        },
                    },
                },
            },
            "/knowledge-stats": {
                "get": {
                    "operationId": "getKnowledgeStats",
                    "summary": "Get knowledge base statistics",
                    "description": (
                        "Returns stats: total documents, memories, categories, tags, "
                        "and storage size. Use to give the user an overview of their knowledge base."
                    ),
                    "responses": {
                        "200": {
                            "description": "Knowledge base statistics",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ApiResponse"},
                                },
                            },
                        },
                    },
                },
            },
            "/contradictions": {
                "get": {
                    "operationId": "detectContradictions",
                    "summary": "Find contradictions between memories",
                    "description": (
                        "Scans all memories for contradictions (e.g. 'use PostgreSQL' vs 'use MySQL'). "
                        "Use when the user wants to audit their knowledge for consistency."
                    ),
                    "responses": {
                        "200": {
                            "description": "List of detected contradictions",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ApiResponse"},
                                },
                            },
                        },
                    },
                },
            },
        },
        "components": {
            "schemas": {
                "ApiResponse": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "example": "ok"},
                        "data": {
                            "description": "Response data (varies by endpoint)",
                        },
                    },
                },
            },
        },
    }


# ---------------------------------------------------------------------------
# GPT instruction template
# ---------------------------------------------------------------------------

GPT_INSTRUCTIONS = """You have access to Tessera, the user's personal knowledge base running on their local machine. Tessera stores their documents and memories across AI sessions.

How to use Tessera:

1. At the START of every conversation, call recallMemories with a query related to the user's first message. This tells you what the user has previously told you about this topic.

2. When the user asks about something that might be in their files (projects, notes, code), call searchDocuments or unifiedSearch.

3. When the user makes a decision, states a preference, or shares a fact worth remembering, call rememberFact to save it. Examples:
   - "I decided to use PostgreSQL for this project" → save it
   - "I prefer TypeScript over JavaScript" → save it
   - "Our deploy target is AWS ap-northeast-2" → save it

4. For complex questions, use deepSearch — it searches from multiple angles and tells you how confident the results are.

5. If the user asks "what do you know about me" or "what have I told you", call listMemories.

6. If the user says "forget that" or "delete the memory about...", use forgetMemory.

Do NOT mention Tessera by name unless the user asks about it. Just use the knowledge naturally, as if you remember it yourself."""


def get_gpt_instructions() -> str:
    """Return the GPT instruction template."""
    return GPT_INSTRUCTIONS


def get_setup_guide(tunnel_url: str | None = None) -> str:
    """Return setup instructions for connecting ChatGPT to Tessera."""
    base_url = tunnel_url or "https://your-tunnel-url.ngrok-free.app"

    return f"""# ChatGPT ↔ Tessera setup guide

## 1. Start Tessera API server

```bash
tessera api
# or: uvicorn src.http_server:app --port 8394
```

## 2. Expose localhost with a tunnel

Tessera runs on localhost:8394. ChatGPT needs a public URL to reach it.

**Option A: ngrok (recommended)**
```bash
ngrok http 8394
```
Copy the https://...ngrok-free.app URL.

**Option B: Cloudflare Tunnel**
```bash
cloudflared tunnel --url http://localhost:8394
```

**Option C: tailscale funnel**
```bash
tailscale funnel 8394
```

## 3. Create a Custom GPT

1. Go to https://chatgpt.com → My GPTs → Create a GPT
2. In the "Configure" tab:
   - Name: "My Knowledge Base" (or whatever you want)
   - Instructions: paste the text from the /chatgpt-actions/instructions endpoint
3. Under "Actions" → "Create new action":
   - Import from URL: `{base_url}/chatgpt-actions/openapi.json`
   - Or paste the JSON from that endpoint manually
4. Set Authentication to "None" (or API Key if you set TESSERA_API_KEY)
5. Save and test

## 4. Test it

Ask your Custom GPT:
- "What do I know about databases?"
- "Remember that I prefer dark mode for all my apps"
- "Search my documents for API documentation"

## Security note

The tunnel exposes your Tessera API to the internet. Set an API key:
```bash
export TESSERA_API_KEY=your-secret-key
tessera api
```
Then configure the same key in your Custom GPT's Action authentication (API Key, header: X-API-Key).

## Current tunnel URL
{base_url}
"""
