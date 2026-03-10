"""Tests for export formats (v0.9.2)."""

from __future__ import annotations

import csv
import io
import json

import pytest

from src.export_formats import (
    export_csv,
    export_json_pretty,
    export_markdown,
    export_obsidian,
)


def _make_memories():
    return [
        {"content": "Use PostgreSQL for production", "date": "2026-03-01", "category": "decision", "tags": ["db", "backend"], "name": "postgres-decision"},
        {"content": "Prefer TypeScript", "date": "2026-03-02", "category": "preference", "tags": ["lang"]},
        {"content": "API rate limit is 100/min", "date": "2026-03-03", "category": "fact", "tags": ["api"]},
    ]


class TestExportObsidian:
    def test_basic(self):
        result = export_obsidian(_make_memories())
        assert "Tessera Export" in result
        assert "3 memories" in result

    def test_frontmatter(self):
        result = export_obsidian(_make_memories())
        assert "category: decision" in result
        assert "tags: [db, backend]" in result

    def test_wikilinks(self):
        result = export_obsidian(_make_memories())
        assert "[[db]]" in result
        assert "[[backend]]" in result

    def test_empty(self):
        assert "No memories" in export_obsidian([])


class TestExportMarkdown:
    def test_basic(self):
        result = export_markdown(_make_memories())
        assert "Knowledge Export" in result
        assert "3 memories" in result

    def test_grouped_by_category(self):
        result = export_markdown(_make_memories())
        assert "## Decision" in result
        assert "## Preference" in result
        assert "## Fact" in result

    def test_content_included(self):
        result = export_markdown(_make_memories())
        assert "PostgreSQL" in result
        assert "TypeScript" in result

    def test_tags(self):
        result = export_markdown(_make_memories())
        assert "#db" in result

    def test_empty(self):
        assert "No memories" in export_markdown([])

    def test_long_content_truncated(self):
        mems = [{"content": "x" * 300, "date": "2026-03-01", "category": "fact", "tags": []}]
        result = export_markdown(mems)
        assert "..." in result


class TestExportCSV:
    def test_basic(self):
        result = export_csv(_make_memories())
        reader = csv.reader(io.StringIO(result))
        rows = list(reader)
        assert rows[0] == ["date", "category", "content", "tags", "source"]
        assert len(rows) == 4  # header + 3 memories

    def test_content(self):
        result = export_csv(_make_memories())
        assert "PostgreSQL" in result
        assert "decision" in result

    def test_empty(self):
        assert "No memories" in export_csv([])


class TestExportJSON:
    def test_valid_json(self):
        result = export_json_pretty(_make_memories())
        data = json.loads(result)
        assert len(data) == 3

    def test_fields(self):
        result = export_json_pretty(_make_memories())
        data = json.loads(result)
        assert data[0]["category"] == "decision"
        assert "db" in data[0]["tags"]

    def test_empty(self):
        result = export_json_pretty([])
        assert json.loads(result) == []

    def test_korean(self):
        mems = [{"content": "한국어 메모", "date": "2026-03-01", "category": "fact", "tags": []}]
        result = export_json_pretty(mems)
        assert "한국어" in result  # ensure_ascii=False
