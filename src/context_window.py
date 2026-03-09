"""Context window builder: assemble optimal context within a token budget.

Selects the most relevant memories + document snippets for a given query,
fitting them within a token budget. Uses simple whitespace tokenization
(~4 chars per token heuristic) to avoid heavy dependencies.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Rough chars-per-token estimate (works for mixed English/Korean)
_CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    """Estimate token count using chars/4 heuristic."""
    return max(1, len(text) // _CHARS_PER_TOKEN)


def build_context_window(
    memories: list[dict],
    documents: list[dict] | None = None,
    token_budget: int = 4000,
    reserve_tokens: int = 500,
    apply_time_decay: bool = False,
    decay_half_life_days: float = 30,
) -> dict:
    """Build an optimal context window within a token budget.

    Args:
        memories: List of memory dicts with 'content', 'score', 'tags', etc.
        documents: Optional list of document dicts with 'content', 'score'.
        token_budget: Total token budget for the context window.
        reserve_tokens: Tokens reserved for system prompt / instructions.
        apply_time_decay: If True, apply time-based relevance decay to scores.
        decay_half_life_days: Half-life for decay (days).

    Returns:
        Dict with 'context' (assembled text), 'token_count', 'included_memories',
        'included_documents', 'truncated' flag.
    """
    if apply_time_decay and memories:
        from src.relevance_decay import apply_decay
        memories = apply_decay(memories, half_life_days=decay_half_life_days)

    available = token_budget - reserve_tokens
    if available <= 0:
        return {
            "context": "",
            "token_count": 0,
            "included_memories": 0,
            "included_documents": 0,
            "truncated": False,
        }

    # Sort by score descending (most relevant first)
    sorted_memories = sorted(memories, key=lambda m: m.get("score", 0), reverse=True)
    sorted_docs = sorted(documents or [], key=lambda d: d.get("score", 0), reverse=True)

    parts: list[str] = []
    used_tokens = 0
    included_memories = 0
    included_documents = 0
    truncated = False

    # Add memories first (higher priority)
    if sorted_memories:
        parts.append("## Relevant Memories")
        used_tokens += estimate_tokens("## Relevant Memories\n")

        for mem in sorted_memories:
            content = mem.get("content", "").strip()
            if not content:
                continue

            entry = _format_memory_entry(mem)
            entry_tokens = estimate_tokens(entry)

            if used_tokens + entry_tokens > available:
                # Try truncating this entry
                remaining_chars = (available - used_tokens) * _CHARS_PER_TOKEN
                if remaining_chars > 50:
                    entry = entry[:remaining_chars - 3] + "..."
                    parts.append(entry)
                    included_memories += 1
                truncated = True
                break

            parts.append(entry)
            used_tokens += entry_tokens
            included_memories += 1

    # Add documents if budget remains
    if sorted_docs and used_tokens < available:
        parts.append("\n## Relevant Documents")
        used_tokens += estimate_tokens("\n## Relevant Documents\n")

        for doc in sorted_docs:
            content = doc.get("content", "").strip()
            if not content:
                continue

            entry = _format_document_entry(doc)
            entry_tokens = estimate_tokens(entry)

            if used_tokens + entry_tokens > available:
                remaining_chars = (available - used_tokens) * _CHARS_PER_TOKEN
                if remaining_chars > 50:
                    entry = entry[:remaining_chars - 3] + "..."
                    parts.append(entry)
                    included_documents += 1
                truncated = True
                break

            parts.append(entry)
            used_tokens += entry_tokens
            included_documents += 1

    context = "\n".join(parts)
    actual_tokens = estimate_tokens(context)

    return {
        "context": context,
        "token_count": actual_tokens,
        "included_memories": included_memories,
        "included_documents": included_documents,
        "truncated": truncated,
    }


def _format_memory_entry(mem: dict) -> str:
    """Format a single memory for context inclusion."""
    content = mem.get("content", "").strip()
    date = mem.get("date", "")[:10] if mem.get("date") else ""
    tags = mem.get("tags", [])
    category = mem.get("category", "")

    parts = []
    if date:
        parts.append(f"[{date}]")
    if category:
        parts.append(f"({category})")
    parts.append(content)
    if tags:
        parts.append(f"  #{' #'.join(tags[:3])}")

    return "- " + " ".join(parts)


def _format_document_entry(doc: dict) -> str:
    """Format a single document snippet for context inclusion."""
    content = doc.get("content", "").strip()
    source = doc.get("source", doc.get("file_path", ""))
    if len(content) > 500:
        content = content[:497] + "..."

    if source:
        return f"- [{source}] {content}"
    return f"- {content}"


def format_context_summary(result: dict) -> str:
    """Format context window result into readable summary."""
    if result["token_count"] == 0:
        return "No relevant context found."

    lines = [
        f"Context assembled: ~{result['token_count']} tokens",
        f"  Memories: {result['included_memories']}",
        f"  Documents: {result['included_documents']}",
    ]
    if result["truncated"]:
        lines.append("  (truncated to fit budget)")

    lines.append("")
    lines.append(result["context"])
    return "\n".join(lines)
