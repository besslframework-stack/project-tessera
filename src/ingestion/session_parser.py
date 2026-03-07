"""Parse Claude session logs into LlamaIndex Documents."""

from __future__ import annotations

import re
from pathlib import Path

from llama_index.core.schema import Document

# Known section headings in session log files (Korean and English)
_KNOWN_SECTIONS = {
    "메타데이터": "metadata",
    "완료된 작업": "completed_tasks",
    "주요 변경사항": "changes",
    "주요 의사결정": "decisions",
    "미완료/다음 작업": "next_tasks",
    "다음 세션 시작점": "next_session",
    "인사이트": "insights",
}


def parse_session_file(file_path: Path) -> list[Document]:
    """Parse a session log markdown file.

    Session logs have a specific structure with metadata, completed tasks,
    changes, and next steps. Each major section becomes a Document.
    The full file is also included for cross-section extraction.
    """
    try:
        text = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = file_path.read_text(encoding="cp949", errors="replace")
    except OSError:
        return []

    metadata = _extract_session_metadata(file_path, text)

    documents: list[Document] = []

    # Extract structured sections by H2 headers
    sections = re.split(r"(?=^## )", text, flags=re.MULTILINE)
    for section in sections:
        section = section.strip()
        if not section:
            continue
        header_match = re.match(r"^## (.+)", section)
        raw_section_name = header_match.group(1).strip() if header_match else "intro"
        # Normalize section name using known mapping
        section_name = _KNOWN_SECTIONS.get(raw_section_name, raw_section_name)
        documents.append(
            Document(
                text=section,
                metadata={**metadata, "section": section_name},
            )
        )

    return documents


def parse_session_directory(dir_path: Path) -> list[Document]:
    """Parse all session log files in a directory."""
    documents: list[Document] = []
    if not dir_path.exists():
        return documents
    for md_file in sorted(dir_path.rglob("*.md")):
        if md_file.name in ("README.md", "CLAUDE.md"):
            continue
        try:
            documents.extend(parse_session_file(md_file))
        except Exception:
            continue
    return documents


def _extract_session_metadata(file_path: Path, text: str) -> dict:
    """Extract metadata from session log content."""
    metadata: dict = {
        "source_path": str(file_path),
        "file_name": file_path.name,
        "file_type": "session_log",
        "doc_type": "session_log",
    }

    # Extract date from filename pattern: topic_YYYYMMDD.md
    date_match = re.search(r"_(\d{8})\.md$", file_path.name)
    if date_match:
        raw = date_match.group(1)
        metadata["date"] = f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"

    # Also look for date in metadata section content
    if "date" not in metadata:
        content_date = re.search(
            r"(?:날짜|date)[:\s]+([\d]{4}[-./][\d]{1,2}[-./][\d]{1,2})",
            text,
            re.IGNORECASE,
        )
        if content_date:
            metadata["date"] = content_date.group(1).strip()

    # Extract project from metadata section (Korean: 프로젝트)
    project_match = re.search(r"프로젝트:\s*(.+)", text)
    if project_match:
        metadata["project"] = project_match.group(1).strip()

    # Extract title from H1
    h1_match = re.search(r"^# (.+)", text, re.MULTILINE)
    if h1_match:
        metadata["title"] = h1_match.group(1).strip()

    # Extract list of completed tasks as a summary field
    completed_match = re.search(
        r"^## 완료된 작업\s*\n(.*?)(?=^## |\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if completed_match:
        # Extract bullet points / numbered items
        items = re.findall(r"^[-\d*]+[\.\)]\s*\*?\*?(.+?)\*?\*?$",
                           completed_match.group(1), re.MULTILINE)
        if items:
            metadata["completed_tasks_summary"] = "; ".join(items[:5])

    # Extract next steps
    next_match = re.search(
        r"^## (?:미완료/다음 작업|다음 세션 시작점)\s*\n(.*?)(?=^## |\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if next_match:
        items = re.findall(r"^[-\d*]+[\.\)]\s*(.+)$", next_match.group(1), re.MULTILINE)
        if items:
            metadata["next_tasks_summary"] = "; ".join(items[:3])

    return metadata
