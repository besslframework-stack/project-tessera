"""Centralized embedding model management using fastembed."""

from __future__ import annotations

import logging
import warnings
from functools import lru_cache

from fastembed import TextEmbedding

from src.config import settings

logger = logging.getLogger(__name__)

# Default model: multilingual, Korean+English, only ~220MB
DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


@lru_cache(maxsize=1)
def get_embed_model() -> TextEmbedding:
    """Get or create the singleton embedding model.

    Uses fastembed (ONNX-based, no server required).
    Model is downloaded automatically on first use (~220MB).
    """
    model_name = settings.models.embed_model
    logger.info("Loading embedding model: %s", model_name)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        return TextEmbedding(model_name)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts. Returns list of float vectors."""
    model = get_embed_model()
    return [e.tolist() for e in model.embed(texts)]


@lru_cache(maxsize=128)
def embed_query(text: str) -> list[float]:
    """Embed a single query text. Returns float vector.

    Cached: repeated queries skip the embedding model entirely.
    """
    model = get_embed_model()
    return list(model.embed([text]))[0].tolist()
