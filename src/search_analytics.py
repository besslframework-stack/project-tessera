"""SQLite-based search analytics for tracking query usage patterns."""

from __future__ import annotations

import logging
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

SourceType = Literal["search", "unified", "recall"]

# Default DB path relative to project root
_PROJECT_ROOT = Path(__file__).parent.parent
_DEFAULT_DB_PATH = _PROJECT_ROOT / "data" / "search_analytics.db"


class SearchAnalyticsDB:
    """SQLite database for tracking search query usage patterns.

    Thread-safe: all DB operations are protected by a reentrant lock
    so concurrent MCP tool calls and background tasks don't collide.
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        db_path = Path(db_path) if db_path else _DEFAULT_DB_PATH
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self._init_tables()

    def _init_tables(self) -> None:
        with self._lock:
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS search_queries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query TEXT NOT NULL,
                    top_k INTEGER NOT NULL,
                    result_count INTEGER NOT NULL,
                    response_time_ms REAL NOT NULL,
                    project TEXT,
                    doc_type TEXT,
                    source TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_search_timestamp
                    ON search_queries(timestamp);
                CREATE INDEX IF NOT EXISTS idx_search_source
                    ON search_queries(source);
                CREATE INDEX IF NOT EXISTS idx_search_query
                    ON search_queries(query);
            """)
            self._conn.commit()

    def log_query(
        self,
        query: str,
        top_k: int,
        result_count: int,
        response_time_ms: float,
        project: str | None = None,
        doc_type: str | None = None,
        source: SourceType = "search",
    ) -> None:
        """Insert a search query record.

        Args:
            query: The search query text.
            top_k: Number of results requested.
            result_count: Number of results actually returned.
            response_time_ms: Response time in milliseconds.
            project: Optional project filter used.
            doc_type: Optional document type filter used.
            source: Query source - "search", "unified", or "recall".
        """
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._conn.execute(
                """INSERT INTO search_queries
                   (query, top_k, result_count, response_time_ms,
                    project, doc_type, source, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (query, top_k, result_count, response_time_ms,
                 project, doc_type, source, now),
            )
            self._conn.commit()

    def get_stats(self, days: int = 30) -> dict:
        """Return aggregated analytics for the specified time window.

        Args:
            days: Number of days to look back from now.

        Returns:
            Dictionary with total_queries, avg_response_ms, top_queries,
            queries_by_source, zero_result_queries, and queries_per_day.
        """
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        with self._lock:
            # Total queries
            row = self._conn.execute(
                "SELECT COUNT(*) AS cnt FROM search_queries WHERE timestamp >= ?",
                (cutoff,),
            ).fetchone()
            total_queries: int = row["cnt"] if row else 0

            # Average response time
            row = self._conn.execute(
                "SELECT AVG(response_time_ms) AS avg_ms "
                "FROM search_queries WHERE timestamp >= ?",
                (cutoff,),
            ).fetchone()
            avg_response_ms: float = round(row["avg_ms"], 2) if row and row["avg_ms"] is not None else 0.0

            # Top 10 most frequent queries
            rows = self._conn.execute(
                """SELECT query, COUNT(*) AS cnt, AVG(response_time_ms) AS avg_ms
                   FROM search_queries
                   WHERE timestamp >= ?
                   GROUP BY query
                   ORDER BY cnt DESC
                   LIMIT 10""",
                (cutoff,),
            ).fetchall()
            top_queries: list[dict] = [
                {"query": r["query"], "count": r["cnt"], "avg_response_ms": round(r["avg_ms"], 2)}
                for r in rows
            ]

            # Queries by source
            rows = self._conn.execute(
                """SELECT source, COUNT(*) AS cnt
                   FROM search_queries
                   WHERE timestamp >= ?
                   GROUP BY source
                   ORDER BY cnt DESC""",
                (cutoff,),
            ).fetchall()
            queries_by_source: dict[str, int] = {r["source"]: r["cnt"] for r in rows}

            # Zero-result queries
            rows = self._conn.execute(
                """SELECT query, COUNT(*) AS cnt
                   FROM search_queries
                   WHERE timestamp >= ? AND result_count = 0
                   GROUP BY query
                   ORDER BY cnt DESC
                   LIMIT 20""",
                (cutoff,),
            ).fetchall()
            zero_result_queries: list[dict] = [
                {"query": r["query"], "count": r["cnt"]}
                for r in rows
            ]

            # Queries per day
            rows = self._conn.execute(
                """SELECT DATE(timestamp) AS date, COUNT(*) AS cnt
                   FROM search_queries
                   WHERE timestamp >= ?
                   GROUP BY DATE(timestamp)
                   ORDER BY date ASC""",
                (cutoff,),
            ).fetchall()
            queries_per_day: list[dict] = [
                {"date": r["date"], "count": r["cnt"]}
                for r in rows
            ]

        return {
            "total_queries": total_queries,
            "avg_response_ms": avg_response_ms,
            "top_queries": top_queries,
            "queries_by_source": queries_by_source,
            "zero_result_queries": zero_result_queries,
            "queries_per_day": queries_per_day,
        }

    def get_recent(self, limit: int = 20) -> list[dict]:
        """Return the most recent query records.

        Args:
            limit: Maximum number of records to return.

        Returns:
            List of query record dicts, newest first.
        """
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM search_queries ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def clear_old(self, days: int = 90) -> int:
        """Delete query records older than the specified number of days.

        Args:
            days: Records older than this many days will be deleted.

        Returns:
            Number of deleted records.
        """
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        with self._lock:
            cursor = self._conn.execute(
                "DELETE FROM search_queries WHERE timestamp < ?",
                (cutoff,),
            )
            self._conn.commit()
            deleted: int = cursor.rowcount
            if deleted > 0:
                logger.info("Cleared %d search analytics records older than %d days", deleted, days)
            return deleted

    def close(self) -> None:
        """Close the database connection."""
        with self._lock:
            self._conn.close()
