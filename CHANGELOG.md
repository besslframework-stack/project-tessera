# Changelog

## [0.7.4] - 2026-03-10

### Added
- **Context Window Builder** — assembles optimal context (memories + documents) within a token budget for cross-AI use
- **`context_window` MCP tool** — query-based context assembly with configurable token budget and document inclusion
- **`src/context_window.py`** — `estimate_tokens()`, `build_context_window()`, `format_context_summary()`
- **Token estimation** — chars/4 heuristic for mixed English/Korean text
- **Priority ordering** — highest-relevance memories first, documents second, truncation when budget exceeded
- **`tests/test_context_window.py`** — 24 tests (estimation, formatting, budget, truncation, ordering)
- Total tools: 41, total tests: 345

## [0.7.3] - 2026-03-10

### Added
- **Decision Tracker** — groups `category=decision` memories by topic similarity (Jaccard), detects when decisions on the same topic evolved over time
- **`decision_timeline` MCP tool** — view how past decisions changed ("we used PostgreSQL → switched to MySQL")
- **`src/decision_tracker.py`** — `_extract_topic_keywords()`, `_topic_similarity()`, `get_decision_timeline()`, `format_decision_timeline()`
- **Korean tokenization fix** — separate `[a-zA-Z]+|[가-힣]+` regex prevents Korean particles merging with English words (e.g. "postgresql을" → "postgresql" + "을")
- **`tests/test_decision_tracker.py`** — 18 tests (keyword extraction, similarity, grouping, change detection, formatting)
- Total tools: 40, total tests: 321

## [0.7.2] - 2026-03-10

### Added
- **Temporal Index** — `recall` now supports `since` and `until` date filters for time-based queries
- **Category filter** on `recall` — filter memories by category (decision, preference, fact)
- **Combined filters** — use time + category together (e.g. "decisions from last week")
- **`tests/test_temporal.py`** — 7 tests for time and category filtering
- Total tools: 39, total tests: 303

### Changed
- **`recall_memories()`** — new `since`, `until`, `category` parameters with post-filter logic
- **`core.recall()`** — accepts and passes through filter parameters
- **MCP `recall` tool** — updated description, accepts `since`, `until`, `category` arguments

## [0.7.1] - 2026-03-10

### Added
- **40+ file type support** — massively expanded from 5 to 40+ supported formats
- **Universal text/code parser** (`src/ingestion/text_parser.py`) — handles 50+ extensions:
  - Code: `.py`, `.js`, `.ts`, `.tsx`, `.jsx`, `.java`, `.go`, `.rs`, `.rb`, `.php`, `.c`, `.cpp`, `.h`, `.swift`, `.kt`, `.sh`, `.sql`, `.cs`, `.dart`, `.r`, `.lua`, `.scala`, `.pl`
  - Config: `.json`, `.yaml`, `.yml`, `.toml`, `.xml`, `.ini`, `.cfg`, `.conf`, `.env`
  - Text: `.txt`, `.rst`, `.log`
  - Web: `.html`, `.htm`, `.css`, `.scss`, `.less`, `.svg` (with HTML tag stripping)
  - DevOps: `.dockerfile`, `.makefile`, `.tf`, `.hcl`, `.proto`, `.graphql`
- **Image OCR parser** (`src/ingestion/image_parser.py`) — `.png`, `.jpg`, `.jpeg`, `.gif`, `.bmp`, `.tiff`, `.webp`
  - OCR via pytesseract (Korean + English), optional dep: `pip install project-tessera[ocr]`
  - Falls back to metadata-only Document with EXIF extraction when OCR unavailable
- **`[ocr]` and `[images]` optional deps** in pyproject.toml
- **Language detection** — auto-detects programming language from extension
- **`tests/test_text_parser.py`** — 25 tests (detection, HTML stripping, parsing)
- **`tests/test_image_parser.py`** — 4 tests (metadata, OCR mock, no-OCR fallback)
- Total tools: 39, total tests: 296

### Changed
- **Default extensions** — expanded from `[".md", ".csv"]` to 30+ formats including code, config, images
- **Ingestion pipeline** — routes new file types to appropriate parsers
- **README** — updated supported file types table

## [0.7.0] - 2026-03-10

### Sponge Phase Complete — Tessera now learns automatically

Tessera no longer requires manual "remember this" commands. It auto-detects decisions,
preferences, and facts from every conversation and saves them with deduplication.

### Added
- **`toggle_auto_learn` tool** — turn auto-learning on/off or check status
- **`review_learned` tool** — review recently auto-learned memories (auto-digest, session summary)
- **`AutoLearnConfig` dataclass** — `enabled`, `min_confidence`, `min_interactions_for_summary` settings in workspace.yaml
- **workspace.yaml `auto_learn` section** — configure auto-learning behavior
- **`tests/test_auto_learn.py`** — 9 tests for toggle, review, and config
- Total tools: 39, total tests: 267

### Sponge Phase summary (v0.6.4 → v0.7.0)
| Version | Feature | Tests added |
|---------|---------|-------------|
| v0.6.4 | Interaction Log + Session Boundary | 9 |
| v0.6.5 | Auto-Extract engine + Core extraction | 0 |
| v0.6.6 | Memory Dedup + Auto-Extract tests | 36 |
| v0.6.7 | Memory Categories | 17 |
| v0.6.9 | Session Summary | 12 |
| v0.7.0 | Sponge Complete (toggle + review) | 9 |

## [0.6.9] - 2026-03-10

### Added
- **Session Summary** — MCP server shutdown 시 해당 세션의 interaction을 자동 요약해서 memory로 저장
- **`src/session_summary.py`** — 세션 요약 생성기 (도구 사용 통계, 검색 쿼리, 기억된 내용 추출)
- **`generate_session_summary()`** — interaction 리스트에서 텍스트 요약 생성 (LLM 호출 없음)
- **`save_session_summary()`** — 요약을 `category: context` memory로 저장 + 인덱싱
- **`tests/test_session_summary.py`** — 12 tests (요약 생성, 저장, 에러 처리)
- Total tools: 37, total tests: 258

### Changed
- **`mcp_server.py` lifespan** — `finally` 블록에서 세션 요약 자동 저장

### Note
- v0.6.8 (Session Boundary)는 v0.6.4에서 session_id 구현 시 이미 완료됨 — 스킵

## [0.6.7] - 2026-03-10

### Added
- **Memory Categories** — memories are auto-categorized as `decision`, `preference`, `fact`, `reference`, `context`, or `general` using pattern matching from `auto_extract.py`
- **`memory_categories` tool** — list all categories with counts
- **`search_by_category` tool** — filter memories by category (e.g. "show me all my decisions")
- **`_detect_category()` function** — auto-detects category from content text
- **`category` field in frontmatter** — every new memory file now includes `category:` in YAML frontmatter
- **`tests/test_memory_categories.py`** — 17 tests for category detection, listing, and search
- Total tools: 37, total tests: 246

### Changed
- **`save_memory()`** — new `category` parameter; auto-detected if not provided
- **`index_memory()`** — parses and indexes `category` field from frontmatter
- **`recall_memories()`** — includes `category` in search results

## [0.6.6] - 2026-03-10

### Added
- **Memory Dedup** — `save_memory()` and `learn_and_index()` now check cosine similarity before saving. If existing memory is >92% similar, the save is skipped and existing path is returned
- **`_check_duplicate()` function** — vector similarity search against existing memories in LanceDB
- **`tests/test_auto_extract.py`** — 24 tests for the auto-extract pattern matching engine (Korean + English)
- **`tests/test_memory_dedup.py`** — 12 tests for dedup logic (`_check_duplicate`, `save_memory` dedup, `learn_and_index` dedup)
- Total tools: 35, total tests: 229

### Changed
- **`save_memory()`** — new `dedup` and `dedup_threshold` parameters (defaults: `True`, `0.92`)
- **`learn_and_index()`** — returns `deduplicated` flag and `similarity` score when duplicate is detected

## [0.6.5] - 2026-03-10

### Added
- **Auto-Extract engine** (`src/auto_extract.py`) — regex + heuristic pattern matching to detect decisions, preferences, and facts from text (Korean + English)
- **`digest_conversation` tool** — extracts and saves knowledge from current session automatically
- **`src/core.py`** — interface-agnostic business logic layer (35 functions), enabling future HTTP API for ChatGPT/Gemini/extensions
- Architecture diagram in README

### Changed
- **`mcp_server.py` refactored** — 1315 lines → 608 lines. Now a thin MCP wrapper over `src/core.py`
- **`remember` tool** — auto-detects category (decision/preference/fact) from content
- README rewritten with new vision: "Personal Knowledge Layer for AI"
- Total tools: 35, total tests: 193

## [0.6.4] - 2026-03-10

### Added
- **Interaction Log** — every MCP tool call is automatically recorded to SQLite (tool name, input, output, duration, session ID)
- **`session_interactions` tool** — view what happened in the current or past sessions
- **`recent_sessions` tool** — view summary of recent sessions with interaction counts
- Logging added to core tools: `search_documents`, `unified_search`, `remember`, `recall`, `learn`
- Total tools: 33, total tests: 193

### Changed
- Package description updated to "Personal Knowledge Layer for AI"

## [0.6.3] - 2026-03-10

### Added
- **`TESSERA_WORKSPACE` env var** — set document folder path via environment variable, enables uvx users to specify workspace without workspace.yaml
- 3 new config tests (total: 184)

## [0.6.2] - 2026-03-10

### Added
- **`tessera-mcp` entry point** — run MCP server directly via `tessera-mcp` command
- **uvx-first Claude Desktop config** — `tessera install-mcp` auto-detects uvx and generates zero-venv config
- uvx install option in README

### Changed
- `cmd_install_mcp` now prioritizes uvx > venv > system PATH

## [0.6.0] - 2026-03-09

Zero-config experience — Tessera works without workspace.yaml.

### Added
- **`tessera setup` one-command** — creates workspace.yaml, downloads embedding model, configures Claude Desktop in one step
- **Auto-detect workspace** — MCP server starts without workspace.yaml, auto-discovers files in current directory
- **Friendly error messages** — all user-facing errors rewritten to be action-oriented, no technical jargon

### Changed
- `load_workspace_config()` gracefully falls back to auto-detected defaults when no config file exists

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
