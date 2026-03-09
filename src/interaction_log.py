"""Interaction log: records every MCP tool call for auto-learning pipeline.

Each tool invocation is stored in a SQLite table with the tool name,
input parameters, output summary, and session ID. This is the raw
material for Phase 1 (Sponge) auto-extract and session summary.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_DB_DIR = Path(__file__).parent.parent / "data"

# One session ID per server process lifetime
SESSION_ID: str = uuid.uuid4().hex[:12]


class InteractionLog:
    """Thread-safe SQLite logger for MCP tool interactions."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        if db_path is None:
            db_path = _DEFAULT_DB_DIR / "interactions.db"
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _init_db(self) -> None:
        with self._lock:
            conn = sqlite3.connect(str(self._db_path))
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    input_summary TEXT,
                    output_summary TEXT,
                    duration_ms INTEGER
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_interactions_session
                ON interactions (session_id)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_interactions_tool
                ON interactions (tool_name)
                """
            )
            conn.commit()
            conn.close()

    def log(
        self,
        tool_name: str,
        input_summary: str,
        output_summary: str,
        duration_ms: int = 0,
    ) -> None:
        """Record a tool interaction."""
        with self._lock:
            try:
                conn = sqlite3.connect(str(self._db_path))
                conn.execute(
                    """
                    INSERT INTO interactions
                        (session_id, timestamp, tool_name, input_summary, output_summary, duration_ms)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        SESSION_ID,
                        datetime.now().isoformat(),
                        tool_name,
                        input_summary[:2000],
                        output_summary[:2000],
                        duration_ms,
                    ),
                )
                conn.commit()
                conn.close()
            except Exception as exc:
                logger.warning("Failed to log interaction: %s", exc)

    def get_session_interactions(
        self, session_id: str | None = None, limit: int = 50
    ) -> list[dict]:
        """Get interactions for a session (default: current session)."""
        sid = session_id or SESSION_ID
        with self._lock:
            conn = sqlite3.connect(str(self._db_path))
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT tool_name, input_summary, output_summary, timestamp, duration_ms
                FROM interactions
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (sid, limit),
            ).fetchall()
            conn.close()
            return [dict(r) for r in rows]

    def get_recent_sessions(self, limit: int = 10) -> list[dict]:
        """Get summary of recent sessions."""
        with self._lock:
            conn = sqlite3.connect(str(self._db_path))
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT
                    session_id,
                    MIN(timestamp) as started,
                    MAX(timestamp) as ended,
                    COUNT(*) as interaction_count
                FROM interactions
                GROUP BY session_id
                ORDER BY MAX(timestamp) DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            conn.close()
            return [dict(r) for r in rows]

    def get_stats(self) -> dict:
        """Get overall interaction statistics."""
        with self._lock:
            conn = sqlite3.connect(str(self._db_path))
            row = conn.execute(
                """
                SELECT
                    COUNT(*) as total_interactions,
                    COUNT(DISTINCT session_id) as total_sessions,
                    COUNT(DISTINCT tool_name) as unique_tools
                FROM interactions
                """
            ).fetchone()
            conn.close()
            return {
                "total_interactions": row[0],
                "total_sessions": row[1],
                "unique_tools": row[2],
            }
