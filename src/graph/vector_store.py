"""LanceDB vector store wrapper for document chunk embeddings."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import lancedb

from src.config import settings
from src.embedding import get_embed_model

if TYPE_CHECKING:
    from llama_index.core.schema import Document

logger = logging.getLogger(__name__)

_TABLE_NAME = "ontology_chunks"
_MAX_NODE_CHARS = 800

# Metadata keys to exclude from embedding text
_EXCLUDE_KEYS = [
    "source_path", "file_name", "file_type", "doc_type", "project",
    "version", "date", "title", "section",
    "detected_version", "detected_date", "detected_priority",
    "detected_tier", "detected_phase", "detected_person", "detected_req_id",
]


class OntologyVectorStore:
    """Manages LanceDB vector store for document chunk embeddings."""

    def __init__(self) -> None:
        db_path = str(settings.data.lancedb_path)
        Path(db_path).mkdir(parents=True, exist_ok=True)
        self._db = lancedb.connect(db_path)
        self._embed_model = get_embed_model()

    def index_documents(self, documents: list[Document]) -> None:
        """Split documents into chunks, embed, and store in LanceDB."""
        from llama_index.core.node_parser import SentenceSplitter

        # Split into nodes
        splitter = SentenceSplitter(chunk_size=1024, chunk_overlap=100)
        nodes = splitter.get_nodes_from_documents(documents, show_progress=True)

        # Truncate + exclude metadata
        for node in nodes:
            if len(node.text) > _MAX_NODE_CHARS:
                node.text = node.text[:_MAX_NODE_CHARS]
            node.excluded_embed_metadata_keys = _EXCLUDE_KEYS
            node.excluded_llm_metadata_keys = _EXCLUDE_KEYS

        logger.info("Prepared %d nodes from %d documents", len(nodes), len(documents))

        if not nodes:
            return

        # Embed all texts
        texts = [node.text for node in nodes]
        embeddings = list(self._embed_model.embed(texts))

        # Build records for LanceDB
        records = []
        for node, embedding in zip(nodes, embeddings):
            records.append({
                "id": node.node_id,
                "doc_id": node.ref_doc_id or "",
                "vector": np.array(embedding, dtype=np.float32),
                "text": node.text,
                "metadata": node.metadata,
            })

        # Upsert into LanceDB
        if _TABLE_NAME in self._db.table_names():
            table = self._db.open_table(_TABLE_NAME)
            table.add(records)
        else:
            self._db.create_table(_TABLE_NAME, records)

        logger.info("Indexed %d nodes into LanceDB", len(nodes))

    def delete_by_source(self, source_path: str) -> int:
        """Delete all vectors for a given source file."""
        if _TABLE_NAME not in self._db.table_names():
            return 0

        table = self._db.open_table(_TABLE_NAME)
        count_before = table.count_rows()

        escaped = source_path.replace("'", "''")
        table.delete(f"metadata.source_path = '{escaped}'")

        count_after = table.count_rows()
        delete_count = count_before - count_after

        if delete_count > 0:
            logger.info("Deleted %d vectors for source: %s", delete_count, source_path)

        return delete_count
