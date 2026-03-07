"""Tessera CLI — personal knowledge RAG system.

Usage:
    tessera init                          Interactive setup (workspace.yaml + first index)
    tessera ingest [--path PATH]          Ingest documents into the vector store
    tessera sync                          Incremental sync (new/changed/deleted files only)
    tessera status [PROJECT_ID]           Show project status
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def cmd_init(args: argparse.Namespace) -> None:
    """Interactive setup: create workspace.yaml and optionally index."""
    project_root = Path(__file__).parent
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
        "sync": {
            "auto_sync": True,
            "extensions": [".md", ".csv"],
            "ignore": [
                "**/.venv/**", "**/.next/**", "**/node_modules/**",
                "**/__pycache__/**", "**/data/lancedb/**",
                "**/archive/**", "**/.git/**",
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
    print(f'    "args": ["{mcp_server}"]')
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


def cli() -> None:
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Tessera — Personal Knowledge RAG",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

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

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    cli()
