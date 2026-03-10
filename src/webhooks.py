"""Webhook support for Tessera — notify external services on events.

Fires HTTP POST to registered URLs when memories are created,
searches are performed, or other events occur. Async, non-blocking.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import URLError

logger = logging.getLogger(__name__)

# Event types
EVENT_MEMORY_CREATED = "memory.created"
EVENT_MEMORY_DELETED = "memory.deleted"
EVENT_SEARCH_PERFORMED = "search.performed"
EVENT_DOCUMENT_INDEXED = "document.indexed"

ALL_EVENTS = {
    EVENT_MEMORY_CREATED,
    EVENT_MEMORY_DELETED,
    EVENT_SEARCH_PERFORMED,
    EVENT_DOCUMENT_INDEXED,
}

_webhooks: list[dict] = []


def init_webhooks():
    """Load webhooks from TESSERA_WEBHOOK_URL env var."""
    global _webhooks
    url = os.environ.get("TESSERA_WEBHOOK_URL", "").strip()
    if url:
        _webhooks = [{"url": url, "events": ALL_EVENTS}]
        logger.info("Webhook registered: %s", url)


def register_webhook(url: str, events: set[str] | None = None) -> dict:
    """Register a new webhook URL."""
    if not url.startswith(("http://", "https://")):
        return {"error": "URL must start with http:// or https://"}

    webhook = {
        "url": url,
        "events": events or ALL_EVENTS,
    }
    _webhooks.append(webhook)
    return {"registered": True, "url": url, "events": sorted(webhook["events"])}


def list_webhooks() -> list[dict]:
    """List registered webhooks."""
    return [
        {"url": w["url"], "events": sorted(w["events"])}
        for w in _webhooks
    ]


def fire_event(event: str, data: dict | None = None):
    """Fire an event to all matching webhooks (non-blocking)."""
    if not _webhooks:
        return

    payload = {
        "event": event,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": data or {},
    }

    for webhook in _webhooks:
        if event in webhook["events"]:
            # Fire in background thread to not block
            thread = threading.Thread(
                target=_send_webhook,
                args=(webhook["url"], payload),
                daemon=True,
            )
            thread.start()


def _send_webhook(url: str, payload: dict):
    """Send webhook payload to URL."""
    try:
        body = json.dumps(payload).encode("utf-8")
        req = Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req, timeout=10) as resp:
            logger.debug("Webhook sent to %s: %d", url, resp.status)
    except URLError as e:
        logger.warning("Webhook failed for %s: %s", url, e)
    except Exception as e:
        logger.warning("Webhook error for %s: %s", url, e)
