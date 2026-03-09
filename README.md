# Tessera

[![PyPI version](https://img.shields.io/pypi/v/project-tessera)](https://pypi.org/project/project-tessera/)
[![Python](https://img.shields.io/pypi/pyversions/project-tessera)](https://pypi.org/project/project-tessera/)
[![License](https://img.shields.io/pypi/l/project-tessera)](https://github.com/besslframework-stack/project-tessera/blob/main/LICENSE)

<a href="https://glama.ai/mcp/servers/@besslframework-stack/project-tessera">
  <img width="380" height="200" src="https://glama.ai/mcp/servers/@besslframework-stack/project-tessera/badge" />
</a>

**Personal Knowledge Layer for AI. Own your memory across every AI tool.**

You use Claude, ChatGPT, Gemini, Copilot. Each conversation generates knowledge that disappears when the session ends. Tessera captures that knowledge, stores it locally, and serves it back to any AI. Your memory, your machine, your data.

## What makes Tessera different

- **Auto-learning** -- Tessera records every interaction and extracts decisions, preferences, and facts automatically. No manual "remember this."
- **Interface-agnostic core** -- One knowledge engine, multiple interfaces. MCP today, HTTP API for ChatGPT/Gemini/extensions coming next.
- **Cross-session memory** -- AI remembers your decisions and context between conversations.
- **100% local** -- No cloud, no API keys, no data leaving your machine. LanceDB + fastembed/ONNX.
- **Hybrid search** -- Semantic + keyword search with reranking. Not just vector similarity.

## Architecture

```
                    +-----------------+
                    |    src/core.py  |   Business logic (35 functions)
                    |                 |   Search, memory, knowledge graph,
                    |                 |   auto-extract, interaction log
                    +-----------------+
                     /        |        \
    +-------------+  +----------------+  +----------+
    | mcp_server  |  | http_server.py |  | cli.py   |
    | (stdio/MCP) |  | (REST API)     |  | (CLI)    |
    | Claude      |  | ChatGPT,       |  |          |
    | Desktop     |  | Gemini, etc.   |  |          |
    +-------------+  +----------------+  +----------+
                          (planned)

    Core engine:
    +--------------------------------------------------+
    | LanceDB (vectors) | SQLite (metadata, analytics) |
    | fastembed/ONNX (local embeddings, no API keys)   |
    | Auto-extract (pattern-based fact detection)       |
    | Interaction log (every tool call recorded)        |
    +--------------------------------------------------+
```

One core, multiple interfaces. The same knowledge base works regardless of which AI tool you use.

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

This does everything:
- Creates a workspace config
- Downloads the embedding model (~220MB, first time only)
- Configures Claude Desktop automatically

### 3. Restart Claude Desktop

Ask Claude about your documents. It searches automatically.

## Supported file types

| Type | Extension | Install |
|------|-----------|---------|
| Markdown | `.md` | included |
| CSV | `.csv` | included |
| Excel | `.xlsx` | `pip install project-tessera[xlsx]` |
| Word | `.docx` | `pip install project-tessera[docx]` |
| PDF | `.pdf` | `pip install project-tessera[pdf]` |

## Tools (35)

### Search
| Tool | What it does |
|------|-------------|
| `search_documents` | Semantic + keyword hybrid search across all docs |
| `unified_search` | Search documents AND memories in one call |
| `view_file_full` | Full file view (CSV as table, XLSX per sheet, etc.) |
| `read_file` | Read any file's full content |
| `list_sources` | See what's indexed |

### Memory
| Tool | What it does |
|------|-------------|
| `remember` | Save knowledge that persists across sessions |
| `recall` | Search past memories from previous conversations |
| `learn` | Save and immediately index new knowledge |
| `digest_conversation` | Auto-extract decisions/facts from the current session |
| `list_memories` | Browse saved memories |
| `forget_memory` | Delete a specific memory |
| `export_memories` | Batch export all memories as JSON |
| `import_memories` | Batch import memories from JSON |
| `memory_tags` | List all unique tags with counts |
| `search_by_tag` | Filter memories by specific tag |

### Knowledge graph
| Tool | What it does |
|------|-------------|
| `find_similar` | Find documents similar to a given file |
| `knowledge_graph` | Build a Mermaid diagram of document relationships |
| `explore_connections` | Show connections around a specific topic |

### Auto-learn
| Tool | What it does |
|------|-------------|
| `digest_conversation` | Extract and save knowledge from the current session |
| `session_interactions` | View tool calls from current/past sessions |
| `recent_sessions` | Session history with interaction counts |

### Workspace
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

## CLI

```bash
tessera setup          # One-command setup
tessera init           # Interactive setup
tessera ingest         # Index all sources
tessera sync           # Re-index changed files
tessera check          # Workspace health
tessera status         # Project status
tessera install-mcp    # Configure Claude Desktop
tessera version        # Show version
```

## How it works

```
Documents (Markdown, CSV, XLSX, DOCX, PDF)
    |
    v
Parse & chunk --> Embed locally (fastembed/ONNX) --> LanceDB (local vector DB)
    |
    v
src/core.py (search, memory, knowledge graph, auto-extract)
    |
    v
MCP server (Claude Desktop) / HTTP API (ChatGPT, Gemini, extensions)
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

`tessera setup` creates `workspace.yaml`. All parameters are tunable:

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

watcher:
  poll_interval: 30.0      # Seconds between scans
  debounce: 5.0            # Wait before syncing
```

Or skip config entirely -- Tessera auto-detects your workspace. Set `TESSERA_WORKSPACE=/path/to/docs` to specify a folder.

## Roadmap

See [ROADMAP.md](ROADMAP.md) for the full plan from v0.6 to v1.0.

| Phase | Version | What changes |
|-------|---------|-------------|
| Sponge | v0.7 | Manual memory becomes automatic learning |
| Radar | v0.8 | Reactive search becomes proactive intelligence |
| Gateway | v0.9 | MCP-only becomes multi-interface (HTTP API) |
| Cortex | v1.0 | Search tool becomes Claude's persistent brain |

## License

AGPL-3.0 -- see [LICENSE](LICENSE).

Commercial licensing: bessl.framework@gmail.com
