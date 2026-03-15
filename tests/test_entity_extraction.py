"""Tests for entity extraction (regex-based, no LLM)."""

from __future__ import annotations

import pytest

from src.entity_extraction import Entity, Triple, extract_triples, _detect_entity_type, _clean_entity_name


class TestEntityTypeDetection:
    def test_known_technology(self):
        assert _detect_entity_type("PostgreSQL") == "technology"
        assert _detect_entity_type("python") == "technology"
        assert _detect_entity_type("React") == "technology"

    def test_versioned_technology(self):
        assert _detect_entity_type("Python 3.11") == "technology"
        assert _detect_entity_type("React 18") == "technology"

    def test_project_english(self):
        assert _detect_entity_type("auth service") == "project"
        assert _detect_entity_type("payment module") == "project"

    def test_project_korean(self):
        assert _detect_entity_type("결제서비스") == "project"
        assert _detect_entity_type("인증시스템") == "project"

    def test_person_english(self):
        assert _detect_entity_type("Alice Kim") == "person"
        assert _detect_entity_type("John Smith") == "person"

    def test_person_korean(self):
        assert _detect_entity_type("김철수") == "person"
        assert _detect_entity_type("정재성") == "person"

    def test_concept_fallback(self):
        assert _detect_entity_type("microservices") == "concept"
        assert _detect_entity_type("scalability") == "concept"


class TestCleanEntityName:
    def test_trailing_punctuation(self):
        assert _clean_entity_name("PostgreSQL.") == "PostgreSQL"
        assert _clean_entity_name("Redis,") == "Redis"

    def test_leading_articles(self):
        assert _clean_entity_name("the backend") == "backend"
        assert _clean_entity_name("a database") == "database"

    def test_korean_particles(self):
        assert _clean_entity_name("PostgreSQL을") == "PostgreSQL"
        assert _clean_entity_name("프로젝트에") == "프로젝트"

    def test_whitespace(self):
        assert _clean_entity_name("  Redis  ") == "Redis"


class TestEnglishChoicePatterns:
    def test_chose_for(self):
        triples = extract_triples("We chose PostgreSQL for the production database.")
        assert len(triples) >= 1
        t = triples[0]
        assert t.subject.name.lower() == "postgresql"
        assert t.predicate == "chosen_for"
        assert "production" in t.object.name.lower() or "database" in t.object.name.lower()

    def test_using_for(self):
        triples = extract_triples("We are using Redis for caching.")
        assert len(triples) >= 1
        assert triples[0].subject.name.lower() == "redis"
        assert triples[0].predicate == "chosen_for"

    def test_adopted_for(self):
        triples = extract_triples("We adopted TypeScript for the frontend.")
        assert len(triples) >= 1
        assert triples[0].subject.name.lower() == "typescript"

    def test_selected_for(self):
        triples = extract_triples("Selected MongoDB for the analytics pipeline.")
        assert len(triples) >= 1
        assert triples[0].subject.name.lower() == "mongodb"


class TestEnglishReplacementPatterns:
    def test_switched_to(self):
        triples = extract_triples("Switched from MySQL to PostgreSQL.")
        assert len(triples) >= 1
        t = triples[0]
        assert t.subject.name.lower() == "mysql"
        assert t.predicate == "replaced_by"
        assert t.object.name.lower() == "postgresql"

    def test_replaced_with(self):
        triples = extract_triples("Replaced Jenkins with GitHub Actions.")
        assert len(triples) >= 1
        t = triples[0]
        assert "jenkins" in t.subject.name.lower()
        assert t.predicate == "replaced_by"

    def test_migrated_to(self):
        triples = extract_triples("Migrated from Heroku to Railway.")
        assert len(triples) >= 1
        assert t.predicate == "replaced_by" if (t := triples[0]) else False


class TestEnglishDependencyPatterns:
    def test_depends_on(self):
        triples = extract_triples("Tessera depends on LanceDB for vector storage.")
        assert len(triples) >= 1
        t = triples[0]
        assert "tessera" in t.subject.name.lower()
        assert t.predicate == "depends_on"
        assert "lancedb" in t.object.name.lower()

    def test_requires(self):
        triples = extract_triples("FastAPI requires Python 3.7+.")
        assert len(triples) >= 1
        assert triples[0].predicate == "depends_on"


class TestEnglishOwnershipPatterns:
    def test_manages(self):
        triples = extract_triples("Alice Kim manages the backend infrastructure.")
        assert len(triples) >= 1
        t = triples[0]
        assert "alice" in t.subject.name.lower()
        assert t.predicate == "manages"

    def test_created(self):
        triples = extract_triples("John Smith created the auth module.")
        assert len(triples) >= 1
        assert triples[0].predicate == "manages"


class TestKoreanPatterns:
    def test_ko_choice(self):
        triples = extract_triples("PostgreSQL을 프로덕션에 사용")
        assert len(triples) >= 1
        assert triples[0].predicate == "chosen_for"

    def test_ko_replacement(self):
        triples = extract_triples("MySQL에서 PostgreSQL로 전환")
        assert len(triples) >= 1
        t = triples[0]
        assert t.predicate == "replaced_by"

    def test_ko_dependency(self):
        triples = extract_triples("프론트엔드는 React에 의존")
        assert len(triples) >= 1
        assert triples[0].predicate == "depends_on"

    def test_ko_ownership(self):
        triples = extract_triples("김철수가 백엔드를 담당")
        assert len(triples) >= 1
        assert triples[0].predicate == "manages"


class TestEdgeCases:
    def test_empty_string(self):
        assert extract_triples("") == []

    def test_short_string(self):
        assert extract_triples("hi") == []

    def test_no_patterns(self):
        assert extract_triples("The weather is nice today.") == []

    def test_deduplication(self):
        triples = extract_triples(
            "We chose PostgreSQL for the database. We also chose PostgreSQL for the database."
        )
        # Should deduplicate
        pg_triples = [t for t in triples if "postgresql" in t.subject.name.lower()]
        assert len(pg_triples) <= 1

    def test_multiple_triples(self):
        text = (
            "We chose PostgreSQL for the database. "
            "Switched from Heroku to Railway. "
            "The API depends on Redis."
        )
        triples = extract_triples(text)
        assert len(triples) >= 2  # At least some should match

    def test_confidence_values(self):
        triples = extract_triples("We chose PostgreSQL for production.")
        if triples:
            assert 0.0 < triples[0].confidence <= 1.0

    def test_entity_equality(self):
        e1 = Entity("PostgreSQL", "technology")
        e2 = Entity("postgresql", "technology")
        assert e1 == e2
        assert hash(e1) == hash(e2)
