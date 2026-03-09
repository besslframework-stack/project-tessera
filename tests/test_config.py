"""Tests for workspace configuration loading."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from src.config import (
    ConfigValidationError,
    IngestionConfig,
    KnowledgeGraphConfig,
    LimitsConfig,
    SearchConfig,
    SourceConfig,
    WatcherConfig,
    WorkspaceConfig,
    _build_auto_detected_defaults,
    _validate_positive,
    _validate_range,
    load_workspace_config,
)


class TestSourceConfig:
    def test_basic_creation(self):
        s = SourceConfig(path="docs", type="document", project="proj_a")
        assert s.path == "docs"
        assert s.type == "document"
        assert s.project == "proj_a"


class TestWorkspaceConfig:
    def test_resolve_source_path(self, tmp_path):
        ws = WorkspaceConfig(
            root=tmp_path,
            name="test",
            sources=[SourceConfig(path="docs", type="document", project="p1")],
            projects={},
            archive_dir="_archive",
            sync_auto=True,
            extensions=[".md"],
            ignore_patterns=[],
            lancedb_path=tmp_path / "data" / "lancedb",
            meta_db_path=tmp_path / "data" / "file_meta.db",
            embed_model="test-model",
        )
        assert ws.resolve_source_path(ws.sources[0]) == tmp_path / "docs"

    def test_resolve_project_root_exists(self, tmp_path):
        from src.config import ProjectConfig

        ws = WorkspaceConfig(
            root=tmp_path,
            name="test",
            sources=[],
            projects={"p1": ProjectConfig(id="p1", display_name="P1", root="my-project")},
            archive_dir="_archive",
            sync_auto=True,
            extensions=[".md"],
            ignore_patterns=[],
            lancedb_path=tmp_path / "data" / "lancedb",
            meta_db_path=tmp_path / "data" / "file_meta.db",
            embed_model="test-model",
        )
        assert ws.resolve_project_root("p1") == tmp_path / "my-project"

    def test_resolve_project_root_missing(self, tmp_path):
        ws = WorkspaceConfig(
            root=tmp_path,
            name="test",
            sources=[],
            projects={},
            archive_dir="_archive",
            sync_auto=True,
            extensions=[".md"],
            ignore_patterns=[],
            lancedb_path=tmp_path / "data" / "lancedb",
            meta_db_path=tmp_path / "data" / "file_meta.db",
            embed_model="test-model",
        )
        assert ws.resolve_project_root("nonexistent") is None

    def test_all_source_paths(self, tmp_path):
        ws = WorkspaceConfig(
            root=tmp_path,
            name="test",
            sources=[
                SourceConfig(path="a", type="document", project="p1"),
                SourceConfig(path="b", type="document", project="p2"),
            ],
            projects={},
            archive_dir="_archive",
            sync_auto=True,
            extensions=[".md"],
            ignore_patterns=[],
            lancedb_path=tmp_path / "data" / "lancedb",
            meta_db_path=tmp_path / "data" / "file_meta.db",
            embed_model="test-model",
        )
        paths = ws.all_source_paths()
        assert len(paths) == 2
        assert paths[0] == tmp_path / "a"
        assert paths[1] == tmp_path / "b"


class TestSubConfigs:
    def test_search_defaults(self):
        sc = SearchConfig()
        assert sc.max_top_k == 50
        assert sc.reranker_weight == 0.7
        assert sc.fetch_multiplier == 6
        assert sc.result_text_limit == 1500
        assert sc.unified_text_limit == 800

    def test_ingestion_defaults(self):
        ic = IngestionConfig()
        assert ic.chunk_size == 1024
        assert ic.chunk_overlap == 100
        assert ic.max_node_chars == 800

    def test_watcher_defaults(self):
        wc = WatcherConfig()
        assert wc.poll_interval == 30.0
        assert wc.debounce == 5.0

    def test_knowledge_graph_defaults(self):
        kc = KnowledgeGraphConfig()
        assert kc.default_max_nodes == 30
        assert kc.max_max_nodes == 100
        assert kc.max_topics == 10
        assert kc.min_word_length == 4

    def test_limits_defaults(self):
        lc = LimitsConfig()
        assert lc.max_file_read == 50000

    def test_workspace_has_sub_configs(self, tmp_path):
        ws = WorkspaceConfig(
            root=tmp_path,
            name="test",
            sources=[],
            projects={},
            archive_dir="_archive",
            sync_auto=True,
            extensions=[".md"],
            ignore_patterns=[],
            lancedb_path=tmp_path / "data" / "lancedb",
            meta_db_path=tmp_path / "data" / "file_meta.db",
            embed_model="test-model",
        )
        assert isinstance(ws.search, SearchConfig)
        assert isinstance(ws.ingestion, IngestionConfig)
        assert isinstance(ws.watcher, WatcherConfig)
        assert isinstance(ws.knowledge_graph, KnowledgeGraphConfig)
        assert isinstance(ws.limits, LimitsConfig)

    def test_custom_values(self):
        sc = SearchConfig(max_top_k=100, reranker_weight=0.5)
        assert sc.max_top_k == 100
        assert sc.reranker_weight == 0.5


class TestConfigValidation:
    def test_validate_positive_ok(self):
        _validate_positive("test", 10)
        _validate_positive("test", 0.5)

    def test_validate_positive_zero(self):
        with pytest.raises(ConfigValidationError):
            _validate_positive("test", 0)

    def test_validate_positive_negative(self):
        with pytest.raises(ConfigValidationError):
            _validate_positive("test", -1)

    def test_validate_range_ok(self):
        _validate_range("test", 0.5, 0.0, 1.0)

    def test_validate_range_out(self):
        with pytest.raises(ConfigValidationError):
            _validate_range("test", 1.5, 0.0, 1.0)

    def test_validate_range_below(self):
        with pytest.raises(ConfigValidationError):
            _validate_range("test", -0.1, 0.0, 1.0)


class TestTesseraWorkspaceEnv:
    def test_env_var_overrides_cwd(self, tmp_path, monkeypatch):
        target = tmp_path / "my-docs"
        target.mkdir()
        monkeypatch.setenv("TESSERA_WORKSPACE", str(target))
        result = _build_auto_detected_defaults()
        assert result["workspace"]["root"] == str(target)
        assert result["workspace"]["name"] == "my-docs"

    def test_env_var_with_tilde(self, monkeypatch):
        monkeypatch.setenv("TESSERA_WORKSPACE", "~/Documents/notes")
        result = _build_auto_detected_defaults()
        assert "~" not in result["workspace"]["root"]
        assert "Documents/notes" in result["workspace"]["root"]

    def test_no_env_var_uses_cwd(self, monkeypatch):
        monkeypatch.delenv("TESSERA_WORKSPACE", raising=False)
        result = _build_auto_detected_defaults()
        assert result["workspace"]["root"] == str(Path.cwd())
