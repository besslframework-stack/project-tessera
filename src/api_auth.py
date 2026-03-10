"""API authentication for Tessera HTTP server.

Simple API key authentication. Keys are stored in workspace.yaml
or via TESSERA_API_KEY environment variable.
"""

from __future__ import annotations

import hashlib
import logging
import os
import secrets

logger = logging.getLogger(__name__)

# Default: no auth required (local-first design)
_REQUIRE_AUTH = False
_API_KEYS: set[str] = set()


def init_auth():
    """Initialize API auth from environment or config."""
    global _REQUIRE_AUTH, _API_KEYS

    env_key = os.environ.get("TESSERA_API_KEY", "").strip()
    if env_key:
        _API_KEYS.add(env_key)
        _REQUIRE_AUTH = True
        logger.info("API auth enabled via TESSERA_API_KEY")
        return

    # Try loading from workspace config
    try:
        from src.config import workspace
        api_keys = getattr(workspace, "api_keys", None)
        if api_keys:
            _API_KEYS.update(api_keys)
            _REQUIRE_AUTH = True
            logger.info("API auth enabled via workspace config (%d keys)", len(_API_KEYS))
    except Exception as e:
        logger.debug("Could not load workspace config for auth: %s", e)


def generate_api_key() -> str:
    """Generate a new random API key."""
    return f"tsr_{secrets.token_urlsafe(32)}"


def is_auth_required() -> bool:
    """Check if authentication is currently required."""
    return _REQUIRE_AUTH


def validate_key(key: str) -> bool:
    """Validate an API key."""
    if not _REQUIRE_AUTH:
        return True
    if not key:
        return False
    return key in _API_KEYS


def hash_key(key: str) -> str:
    """Hash an API key for safe logging/storage."""
    return hashlib.sha256(key.encode()).hexdigest()[:16]
