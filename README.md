# Tessera

[![PyPI version](https://img.shields.io/pypi/v/project-tessera)](https://pypi.org/project/project-tessera/)
[![Python](https://img.shields.io/pypi/pyversions/project-tessera)](https://pypi.org/project/project-tessera/)
[![License](https://img.shields.io/pypi/l/project-tessera)](https://github.com/besslframework-stack/project-tessera/blob/main/LICENSE)

<a href="https://glama.ai/mcp/servers/@besslframework-stack/project-tessera">
  <img width="380" height="200" src="https://glama.ai/mcp/servers/@besslframework-stack/project-tessera/badge" />
</a>

**Make Claude Desktop remember your entire workspace.**

You have hundreds of documents — PRDs, meeting notes, decision logs, session records. Claude Desktop can read files you attach, but it can't search across your whole workspace. Tessera bridges that gap.

It indexes your local documents into a vector store and connects to Claude Desktop via MCP. When you ask a question, Claude automatically searches your files and answers with context — and remembers across sessions.

### Why Tessera?

- **No servers to run** — No Ollama, no Docker, no API keys. Everything runs locally.
- **Cross-session memory** — Claude remembers your decisions and preferences between conversations.
- **Auto-sync** — File watcher detects changes and re-indexes in the background.
- **100% local** — Nothing leaves your machine.

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

This does everything for you:
- Creates a workspace config
- Downloads the embedding model (~220MB, first time only)
- Configures Claude Desktop automatically

### 3. Restart Claude Desktop

That's it. Ask Claude about your documents and it will search them automatically.

## Supported file types

| Type | Extension | Install |
|------|-----------|---------|
| Markdown | `.md` | included |
| CSV | `.csv` | included |
| Excel | `.xlsx` | `pip install project-tessera[xlsx]` |
| Word | `.docx` | `pip install project-tessera[docx]` |
| PDF | `.pdf` | `pip install project-tessera[pdf]` |

## What Claude can do with Tessera

31 tools across search, memory, knowledge graph, and workspace management.

| Tool | What it does |
|------|-------------|
| **Search** | |
| `search_documents` | Semantic + keyword hybrid search across all your docs |
| `unified_search` | Search documents AND memories in one call |
| `view_file_full` | Full file view (CSV as table, XLSX per sheet, etc.) |
| `read_file` | Read any file's full content |
| `list_sources` | See what's indexed |
| **Memory** | |
| `remember` | Save knowledge that persists across sessions |
| `recall` | Search past memories from previous conversations |
| `learn` | Auto-learn: save and immediately index new knowledge |
| `list_memories` | Browse saved memories |
| `forget_memory` | Delete a specific memory |
| `export_memories` | Batch export all memories as JSON |
| `import_memories` | Batch import memories from JSON |
| `memory_tags` | List all unique tags with counts |
| `search_by_tag` | Filter memories by specific tag |
| **Knowledge Graph** | |
| `find_similar` | Find documents similar to a given file |
| `knowledge_graph` | Build a Mermaid diagram of document relationships |
| `explore_connections` | Show connections around a specific topic |
| **Indexing** | |
| `ingest_documents` | Index your documents (first-time or full rebuild) |
| `sync_documents` | Incremental sync — only re-index changed files |
| **Workspace** | |
| `project_status` | See what's changed recently in each project |
| `extract_decisions` | Find past decisions from logs |
| `audit_prd` | Check PRD quality (section coverage, versioning) |
| `organize_files` | Move, rename, archive files |
| `suggest_cleanup` | Detect backup files, empty dirs, misplaced files |
| `tessera_status` | Server health: tracked files, sync history, cache stats |
| `health_check` | Comprehensive workspace diagnostics |
| `search_analytics` | Search usage patterns, top queries, response times |
| `check_document_freshness` | Detect stale documents older than N days |

## CLI commands

```bash
tessera setup                   # One-command setup (recommended)
tessera init                    # Interactive setup with more options
tessera ingest                  # Index all configured sources
tessera sync                    # Re-index only changed files
tessera check                   # Check workspace health
tessera status                  # Show project status
tessera install-mcp             # Configure Claude Desktop
tessera version                 # Show version
```

## How it works

```
Your documents (Markdown, CSV, XLSX, DOCX, PDF)
        |
   Parse & chunk
        |
   Embed locally (fastembed/ONNX)
        |
   Store in LanceDB (local vector DB)
        |
   Expose via MCP server
        |
   Claude Desktop searches automatically
```

## Advanced: Manual Claude Desktop config

If `tessera setup` didn't configure Claude Desktop automatically, add this to your `claude_desktop_config.json`:

**With uvx (recommended — no venv needed):**

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

**With pip install:**

```json
{
  "mcpServers": {
    "tessera": {
      "command": "tessera-mcp"
    }
  }
}
```

Config file location:
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

## Configuration

`tessera setup` creates a `workspace.yaml` with sensible defaults. You can edit it:

```yaml
workspace:
  root: /Users/you/Documents
  name: my-workspace

sources:
  - path: .
    type: document
```

All parameters are configurable:

```yaml
search:
  reranker_weight: 0.7       # Semantic vs keyword balance
  max_top_k: 50              # Max results per search

ingestion:
  chunk_size: 1024           # Text chunk size
  chunk_overlap: 100         # Overlap between chunks

watcher:
  poll_interval: 30.0        # Seconds between scans
  debounce: 5.0              # Wait before syncing
```

## License

AGPL-3.0 — see [LICENSE](LICENSE).

For commercial licensing: bessl.framework@gmail.com
