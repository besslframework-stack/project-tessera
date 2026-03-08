"""Tests for knowledge graph topic extraction and link detection."""

from __future__ import annotations

from src.knowledge_graph import _extract_topics, _extract_links


class TestExtractTopics:
    def test_basic_extraction(self):
        text = "The authentication flow uses OAuth protocol with PKCE extension"
        topics = _extract_topics(text)
        assert isinstance(topics, list)
        assert len(topics) > 0

    def test_filters_short_words(self):
        text = "I am a go to the do it"
        topics = _extract_topics(text)
        # All short or stop words — should return empty or very few
        for t in topics:
            assert len(t) > 3

    def test_filters_stop_words(self):
        text = "the the the about about through through"
        topics = _extract_topics(text)
        assert "the" not in topics
        assert "about" not in topics
        assert "through" not in topics

    def test_returns_max_10(self):
        text = " ".join(f"word{i}" * 5 for i in range(20))
        topics = _extract_topics(text)
        assert len(topics) <= 10

    def test_markdown_cleaned(self):
        text = "# Header\n**bold** and `code` with [link](url)"
        topics = _extract_topics(text)
        # Should not contain markdown chars
        for t in topics:
            assert "#" not in t
            assert "*" not in t
            assert "`" not in t

    def test_empty_text(self):
        topics = _extract_topics("")
        assert topics == []

    def test_frequency_order(self):
        text = "apple apple apple banana banana cherry"
        topics = _extract_topics(text)
        if "apple" in topics and "banana" in topics:
            assert topics.index("apple") < topics.index("banana")


class TestExtractLinks:
    def test_wiki_links(self):
        text = "See [[Authentication Flow]] and [[API Design]]"
        links = _extract_links(text)
        assert "Authentication Flow" in links
        assert "API Design" in links

    def test_see_also(self):
        text = "see also: Security Requirements"
        links = _extract_links(text)
        assert any("Security Requirements" in l for l in links)

    def test_related_to(self):
        text = "related to: Database Schema"
        links = _extract_links(text)
        assert any("Database Schema" in l for l in links)

    def test_depends_on(self):
        text = "depends on: User Authentication"
        links = _extract_links(text)
        assert any("User Authentication" in l for l in links)

    def test_references(self):
        text = "references: API Specification"
        links = _extract_links(text)
        assert any("API Specification" in l for l in links)

    def test_no_links(self):
        text = "This is plain text without any links."
        links = _extract_links(text)
        assert links == []

    def test_case_insensitive(self):
        text = "See Also: Important Document"
        links = _extract_links(text)
        assert len(links) > 0

    def test_multiple_patterns(self):
        text = "[[Doc A]] and see also: Doc B\ndepends on: Doc C"
        links = _extract_links(text)
        assert len(links) >= 3
