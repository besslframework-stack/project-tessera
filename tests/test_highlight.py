"""Tests for src.search.highlight_matches."""

from __future__ import annotations

from src.search import highlight_matches


class TestHighlightMatches:
    """Tests for highlight_matches(text, query, context_chars=80)."""

    def test_basic_highlight(self) -> None:
        """Matching word should appear wrapped in **bold** in the snippet."""
        text = "The authentication flow requires a valid token from the server."
        result = highlight_matches(text, "authentication")
        assert "**" in result
        assert "authentication" in result.replace("**", "").lower()

    def test_no_match_returns_preview(self) -> None:
        """When no words match, return the first 200 chars of text."""
        text = "Alpha beta gamma delta epsilon zeta eta theta."
        result = highlight_matches(text, "xylophone")
        assert result == text[:200]

    def test_multiple_matches(self) -> None:
        """Multiple distinct word matches should all be bold-wrapped."""
        text = (
            "The design system uses tokens for spacing and color. "
            "Each token maps to a specific design decision documented in the PRD."
        )
        result = highlight_matches(text, "design token")
        # Both words should be highlighted (bold-wrapped)
        assert result.count("**") >= 4  # at least 2 pairs of **

    def test_case_insensitive(self) -> None:
        """Matching should be case-insensitive."""
        text = "The API endpoint handles Authentication via OAuth tokens."
        result = highlight_matches(text, "authentication")
        assert "**" in result
        # The original casing should be preserved inside bold markers
        assert "**Authentication**" in result

    def test_korean_highlight(self) -> None:
        """Korean words should be found and highlighted."""
        text = "이 프로젝트의 디자인 시스템은 컴포넌트 기반으로 구성되어 있습니다."
        result = highlight_matches(text, "디자인 시스템")
        assert "**디자인**" in result
        assert "**시스템**" in result

    def test_short_query_words_ignored(self) -> None:
        """Words shorter than 3 characters should be skipped."""
        text = "An API is available for data access on the platform."
        # "an" and "is" are < 3 chars, only "API" qualifies after _clean_query
        result = highlight_matches(text, "an is API")
        assert "**API**" in result
        # Short words should NOT be highlighted
        lower_no_bold = result.replace("**", "")
        # Verify "an" is not independently bolded (would show as **an**)
        assert "** an**" not in result
        assert "**an **" not in result

    def test_empty_query(self) -> None:
        """Empty query should return the text preview."""
        text = "Some document content here for testing purposes."
        result = highlight_matches(text, "")
        assert result == text[:200]

    def test_output_capped(self) -> None:
        """Output should not exceed 500 characters."""
        # Build a long text with many occurrences of the query word
        text = ("performance optimization " * 200).strip()
        result = highlight_matches(text, "performance optimization")
        assert len(result) <= 500
