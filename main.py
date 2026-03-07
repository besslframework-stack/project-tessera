"""Tessera CLI — personal knowledge RAG system.

Usage:
    python main.py ingest [--path PATH]   Ingest documents into the vector store
    python main.py sync                   Run incremental sync (new/changed/deleted files only)
    python main.py status [PROJECT_ID]    Show project status
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from llama_index.embeddings.ollama import OllamaEmbedding

from src.config import settings, workspace

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def _create_embed_model() -> OllamaEmbedding:
    return OllamaEmbedding(
        model_name=settings.models.embed_model,
        base_url=settings.models.ollama_base_url,
    )


def cmd_ingest(args: argparse.Namespace) -> None:
    """Run the ingestion pipeline."""
    from src.graph.vector_store import OntologyVectorStore
    from src.ingestion.pipeline import IngestionPipeline

    embed_model = _create_embed_model()
    vector_store = OntologyVectorStore(embed_model=embed_model)

    pipeline = IngestionPipeline(vector_store=vector_store)

    source_paths = [Path(p) for p in args.path] if args.path else None
    count, per_file = pipeline.run(source_paths=source_paths)
    print(f"Ingested {count} documents from {len(per_file)} files.")


def cmd_sync(args: argparse.Namespace) -> None:
    """Run incremental sync."""
    from src.graph.vector_store import OntologyVectorStore
    from src.ingestion.pipeline import IngestionPipeline
    from src.sync import FileMetaDB, run_incremental_sync

    meta_db = FileMetaDB(workspace.meta_db_path)
    embed_model = _create_embed_model()
    vector_store = OntologyVectorStore(embed_model=embed_model)
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

    # ingest
    ingest_parser = subparsers.add_parser("ingest", help="Ingest documents")
    ingest_parser.add_argument(
        "--path", nargs="+", help="Specific paths to ingest (default: Tier 1 sources)"
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
