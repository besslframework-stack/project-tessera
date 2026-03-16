# Tessera

[![PyPI version](https://img.shields.io/pypi/v/project-tessera)](https://pypi.org/project/project-tessera/)
[![Downloads](https://img.shields.io/pypi/dm/project-tessera)](https://pypi.org/project/project-tessera/)
[![Tests](https://img.shields.io/badge/tests-996%20passing-brightgreen)]()
[![Python](https://img.shields.io/pypi/pyversions/project-tessera)](https://pypi.org/project/project-tessera/)
[![License](https://img.shields.io/pypi/l/project-tessera)](https://github.com/besslframework-stack/project-tessera/blob/main/LICENSE)

<a href="https://glama.ai/mcp/servers/@besslframework-stack/project-tessera">
  <img width="380" height="200" src="https://glama.ai/mcp/servers/@besslframework-stack/project-tessera/badge" />
</a>

**Every AI conversation produces knowledge. When the session ends, it's gone. Tessera keeps it.**

One knowledge base shared across Claude, ChatGPT, Gemini, and Copilot. Runs locally. No API keys, no Docker, no data leaving your machine.

```bash
pip install project-tessera
tessera setup
# Done. Claude Desktop now has persistent memory + document search.
```

---

## Why Tessera over alternatives

|  | Tessera | Mem0 | Basic Memory | mcp-memory-service |
|--|---------|------|--------------|-------------------|
| Works without API keys | Yes | No (needs OpenAI) | Yes | Partial |
| Works without Docker | Yes | No | Yes | No |
| Document search (40+ types) | Yes | No | Markdown only | No |
| ChatGPT live integration (Actions) | Yes | No | No | No |
| Contradiction detection | Yes | No | No | No |
| Memory confidence scoring | Yes | No | No | No |
| Encrypted vault (AES-256) | Yes | No | No | No |
| HTTP API for non-MCP tools | 47 endpoints | Yes | No | Yes |
| Auto-learning from conversations | Yes | Yes | No | No |
| MCP tools | 53 | ~10 | ~15 | 24 |

### The short version

Most memory tools store text and search it. Tessera does that, plus:

- **Cross-AI**: ChatGPT calls Tessera's API through Custom GPT Actions. One knowledge base, two AIs reading and writing to it live.
- **Self-maintaining**: finds contradictions between old and new memories, scores confidence by reinforcement frequency, flags stale knowledge, auto-merges near-duplicates.
- **Zero infrastructure**: `pip install` and go. LanceDB and fastembed are embedded -- no Docker, no database server, no API keys.
- **Encrypted**: set `TESSERA_VAULT_KEY` and all memories are AES-256-CBC encrypted at rest.

---

## Architecture

### How search works (query path)

```
    User asks: "What did we decide about the database?"
                            |
                            v
                +-----------------------+
                |    Query Processing   |
                |  Multi-angle decomp   |    "database decision"
                |  (2-4 perspectives)   |    "database", "decision"
                +-----------------------+    "decision about database"
                            |
              +-------------+-------------+
              |                           |
              v                           v
    +------------------+        +------------------+
    |  Vector Search   |        |  Keyword Search  |
    |  (LanceDB)       |        |  (FTS index)     |
    |  384-dim MiniLM  |        |  BM25 scoring    |
    +------------------+        +------------------+
              |                           |
              +-------------+-------------+
                            |
                            v
                +-----------------------+
                |      Reranking        |
                |  70% semantic weight  |    LinearCombinationReranker
                |  30% keyword weight   |    + version-aware scoring
                +-----------------------+
                            |
                            v
                +-----------------------+
                |   Result Assembly     |
                |  Dedup (content hash) |    2-pass deduplication
                |  Verdict labels       |    found / weak / none
                |  Cache (60s TTL)      |
                +-----------------------+
                            |
                            v
                    Top-K results with
                    confidence scores
```

### How ingestion works (ingest path)

```
    Documents: .md .pdf .docx .xlsx .py .ts .go ...  (40+ types)
                            |
                            v
                +-----------------------+
                |   File Type Router    |
                |  Markdown, CSV, XLSX  |    Type-specific parsers
                |  Code, PDF, Images    |    with metadata extraction
                +-----------------------+
                            |
                            v
                +-----------------------+
                |   Chunking Engine     |
                |  1024 tokens/chunk    |    Sentence-boundary aware
                |  100 token overlap    |    Heading-preserving
                +-----------------------+
                            |
                            v
                +-----------------------+
                |   Local Embedding     |
                |  fastembed/ONNX       |    paraphrase-multilingual
                |  384 dimensions       |    MiniLM-L12-v2
                |  No API calls         |    101 languages
                +-----------------------+
                            |
              +-------------+-------------+
              |                           |
              v                           v
    +------------------+        +------------------+
    |    LanceDB       |        |     SQLite       |
    |  Vector storage  |        |  File metadata   |
    |  Columnar format |        |  Search analytics|
    |  Zero-config     |        |  Interaction log |
    +------------------+        +------------------+
```

### System overview

```
                    +--------------------------------------------+
                    |              src/core.py                    |
                    |         58 orchestration functions          |
                    |   55 specialized modules, 10.5k LOC        |
                    +--------------------------------------------+
                     /                |                \
    +---------------+  +-------------------+  +--------------+
    | MCP Server    |  | HTTP API Server   |  | CLI          |
    | Claude Desktop|  | FastAPI + Swagger |  | 11 commands  |
    | 53 tools      |  | 47 endpoints      |  | setup, sync  |
    | stdio         |  | port 8394         |  | ingest, api  |
    +---------------+  +-------------------+  +--------------+
           |                    |                     |
           v                    v                     v
    +------------------------------------------------------------+
    |                    Storage Layer                            |
    |  LanceDB         SQLite           Filesystem               |
    |  (vectors)       (metadata,       (memories as .md,        |
    |                   analytics,       encrypted with           |
    |                   interactions)    AES-256-CBC)             |
    |                                                            |
    |  fastembed/ONNX: local embedding, no API keys              |
    |  101 languages, 384-dim vectors, ~220MB model              |
    +------------------------------------------------------------+
```

---

## Get started

### 1. Install

```bash
pip install project-tessera
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uvx --from project-tessera tessera setup
```

### 2. Setup

```bash
tessera setup
```

Creates workspace config, downloads embedding model (~220MB, first time only), configures Claude Desktop.

### 3. Restart Claude Desktop

Ask Claude about your documents. It searches automatically.

### Use with ChatGPT (Custom GPT Actions)

```bash
tessera api                     # Start REST API on localhost:8394
ngrok http 8394                 # Expose to the internet
# Then create a Custom GPT with the Actions spec from /chatgpt-actions/openapi.json
```

Full setup guide at `http://127.0.0.1:8394/chatgpt-actions/setup`. Swagger docs at `http://127.0.0.1:8394/docs`.

---

## How it works

### Hybrid search with reranking

Every search goes through four stages:

1. Query decomposition -- the query is split into 2-4 search angles (core keywords, individual terms, reversed emphasis)
2. Hybrid retrieval -- vector similarity (LanceDB) and keyword matching (FTS/BM25) run in parallel
3. Reranking -- a LinearCombinationReranker merges the two result sets (70% semantic, 30% keyword weight)
4. Verdict scoring -- each result gets a label: `confident match` (>= 45%), `possible match` (25-45%), or `low relevance` (< 25%)

When multiple versions of the same document exist, Tessera prefers the latest.

### Cross-session memory

```bash
# Via MCP (Claude)
"Remember that we chose PostgreSQL for the production database"

# Via HTTP API (ChatGPT, Gemini, scripts)
curl -X POST http://127.0.0.1:8394/remember \
  -H "Content-Type: application/json" \
  -d '{"content": "Use PostgreSQL for production", "tags": ["db", "architecture"]}'
```

Each memory gets a category (decision, preference, or fact), is checked for duplicates against existing memories (cosine similarity, 0.92 threshold), and receives a confidence score -- weighted by repetition (35%), recency (25%), source diversity (20%), and category (20%). Set `TESSERA_VAULT_KEY` to encrypt all memories with AES-256-CBC.

### Auto-learning

Tessera picks up decisions, preferences, and facts from your conversations without being asked. `toggle_auto_learn` turns it on or off; `review_learned` shows what it caught.

### Contradiction detection

Memories contradict each other over time. Tessera finds them:

```
CONTRADICTION (HIGH severity):
  "We decided to use PostgreSQL" (2026-03-01)
  vs
  "Switched to MongoDB for the main database" (2026-03-10)

  The newer memory (2026-03-10) likely reflects the current state.
```

Works with both English and Korean negation patterns.

### Cross-AI: ChatGPT Custom GPT Actions

ChatGPT talks to Tessera's HTTP API through Custom GPT Actions. No export/import step -- it reads and writes the same knowledge base Claude uses through MCP, in real time.

```bash
# 1. Start Tessera API + tunnel
tessera api
ngrok http 8394

# 2. Get the OpenAPI spec for your Custom GPT
curl https://your-tunnel.ngrok-free.app/chatgpt-actions/openapi.json?server_url=https://your-tunnel.ngrok-free.app

# 3. Get the GPT instruction template
curl https://your-tunnel.ngrok-free.app/chatgpt-actions/instructions

# 4. Full setup guide
curl https://your-tunnel.ngrok-free.app/chatgpt-actions/setup
```

Create a Custom GPT, paste the instructions, import the OpenAPI spec as an Action. ChatGPT can then search your documents, save memories, and recall past decisions from the same knowledge base.

You can also import past ChatGPT conversations to extract knowledge from them:

```bash
curl -X POST http://127.0.0.1:8394/import-conversations \
  -H "Content-Type: application/json" \
  -d '{"data": "<ChatGPT export JSON>", "source": "chatgpt"}'
```

Export as Obsidian vault (wikilinks), Markdown, CSV, or JSON:

```bash
curl http://127.0.0.1:8394/export?format=obsidian
```

### Memory health

Each memory is healthy, stale (90+ days without reinforcement), or orphaned (no metadata, no category). The health report tells you what to clean up and tracks growth over time.

### Plugin hooks

Run your own scripts when things happen:

```yaml
# workspace.yaml
hooks:
  on_memory_created:
    - script: ./notify-slack.sh
  on_contradiction_found:
    - script: ./alert.py
```

7 event types: `on_memory_created`, `on_memory_deleted`, `on_search`, `on_session_start`, `on_session_end`, `on_ingest_complete`, `on_contradiction_found`.

---

## Supported file types (40+)

| Category | Extensions | Install |
|----------|-----------|---------|
| Documents | `.md` `.txt` `.rst` `.csv` | included |
| Office | `.xlsx` `.docx` `.pdf` | `pip install project-tessera[xlsx,docx,pdf]` |
| Code | `.py` `.js` `.ts` `.tsx` `.jsx` `.java` `.go` `.rs` `.rb` `.php` `.c` `.cpp` `.h` `.swift` `.kt` `.sh` `.sql` `.cs` `.dart` `.r` `.lua` `.scala` | included |
| Config | `.json` `.yaml` `.yml` `.toml` `.xml` `.ini` `.cfg` `.env` | included |
| Web | `.html` `.htm` `.css` `.scss` `.less` `.svg` | included |
| Images | `.png` `.jpg` `.jpeg` `.webp` `.gif` `.bmp` `.tiff` | `pip install project-tessera[ocr]` |

---

## MCP tools (53)

<details>
<summary><strong>Search (5)</strong></summary>

| Tool | What it does |
|------|-------------|
| `search_documents` | Semantic + keyword hybrid search across all docs |
| `unified_search` | Search documents AND memories in one call |
| `view_file_full` | Full file view (CSV as table, XLSX per sheet) |
| `read_file` | Read any file's full content |
| `list_sources` | See what's indexed |

</details>

<details>
<summary><strong>Memory (13)</strong></summary>

| Tool | What it does |
|------|-------------|
| `remember` | Save knowledge that persists across sessions |
| `recall` | Search past memories with date/category filters |
| `learn` | Save and immediately index new knowledge |
| `list_memories` | Browse saved memories |
| `forget_memory` | Delete a specific memory |
| `export_memories` | Batch export all memories as JSON |
| `import_memories` | Batch import memories from JSON |
| `memory_tags` | List all unique tags with counts |
| `search_by_tag` | Filter memories by specific tag |
| `memory_categories` | List auto-detected categories (decision/preference/fact) |
| `search_by_category` | Filter memories by category |
| `find_similar` | Find documents similar to a given file |
| `knowledge_graph` | Build a Mermaid diagram of document relationships |

</details>

<details>
<summary><strong>Auto-learn (5)</strong></summary>

| Tool | What it does |
|------|-------------|
| `digest_conversation` | Extract and save knowledge from the current session |
| `toggle_auto_learn` | Turn auto-learning on/off or check status |
| `review_learned` | Review recently auto-learned memories |
| `session_interactions` | View tool calls from current/past sessions |
| `recent_sessions` | Session history with interaction counts |

</details>

<details>
<summary><strong>Intelligence (7)</strong></summary>

| Tool | What it does |
|------|-------------|
| `decision_timeline` | How your decisions changed over time, by topic |
| `context_window` | Pack the best context into a token budget |
| `smart_suggest` | Query suggestions based on your past searches |
| `topic_map` | Cluster memories by topic with Mermaid mindmap |
| `knowledge_stats` | Aggregate statistics (categories, tags, growth) |
| `user_profile` | Auto-built profile (language, preferences, expertise) |
| `explore_connections` | Show connections around a specific topic |

</details>

<details>
<summary><strong>Insight (6)</strong></summary>

| Tool | What it does |
|------|-------------|
| `deep_search` | Breaks a query into 2-4 angles, searches each, merges best results |
| `deep_recall` | Multi-angle memory recall with verdict labels |
| `detect_contradictions` | Find conflicting memories with severity rating |
| `memory_confidence` | How reliable is each memory (repetition, recency, source diversity) |
| `memory_health` | Which memories are healthy, stale, or orphaned |
| `list_plugin_hooks` | See what hooks are registered |

</details>

<details>
<summary><strong>Cross-AI (4)</strong></summary>

| Tool | What it does |
|------|-------------|
| `export_for_ai` | Export memories in ChatGPT/Gemini-readable format |
| `import_from_ai` | Import memories from external AI tools |
| `import_conversations` | Extract knowledge from ChatGPT/Claude conversation exports |
| `export_knowledge` | Export as Obsidian (wikilinks), Markdown, CSV, or JSON |

ChatGPT connects via Custom GPT Actions (HTTP API). See `/chatgpt-actions/setup` for the full guide.

</details>

<details>
<summary><strong>Security and data (2)</strong></summary>

| Tool | What it does |
|------|-------------|
| `vault_status` | Check AES-256 encryption status |
| `migrate_data` | Upgrade data from older schema versions |

</details>

<details>
<summary><strong>Workspace (11)</strong></summary>

| Tool | What it does |
|------|-------------|
| `ingest_documents` | Index documents (first-time or full rebuild) |
| `sync_documents` | Incremental sync (only changed files) |
| `project_status` | Recent changes per project |
| `extract_decisions` | Find past decisions from logs |
| `audit_prd` | Check PRD quality (13-section structure) |
| `organize_files` | Move, rename, archive files |
| `suggest_cleanup` | Detect backup files, empty dirs, misplaced files |
| `tessera_status` | Server health: tracked files, sync history, cache |
| `health_check` | Full workspace diagnostics |
| `search_analytics` | Search usage patterns, top queries, response times |
| `check_document_freshness` | Detect stale documents older than N days |

</details>

---

## HTTP API (47 endpoints)

```bash
pip install project-tessera[api]
tessera api  # http://127.0.0.1:8394
```

Swagger UI at `http://127.0.0.1:8394/docs`. Optional auth via `TESSERA_API_KEY` env var.

<details>
<summary><strong>All endpoints</strong></summary>

| Method | Path | What it does |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/version` | Version info |
| POST | `/search` | Semantic + keyword search |
| POST | `/unified-search` | Search docs + memories |
| POST | `/remember` | Save a memory |
| POST | `/recall` | Search memories with filters |
| POST | `/learn` | Save and index knowledge |
| GET | `/memories` | List memories |
| DELETE | `/memories/{id}` | Delete a memory |
| GET | `/memories/categories` | List categories |
| GET | `/memories/search-by-category` | Filter by category |
| GET | `/memories/tags` | List tags |
| GET | `/memories/search-by-tag` | Filter by tag |
| POST | `/context-window` | Build token-budgeted context |
| GET | `/decision-timeline` | Decision evolution |
| GET | `/smart-suggest` | Query suggestions |
| GET | `/topic-map` | Topic clusters |
| GET | `/knowledge-stats` | Stats dashboard |
| POST | `/batch` | Multiple operations in one call |
| GET | `/export` | Export as Obsidian/MD/CSV/JSON |
| GET | `/export-for-ai` | Export for ChatGPT/Gemini |
| POST | `/import-from-ai` | Import from ChatGPT/Gemini |
| POST | `/import-conversations` | Import past conversations |
| POST | `/migrate` | Run data migration |
| GET | `/vault-status` | Encryption status |
| GET | `/user-profile` | User profile |
| GET | `/status` | Server status |
| GET | `/health-check` | Workspace diagnostics |
| POST | `/deep-search` | Multi-angle document search |
| POST | `/deep-recall` | Multi-angle memory recall |
| GET | `/contradictions` | Detect conflicting memories |
| GET | `/memory-confidence` | Memory reliability scores |
| GET | `/memory-health` | Memory health analytics |
| GET | `/hooks` | List plugin hooks |
| GET | `/entity-search` | Search entity knowledge graph |
| POST | `/entity-graph` | Mermaid diagram from entities |
| GET | `/consolidation-candidates` | Find similar memory clusters |
| POST | `/consolidate` | Merge similar memories |
| GET | `/dashboard` | Web dashboard (dark theme, entity graph, stats) |
| POST | `/sleep-consolidate` | Auto-merge near-duplicate memories |
| POST | `/retention-policy` | Flag old or low-quality memories |
| GET | `/retention-summary` | Age distribution and at-risk counts |
| GET | `/adapters/{framework}` | Setup code for LangChain, CrewAI, AutoGen |
| POST | `/auto-curate` | Classify, tag, deduplicate, and clean up memories |
| GET | `/chatgpt-actions/openapi.json` | OpenAPI spec for Custom GPT Actions |
| GET | `/chatgpt-actions/instructions` | GPT instruction template |
| GET | `/chatgpt-actions/setup` | ChatGPT integration setup guide |

</details>

### Quick examples

```bash
# Search documents
curl -X POST http://127.0.0.1:8394/search \
  -H "Content-Type: application/json" \
  -d '{"query": "database architecture", "top_k": 5}'

# Save a memory
curl -X POST http://127.0.0.1:8394/remember \
  -H "Content-Type: application/json" \
  -d '{"content": "Use PostgreSQL for production", "tags": ["db"]}'

# Export for ChatGPT
curl http://127.0.0.1:8394/export-for-ai?target=chatgpt

# Batch (multiple operations, single request)
curl -X POST http://127.0.0.1:8394/batch \
  -H "Content-Type: application/json" \
  -d '{"operations": [{"method": "search", "params": {"query": "test"}}, {"method": "knowledge_stats"}]}'
```

---

## CLI (11 commands)

```bash
tessera setup          # One-command setup (config + model download + Claude Desktop)
tessera init           # Interactive setup
tessera ingest         # Index all document sources
tessera sync           # Re-index changed files only
tessera serve          # Start MCP server (stdio)
tessera api            # Start HTTP API server (port 8394)
tessera migrate        # Upgrade data schema
tessera check          # Workspace health diagnostics
tessera status         # Project status summary
tessera install-mcp    # Configure Claude Desktop
tessera version        # Show version
```

---

## Claude Desktop config

**With uvx (recommended):**

```json
{
  "mcpServers": {
    "tessera": {
      "command": "uvx",
      "args": ["--from", "project-tessera", "tessera-mcp"]
    }
  }
}
```

**With pip:**

```json
{
  "mcpServers": {
    "tessera": {
      "command": "tessera-mcp"
    }
  }
}
```

Config location:
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

---

## Configuration

`tessera setup` creates `workspace.yaml`:

```yaml
workspace:
  root: /Users/you/Documents
  name: my-workspace

sources:
  - path: .
    type: document

search:
  reranker_weight: 0.7     # Semantic vs keyword balance (0.0 = keyword only, 1.0 = vector only)
  max_top_k: 50            # Max results per search

ingestion:
  chunk_size: 1024         # Tokens per chunk
  chunk_overlap: 100       # Overlap between chunks

hooks:                      # Optional plugin hooks
  on_memory_created:
    - script: ./my-hook.sh
```

Or set `TESSERA_WORKSPACE=/path/to/docs` to skip config file entirely.

Environment variables:
- `TESSERA_API_KEY` -- enable API authentication
- `TESSERA_VAULT_KEY` -- enable AES-256 encryption for memories

---

## Technical details

| Component | Technology | Why |
|-----------|-----------|-----|
| Vector store | LanceDB | Embedded columnar store. No server process, handles vector + metadata queries natively |
| Embeddings | fastembed/ONNX | Local inference, no API keys. `paraphrase-multilingual-MiniLM-L12-v2` (384-dim, 101 languages) |
| Metadata | SQLite | File tracking, search analytics, interaction logging. Thread-safe with reentrant locks |
| Memory storage | Filesystem (.md) | Human-readable, git-friendly, encryptable. YAML frontmatter for metadata |
| Encryption | Pure Python AES-256-CBC | No OpenSSL dependency. PKCS7 padding, random IV per memory |
| HTTP API | FastAPI | Swagger docs, Pydantic validation, async-capable |
| MCP | FastMCP (stdio) | Standard MCP protocol for Claude Desktop |

### Numbers

| Metric | Count |
|--------|-------|
| MCP tools | 53 |
| HTTP endpoints | 47 |
| CLI commands | 11 |
| Core modules | 61 |
| Lines of code | 16,000+ |
| Tests | 996 |
| File types | 40+ |

---

## License

AGPL-3.0 -- see [LICENSE](LICENSE).

Commercial licensing: bessl.framework@gmail.com
