"""Application configuration loaded from environment variables and workspace.yaml."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class ModelConfig:
    embed_model: str = os.getenv("EMBED_MODEL", "nomic-embed-text-v2-moe")
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


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
    ollama_base_url: str

    def resolve_source_path(self, source: SourceConfig) -> Path:
        return self.root / source.path

    def resolve_project_root(self, project_id: str) -> Path | None:
        proj = self.projects.get(project_id)
        if proj is None:
            return None
        return self.root / proj.root

    def all_source_paths(self) -> list[Path]:
        return [self.resolve_source_path(s) for s in self.sources]


def load_workspace_config() -> WorkspaceConfig:
    """Load workspace config from workspace.yaml, falling back to hardcoded defaults."""
    project_root = Path(__file__).parent.parent
    yaml_path = project_root / "workspace.yaml"

    if yaml_path.exists():
        with open(yaml_path) as f:
            raw = yaml.safe_load(f)
    else:
        raw = {}

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
    # Fallback: use hardcoded tier1 + tier2 if no sources in yaml
    if not sources:
        for p in settings.data.tier1_sources + settings.data.tier2_sources:
            rel = str(p.relative_to(root))
            sources.append(SourceConfig(path=rel, type="unknown", project="_global"))

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
    ollama_base_url = models_cfg.get("ollama_base_url", settings.models.ollama_base_url)

    sync_cfg = raw.get("sync", {})
    sync_auto = sync_cfg.get("auto_sync", True)
    extensions = sync_cfg.get("extensions", [".md", ".csv"])
    ignore_patterns = sync_cfg.get("ignore", [])

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
        ollama_base_url=ollama_base_url,
    )


workspace = load_workspace_config()
