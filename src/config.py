"""Application configuration loaded from environment variables and workspace.yaml."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()


@dataclass(frozen=True)
class ModelConfig:
    embed_model: str = os.getenv(
        "EMBED_MODEL",
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    )


@dataclass(frozen=True)
class DataConfig:
    base_dir: Path = field(
        default_factory=lambda: Path(
            os.getenv("DATA_DIR", str(Path.home()))
        )
    )
    lancedb_path: Path = field(
        default_factory=lambda: Path(__file__).parent.parent / "data" / "lancedb"
    )

    @property
    def tier1_sources(self) -> list[Path]:
        """Tier 1 data sources: high-structure documents with clear entity/relation signals."""
        return [
            self.base_dir / "valley" / "valley_industry_research" / "01_prd",
            self.base_dir / "valley" / "valley_llm" / "prd",
            self.base_dir / "claude_sessions",
        ]

    @property
    def tier2_sources(self) -> list[Path]:
        """Tier 2 data sources: semi-structured documents."""
        return [
            self.base_dir / "valley" / "valley_industry_research" / "00_decision_log",
            self.base_dir / "valley" / "valley_llm" / "00_decision_log",
        ]


@dataclass(frozen=True)
class Settings:
    models: ModelConfig = field(default_factory=ModelConfig)
    data: DataConfig = field(default_factory=DataConfig)


settings = Settings()


# --- Workspace Config (from workspace.yaml) ---


@dataclass
class SourceConfig:
    path: str
    type: str
    project: str


@dataclass
class ProjectConfig:
    id: str
    display_name: str
    root: str


@dataclass(frozen=True)
class SearchConfig:
    max_top_k: int = 50
    reranker_weight: float = 0.7
    fetch_multiplier: int = 6
    result_text_limit: int = 1500
    unified_text_limit: int = 800


@dataclass(frozen=True)
class IngestionConfig:
    chunk_size: int = 1024
    chunk_overlap: int = 100
    max_node_chars: int = 800
    max_meta_value_len: int = 200


@dataclass(frozen=True)
class WatcherConfig:
    poll_interval: float = 30.0
    debounce: float = 5.0


@dataclass(frozen=True)
class KnowledgeGraphConfig:
    default_max_nodes: int = 30
    max_max_nodes: int = 100
    max_topics: int = 10
    min_word_length: int = 4


@dataclass(frozen=True)
class AutoLearnConfig:
    enabled: bool = True
    min_confidence: float = 0.75
    min_interactions_for_summary: int = 3


@dataclass(frozen=True)
class LimitsConfig:
    max_file_read: int = 50000


@dataclass
class WorkspaceConfig:
    root: Path
    name: str
    sources: list[SourceConfig]
    projects: dict[str, ProjectConfig]
    archive_dir: str
    sync_auto: bool
    extensions: list[str]
    ignore_patterns: list[str]
    lancedb_path: Path
    meta_db_path: Path
    embed_model: str
    search: SearchConfig = SearchConfig()
    ingestion: IngestionConfig = IngestionConfig()
    watcher: WatcherConfig = WatcherConfig()
    knowledge_graph: KnowledgeGraphConfig = KnowledgeGraphConfig()
    limits: LimitsConfig = LimitsConfig()
    auto_learn: AutoLearnConfig = AutoLearnConfig()

    def resolve_source_path(self, source: SourceConfig) -> Path:
        return self.root / source.path

    def resolve_project_root(self, project_id: str) -> Path | None:
        proj = self.projects.get(project_id)
        if proj is None:
            return None
        return self.root / proj.root

    def all_source_paths(self) -> list[Path]:
        return [self.resolve_source_path(s) for s in self.sources]


class ConfigValidationError(ValueError):
    """Raised when workspace.yaml has invalid values."""


def _validate_positive(name: str, value, min_val=0) -> None:
    if not isinstance(value, (int, float)) or value <= min_val:
        raise ConfigValidationError(
            f"Invalid config: {name} must be > {min_val}, got {value}"
        )


def _validate_range(name: str, value, lo, hi) -> None:
    if not isinstance(value, (int, float)) or value < lo or value > hi:
        raise ConfigValidationError(
            f"Invalid config: {name} must be between {lo} and {hi}, got {value}"
        )


def _build_auto_detected_defaults() -> dict:
    """Build a sensible default config from the current working directory.

    Used when no workspace.yaml is found, enabling zero-config startup
    for non-technical users. Respects TESSERA_WORKSPACE env var if set.
    """
    workspace_env = os.environ.get("TESSERA_WORKSPACE")
    if workspace_env:
        workspace_path = Path(workspace_env).expanduser().resolve()
        folder_name = workspace_path.name or "workspace"
    else:
        workspace_path = Path.cwd()
        folder_name = workspace_path.name or "workspace"
    return {
        "workspace": {
            "name": folder_name,
            "root": str(workspace_path),
        },
        "sources": [
            {
                "path": ".",
                "type": "document",
                "project": "_global",
            },
        ],
        "sync": {
            "auto_sync": True,
            "extensions": [".md", ".csv", ".xlsx", ".docx", ".pdf"],
        },
    }


def load_workspace_config() -> WorkspaceConfig:
    """Load workspace config from workspace.yaml, falling back to auto-detected defaults."""
    project_root = Path(__file__).parent.parent
    yaml_path = project_root / "workspace.yaml"

    if yaml_path.exists():
        with open(yaml_path) as f:
            raw = yaml.safe_load(f) or {}
    else:
        workspace_env = os.environ.get("TESSERA_WORKSPACE")
        if workspace_env:
            logger.info(
                "No workspace.yaml found, using TESSERA_WORKSPACE=%s",
                workspace_env,
            )
        else:
            logger.info(
                "No workspace.yaml found, using auto-detected defaults for %s",
                Path.cwd().name or "workspace",
            )
        raw = _build_auto_detected_defaults()

    ws = raw.get("workspace", {})
    root = Path(ws.get("root", settings.data.base_dir))
    name = ws.get("name", "tessera")

    sources = []
    for s in raw.get("sources", []):
        sources.append(SourceConfig(
            path=s["path"],
            type=s.get("type", "unknown"),
            project=s.get("project", "_global"),
        ))
    # Fallback: use current directory as single document source
    if not sources:
        sources.append(
            SourceConfig(path=".", type="document", project="_global")
        )

    projects = {}
    for pid, pdata in raw.get("projects", {}).items():
        projects[pid] = ProjectConfig(
            id=pid,
            display_name=pdata.get("display_name", pid),
            root=pdata.get("root", pid),
        )

    archive_cfg = raw.get("archive", {})
    archive_dir = archive_cfg.get("directory", "_archive")

    models_cfg = raw.get("models", {})
    embed_model = models_cfg.get("embed_model", settings.models.embed_model)

    sync_cfg = raw.get("sync", {})
    sync_auto = sync_cfg.get("auto_sync", True)
    extensions = sync_cfg.get("extensions", [".md", ".csv"])
    ignore_patterns = sync_cfg.get("ignore", [])

    # Search config
    search_cfg = raw.get("search", {})
    search_config = SearchConfig(
        max_top_k=search_cfg.get("max_top_k", 50),
        reranker_weight=search_cfg.get("reranker_weight", 0.7),
        fetch_multiplier=search_cfg.get("fetch_multiplier", 6),
        result_text_limit=search_cfg.get("result_text_limit", 1500),
        unified_text_limit=search_cfg.get("unified_text_limit", 800),
    )

    # Ingestion config
    ingest_cfg = raw.get("ingestion", {})
    ingestion_config = IngestionConfig(
        chunk_size=ingest_cfg.get("chunk_size", 1024),
        chunk_overlap=ingest_cfg.get("chunk_overlap", 100),
        max_node_chars=ingest_cfg.get("max_node_chars", 800),
        max_meta_value_len=ingest_cfg.get("max_meta_value_len", 200),
    )

    # Watcher config
    watcher_cfg = raw.get("watcher", {})
    watcher_config = WatcherConfig(
        poll_interval=watcher_cfg.get("poll_interval", 30.0),
        debounce=watcher_cfg.get("debounce", 5.0),
    )

    # Knowledge graph config
    kg_cfg = raw.get("knowledge_graph", {})
    kg_config = KnowledgeGraphConfig(
        default_max_nodes=kg_cfg.get("default_max_nodes", 30),
        max_max_nodes=kg_cfg.get("max_max_nodes", 100),
        max_topics=kg_cfg.get("max_topics", 10),
        min_word_length=kg_cfg.get("min_word_length", 4),
    )

    # Limits config
    limits_cfg = raw.get("limits", {})
    limits_config = LimitsConfig(
        max_file_read=limits_cfg.get("max_file_read", 50000),
    )

    # Auto-learn config
    al_cfg = raw.get("auto_learn", {})
    auto_learn_config = AutoLearnConfig(
        enabled=al_cfg.get("enabled", True),
        min_confidence=al_cfg.get("min_confidence", 0.75),
        min_interactions_for_summary=al_cfg.get("min_interactions_for_summary", 3),
    )

    # Validate configs
    _validate_positive("search.max_top_k", search_config.max_top_k)
    _validate_range("search.reranker_weight", search_config.reranker_weight, 0.0, 1.0)
    _validate_positive("search.fetch_multiplier", search_config.fetch_multiplier)
    _validate_positive("ingestion.chunk_size", ingestion_config.chunk_size)
    _validate_positive("ingestion.chunk_overlap", ingestion_config.chunk_overlap, min_val=-1)
    if ingestion_config.chunk_overlap >= ingestion_config.chunk_size:
        raise ConfigValidationError(
            f"ingestion.chunk_overlap ({ingestion_config.chunk_overlap}) "
            f"must be less than chunk_size ({ingestion_config.chunk_size})"
        )
    _validate_positive("watcher.poll_interval", watcher_config.poll_interval)
    _validate_positive("watcher.debounce", watcher_config.debounce, min_val=-1)
    _validate_positive("limits.max_file_read", limits_config.max_file_read)

    return WorkspaceConfig(
        root=root,
        name=name,
        sources=sources,
        projects=projects,
        archive_dir=archive_dir,
        sync_auto=sync_auto,
        extensions=extensions,
        ignore_patterns=ignore_patterns,
        lancedb_path=project_root / "data" / "lancedb",
        meta_db_path=project_root / "data" / "file_meta.db",
        embed_model=embed_model,
        search=search_config,
        ingestion=ingestion_config,
        watcher=watcher_config,
        knowledge_graph=kg_config,
        limits=limits_config,
        auto_learn=auto_learn_config,
    )


workspace = load_workspace_config()
