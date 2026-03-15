"""Entity store: SQLite-backed storage for entities and relationships.

Stores the knowledge graph extracted from memories. No external databases
required — everything lives in a single SQLite file alongside the existing
interaction log and search analytics databases.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_DB_DIR = Path(__file__).parent.parent / "data"


class EntityStore:
    """Thread-safe SQLite store for entities and relationships."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        if db_path is None:
            db_path = _DEFAULT_DB_DIR / "entities.db"
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _init_db(self) -> None:
        with self._lock:
            conn = sqlite3.connect(str(self._db_path))
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS entities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    name_normalized TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    mention_count INTEGER DEFAULT 1
                )
                """
            )
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_entity_name_norm
                ON entities (name_normalized)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS relationships (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subject_entity_id INTEGER NOT NULL REFERENCES entities(id),
                    predicate TEXT NOT NULL,
                    object_entity_id INTEGER NOT NULL REFERENCES entities(id),
                    memory_id TEXT NOT NULL,
                    confidence REAL DEFAULT 1.0,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_rel_subject ON relationships (subject_entity_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_rel_object ON relationships (object_entity_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_rel_memory ON relationships (memory_id)"
            )
            conn.commit()
            conn.close()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    # ----- Entity CRUD -----

    def upsert_entity(self, name: str, entity_type: str) -> int:
        """Insert or update an entity, return its ID.

        If the entity already exists (case-insensitive), update last_seen
        and increment mention_count. Otherwise insert a new row.
        """
        now = datetime.now().isoformat()
        normalized = name.strip().lower()

        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT id, mention_count FROM entities WHERE name_normalized = ?",
                    (normalized,),
                ).fetchone()

                if row:
                    conn.execute(
                        "UPDATE entities SET last_seen = ?, mention_count = ? WHERE id = ?",
                        (now, row["mention_count"] + 1, row["id"]),
                    )
                    conn.commit()
                    return row["id"]

                cursor = conn.execute(
                    """
                    INSERT INTO entities (name, name_normalized, entity_type, first_seen, last_seen)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (name.strip(), normalized, entity_type, now, now),
                )
                conn.commit()
                return cursor.lastrowid  # type: ignore[return-value]
            finally:
                conn.close()

    def find_entity(self, name: str) -> dict | None:
        """Find an entity by name (case-insensitive)."""
        normalized = name.strip().lower()
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT * FROM entities WHERE name_normalized = ?",
                    (normalized,),
                ).fetchone()
                return dict(row) if row else None
            finally:
                conn.close()

    def search_entities(self, query: str, limit: int = 20) -> list[dict]:
        """Search entities by name (LIKE-based)."""
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    "SELECT * FROM entities WHERE name_normalized LIKE ? ORDER BY mention_count DESC LIMIT ?",
                    (f"%{query.strip().lower()}%", limit),
                ).fetchall()
                return [dict(r) for r in rows]
            finally:
                conn.close()

    def get_all_entities(self, limit: int = 200) -> list[dict]:
        """Get all entities ordered by mention count."""
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    "SELECT * FROM entities ORDER BY mention_count DESC LIMIT ?",
                    (limit,),
                ).fetchall()
                return [dict(r) for r in rows]
            finally:
                conn.close()

    # ----- Relationship CRUD -----

    def add_relationship(
        self,
        subject_id: int,
        predicate: str,
        object_id: int,
        memory_id: str,
        confidence: float = 1.0,
    ) -> int:
        """Add a relationship between two entities."""
        now = datetime.now().isoformat()
        with self._lock:
            conn = self._connect()
            try:
                # Check for duplicate relationship
                existing = conn.execute(
                    """
                    SELECT id FROM relationships
                    WHERE subject_entity_id = ? AND predicate = ? AND object_entity_id = ? AND memory_id = ?
                    """,
                    (subject_id, predicate, object_id, memory_id),
                ).fetchone()
                if existing:
                    return existing["id"]

                cursor = conn.execute(
                    """
                    INSERT INTO relationships (subject_entity_id, predicate, object_entity_id, memory_id, confidence, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (subject_id, predicate, object_id, memory_id, confidence, now),
                )
                conn.commit()
                return cursor.lastrowid  # type: ignore[return-value]
            finally:
                conn.close()

    def get_entity_relationships(self, entity_id: int) -> list[dict]:
        """Get all relationships involving an entity (as subject or object)."""
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    """
                    SELECT r.*, s.name as subject_name, s.entity_type as subject_type,
                           o.name as object_name, o.entity_type as object_type
                    FROM relationships r
                    JOIN entities s ON r.subject_entity_id = s.id
                    JOIN entities o ON r.object_entity_id = o.id
                    WHERE r.subject_entity_id = ? OR r.object_entity_id = ?
                    ORDER BY r.created_at DESC
                    """,
                    (entity_id, entity_id),
                ).fetchall()
                return [dict(r) for r in rows]
            finally:
                conn.close()

    def get_memory_entities(self, memory_id: str) -> list[dict]:
        """Get all entities and relationships linked to a memory."""
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    """
                    SELECT r.predicate, r.confidence,
                           s.name as subject_name, s.entity_type as subject_type,
                           o.name as object_name, o.entity_type as object_type
                    FROM relationships r
                    JOIN entities s ON r.subject_entity_id = s.id
                    JOIN entities o ON r.object_entity_id = o.id
                    WHERE r.memory_id = ?
                    """,
                    (memory_id,),
                ).fetchall()
                return [dict(r) for r in rows]
            finally:
                conn.close()

    def get_all_relationships(self, limit: int = 500) -> list[dict]:
        """Get all relationships with entity names."""
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    """
                    SELECT r.*, s.name as subject_name, s.entity_type as subject_type,
                           o.name as object_name, o.entity_type as object_type
                    FROM relationships r
                    JOIN entities s ON r.subject_entity_id = s.id
                    JOIN entities o ON r.object_entity_id = o.id
                    ORDER BY r.created_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
                return [dict(r) for r in rows]
            finally:
                conn.close()

    def delete_memory_relationships(self, memory_id: str) -> int:
        """Delete all relationships for a given memory. Returns count deleted."""
        with self._lock:
            conn = self._connect()
            try:
                cursor = conn.execute(
                    "DELETE FROM relationships WHERE memory_id = ?",
                    (memory_id,),
                )
                conn.commit()
                return cursor.rowcount
            finally:
                conn.close()

    def search_entities_with_memories(self, query: str, limit: int = 10) -> list[dict]:
        """Search entities and return them with their relationships and memory IDs.

        This is the main query method for entity-augmented search.
        """
        entities = self.search_entities(query, limit=limit)
        results = []
        for entity in entities:
            rels = self.get_entity_relationships(entity["id"])
            memory_ids = list({r["memory_id"] for r in rels})
            results.append({
                "entity": entity,
                "relationships": rels,
                "memory_ids": memory_ids,
            })
        return results

    def entity_count(self) -> int:
        """Total number of entities."""
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute("SELECT COUNT(*) as cnt FROM entities").fetchone()
                return row["cnt"] if row else 0
            finally:
                conn.close()

    def relationship_count(self) -> int:
        """Total number of relationships."""
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute("SELECT COUNT(*) as cnt FROM relationships").fetchone()
                return row["cnt"] if row else 0
            finally:
                conn.close()
