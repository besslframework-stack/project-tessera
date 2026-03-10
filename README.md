# Tessera

[![PyPI version](https://img.shields.io/pypi/v/project-tessera)](https://pypi.org/project/project-tessera/)
[![Python](https://img.shields.io/pypi/pyversions/project-tessera)](https://pypi.org/project/project-tessera/)
[![License](https://img.shields.io/pypi/l/project-tessera)](https://github.com/besslframework-stack/project-tessera/blob/main/LICENSE)

<a href="https://glama.ai/mcp/servers/@besslframework-stack/project-tessera">
  <img width="380" height="200" src="https://glama.ai/mcp/servers/@besslframework-stack/project-tessera/badge" />
</a>

**Personal Knowledge Layer for AI. Own your memory across every AI tool.**

You use Claude, ChatGPT, Gemini, Copilot. Each conversation generates knowledge that disappears when the session ends. Tessera captures that knowledge, stores it locally, and serves it back to any AI tool through MCP or REST API.

## Why Tessera

- **Auto-learning** -- extracts decisions, preferences, and facts from conversations automatically.
- **Works with any AI** -- Claude via MCP, ChatGPT/Gemini/Copilot via HTTP API. One knowledge base, every tool.
- **Cross-session memory** -- AI remembers your decisions and context between conversations.
- **Cross-AI portability** -- export memories to ChatGPT or Gemini format. Import past conversations from any AI.
- **100% local** -- no cloud, no API keys, no data leaving your machine. LanceDB + fastembed/ONNX.
- **Encrypted storage** -- optional AES-256 encryption at rest for sensitive knowledge.

## Architecture

```
                    +-----------------+
                    |    src/core.py  |   49 public functions
                    |                 |   Search, memory, knowledge graph,
                    |                 |   auto-extract, intelligence, export
                    +-----------------+
                     /        |        \
    +-------------+  +----------------+  +----------+
    | mcp_server  |  | http_server.py |  | cli.py   |
    | (stdio/MCP) |  | (REST API)     |  | (CLI)    |
    | 47 tools    |  | 28 endpoints   |  | 11 cmds  |
    +-------------+  +----------------+  +----------+

    +--------------------------------------------------+
    | LanceDB (vectors) | SQLite (metadata, analytics) |
    | fastembed/ONNX (local embeddings, no API keys)   |
    | AES-256-CBC vault (optional encryption)          |
    +--------------------------------------------------+
```

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

## Supported file types (40+)

| Category | Extensions | Install |
|----------|-----------|---------|
| Documents | `.md` `.txt` `.rst` `.csv` | included |
| Office | `.xlsx` `.docx` `.pdf` | `pip install project-tessera[xlsx,docx,pdf]` |
| Code | `.py` `.js` `.ts` `.tsx` `.jsx` `.java` `.go` `.rs` `.rb` `.php` `.c` `.cpp` `.h` `.swift` `.kt` `.sh` `.sql` `.cs` `.dart` `.r` `.lua` `.scala` | included |
| Config | `.json` `.yaml` `.yml` `.toml` `.xml` `.ini` `.cfg` `.env` | included |
| Web | `.html` `.htm` `.css` `.scss` `.less` `.svg` | included |
| Images | `.png` `.jpg` `.jpeg` `.webp` `.gif` `.bmp` `.tiff` | `pip install project-tessera[ocr]` |

## MCP tools (47)

### Search (5)
| Tool | What it does |
|------|-------------|
| `search_documents` | Semantic + keyword hybrid search across all docs |
| `unified_search` | Search documents AND memories in one call |
| `view_file_full` | Full file view (CSV as table, XLSX per sheet) |
| `read_file` | Read any file's full content |
| `list_sources` | See what's indexed |

### Memory (13)
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

### Auto-learn (5)
| Tool | What it does |
|------|-------------|
| `digest_conversation` | Extract and save knowledge from the current session |
| `toggle_auto_learn` | Turn auto-learning on/off or check status |
| `review_learned` | Review recently auto-learned memories |
| `session_interactions` | View tool calls from current/past sessions |
| `recent_sessions` | Session history with interaction counts |

### Intelligence (7)
| Tool | What it does |
|------|-------------|
| `decision_timeline` | Track how decisions evolved over time, grouped by topic |
| `context_window` | Build optimal context within a token budget |
| `smart_suggest` | Personalized query suggestions based on past patterns |
| `topic_map` | Cluster memories by topic with Mermaid mindmap |
| `knowledge_stats` | Aggregate statistics (categories, tags, growth) |
| `user_profile` | Auto-built profile (language, preferences, expertise) |
| `explore_connections` | Show connections around a specific topic |

### Cross-AI (4)
| Tool | What it does |
|------|-------------|
| `export_for_ai` | Export memories in ChatGPT or Gemini format |
| `import_from_ai` | Import memories from ChatGPT or Gemini |
| `import_conversations` | Extract knowledge from ChatGPT/Claude/Gemini conversation exports |
| `export_knowledge` | Export as Obsidian (wikilinks), Markdown, CSV, or JSON |

### Security and data (2)
| Tool | What it does |
|------|-------------|
| `vault_status` | Check AES-256 encryption status |
| `migrate_data` | Upgrade data from older schema versions |

### Workspace (11)
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
| `health_check` | Comprehensive workspace diagnostics |
| `search_analytics` | Search usage patterns, top queries, response times |
| `check_document_freshness` | Detect stale documents older than N days |

## CLI (11 commands)

```bash
tessera setup          # One-command setup
tessera init           # Interactive setup
tessera ingest         # Index all sources
tessera sync           # Re-index changed files
tessera serve          # Start MCP server
tessera api            # Start HTTP API server (port 8394)
tessera migrate        # Upgrade data schema
tessera check          # Workspace health
tessera status         # Project status
tessera install-mcp    # Configure Claude Desktop
tessera version        # Show version
```

## HTTP API (28 endpoints)

Install with API support:

```bash
pip install project-tessera[api]
tessera api  # Starts on http://127.0.0.1:8394
```

Interactive docs at `http://127.0.0.1:8394/docs`.

### Endpoints

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

### Examples

```bash
# Search
curl -X POST http://127.0.0.1:8394/search \
  -H "Content-Type: application/json" \
  -d '{"query": "database architecture", "top_k": 5}'

# Remember
curl -X POST http://127.0.0.1:8394/remember \
  -H "Content-Type: application/json" \
  -d '{"content": "Use PostgreSQL for production", "tags": ["db"]}'

# Export for ChatGPT
curl http://127.0.0.1:8394/export-for-ai?target=chatgpt

# Batch
curl -X POST http://127.0.0.1:8394/batch \
  -H "Content-Type: application/json" \
  -d '{"operations": [{"method": "search", "params": {"query": "test"}}, {"method": "knowledge_stats"}]}'
```

Optional auth: set `TESSERA_API_KEY` environment variable.

Optional encryption: set `TESSERA_VAULT_KEY` environment variable.

## How it works

```
Documents (Markdown, CSV, XLSX, DOCX, PDF, code, images)
    |
    v
Parse & chunk --> Embed locally (fastembed/ONNX) --> LanceDB (vectors)
    |
    v
src/core.py (search, memory, knowledge graph, auto-extract, intelligence)
    |
    v
MCP server (Claude) / HTTP API (ChatGPT, Gemini, extensions) / CLI
```

Everything runs on your machine. No external API calls for search or embedding.

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
  reranker_weight: 0.7     # Semantic vs keyword balance
  max_top_k: 50            # Max results per search

ingestion:
  chunk_size: 1024         # Text chunk size
  chunk_overlap: 100       # Overlap between chunks
```

Or set `TESSERA_WORKSPACE=/path/to/docs` to skip config.

## Numbers

| Metric | Count |
|--------|-------|
| MCP tools | 47 |
| HTTP endpoints | 28 |
| CLI commands | 11 |
| Tests | 652 |
| Supported file types | 40+ |
| Core functions | 49 |

## License

AGPL-3.0 -- see [LICENSE](LICENSE).

Commercial licensing: bessl.framework@gmail.com
