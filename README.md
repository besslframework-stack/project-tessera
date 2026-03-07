# Tessera

**Make Claude Desktop remember your entire workspace.**

You have hundreds of documents — PRDs, meeting notes, decision logs, session records. Claude Desktop can read files you attach, but it can't search across your whole workspace. Tessera bridges that gap.

It indexes your local documents into a vector store and connects to Claude Desktop via MCP. When you ask a question, Claude automatically searches your files and answers with context.

```
You: "What did we decide about the auth flow?"

Claude: [searches 2,600 documents] Based on your decision log from Jan 15...
```

## How it works

1. **You point Tessera at your document folders** (Markdown, CSV, session logs)
2. **Tessera indexes them locally** using fastembed (ONNX) + LanceDB
3. **Claude Desktop searches them automatically** via MCP tools
4. **Only changed files are re-indexed** on each sync

Everything stays on your machine. No cloud, no API keys, no data leaves your laptop.

## Get started

### Install + Setup

```bash
git clone https://github.com/besslframework-stack/project-tessera.git
cd project-tessera

python3 -m venv .venv && source .venv/bin/activate
pip install -e .

tessera init
```

`tessera init` walks you through everything:
- Picks your document root directory
- Scans for folders with documents
- Lets you choose which to index
- Downloads the embedding model (~220MB, once)
- Generates `workspace.yaml` automatically
- Shows you the Claude Desktop config snippet
- Offers to index immediately

### Connect to Claude Desktop

`tessera init` prints the config snippet. Add it to your `claude_desktop_config.json`:

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

Restart Claude Desktop. You'll see "tessera" in the MCP integrations.

## What Claude can do with Tessera

| Tool | What it does |
|------|-------------|
| `search_documents` | Semantic + keyword hybrid search across all your docs |
| `ingest_documents` | Index your documents (first-time setup or full rebuild) |
| `sync_documents` | Incremental sync — only re-index changed files |
| `read_file` | Read any file's full content |
| `project_status` | See what's changed recently in each project |
| `extract_decisions` | Find past decisions from logs |
| `audit_prd` | Check PRD quality (section coverage, versioning) |
| `organize_files` | Move, rename, archive files |
| `suggest_cleanup` | Detect backup files, empty dirs, misplaced files |
| `list_sources` | See what's indexed |

## CLI commands

```bash
tessera init                    # Interactive setup
tessera ingest                  # Index all configured sources
tessera ingest --path ./docs    # Index a specific directory
tessera sync                    # Re-index only changed files
tessera status                  # Show all projects
tessera status my_project       # Show one project's status
```

## Architecture

```
Your documents (Markdown, CSV)
        |
   Parse & chunk (~800 chars)
        |
   Embed locally (fastembed/ONNX)
        |
   Store in LanceDB (local vector DB)
        |
   Expose via MCP server
        |
   Claude Desktop searches automatically
```

## Configuration

After `tessera init`, your `workspace.yaml` looks like:

```yaml
workspace:
  root: /Users/you/Documents
  name: my-workspace

sources:
  - path: project-alpha
    type: document
    project: project_alpha

projects:
  project_alpha:
    display_name: Project Alpha
    root: project-alpha
```

Edit it anytime to add/remove sources. Run `tessera sync` after changes.

## License

AGPL-3.0 — see [LICENSE](LICENSE).

For commercial licensing: bessl.framework@gmail.com
