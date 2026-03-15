"""Tessera CLI — personal knowledge RAG system.

Usage:
    tessera setup                         One-command setup for new users
    tessera init                          Interactive setup (workspace.yaml + first index)
    tessera ingest [--path PATH]          Ingest documents into the vector store
    tessera sync                          Incremental sync (new/changed/deleted files only)
    tessera status [PROJECT_ID]           Show project status
    tessera version                       Show version
    tessera check                         Check workspace health
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Project root is one level up from src/
PROJECT_ROOT = Path(__file__).parent.parent


def cmd_setup(args: argparse.Namespace) -> None:
    """One-command setup: workspace.yaml + embedding model + Claude Desktop config."""
    project_root = PROJECT_ROOT
    yaml_path = project_root / "workspace.yaml"

    print("Setting up Tessera...")
    print()

    # Step 1: Create workspace.yaml if missing
    if yaml_path.exists():
        print(f"workspace.yaml already exists at {yaml_path}")
    else:
        try:
            import yaml

            workspace_name = project_root.name
            config = {
                "workspace": {
                    "root": str(project_root),
                    "name": workspace_name,
                },
                "sources": [
                    {"path": ".", "type": "document", "project": "_global"},
                ],
                "projects": {},
                "archive": {"directory": "archive"},
                "models": {
                    "embed_model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
                },
                "search": {
                    "max_top_k": 50,
                    "reranker_weight": 0.7,
                    "fetch_multiplier": 6,
                    "result_text_limit": 1500,
                    "unified_text_limit": 800,
                },
                "ingestion": {
                    "chunk_size": 1024,
                    "chunk_overlap": 100,
                    "max_node_chars": 800,
                },
                "watcher": {
                    "poll_interval": 30.0,
                    "debounce": 5.0,
                },
                "sync": {
                    "auto_sync": True,
                    "extensions": [".md", ".csv"],
                    "ignore": [
                        "**/.venv/**", "**/.next/**", "**/node_modules/**",
                        "**/__pycache__/**", "**/data/lancedb/**",
                        "**/data/logs/**", "**/archive/**", "**/.git/**",
                    ],
                },
            }

            with open(yaml_path, "w") as f:
                yaml.dump(
                    config, f,
                    default_flow_style=False,
                    allow_unicode=True,
                    sort_keys=False,
                )
            print(f"Created workspace.yaml at {yaml_path}")
        except Exception as exc:
            print(f"Failed to create workspace.yaml: {exc}")
            print("You can create it manually with `tessera init`.")

    # Step 2: Pre-download embedding model
    print()
    print("Downloading embedding model (first time only)...")
    try:
        from fastembed import TextEmbedding

        TextEmbedding(
            model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        )
        print("Embedding model ready.")
    except ImportError:
        print("fastembed not installed. Run `pip install -e .` first, then re-run setup.")
    except Exception as exc:
        print(f"Could not download embedding model: {exc}")
        print("The model will be downloaded automatically on first use.")

    # Step 3: Configure Claude Desktop
    print()
    try:
        mcp_args = argparse.Namespace(force=True)
        cmd_install_mcp(mcp_args)
    except Exception as exc:
        print(f"Could not configure Claude Desktop automatically: {exc}")
        print("You can configure it later with `tessera install-mcp`.")

    # Summary
    print()
    print("=" * 50)
    print("Setup complete! Restart Claude Desktop to start using Tessera.")
    print("=" * 50)


def cmd_init(args: argparse.Namespace) -> None:
    """Interactive setup: create workspace.yaml and optionally index."""
    project_root = PROJECT_ROOT
    yaml_path = project_root / "workspace.yaml"
    env_path = project_root / ".env"

    print("=" * 50)
    print("  Tessera Setup")
    print("=" * 50)
    print()

    # Step 1: Workspace root
    if yaml_path.exists():
        print(f"workspace.yaml already exists at {yaml_path}")
        overwrite = input("Overwrite? [y/N] ").strip().lower()
        if overwrite != "y":
            print("Keeping existing workspace.yaml")
            _step_claude_desktop(project_root)
            return

    default_root = str(Path.home() / "Documents")
    root = input(f"Where are your documents? [{default_root}] ").strip()
    if not root:
        root = default_root

    root_path = Path(root).expanduser().resolve()
    if not root_path.exists():
        print(f"Directory not found: {root_path}")
        create = input("Create it? [Y/n] ").strip().lower()
        if create != "n":
            root_path.mkdir(parents=True, exist_ok=True)
            print(f"Created: {root_path}")
        else:
            print("Aborted.")
            return

    # Step 2: Scan for indexable directories
    print(f"\nScanning {root_path} for documents...")
    sources = []
    projects = {}

    skip_dirs = {
        "node_modules", ".venv", "__pycache__", ".git", "archive",
        ".next", "dist", "build", ".cache",
    }

    for child in sorted(root_path.iterdir()):
        if not child.is_dir():
            continue
        if child.name.startswith(".") or child.name in skip_dirs:
            continue

        md_count = len(list(child.rglob("*.md")))
        csv_count = len(list(child.rglob("*.csv")))
        total = md_count + csv_count

        if total == 0:
            continue

        rel = child.name
        print(f"  Found: {rel}/ ({md_count} md, {csv_count} csv)")
        include = input(f"    Index this directory? [Y/n] ").strip().lower()
        if include == "n":
            continue

        project_id = rel.lower().replace("-", "_").replace(" ", "_")
        sources.append({"path": rel, "type": "document", "project": project_id})
        projects[project_id] = {
            "display_name": rel.replace("-", " ").replace("_", " ").title(),
            "root": rel,
        }

    if not sources:
        print("\nNo subdirectories with documents found.")
        print(f"Will index {root_path} directly.")
        sources.append({"path": ".", "type": "document", "project": "_global"})

    # Step 3: Write workspace.yaml
    import yaml

    config = {
        "workspace": {"root": str(root_path), "name": root_path.name},
        "sources": sources,
        "projects": projects,
        "archive": {"directory": "archive"},
        "models": {
            "embed_model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        },
        "search": {
            "max_top_k": 50,
            "reranker_weight": 0.7,
            "fetch_multiplier": 6,
            "result_text_limit": 1500,
            "unified_text_limit": 800,
        },
        "ingestion": {
            "chunk_size": 1024,
            "chunk_overlap": 100,
            "max_node_chars": 800,
        },
        "watcher": {
            "poll_interval": 30.0,
            "debounce": 5.0,
        },
        "sync": {
            "auto_sync": True,
            "extensions": [".md", ".csv"],
            "ignore": [
                "**/.venv/**", "**/.next/**", "**/node_modules/**",
                "**/__pycache__/**", "**/data/lancedb/**",
                "**/data/logs/**", "**/archive/**", "**/.git/**",
            ],
        },
    }

    with open(yaml_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    print(f"\nCreated: {yaml_path}")

    # Step 4: .env
    if not env_path.exists():
        example = project_root / ".env.example"
        if example.exists():
            shutil.copy(example, env_path)
            print(f"Created: {env_path}")

    # Step 5: Claude Desktop config hint
    _step_claude_desktop(project_root)

    # Step 6: Offer to ingest now
    print()
    ingest_now = input("Index your documents now? [Y/n] ").strip().lower()
    if ingest_now != "n":
        print("\nEmbedding model will be downloaded on first run (~220MB)...")
        import importlib
        import src.config
        importlib.reload(src.config)
        args_ns = argparse.Namespace(path=None)
        cmd_ingest(args_ns)
    else:
        print("\nRun later: tessera ingest")

    print("\nSetup complete!")


def _step_claude_desktop(project_root: Path) -> None:
    """Print Claude Desktop config snippet."""
    venv_python = project_root / ".venv" / "bin" / "python"
    mcp_server = project_root / "mcp_server.py"

    print("\n" + "-" * 50)
    print("Claude Desktop Integration")
    print("-" * 50)
    print()
    print("Add this to your claude_desktop_config.json:")
    print()
    print('  "tessera": {')
    print(f'    "command": "{venv_python}",')
    print(f'    "args": ["{mcp_server}"],')
    print(f'    "cwd": "{project_root}"')
    print("  }")
    print()

    config_locations = [
        Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json",
        Path.home() / ".config" / "claude" / "claude_desktop_config.json",
    ]
    for loc in config_locations:
        if loc.exists():
            print(f"Config file: {loc}")
            break


def cmd_ingest(args: argparse.Namespace) -> None:
    """Run the ingestion pipeline."""
    from src.graph.vector_store import OntologyVectorStore
    from src.ingestion.pipeline import IngestionPipeline

    vector_store = OntologyVectorStore()
    pipeline = IngestionPipeline(vector_store=vector_store)

    source_paths = [Path(p) for p in args.path] if args.path else None
    count, per_file = pipeline.run(source_paths=source_paths)
    print(f"Ingested {count} documents from {len(per_file)} files.")


def cmd_sync(args: argparse.Namespace) -> None:
    """Run incremental sync."""
    from src.config import workspace
    from src.graph.vector_store import OntologyVectorStore
    from src.ingestion.pipeline import IngestionPipeline
    from src.sync import FileMetaDB, run_incremental_sync

    meta_db = FileMetaDB(workspace.meta_db_path)
    vector_store = OntologyVectorStore()
    pipeline = IngestionPipeline(vector_store=vector_store)

    def _ingest(paths: list[Path]) -> tuple[int, dict[str, int]]:
        return pipeline.run(source_paths=paths)

    result = run_incremental_sync(
        ws=workspace,
        meta_db=meta_db,
        vector_store_delete_fn=vector_store.delete_by_source,
        ingest_fn=_ingest,
    )

    print(f"Sync complete: {result.summary()}")
    if result.new:
        print(f"  New: {', '.join(str(p.name) for p in result.new)}")
    if result.changed:
        print(f"  Changed: {', '.join(str(p.name) for p in result.changed)}")
    if result.deleted:
        print(f"  Deleted: {', '.join(Path(p).name for p in result.deleted)}")

    meta_db.close()


def cmd_status(args: argparse.Namespace) -> None:
    """Show project status."""
    from src.project_status import get_all_projects_summary, get_project_status

    if args.project:
        print(get_project_status(args.project))
    else:
        print(get_all_projects_summary())


def cmd_version(args: argparse.Namespace) -> None:
    """Show Tessera version."""
    try:
        from importlib.metadata import version
        v = version("project-tessera")
    except Exception:
        import tomllib
        with open(PROJECT_ROOT / "pyproject.toml", "rb") as f:
            v = tomllib.load(f)["project"]["version"]
    print(f"Tessera v{v}")


def cmd_check(args: argparse.Namespace) -> None:
    """Check workspace health: config, dependencies, index."""
    import json
    import platform

    project_root = PROJECT_ROOT
    yaml_path = project_root / "workspace.yaml"

    # --- Version ---
    try:
        from importlib.metadata import version
        ver = version("project-tessera")
    except Exception:
        try:
            import tomllib
            with open(project_root / "pyproject.toml", "rb") as f:
                ver = tomllib.load(f)["project"]["version"]
        except Exception:
            ver = "unknown"

    print(f"Tessera v{ver}")
    print()

    ok_sym = "\u2713"
    fail_sym = "\u2717"
    issues = 0

    def _ok(msg: str) -> None:
        print(f"{ok_sym} {msg}")

    def _fail(msg: str) -> None:
        nonlocal issues
        issues += 1
        print(f"{fail_sym} {msg}")

    # 1. workspace.yaml
    if yaml_path.exists():
        _ok("workspace.yaml found")
    else:
        _fail("workspace.yaml not found -- run `tessera init`")

    # 2. LanceDB index
    lancedb_dir = project_root / "data" / "lancedb"
    if lancedb_dir.exists():
        try:
            import lancedb as _lancedb
            db = _lancedb.connect(str(lancedb_dir))
            table_names = db.table_names()
            total_rows = 0
            for tname in table_names:
                tbl = db.open_table(tname)
                total_rows += tbl.count_rows()
            _ok(f"LanceDB index: {total_rows:,} nodes")
        except Exception:
            _ok("LanceDB index: directory exists (could not read row count)")
    else:
        _fail("LanceDB index not found -- run `tessera ingest`")

    # 3. Embedding model cached
    fastembed_cache = Path.home() / ".cache" / "fastembed"
    if fastembed_cache.exists() and any(fastembed_cache.iterdir()):
        _ok("Embedding model cached")
    else:
        _fail("Embedding model not cached -- will download on first ingest (~220MB)")

    # 4. Claude Desktop config
    if platform.system() == "Darwin":
        config_path = (
            Path.home() / "Library" / "Application Support" / "Claude"
            / "claude_desktop_config.json"
        )
    else:
        config_path = Path.home() / ".config" / "claude" / "claude_desktop_config.json"

    if config_path.exists():
        try:
            with open(config_path) as f:
                desktop_cfg = json.load(f)
            tessera_cfg = desktop_cfg.get("mcpServers", {}).get("tessera")
            if tessera_cfg:
                _ok("Claude Desktop config: tessera registered")
                cwd_val = tessera_cfg.get("cwd", "")
                cwd_match = Path(cwd_val).resolve() == project_root.resolve() if cwd_val else False
                sym = ok_sym if cwd_match else fail_sym
                if not cwd_match:
                    issues += 1
                print(f"  cwd: {cwd_val or '(not set)'} {sym}")
            else:
                _fail("Claude Desktop config: tessera not registered -- run `tessera install-mcp`")
        except Exception as exc:
            _fail(f"Claude Desktop config: parse error ({exc})")
    else:
        _fail("Claude Desktop config not found")

    # 5. Required Python dependencies
    print()
    required_deps = {
        "fastembed": "fastembed",
        "lancedb": "lancedb",
        "mcp": "mcp",
    }
    for mod, label in required_deps.items():
        try:
            __import__(mod)
            _ok(f"{label} installed")
        except ImportError:
            _fail(f"{label} not installed -- run `pip install -e .`")

    # 6. Optional dependencies
    print()
    optional_deps = {
        "openpyxl": "openpyxl (xlsx support)",
        "docx": "python-docx (docx support)",
        "pymupdf": "pymupdf (pdf support)",
    }
    for mod, label in optional_deps.items():
        try:
            __import__(mod)
            print(f"  {label}: installed")
        except ImportError:
            print(f"  {label}: not installed")

    # Summary
    print()
    if issues:
        print(f"{issues} issue(s) found.")
    else:
        print("All checks passed.")


def cmd_install_mcp(args: argparse.Namespace) -> None:
    """Auto-configure Claude Desktop to use Tessera MCP."""
    import json
    import shutil

    # Find Claude Desktop config
    config_locations = [
        Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json",
        Path.home() / ".config" / "claude" / "claude_desktop_config.json",
    ]

    config_path = None
    for loc in config_locations:
        if loc.exists():
            config_path = loc
            break

    if config_path is None:
        config_path = config_locations[0]
        config_path.parent.mkdir(parents=True, exist_ok=True)

    # Read existing config or create new
    if config_path.exists():
        with open(config_path) as f:
            config = json.load(f)
    else:
        config = {}

    if "mcpServers" not in config:
        config["mcpServers"] = {}

    # Check if tessera already configured
    force = getattr(args, "force", False)
    existing = config["mcpServers"].get("tessera")
    if existing and not force:
        print(f"Tessera already configured in {config_path}")
        print(f"  command: {existing.get('command', '?')}")
        update = input("Update to current paths? [y/N] ").strip().lower()
        if update != "y":
            print("Keeping existing config.")
            return

    # Determine best command: uvx > venv python > system python
    project_root = Path(__file__).parent.parent
    uvx_path = shutil.which("uvx")
    venv_python = project_root / ".venv" / "bin" / "python"

    if uvx_path:
        # uvx: no venv needed, works anywhere
        tessera_config = {
            "command": "uvx",
            "args": ["--from", "project-tessera", "tessera-mcp"],
        }
        method = "uvx (recommended)"
    elif venv_python.exists():
        # Local venv: traditional method
        mcp_server = project_root / "mcp_server.py"
        tessera_config = {
            "command": str(venv_python),
            "args": [str(mcp_server)],
            "cwd": str(project_root),
        }
        method = "venv"
    else:
        # Fallback: assume tessera-mcp is in PATH
        tessera_config = {
            "command": "tessera-mcp",
        }
        method = "system PATH"

    config["mcpServers"]["tessera"] = tessera_config

    with open(config_path, "w") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print(f"Tessera MCP configured in: {config_path}")
    print(f"  method: {method}")
    for k, v in tessera_config.items():
        print(f"  {k}: {v}")
    print()
    print("Restart Claude Desktop to apply changes.")


def cmd_serve(args: argparse.Namespace) -> None:
    """Start the MCP server."""
    sse_port = getattr(args, "sse", None)
    if sse_port is not None:
        # Inject --sse arg for mcp_server.main() to parse
        import sys
        sys.argv = ["tessera-mcp", "--sse", str(sse_port)]
    from mcp_server import main as mcp_main
    mcp_main()


def cmd_api(args: argparse.Namespace) -> None:
    """Start the HTTP API server."""
    port = getattr(args, "port", 8394)
    host = getattr(args, "host", "127.0.0.1")
    print(f"Starting Tessera HTTP API on {host}:{port}")
    import uvicorn
    uvicorn.run("src.http_server:app", host=host, port=port)


def cmd_migrate(args: argparse.Namespace) -> None:
    """Run data migration."""
    from src.migrate import format_migration_result, run_migration
    dry_run = getattr(args, "dry_run", False)
    result = run_migration(dry_run=dry_run)
    print(format_migration_result(result))


def cli() -> None:
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Tessera — Personal Knowledge RAG",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # serve
    serve_parser = subparsers.add_parser("serve", help="Start MCP server")
    serve_parser.add_argument("--sse", nargs="?", const=8395, type=int, metavar="PORT",
                              help="Run in SSE mode for remote access (default port: 8395)")
    serve_parser.set_defaults(func=cmd_serve)

    # setup
    setup_parser = subparsers.add_parser("setup", help="One-command setup for new users")
    setup_parser.set_defaults(func=cmd_setup)

    # init
    init_parser = subparsers.add_parser("init", help="Interactive setup")
    init_parser.set_defaults(func=cmd_init)

    # ingest
    ingest_parser = subparsers.add_parser("ingest", help="Ingest documents")
    ingest_parser.add_argument(
        "--path", nargs="+", help="Specific paths to ingest (default: all sources)"
    )
    ingest_parser.set_defaults(func=cmd_ingest)

    # sync
    sync_parser = subparsers.add_parser("sync", help="Run incremental sync")
    sync_parser.set_defaults(func=cmd_sync)

    # status
    status_parser = subparsers.add_parser("status", help="Show project status")
    status_parser.add_argument(
        "project", nargs="?", default=None, help="Project ID (default: all projects)"
    )
    status_parser.set_defaults(func=cmd_status)

    # version
    version_parser = subparsers.add_parser("version", help="Show version")
    version_parser.set_defaults(func=cmd_version)

    # check
    check_parser = subparsers.add_parser("check", help="Check workspace health")
    check_parser.set_defaults(func=cmd_check)

    # api
    api_parser = subparsers.add_parser("api", help="Start HTTP API server")
    api_parser.add_argument("--port", type=int, default=8394, help="Port (default: 8394)")
    api_parser.add_argument("--host", default="127.0.0.1", help="Host (default: 127.0.0.1)")
    api_parser.set_defaults(func=cmd_api)

    # migrate
    migrate_parser = subparsers.add_parser("migrate", help="Run data migration to latest schema")
    migrate_parser.add_argument("--dry-run", action="store_true", help="Preview changes without migrating")
    migrate_parser.set_defaults(func=cmd_migrate)

    # install-mcp
    install_parser = subparsers.add_parser("install-mcp", help="Configure Claude Desktop for Tessera")
    install_parser.add_argument(
        "--force", action="store_true", help="Overwrite existing config without prompting"
    )
    install_parser.set_defaults(func=cmd_install_mcp)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    cli()
