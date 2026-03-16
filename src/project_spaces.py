"""Project spaces: isolate and manage knowledge by project.

Each memory can belong to a project. Project spaces enable scoped recall,
project-specific context priming, and cross-project knowledge discovery.

No LLM calls — metadata-based filtering and aggregation.
"""

from __future__ import annotations

import logging
from collections import Counter
from pathlib import Path

logger = logging.getLogger(__name__)


def list_project_spaces() -> list[dict]:
    """List all project spaces with memory counts and recent activity.

    Returns:
        List of dicts with 'project', 'memory_count', 'latest_date', 'top_tags'.
    """
    from src.memory import _memory_dir

    mem_dir = _memory_dir()
    projects: dict[str, dict] = {}

    for f in mem_dir.glob("*.md"):
        text = f.read_text(encoding="utf-8")
        project = ""
        date = ""
        tags = ""

        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                for line in parts[1].strip().splitlines():
                    if line.startswith("project:"):
                        project = line.split(":", 1)[1].strip()
                    elif line.startswith("date:"):
                        date = line.split(":", 1)[1].strip()[:10]
                    elif line.startswith("tags:"):
                        tags = line.split(":", 1)[1].strip()

        project = project or "(unassigned)"

        if project not in projects:
            projects[project] = {
                "project": project,
                "memory_count": 0,
                "latest_date": "",
                "tag_counter": Counter(),
            }

        projects[project]["memory_count"] += 1
        if date > projects[project]["latest_date"]:
            projects[project]["latest_date"] = date

        for tag in tags.strip("[]").split(","):
            tag = tag.strip()
            if tag and tag != "general":
                projects[project]["tag_counter"][tag.lower()] += 1

    result = []
    for p in sorted(projects.values(), key=lambda x: -x["memory_count"]):
        top_tags = [t for t, _ in p["tag_counter"].most_common(5)]
        result.append({
            "project": p["project"],
            "memory_count": p["memory_count"],
            "latest_date": p["latest_date"],
            "top_tags": top_tags,
        })

    return result


def assign_project(memory_id: str, project: str) -> bool:
    """Assign or reassign a memory to a project space.

    Args:
        memory_id: The memory file stem.
        project: The project name to assign.

    Returns:
        True if successful, False if memory not found.
    """
    from src.memory import _memory_dir

    mem_dir = _memory_dir()
    candidates = list(mem_dir.glob(f"{memory_id}*"))
    if not candidates:
        return False

    file_path = candidates[0]
    text = file_path.read_text(encoding="utf-8")

    if not text.startswith("---"):
        return False

    parts = text.split("---", 2)
    if len(parts) < 3:
        return False

    frontmatter = parts[1]
    body = parts[2]

    # Replace or add project field
    lines = frontmatter.strip().splitlines()
    new_lines = []
    found = False
    for line in lines:
        if line.startswith("project:"):
            new_lines.append(f"project: {project}")
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append(f"project: {project}")

    new_text = "---\n" + "\n".join(new_lines) + "\n---" + body
    file_path.write_text(new_text, encoding="utf-8")

    # Re-index to update LanceDB
    try:
        from src.memory import index_memory
        index_memory(file_path)
    except Exception as exc:
        logger.debug("Re-index after project assign failed: %s", exc)

    return True


def format_project_spaces(spaces: list[dict]) -> str:
    """Format project spaces list as readable text."""
    if not spaces:
        return "No project spaces found. Memories will be created without project assignment until you specify one."

    parts = ["## Project Spaces\n"]
    for s in spaces:
        name = s["project"]
        count = s["memory_count"]
        date = s["latest_date"]
        tags = ", ".join(s["top_tags"][:5]) if s["top_tags"] else "no tags"
        parts.append(f"**{name}** — {count} memories (latest: {date})")
        parts.append(f"  Tags: {tags}\n")

    return "\n".join(parts)
