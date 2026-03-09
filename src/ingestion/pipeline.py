"""Main ingestion pipeline: load, parse, enrich, and index documents."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from src.config import settings, workspace
from src.ingestion.csv_parser import parse_csv_file
from src.ingestion.docx_parser import parse_docx_file
from src.ingestion.xlsx_parser import parse_xlsx_file
from src.ingestion.markdown_parser import parse_markdown_directory, parse_markdown_file
from src.ingestion.metadata_extractor import enrich_documents
from src.ingestion.session_parser import parse_session_directory, parse_session_file

if TYPE_CHECKING:
    from llama_index.core.schema import Document

    from src.graph.vector_store import OntologyVectorStore

logger = logging.getLogger(__name__)

# Directories whose names indicate they contain session logs
_SESSION_DIR_INDICATORS = ("claude_sessions", "session_logs", "sessions")


class IngestionPipeline:
    """Orchestrates document loading, parsing, enrichment, and indexing."""

    def __init__(self, vector_store: "OntologyVectorStore") -> None:
        self.vector_store = vector_store

    def run(self, source_paths: list[Path] | None = None) -> tuple[int, dict[str, int]]:
        """Run the full ingestion pipeline.

        Args:
            source_paths: Specific paths to ingest. If None, uses all workspace sources.

        Returns:
            Tuple of (total_count, per_file_counts).
        """
        if source_paths is None:
            source_paths = workspace.all_source_paths()

        documents = self._load_documents(source_paths)
        documents = enrich_documents(documents)

        # Exclude metadata from embedding text to avoid context length overflow
        _exclude_keys = [
            "source_path", "file_name", "file_type", "doc_type", "project",
            "version", "date", "title", "section",
            "detected_version", "detected_date", "detected_priority",
            "detected_tier", "detected_phase", "detected_event_name",
            "detected_person", "detected_req_id",
        ]
        for doc in documents:
            doc.excluded_embed_metadata_keys = _exclude_keys
            doc.excluded_llm_metadata_keys = _exclude_keys

        logger.info("Loaded and enriched %d documents", len(documents))

        # Build per-file chunk counts
        per_file: dict[str, int] = {}
        for doc in documents:
            src = doc.metadata.get("source_path", "unknown")
            per_file[src] = per_file.get(src, 0) + 1

        # Index into vector store
        self.vector_store.index_documents(documents)

        return len(documents), per_file

    def load_only(self, source_paths: list[Path] | None = None) -> list["Document"]:
        """Load and enrich documents without indexing.

        Useful for inspection and testing.
        """
        if source_paths is None:
            source_paths = workspace.all_source_paths()

        documents = self._load_documents(source_paths)
        documents = enrich_documents(documents)
        logger.info("Loaded and enriched %d documents (load_only)", len(documents))
        return documents

    def _load_documents(self, source_paths: list[Path]) -> list["Document"]:
        """Load documents from all source paths."""
        all_docs: list["Document"] = []

        for path in source_paths:
            if not path.exists():
                logger.warning("Source path does not exist, skipping: %s", path)
                continue

            try:
                if path.is_file():
                    docs = self._load_single_file(path)
                else:
                    docs = self._load_directory(path)
            except Exception as exc:
                logger.error("Failed to load %s: %s", path, exc)
                docs = []

            logger.debug("Loaded %d docs from %s", len(docs), path)
            all_docs.extend(docs)

        return all_docs

    def _load_single_file(self, file_path: Path) -> list["Document"]:
        """Load a single file based on its extension."""
        suffix = file_path.suffix.lower()
        if suffix == ".md":
            # Determine if it's a session log by its parent directory name
            if _is_session_dir(file_path.parent):
                return parse_session_file(file_path)
            return parse_markdown_file(file_path)
        elif suffix == ".csv":
            return parse_csv_file(file_path)
        elif suffix == ".docx":
            return parse_docx_file(file_path)
        elif suffix in (".xlsx", ".xls"):
            return parse_xlsx_file(file_path)
        logger.debug("Unsupported file type, skipping: %s", file_path)
        return []

    def _load_directory(self, dir_path: Path) -> list["Document"]:
        """Load all supported files from a directory."""
        # Session log directories get the specialised parser
        if _is_session_dir(dir_path):
            return parse_session_directory(dir_path)

        docs: list["Document"] = []
        docs.extend(parse_markdown_directory(dir_path))

        # Also pick up CSV files in the directory tree
        for csv_file in sorted(dir_path.rglob("*.csv")):
            try:
                docs.extend(parse_csv_file(csv_file))
            except Exception as exc:
                logger.error("Failed to parse CSV %s: %s", csv_file, exc)

        # Also pick up DOCX files in the directory tree
        for docx_file in sorted(dir_path.rglob("*.docx")):
            try:
                docs.extend(parse_docx_file(docx_file))
            except Exception as exc:
                logger.error("Failed to parse DOCX %s: %s", docx_file, exc)

        # Also pick up XLSX files in the directory tree
        for xlsx_file in sorted(dir_path.rglob("*.xlsx")):
            try:
                docs.extend(parse_xlsx_file(xlsx_file))
            except Exception as exc:
                logger.error("Failed to parse XLSX %s: %s", xlsx_file, exc)

        return docs


def _is_session_dir(path: Path) -> bool:
    """Return True if the path looks like a session log directory."""
    name_lower = path.name.lower()
    return any(indicator in name_lower for indicator in _SESSION_DIR_INDICATORS)
