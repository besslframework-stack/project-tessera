"""Tests for suggest_alternative_queries() in src/search.py."""

from __future__ import annotations

import pytest

from src.search import suggest_alternative_queries


class TestSuggestAlternativeQueries:
    """Tests for the query suggestion engine."""

    def test_removes_stop_words(self) -> None:
        """English stop words are stripped from suggestions."""
        suggestions = suggest_alternative_queries(
            "what is the authentication flow", top_k=5
        )
        assert len(suggestions) >= 1

        # The first suggestion should be the core-words-only version
        first = suggestions[0].lower()
        for stop in ("what", "is", "the"):
            assert stop not in first.split(), (
                f"Stop word '{stop}' should be removed from '{first}'"
            )
        assert "authentication" in first

    def test_individual_words(self) -> None:
        """Multi-word queries produce individual word suggestions."""
        suggestions = suggest_alternative_queries(
            "database migration strategy", top_k=5
        )
        # Should include individual significant words as suggestions
        individual_words = [s for s in suggestions if " " not in s]
        assert len(individual_words) >= 1

    def test_removes_versions(self) -> None:
        """Version strings like 'v2.0' are stripped in at least one suggestion."""
        suggestions = suggest_alternative_queries("API v2.0 endpoint", top_k=5)
        assert len(suggestions) >= 1

        # At least one suggestion should not contain the version
        has_version_free = any("v2.0" not in s and "2.0" not in s for s in suggestions)
        assert has_version_free, (
            f"Expected at least one version-free suggestion, got: {suggestions}"
        )

    def test_korean_stop_words(self) -> None:
        """Korean stop words (particles/postpositions) are removed."""
        suggestions = suggest_alternative_queries(
            "인증에 대한 플로우", top_k=5
        )
        assert len(suggestions) >= 1

        # "에" and "대한" are Korean stop words; the core query should drop them
        first = suggestions[0]
        words = first.split()
        for stop in ("에", "대한"):
            assert stop not in words, (
                f"Korean stop word '{stop}' should be removed from '{first}'"
            )

    def test_returns_max_top_k(self) -> None:
        """Number of suggestions never exceeds top_k."""
        for k in (1, 2, 3, 5):
            suggestions = suggest_alternative_queries(
                "how to configure the database authentication endpoint", top_k=k
            )
            assert len(suggestions) <= k, (
                f"Expected at most {k} suggestions, got {len(suggestions)}"
            )

    def test_no_suggestions_for_single_word(self) -> None:
        """A single non-stop word produces empty or minimal suggestions."""
        suggestions = suggest_alternative_queries("authentication", top_k=3)
        # "authentication" alone -- no stop words to remove, no split benefit,
        # no version to strip. The only candidate would be itself (already seen).
        assert len(suggestions) == 0

    def test_deduplication(self) -> None:
        """No duplicate suggestions appear in the result list."""
        suggestions = suggest_alternative_queries(
            "what is the authentication flow for API v1.0", top_k=10
        )
        lowered = [s.lower() for s in suggestions]
        assert len(lowered) == len(set(lowered)), (
            f"Duplicate suggestions found: {suggestions}"
        )

    def test_empty_query(self) -> None:
        """An empty query returns an empty list."""
        suggestions = suggest_alternative_queries("", top_k=3)
        assert suggestions == []

    def test_whitespace_only_query(self) -> None:
        """Whitespace-only query returns an empty list."""
        suggestions = suggest_alternative_queries("   ", top_k=3)
        assert suggestions == []

    def test_all_stop_words_query(self) -> None:
        """A query of only stop words may still produce suggestions."""
        suggestions = suggest_alternative_queries("what is the", top_k=3)
        # All words are stop words -- core_words is empty.
        # Strategy 3 (version removal) won't help either.
        # Expect empty or a stripped version of the original.
        assert isinstance(suggestions, list)

    def test_original_query_not_in_suggestions(self) -> None:
        """The original query itself should not appear as a suggestion."""
        query = "database migration strategy"
        suggestions = suggest_alternative_queries(query, top_k=5)
        lowered = [s.lower() for s in suggestions]
        assert query.lower() not in lowered
