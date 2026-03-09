# Changelog

## [0.5.2] - 2026-03-09

### Added
- **PDF file support** — `pymupdf`-based parser, optional dep (`pip install -e ".[pdf]"`)
- **Search result highlighting** — matching terms bold-wrapped in `search_documents` and `unified_search` results
- **`tessera check` improvements** — checks LanceDB index size, embedding model cache, Claude Desktop config with `cwd` validation, required/optional deps
- Total tools: 31 (was 30), total tests: 181 (was 173)

## [0.5.1] - 2026-03-09

Hotfix release addressing real-world installation issues reported by users.

### Fixed
- **[P0] CLI entrypoint bug** — `tessera` command now works from any directory (moved CLI to `src/cli.py` package)
- **[P0] MCP startup timeout** — auto-sync runs in background thread via `run_in_executor`, server starts in ~3s
- **[P1] Missing `cwd`** — README and `tessera init` now include `cwd` in Claude Desktop config example

### Added
- **XLSX file support** — `openpyxl`-based parser, optional dep (`pip install -e ".[xlsx]"`)
- **DOCX file support** — `python-docx`-based parser, optional dep (`pip install -e ".[docx]"`)
- **`view_file_full` tool** — Structured full-file view (CSV → table, XLSX → tables per sheet, MD/DOCX → text)
- **`tessera install-mcp` command** — Auto-configure Claude Desktop config with correct paths and `cwd`
- `format_csv_as_table()` — CSV full contents as markdown table
- `format_xlsx_as_table()` — XLSX full contents as markdown tables per sheet
- Total tools: 30 (was 28)

## [0.5.0] - 2026-03-09

First public release with comprehensive MCP toolset (28 tools, 173 tests).

### Core
- **Hybrid search** — Semantic + keyword search with LinearCombinationReranker
- **Cross-session memory** — remember, recall, learn with vector-indexed persistence
- **Knowledge graph** — Mermaid diagram of document relationships
- **Incremental sync** — SQLite-based file tracking, only re-indexes changed files
- **Auto-sync** — Background file watcher (polling, 30s interval, 5s debounce)

### Search
- **`unified_search`** — Search documents AND memories in one call
- **Search result caching** — TTL cache (60s) + LRU embedding cache (128 entries)
- **Content hash dedup** — SHA-256 at ingestion + 2-pass dedup at search time
- **Query preprocessing** — Markdown/URL stripping, whitespace normalization, Korean support
- **Query suggestions** — Zero-result searches suggest alternative queries (한/영 stop words)
- **Search highlighting** — Bold-wrapped word matches with context snippets
- **Version-aware ranking** — Latest document versions ranked higher

### Memory
- **Tag system** — `memory_tags` lists tags, `search_by_tag` filters by tag
- **Batch operations** — `export_memories` / `import_memories` (JSON format)
- **`list_memories`** / **`forget_memory`** for browsing and deletion

### Analytics & Operations
- **Search analytics** — SQLite query log with usage stats, top queries, zero-result tracking
- **Document freshness** — Detect stale documents by age threshold, grouped by project
- **Health check** — Comprehensive diagnostics (config, deps, index, stale docs)
- **`tessera_status`** — Tracked files, sync history, cache stats, config summary

### Workspace
- **Document similarity** — Find related documents by average embedding comparison
- **PRD auditor** — 13-section quality check with version sprawl detection
- **File organizer** — Move, rename, archive with path traversal protection
- **Project status** — HANDOFF.md summary, recent changes, file stats
- **Decision extraction** — Find past decisions from session/decision logs

### Infrastructure
- **Config externalization** — All tuning in `workspace.yaml` (search, ingestion, watcher, etc.)
- **Config validation** — Friendly errors for invalid values
- **Concurrency protection** — `threading.RLock` on all SQLite operations
- **Error recovery** — Individual file failures don't break sync
- **Logging** — RotatingFileHandler (5MB × 3 backups)
- **CI** — GitHub Actions with Python 3.11/3.12 matrix
- **CLI** — `tessera init`, `ingest`, `sync`, `status`, `check`, `version`

## [0.4.3] - 2026-03-08

### Fixed
- Fixed `glama.json` to match Glama schema (`$schema` + `maintainers`)
- Replaced LICENSE short notice with full AGPL-3.0 text for GitHub auto-detection

## [0.4.0] - 2026-03-07

### Added
- Hybrid search (semantic + keyword) with version ranking and deduplication
- Cross-session memory system (remember, recall, learn)
- Knowledge graph with Mermaid diagram output
- Incremental sync with SQLite file metadata tracking
- PRD auditor with 13-section quality checks
- File organizer with path traversal protection
- Project status and decision extraction tools
- Interactive `tessera init` CLI setup
- Glama badge and Docker support
