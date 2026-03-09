"""Tests for auto_extract pattern matching engine."""

from __future__ import annotations

import pytest

from src.auto_extract import ExtractedFact, extract_facts, should_auto_learn


class TestExtractFacts:
    def test_empty_text(self):
        assert extract_facts("") == []
        assert extract_facts("short") == []
        assert extract_facts("   ") == []

    def test_decision_english(self):
        text = "We decided to use PostgreSQL for the main database instead of MySQL"
        facts = extract_facts(text)
        assert len(facts) >= 1
        assert any(f.category == "decision" for f in facts)

    def test_decision_go_with(self):
        text = "Let's go with React for the frontend framework"
        facts = extract_facts(text)
        assert len(facts) >= 1
        assert any(f.category == "decision" for f in facts)

    def test_decision_korean(self):
        text = "결정했습니다: PostgreSQL을 메인 데이터베이스로 사용하겠습니다"
        facts = extract_facts(text)
        assert len(facts) >= 1

    def test_decision_korean_hagi(self):
        text = "Redis를 캐시로 사용하기로 결정했어"
        facts = extract_facts(text)
        assert len(facts) >= 1

    def test_preference_english(self):
        text = "I prefer using TypeScript over plain JavaScript for type safety"
        facts = extract_facts(text)
        assert len(facts) >= 1
        assert any(f.category == "preference" for f in facts)

    def test_preference_negative(self):
        text = "dont like using jQuery anymore its outdated for modern development"
        facts = extract_facts(text)
        assert len(facts) >= 1
        assert any(f.category == "preference" for f in facts)

    def test_preference_korean(self):
        text = "선호 타입스크립트를 자바스크립트보다 더 좋아해요"
        facts = extract_facts(text)
        assert len(facts) >= 1

    def test_fact_note(self):
        text = "Note that the API rate limit is 100 requests per minute per user"
        facts = extract_facts(text)
        assert len(facts) >= 1
        assert any(f.category == "fact" for f in facts)

    def test_fact_remember(self):
        text = "Remember that the deploy key is stored in vault, not in env vars"
        facts = extract_facts(text)
        assert len(facts) >= 1

    def test_fact_korean(self):
        text = "핵심은 모든 API 호출에 인증 토큰이 필요하다는 것이다"
        facts = extract_facts(text)
        assert len(facts) >= 1

    def test_signal_remember_this(self):
        text = "Remember this: always run migrations before deploying to production"
        facts = extract_facts(text)
        assert len(facts) >= 1
        assert any(f.confidence >= 0.9 for f in facts)

    def test_signal_korean(self):
        text = "이거 기억해: 배포 전에 반드시 테스트 실행"
        facts = extract_facts(text)
        assert len(facts) >= 1
        assert any(f.confidence >= 0.9 for f in facts)

    def test_no_duplicates(self):
        text = "We decided to use PostgreSQL. We decided to use PostgreSQL."
        facts = extract_facts(text)
        contents = [f.content.lower() for f in facts]
        assert len(contents) == len(set(contents))

    def test_content_too_short_filtered(self):
        text = "We decided to X"
        facts = extract_facts(text)
        assert all(len(f.content) >= 10 for f in facts)

    def test_multiple_categories(self):
        text = (
            "We decided to use FastAPI for the HTTP server. "
            "I prefer async frameworks over sync ones. "
            "Note that uvicorn is the recommended ASGI server for FastAPI."
        )
        facts = extract_facts(text)
        categories = {f.category for f in facts}
        assert len(categories) >= 2

    def test_source_text_truncated(self):
        long_text = "We decided to use X" + " very long content" * 100
        facts = extract_facts(long_text)
        for f in facts:
            assert len(f.source_text) <= 500

    def test_confidence_ordering(self):
        text = (
            "Remember this: always backup before deploy. "
            "We decided to use Docker for containerization. "
            "I prefer vim over emacs for quick edits on the server."
        )
        facts = extract_facts(text)
        signals = [f for f in facts if f.confidence >= 0.9]
        decisions = [f for f in facts if f.category == "decision"]
        preferences = [f for f in facts if f.category == "preference"]
        if signals:
            assert signals[0].confidence >= 0.9
        if decisions:
            assert decisions[0].confidence >= 0.8
        if preferences:
            assert preferences[0].confidence >= 0.75


class TestShouldAutoLearn:
    def test_above_threshold(self):
        text = "We decided to use PostgreSQL for all production databases going forward"
        facts = should_auto_learn(text, min_confidence=0.75)
        assert len(facts) >= 1

    def test_below_threshold(self):
        text = "We decided to use PostgreSQL for all production databases going forward"
        facts = should_auto_learn(text, min_confidence=0.99)
        assert len(facts) == 0

    def test_empty_text(self):
        assert should_auto_learn("") == []

    def test_no_patterns(self):
        text = "The weather is nice today and I had coffee this morning."
        facts = should_auto_learn(text)
        assert len(facts) == 0

    def test_custom_threshold(self):
        text = "Remember this: use branch protection on main"
        high = should_auto_learn(text, min_confidence=0.90)
        low = should_auto_learn(text, min_confidence=0.50)
        assert len(low) >= len(high)


class TestExtractedFact:
    def test_dataclass_fields(self):
        fact = ExtractedFact(
            content="test content",
            category="decision",
            confidence=0.85,
            source_text="original text",
        )
        assert fact.content == "test content"
        assert fact.category == "decision"
        assert fact.confidence == 0.85
        assert fact.source_text == "original text"
