"""Simple in-memory rate limiter for Tessera HTTP API.

Token bucket algorithm. Configurable via TESSERA_RATE_LIMIT env var.
Default: 60 requests per minute. Set to 0 to disable.
"""

from __future__ import annotations

import logging
import os
import time
from collections import defaultdict

logger = logging.getLogger(__name__)

# Default: 60 requests per minute
_DEFAULT_RATE = 60
_DEFAULT_WINDOW = 60  # seconds


class RateLimiter:
    """Simple sliding window rate limiter."""

    def __init__(self, max_requests: int = _DEFAULT_RATE, window_seconds: int = _DEFAULT_WINDOW):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._enabled = max_requests > 0

    def is_allowed(self, client_id: str = "default") -> bool:
        """Check if a request is allowed."""
        if not self._enabled:
            return True

        now = time.time()
        cutoff = now - self.window_seconds

        # Clean old entries
        self._requests[client_id] = [
            t for t in self._requests[client_id] if t > cutoff
        ]

        if len(self._requests[client_id]) >= self.max_requests:
            return False

        self._requests[client_id].append(now)
        return True

    def remaining(self, client_id: str = "default") -> int:
        """Get remaining requests in current window."""
        if not self._enabled:
            return self.max_requests

        now = time.time()
        cutoff = now - self.window_seconds
        current = sum(1 for t in self._requests.get(client_id, []) if t > cutoff)
        return max(0, self.max_requests - current)

    def reset_time(self, client_id: str = "default") -> float:
        """Seconds until the oldest request expires from the window."""
        timestamps = self._requests.get(client_id, [])
        if not timestamps:
            return 0
        oldest = min(timestamps)
        return max(0, oldest + self.window_seconds - time.time())


def create_rate_limiter() -> RateLimiter:
    """Create rate limiter from environment config."""
    rate_str = os.environ.get("TESSERA_RATE_LIMIT", str(_DEFAULT_RATE))
    try:
        max_requests = int(rate_str)
    except ValueError:
        max_requests = _DEFAULT_RATE

    return RateLimiter(max_requests=max_requests)
