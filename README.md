# Tessera

Personal knowledge RAG as an MCP server for Claude Desktop.

Tessera indexes your local workspace documents (Markdown, CSV, session logs) into a vector store and exposes them as MCP tools — so Claude Desktop can search, read, and reason over your own files.

## What it does

- **Hybrid search** — semantic (vector) + keyword (FTS) search across your documents
- **Incremental sync** — only re-indexes new or changed files
- **MCP server** — 8 tools available directly in Claude Desktop
- **Workspace management** — project status tracking, file organization, decision extraction, PRD auditing
- **100% local** — Ollama for embeddings, LanceDB for storage. No data leaves your machine.

## Requirements

- Python 3.11+
- [Ollama](https://ollama.ai) running locally with an embedding model

## Quick start

```bash
# Clone
git clone https://github.com/YOUR_USERNAME/project-tessera.git
cd project-tessera

# Setup
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# Pull embedding model
ollama pull nomic-embed-text-v2-moe

# Configure
cp .env.example .env
cp workspace.yaml.example workspace.yaml
# Edit workspace.yaml — set root path and define your sources

# Index your documents
python main.py ingest

# Or run incremental sync
python main.py sync

# Check status
python main.py status
```

## Claude Desktop integration

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "tessera": {
      "command": "/path/to/project-tessera/.venv/bin/python",
      "args": ["/path/to/project-tessera/mcp_server.py"]
    }
  }
}
```

Restart Claude Desktop. Tessera will appear as an MCP integration with these tools:

| Tool | Description |
|------|-------------|
| `search_documents` | Hybrid vector+keyword search with project/type filters |
| `list_sources` | List all indexed files |
| `read_file` | Read any file by path |
| `organize_files` | Move, archive, rename files |
| `suggest_cleanup` | Detect cleanup opportunities |
| `project_status` | Project status from HANDOFF.md + recent changes |
| `extract_decisions` | Extract decisions from logs |
| `audit_prd` | Audit PRD quality against 13-section structure |

## Configuration

### workspace.yaml

Defines what to index and how. See `workspace.yaml.example` for the full schema.

```yaml
workspace:
  root: /path/to/your/documents
  name: "my-workspace"

sources:
  - path: projects/my-project
    type: prd
    project: my_project

projects:
  my_project:
    display_name: "My Project"
    root: projects/my-project
```

### .env

```
OLLAMA_BASE_URL=http://localhost:11434
EMBED_MODEL=nomic-embed-text-v2-moe
```

## Architecture

```
workspace.yaml          # What to index
        |
   IngestionPipeline    # Parse markdown/CSV/session logs
        |
   MetadataExtractor    # Enrich with project, version, dates
        |
   SentenceSplitter     # Chunk into ~800 char nodes
        |
   OllamaEmbedding      # Local embeddings via Ollama
        |
   LanceDB              # Vector + FTS storage (local)
        |
   MCP Server           # Expose as tools to Claude Desktop
```

## License

AGPL-3.0 — see [LICENSE](LICENSE).

For commercial licensing, contact jsjeong.contact@gmail.com.
