"""Parse CSV files (event taxonomies, data tables) into LlamaIndex Documents."""

from __future__ import annotations

import csv
from pathlib import Path

from llama_index.core.schema import Document


def parse_csv_file(file_path: Path) -> list[Document]:
    """Parse a CSV file into Documents.

    Handles two CSV formats:
    1. Event taxonomy CSVs — rows may span multiple lines (continuation rows
       where the event name is blank inherit the event from the previous row).
       These are consolidated into one Document per logical event.
    2. Generic CSVs — each row becomes its own Document.

    All Documents carry the source path, filename, file type, and row index.
    """
    try:
        rows = _read_csv(file_path)
    except Exception:
        return []

    if not rows:
        return []

    headers = list(rows[0].keys()) if rows else []

    # Detect event taxonomy format: has an "Event Name" column (Korean or English)
    event_name_col = _find_column(headers, ["Event Name", "event name", "이벤트명"])
    if event_name_col:
        return _parse_event_taxonomy(file_path, rows, event_name_col, headers)

    return _parse_generic(file_path, rows)


def _read_csv(file_path: Path) -> list[dict]:
    """Read CSV with fallback encoding."""
    for encoding in ("utf-8", "utf-8-sig", "cp949"):
        try:
            with open(file_path, encoding=encoding, newline="") as f:
                reader = csv.DictReader(f)
                return [row for row in reader]
        except (UnicodeDecodeError, Exception):
            continue
    return []


def _find_column(headers: list[str], candidates: list[str]) -> str | None:
    """Return the first header that matches any candidate (case-insensitive)."""
    lower_headers = {h.lower(): h for h in headers}
    for candidate in candidates:
        if candidate.lower() in lower_headers:
            return lower_headers[candidate.lower()]
    return None


def _parse_event_taxonomy(
    file_path: Path,
    rows: list[dict],
    event_col: str,
    headers: list[str],
) -> list[Document]:
    """Parse an event taxonomy CSV into one Document per logical event.

    Continuation rows (empty event name) are merged into the previous event.
    Continuation rows (where the event name column is empty) are merged
    into the preceding event's Document.
    """
    documents: list[Document] = []
    current_event: dict | None = None
    current_properties: list[dict] = []
    event_index = 0

    category_col = _find_column(headers, ["구분", "Category", "category"])
    desc_col = _find_column(headers, ["Event Description", "event description", "이벤트 설명"])
    prop_key_col = _find_column(headers, ["Property Key", "property key", "Property Key (속성명)"])
    prop_val_col = _find_column(
        headers,
        ["Property Value", "property value", "Property Value (값 예시)"],
    )
    note_col = _find_column(
        headers,
        ["비고 (Logic & Why)", "비고 (측정 지표)", "비고", "Note", "note"],
    )

    def _flush() -> None:
        nonlocal event_index
        if current_event is None:
            return
        parts = []
        event_name = current_event.get(event_col, "").strip()
        if event_name:
            parts.append(f"Event Name: {event_name}")
        if category_col and current_event.get(category_col, "").strip():
            parts.append(f"Category: {current_event[category_col].strip()}")
        if desc_col and current_event.get(desc_col, "").strip():
            parts.append(f"Description: {current_event[desc_col].strip()}")
        if note_col and current_event.get(note_col, "").strip():
            parts.append(f"Note: {current_event[note_col].strip()}")
        if current_properties:
            prop_lines = []
            for p in current_properties:
                key = p.get(prop_key_col or "", "").strip() if prop_key_col else ""
                val = p.get(prop_val_col or "", "").strip() if prop_val_col else ""
                if key:
                    prop_lines.append(f"  {key}: {val}")
            if prop_lines:
                parts.append("Properties:\n" + "\n".join(prop_lines))

        text = " | ".join(p for p in parts if p)
        if not text:
            return

        meta: dict = {
            "source_path": str(file_path),
            "file_name": file_path.name,
            "file_type": "csv",
            "doc_subtype": "event_taxonomy",
            "row_index": event_index,
        }
        if event_name:
            meta["event_name"] = event_name
            # Extract category segments from event name path (e.g. "industry-research/home/...")
            segments = event_name.split("/")
            if len(segments) >= 1:
                meta["event_service"] = segments[0]
            if len(segments) >= 2:
                meta["event_screen"] = segments[1]
            if len(segments) >= 4:
                meta["event_action"] = segments[3]
        if category_col and current_event.get(category_col, "").strip():
            meta["category"] = current_event[category_col].strip()

        documents.append(Document(text=text, metadata=meta))
        event_index += 1

    for row in rows:
        event_name = row.get(event_col, "").strip()
        if event_name:
            # New event — flush previous
            _flush()
            current_event = dict(row)
            current_properties = []
            # If this row also has a property key, capture it
            if prop_key_col and row.get(prop_key_col, "").strip():
                current_properties.append(dict(row))
        else:
            # Continuation row (property detail)
            if current_event is not None and prop_key_col and row.get(prop_key_col, "").strip():
                current_properties.append(dict(row))

    _flush()
    return documents


def _parse_generic(file_path: Path, rows: list[dict]) -> list[Document]:
    """Parse a generic CSV: one Document per row."""
    documents: list[Document] = []
    for i, row in enumerate(rows):
        text_parts = [f"{k}: {v}" for k, v in row.items() if v and str(v).strip()]
        text = " | ".join(text_parts)
        if not text.strip():
            continue
        documents.append(
            Document(
                text=text,
                metadata={
                    "source_path": str(file_path),
                    "file_name": file_path.name,
                    "file_type": "csv",
                    "doc_subtype": "table",
                    "row_index": i,
                },
            )
        )
    return documents
