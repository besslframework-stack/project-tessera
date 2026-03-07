"""LanceDB vector store wrapper for document chunk embeddings."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import lancedb
from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.core.node_parser import SentenceSplitter
from llama_index.vector_stores.lancedb import LanceDBVectorStore

from src.config import settings

if TYPE_CHECKING:
    from llama_index.core.base.base_retriever import BaseRetriever
    from llama_index.core.base.embeddings.base import BaseEmbedding
    from llama_index.core.schema import Document

logger = logging.getLogger(__name__)

_TABLE_NAME = "ontology_chunks"

# nomic-embed-text-v2-moe: 8192 token limit.
# Korean ≈ 3 tokens/char → 1500 chars ≈ 4500 tokens (safe).
_MAX_NODE_CHARS = 800

# All metadata keys to exclude from embedding text
_EXCLUDE_KEYS = [
    "source_path", "file_name", "file_type", "doc_type", "project",
    "version", "date", "title", "section",
    "detected_version", "detected_date", "detected_priority",
    "detected_tier", "detected_phase", "detected_person", "detected_req_id",
]


class OntologyVectorStore:
    """Manages LanceDB vector store for document chunk embeddings."""

    def __init__(self, embed_model: BaseEmbedding) -> None:
        db_path = str(settings.data.lancedb_path)
        Path(db_path).mkdir(parents=True, exist_ok=True)

        self._db = lancedb.connect(db_path)
        self._vector_store = LanceDBVectorStore(
            uri=db_path,
            table_name=_TABLE_NAME,
        )
        self.embed_model = embed_model
        self._index: VectorStoreIndex | None = None

    @property
    def index(self) -> VectorStoreIndex:
        if self._index is None:
            self._index = VectorStoreIndex.from_vector_store(
                vector_store=self._vector_store,
                embed_model=self.embed_model,
            )
        return self._index

    def index_documents(self, documents: list[Document]) -> None:
        """Index documents: split into safe-sized nodes, then embed and store."""
        # Step 1: Split documents into nodes
        splitter = SentenceSplitter(chunk_size=1024, chunk_overlap=100)
        nodes = splitter.get_nodes_from_documents(documents, show_progress=True)

        # Step 2: Hard-truncate + exclude metadata from embedding for every node
        for node in nodes:
            if len(node.text) > _MAX_NODE_CHARS:
                node.text = node.text[:_MAX_NODE_CHARS]
            node.excluded_embed_metadata_keys = _EXCLUDE_KEYS
            node.excluded_llm_metadata_keys = _EXCLUDE_KEYS

        logger.info("Prepared %d nodes from %d documents", len(nodes), len(documents))

        # Step 3: Build index from pre-split nodes
        storage_context = StorageContext.from_defaults(vector_store=self._vector_store)
        self._index = VectorStoreIndex(
            nodes=nodes,
            storage_context=storage_context,
            embed_model=self.embed_model,
            show_progress=True,
        )
        logger.info("Indexed %d nodes into LanceDB", len(nodes))

    def delete_by_source(self, source_path: str) -> int:
        if _TABLE_NAME not in self._db.table_names():
            return 0

        table = self._db.open_table(_TABLE_NAME)
        count_before = table.count_rows()

        escaped = source_path.replace("'", "''")
        table.delete(f"metadata.source_path = '{escaped}'")

        count_after = table.count_rows()
        delete_count = count_before - count_after

        if delete_count > 0:
            self._index = None
            self._vector_store = LanceDBVectorStore(
                uri=str(settings.data.lancedb_path),
                table_name=_TABLE_NAME,
            )
            logger.info("Deleted %d vectors for source: %s", delete_count, source_path)

        return delete_count

    def as_retriever(self, similarity_top_k: int = 5) -> BaseRetriever:
        return self.index.as_retriever(similarity_top_k=similarity_top_k)
