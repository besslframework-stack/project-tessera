"""Universal text/code parser for plain text, code, config, and markup files.

Handles all text-based file formats that don't need specialized parsing:
- Code: .py, .js, .ts, .tsx, .jsx, .java, .go, .rs, .rb, .php, .c, .cpp, .h,
        .swift, .kt, .sh, .bash, .zsh, .sql, .r, .lua, .scala, .pl
- Config: .json, .yaml, .yml, .toml, .xml, .ini, .cfg, .conf, .env
- Text: .txt, .rst, .log
- Web: .html, .htm, .css, .scss, .less, .svg
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from llama_index.core.schema import Document

logger = logging.getLogger(__name__)

# Language detection by extension
_LANG_MAP: dict[str, str] = {
    ".py": "python", ".pyw": "python",
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".ts": "typescript", ".tsx": "typescript-react",
    ".jsx": "javascript-react",
    ".java": "java", ".kt": "kotlin", ".kts": "kotlin",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
    ".c": "c", ".h": "c-header",
    ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp", ".hpp": "cpp-header",
    ".swift": "swift",
    ".sh": "shell", ".bash": "shell", ".zsh": "shell",
    ".sql": "sql",
    ".r": "r", ".R": "r",
    ".lua": "lua",
    ".scala": "scala",
    ".pl": "perl", ".pm": "perl",
    ".cs": "csharp",
    ".dart": "dart",
    ".ex": "elixir", ".exs": "elixir",
    ".hs": "haskell",
    ".json": "json", ".jsonl": "json",
    ".yaml": "yaml", ".yml": "yaml",
    ".toml": "toml",
    ".xml": "xml",
    ".ini": "ini", ".cfg": "ini", ".conf": "config",
    ".env": "env",
    ".html": "html", ".htm": "html",
    ".css": "css", ".scss": "scss", ".less": "less",
    ".svg": "svg",
    ".txt": "text", ".rst": "rst", ".log": "log",
    ".graphql": "graphql", ".gql": "graphql",
    ".proto": "protobuf",
    ".tf": "terraform", ".hcl": "hcl",
    ".dockerfile": "dockerfile",
    ".makefile": "makefile",
    ".gradle": "gradle",
}

# Extensions that should have HTML tags stripped
_STRIP_HTML = {".html", ".htm", ".svg"}

# All supported extensions
SUPPORTED_EXTENSIONS: set[str] = set(_LANG_MAP.keys())


def _detect_language(file_path: Path) -> str:
    """Detect programming language from file extension."""
    suffix = file_path.suffix.lower()
    # Special cases for files without standard extensions
    name_lower = file_path.name.lower()
    if name_lower == "dockerfile":
        return "dockerfile"
    if name_lower == "makefile":
        return "makefile"
    if name_lower in (".gitignore", ".dockerignore", ".eslintignore"):
        return "ignore"
    return _LANG_MAP.get(suffix, "text")


def _strip_html_tags(text: str) -> str:
    """Strip HTML tags, keeping text content."""
    # Remove script and style blocks entirely
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", text, flags=re.DOTALL | re.IGNORECASE)
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Decode common HTML entities
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&nbsp;", " ").replace("&quot;", '"')
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_text_file(file_path: Path) -> list[Document]:
    """Parse a text/code/config file into Documents.

    For code files: creates one Document per file with language metadata.
    For HTML/SVG: strips tags and extracts text content.
    """
    try:
        text = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            text = file_path.read_text(encoding="cp949", errors="replace")
        except Exception:
            logger.debug("Cannot decode file: %s", file_path)
            return []
    except OSError as exc:
        logger.debug("Cannot read file %s: %s", file_path, exc)
        return []

    if not text.strip():
        return []

    # Skip very large files (> 500KB of text)
    if len(text) > 500_000:
        logger.debug("File too large, truncating: %s (%d bytes)", file_path, len(text))
        text = text[:500_000]

    language = _detect_language(file_path)
    suffix = file_path.suffix.lower()

    # Strip HTML for web files
    display_text = text
    if suffix in _STRIP_HTML:
        display_text = _strip_html_tags(text)
        if not display_text.strip():
            return []

    metadata = {
        "source_path": str(file_path),
        "file_name": file_path.name,
        "file_type": language,
        "doc_type": "code" if language not in ("text", "rst", "log", "json", "yaml", "toml", "xml", "ini", "config", "env", "html", "svg") else "document",
        "language": language,
        "line_count": text.count("\n") + 1,
        "char_count": len(text),
    }

    return [Document(text=display_text, metadata=metadata)]
