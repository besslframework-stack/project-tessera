"""Migration tool for Tessera data upgrades.

Handles schema changes between versions, normalizes memory frontmatter,
and ensures data integrity during upgrades.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

CURRENT_SCHEMA_VERSION = "1.0"


def get_data_dir() -> Path:
    """Get the Tessera data directory."""
    return Path(os.environ.get("TESSERA_DATA_DIR", "./data"))


def detect_version(data_dir: Path | None = None) -> str:
    """Detect the current data schema version.

    Returns version string like "0.6", "0.7", "0.8", "0.9", "1.0".
    """
    data_dir = data_dir or get_data_dir()

    if not data_dir.exists():
        return "none"

    # Check for version marker file
    version_file = data_dir / ".schema_version"
    if version_file.exists():
        return version_file.read_text().strip()

    # Heuristic detection based on files present
    has_memories_db = (data_dir / "memories.db").exists() or (data_dir / "memories").exists()
    has_lancedb = (data_dir / "lancedb").exists() or any(data_dir.glob("*.lance"))
    has_interactions = (data_dir / "interactions.db").exists()
    has_profile = (data_dir / "profile.json").exists()

    if has_profile and has_interactions:
        return "0.9"
    if has_interactions:
        return "0.8"
    if has_lancedb and has_memories_db:
        return "0.7"
    if has_lancedb:
        return "0.6"

    return "unknown"


def create_backup(data_dir: Path | None = None) -> Path | None:
    """Create a backup of the data directory before migration.

    Returns the backup path, or None if no data to back up.
    """
    data_dir = data_dir or get_data_dir()

    if not data_dir.exists():
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = data_dir.parent / f"{data_dir.name}_backup_{timestamp}"

    try:
        shutil.copytree(data_dir, backup_dir)
        logger.info("Backup created at %s", backup_dir)
        return backup_dir
    except Exception as e:
        logger.error("Backup failed: %s", e)
        return None


def normalize_memory(memory: dict) -> dict:
    """Normalize a memory dict to the v1.0 schema.

    Ensures all required fields exist with correct types.
    """
    normalized = {}

    # Content (required)
    content = memory.get("content", "")
    if isinstance(content, str):
        normalized["content"] = content.strip()
    else:
        normalized["content"] = str(content).strip()

    # Date normalization
    date = memory.get("date", memory.get("created_at", memory.get("timestamp", "")))
    normalized["date"] = _normalize_date(str(date)) if date else ""

    # Category
    category = memory.get("category", memory.get("type", "general"))
    valid_categories = {"decision", "preference", "fact", "procedure", "reference", "general"}
    normalized["category"] = category if category in valid_categories else "general"

    # Tags
    tags = memory.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    elif isinstance(tags, list):
        tags = [str(t).strip() for t in tags if t]
    else:
        tags = []
    normalized["tags"] = tags

    # Source
    normalized["source"] = memory.get("source", "")

    # Preserve ID if present
    if "id" in memory:
        normalized["id"] = memory["id"]

    return normalized


def migrate_memories_file(filepath: Path) -> list[dict]:
    """Migrate a JSON memories file to v1.0 format.

    Reads memories from various legacy formats and normalizes them.
    """
    try:
        data = json.loads(filepath.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.error("Failed to read %s: %s", filepath, e)
        return []

    memories = []
    if isinstance(data, list):
        memories = data
    elif isinstance(data, dict):
        # Handle various wrapper formats
        memories = data.get("memories", data.get("data", data.get("items", [])))
        if not isinstance(memories, list):
            memories = [data]

    return [normalize_memory(m) for m in memories if isinstance(m, dict) and m.get("content")]


def write_schema_version(data_dir: Path | None = None, version: str = CURRENT_SCHEMA_VERSION) -> None:
    """Write the schema version marker file."""
    data_dir = data_dir or get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / ".schema_version").write_text(version)


def run_migration(data_dir: Path | None = None, dry_run: bool = False) -> dict:
    """Run the full migration process.

    Returns a summary dict with migration results.
    """
    data_dir = data_dir or get_data_dir()

    current_version = detect_version(data_dir)

    if current_version == CURRENT_SCHEMA_VERSION:
        return {
            "status": "up_to_date",
            "version": current_version,
            "message": "Data is already at the latest schema version.",
        }

    if current_version == "none":
        return {
            "status": "no_data",
            "version": "none",
            "message": "No data directory found. Nothing to migrate.",
        }

    result = {
        "status": "migrated",
        "from_version": current_version,
        "to_version": CURRENT_SCHEMA_VERSION,
        "backup_path": None,
        "memories_processed": 0,
        "memories_normalized": 0,
        "errors": [],
    }

    # Create backup
    if not dry_run:
        backup = create_backup(data_dir)
        result["backup_path"] = str(backup) if backup else None

    # Find and normalize memory files
    json_files = list(data_dir.glob("*.json"))
    for filepath in json_files:
        if filepath.name.startswith("."):
            continue
        try:
            memories = migrate_memories_file(filepath)
            result["memories_processed"] += len(memories)

            if memories and not dry_run:
                # Write normalized data back
                filepath.write_text(
                    json.dumps(memories, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
                result["memories_normalized"] += len(memories)
        except Exception as e:
            result["errors"].append(f"{filepath.name}: {e}")

    # Write version marker
    if not dry_run:
        write_schema_version(data_dir)

    if dry_run:
        result["status"] = "dry_run"
        result["message"] = f"Would migrate {result['memories_processed']} memories from {current_version} to {CURRENT_SCHEMA_VERSION}."
    else:
        result["message"] = f"Migrated {result['memories_normalized']} memories from {current_version} to {CURRENT_SCHEMA_VERSION}."

    return result


def format_migration_result(result: dict) -> str:
    """Format migration result as readable text."""
    lines = ["## Migration Result", ""]

    status = result.get("status", "unknown")
    if status == "up_to_date":
        lines.append("Data is already at the latest schema version (1.0).")
        return "\n".join(lines)

    if status == "no_data":
        lines.append("No data directory found. Start using Tessera to create data.")
        return "\n".join(lines)

    lines.append(f"- Status: {status}")
    if "from_version" in result:
        lines.append(f"- From: v{result['from_version']} → v{result['to_version']}")
    if result.get("backup_path"):
        lines.append(f"- Backup: {result['backup_path']}")
    lines.append(f"- Memories processed: {result.get('memories_processed', 0)}")
    if result.get("memories_normalized"):
        lines.append(f"- Memories normalized: {result['memories_normalized']}")

    errors = result.get("errors", [])
    if errors:
        lines.append(f"\n### Errors ({len(errors)})")
        for err in errors:
            lines.append(f"- {err}")

    if result.get("message"):
        lines.append(f"\n{result['message']}")

    return "\n".join(lines)


def _normalize_date(date_str: str) -> str:
    """Normalize date string to YYYY-MM-DD format."""
    if not date_str:
        return ""
    # Already in ISO format
    if len(date_str) >= 10 and date_str[4] == "-":
        return date_str[:10]
    # Try parsing common formats
    for fmt in ("%Y/%m/%d", "%m/%d/%Y", "%d-%m-%Y", "%Y.%m.%d"):
        try:
            return datetime.strptime(date_str[:10], fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return date_str[:10]
