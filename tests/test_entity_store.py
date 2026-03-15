"""Tests for entity store (SQLite-backed entity/relationship storage)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from src.entity_store import EntityStore


@pytest.fixture
def store(tmp_path):
    """Create a fresh entity store for each test."""
    return EntityStore(db_path=tmp_path / "test_entities.db")


class TestEntityCRUD:
    def test_upsert_new_entity(self, store):
        entity_id = store.upsert_entity("PostgreSQL", "technology")
        assert entity_id > 0

    def test_upsert_existing_entity_increments_count(self, store):
        id1 = store.upsert_entity("PostgreSQL", "technology")
        id2 = store.upsert_entity("PostgreSQL", "technology")
        assert id1 == id2
        entity = store.find_entity("PostgreSQL")
        assert entity["mention_count"] == 2

    def test_upsert_case_insensitive(self, store):
        id1 = store.upsert_entity("PostgreSQL", "technology")
        id2 = store.upsert_entity("postgresql", "technology")
        assert id1 == id2

    def test_find_entity(self, store):
        store.upsert_entity("Redis", "technology")
        result = store.find_entity("Redis")
        assert result is not None
        assert result["name"] == "Redis"
        assert result["entity_type"] == "technology"

    def test_find_entity_case_insensitive(self, store):
        store.upsert_entity("Redis", "technology")
        result = store.find_entity("redis")
        assert result is not None

    def test_find_entity_not_found(self, store):
        assert store.find_entity("NonExistent") is None

    def test_search_entities(self, store):
        store.upsert_entity("PostgreSQL", "technology")
        store.upsert_entity("MySQL", "technology")
        store.upsert_entity("Redis", "technology")
        results = store.search_entities("sql")
        names = [r["name"] for r in results]
        assert "PostgreSQL" in names
        assert "MySQL" in names

    def test_search_entities_empty(self, store):
        results = store.search_entities("nothing")
        assert results == []

    def test_get_all_entities(self, store):
        store.upsert_entity("A", "concept")
        store.upsert_entity("B", "concept")
        store.upsert_entity("C", "concept")
        results = store.get_all_entities()
        assert len(results) == 3

    def test_entity_count(self, store):
        assert store.entity_count() == 0
        store.upsert_entity("X", "concept")
        store.upsert_entity("Y", "concept")
        assert store.entity_count() == 2


class TestRelationshipCRUD:
    def test_add_relationship(self, store):
        subj_id = store.upsert_entity("PostgreSQL", "technology")
        obj_id = store.upsert_entity("Project X", "project")
        rel_id = store.add_relationship(subj_id, "chosen_for", obj_id, "mem_001")
        assert rel_id > 0

    def test_duplicate_relationship_returns_existing(self, store):
        subj_id = store.upsert_entity("A", "concept")
        obj_id = store.upsert_entity("B", "concept")
        id1 = store.add_relationship(subj_id, "uses", obj_id, "mem_001")
        id2 = store.add_relationship(subj_id, "uses", obj_id, "mem_001")
        assert id1 == id2

    def test_same_relationship_different_memory(self, store):
        subj_id = store.upsert_entity("A", "concept")
        obj_id = store.upsert_entity("B", "concept")
        id1 = store.add_relationship(subj_id, "uses", obj_id, "mem_001")
        id2 = store.add_relationship(subj_id, "uses", obj_id, "mem_002")
        assert id1 != id2

    def test_get_entity_relationships(self, store):
        a = store.upsert_entity("PostgreSQL", "technology")
        b = store.upsert_entity("Project X", "project")
        c = store.upsert_entity("Redis", "technology")
        store.add_relationship(a, "chosen_for", b, "mem_001")
        store.add_relationship(c, "chosen_for", b, "mem_002")

        rels = store.get_entity_relationships(b)
        assert len(rels) == 2

    def test_get_memory_entities(self, store):
        a = store.upsert_entity("PostgreSQL", "technology")
        b = store.upsert_entity("Project X", "project")
        store.add_relationship(a, "chosen_for", b, "mem_001")
        results = store.get_memory_entities("mem_001")
        assert len(results) == 1
        assert results[0]["subject_name"] == "PostgreSQL"
        assert results[0]["object_name"] == "Project X"

    def test_get_all_relationships(self, store):
        a = store.upsert_entity("A", "concept")
        b = store.upsert_entity("B", "concept")
        c = store.upsert_entity("C", "concept")
        store.add_relationship(a, "uses", b, "m1")
        store.add_relationship(b, "depends_on", c, "m2")
        rels = store.get_all_relationships()
        assert len(rels) == 2

    def test_delete_memory_relationships(self, store):
        a = store.upsert_entity("A", "concept")
        b = store.upsert_entity("B", "concept")
        store.add_relationship(a, "uses", b, "mem_001")
        store.add_relationship(a, "uses", b, "mem_002")

        deleted = store.delete_memory_relationships("mem_001")
        assert deleted == 1
        assert store.relationship_count() == 1

    def test_relationship_count(self, store):
        assert store.relationship_count() == 0
        a = store.upsert_entity("A", "concept")
        b = store.upsert_entity("B", "concept")
        store.add_relationship(a, "uses", b, "m1")
        assert store.relationship_count() == 1


class TestSearchWithMemories:
    def test_search_entities_with_memories(self, store):
        pg = store.upsert_entity("PostgreSQL", "technology")
        proj = store.upsert_entity("Project Alpha", "project")
        store.add_relationship(pg, "chosen_for", proj, "mem_001")
        store.add_relationship(pg, "chosen_for", proj, "mem_002")

        results = store.search_entities_with_memories("postgres")
        assert len(results) == 1
        assert results[0]["entity"]["name"] == "PostgreSQL"
        assert len(results[0]["memory_ids"]) == 2

    def test_search_entities_with_memories_no_match(self, store):
        results = store.search_entities_with_memories("nonexistent")
        assert results == []


class TestThreadSafety:
    def test_concurrent_upserts(self, store):
        import threading

        errors = []

        def upsert():
            try:
                for i in range(10):
                    store.upsert_entity(f"Entity_{i}", "concept")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=upsert) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        # All 10 unique entities should exist
        assert store.entity_count() == 10
