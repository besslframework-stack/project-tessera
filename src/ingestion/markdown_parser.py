"""Parse markdown files (PRDs, decision logs) into LlamaIndex Documents."""

from __future__ import annotations

import re
from pathlib import Path

from llama_index.core.schema import Document


def parse_markdown_file(file_path: Path) -> list[Document]:
    """Parse a single markdown file into Documents, split by H2 sections.

    Each H2 section becomes a separate Document with metadata from the file
    and section header. The full file is also included as a Document for
    cross-section entity extraction.
    """
    try:
        text = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = file_path.read_text(encoding="cp949", errors="replace")
    except OSError:
        return []

    metadata = _extract_file_metadata(file_path, text)

    documents: list[Document] = []

    # Split by H2 sections; content before the first H2 is the intro
    sections = re.split(r"(?=^## )", text, flags=re.MULTILINE)
    for section in sections:
        section = section.strip()
        if not section:
            continue
        header_match = re.match(r"^## (.+)", section)
        section_name = header_match.group(1).strip() if header_match else "intro"
        # Skip sections that are just whitespace after stripping the header
        content = section
        if not content:
            continue
        documents.append(
            Document(
                text=content,
                metadata={**metadata, "section": section_name},
            )
        )

    return documents


def parse_markdown_directory(dir_path: Path) -> list[Document]:
    """Parse all markdown files in a directory recursively."""
    documents: list[Document] = []
    if not dir_path.exists():
        return documents
    for md_file in sorted(dir_path.rglob("*.md")):
        try:
            documents.extend(parse_markdown_file(md_file))
        except Exception:
            # Skip files that cannot be parsed
            continue
    return documents


def _extract_file_metadata(file_path: Path, text: str) -> dict:
    """Extract metadata from file path and content."""
    metadata: dict = {
        "source_path": str(file_path),
        "file_name": file_path.name,
        "file_type": "markdown",
    }

    # Detect document type from path/content
    path_str = str(file_path).lower()
    if "prd" in path_str:
        metadata["doc_type"] = "prd"
    elif "decision" in path_str:
        metadata["doc_type"] = "decision_log"
    elif "session" in path_str or "claude_sessions" in path_str:
        metadata["doc_type"] = "session_log"
    else:
        metadata["doc_type"] = "document"

    # Extract version from filename pattern PRD_xxx_v1.md or v3.19 in filename/title
    version_match = re.search(r"[_\s]v(\d+(?:\.\d+)+)", file_path.stem, re.IGNORECASE)
    if not version_match:
        version_match = re.search(r"_v(\d+(?:\.\d+)?)", file_path.stem)
    if version_match:
        metadata["version"] = version_match.group(1)

    # Extract project from path segments
    parts = file_path.parts
    for part in parts:
        if part.startswith("valley_"):
            metadata["project"] = part
            break
    # Fallback: check for known project folders
    if "project" not in metadata:
        for part in parts:
            if part in ("valley", "valley_industry_research", "valley_llm", "ralph",
                        "youtuber_insights", "skills"):
                metadata["project"] = part
                break

    # Extract title from H1
    h1_match = re.search(r"^# (.+)", text, re.MULTILINE)
    if h1_match:
        metadata["title"] = h1_match.group(1).strip()

    # Extract date from Korean date patterns in content
    date_match = re.search(
        r"(?:작성일|날짜|일자|date)[:\s]+([\d]{4}[-./][\d]{1,2}[-./][\d]{1,2})",
        text,
        re.IGNORECASE,
    )
    if date_match:
        metadata["date"] = date_match.group(1).strip()

    # Extract date from filename pattern (YYYYMMDD or YYMMDD)
    if "date" not in metadata:
        fname_date = re.search(r"_(\d{8})\.", file_path.name)
        if fname_date:
            raw = fname_date.group(1)
            metadata["date"] = f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
        else:
            fname_date = re.search(r"(\d{6})\.", file_path.name)
            if fname_date:
                raw = fname_date.group(1)
                metadata["date"] = f"20{raw[:2]}-{raw[2:4]}-{raw[4:6]}"

    return metadata
