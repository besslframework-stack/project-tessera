"""Tests for multi-angle search decomposition and merging."""

import pytest

from src.multi_angle import build_search_angles, merge_results


class TestBuildSearchAngles:
    """Test query decomposition into multiple angles."""

    def test_always_includes_original(self):
        angles = build_search_angles("hello world")
        assert angles[0] == "hello world"

    def test_empty_query(self):
        angles = build_search_angles("")
        assert len(angles) >= 1

    def test_single_word(self):
        angles = build_search_angles("PostgreSQL")
        assert "PostgreSQL" in angles

    def test_removes_stop_words(self):
        angles = build_search_angles("what is the best database for this project")
        # Should have an angle with stop words removed
        assert any("best" in a and "database" in a and "project" in a for a in angles)

    def test_korean_query(self):
        angles = build_search_angles("데이터베이스 선택에 대한 결정")
        assert len(angles) >= 2
        # First angle is always original
        assert angles[0] == "데이터베이스 선택에 대한 결정"

    def test_mixed_language(self):
        angles = build_search_angles("React 컴포넌트 설계")
        assert len(angles) >= 2

    def test_max_angles_respected(self):
        angles = build_search_angles("this is a very long query with many words", max_angles=2)
        assert len(angles) <= 2

    def test_no_duplicate_angles(self):
        angles = build_search_angles("search for documents about search")
        # Check case-insensitive uniqueness
        lower_angles = [a.lower() for a in angles]
        assert len(lower_angles) == len(set(lower_angles))

    def test_whitespace_normalization(self):
        angles = build_search_angles("  hello   world  ")
        assert angles[0] == "hello world"

    def test_significant_terms_extracted(self):
        angles = build_search_angles("authentication middleware security")
        # Should include individual significant terms
        found_individual = any(
            a in ("authentication", "middleware", "security")
            for a in angles[1:]
        )
        assert found_individual or len(angles) >= 2


class TestMergeResults:
    """Test result merging from multiple angles."""

    def test_keeps_best_score_per_source(self):
        results_a = [
            {"file_path": "a.md", "content": "foo", "similarity": 0.5},
            {"file_path": "b.md", "content": "bar", "similarity": 0.3},
        ]
        results_b = [
            {"file_path": "a.md", "content": "foo", "similarity": 0.8},
            {"file_path": "c.md", "content": "baz", "similarity": 0.6},
        ]
        merged = merge_results([results_a, results_b], top_k=10)

        # a.md should have score 0.8 (best)
        a_result = next(r for r in merged if r["file_path"] == "a.md")
        assert a_result["similarity"] == 0.8

    def test_sorted_by_score(self):
        results = [
            [{"file_path": "a.md", "similarity": 0.3}],
            [{"file_path": "b.md", "similarity": 0.9}],
            [{"file_path": "c.md", "similarity": 0.6}],
        ]
        merged = merge_results(results, top_k=10)
        scores = [r["similarity"] for r in merged]
        assert scores == sorted(scores, reverse=True)

    def test_top_k_limit(self):
        results = [
            [{"file_path": f"{i}.md", "similarity": i * 0.1} for i in range(10)]
        ]
        merged = merge_results(results, top_k=3)
        assert len(merged) <= 3

    def test_empty_results(self):
        merged = merge_results([], top_k=5)
        assert merged == []

    def test_all_empty_sublists(self):
        merged = merge_results([[], []], top_k=5)
        assert merged == []

    def test_document_results_with_metadata(self):
        results = [
            [
                {
                    "text": "doc content",
                    "metadata": {"source_path": "/a.md", "section": "intro"},
                    "similarity": 0.7,
                },
            ],
            [
                {
                    "text": "doc content v2",
                    "metadata": {"source_path": "/a.md", "section": "intro"},
                    "similarity": 0.9,
                },
            ],
        ]
        merged = merge_results(results, top_k=5, key_field="source_path")
        # Same source+section → keep best
        assert len(merged) == 1
        assert merged[0]["similarity"] == 0.9

    def test_different_sections_kept(self):
        results = [
            [
                {
                    "text": "intro",
                    "metadata": {"source_path": "/a.md", "section": "intro"},
                    "similarity": 0.7,
                },
                {
                    "text": "conclusion",
                    "metadata": {"source_path": "/a.md", "section": "conclusion"},
                    "similarity": 0.5,
                },
            ],
        ]
        merged = merge_results(results, top_k=5, key_field="source_path")
        assert len(merged) == 2

    def test_single_angle_passthrough(self):
        results = [
            [
                {"file_path": "a.md", "similarity": 0.5},
                {"file_path": "b.md", "similarity": 0.3},
            ]
        ]
        merged = merge_results(results, top_k=5)
        assert len(merged) == 2
