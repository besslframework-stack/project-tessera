"""macOS notification system via osascript (no external dependencies)."""

from __future__ import annotations

import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

TESSERA_DIR = Path.home() / ".tessera"
HISTORY_FILE = TESSERA_DIR / "notification_history.json"
MAX_HISTORY = 100


def send_notification(
    title: str,
    body: str,
    subtitle: str = "",
    sound: str = "default",
) -> bool:
    """Send a macOS notification via osascript.

    Args:
        title: Notification title (e.g. persona name).
        body: Notification body text.
        subtitle: Optional subtitle.
        sound: Sound name or "" for silent.

    Returns:
        True if notification was sent successfully.
    """
    try:
        # Build AppleScript command
        parts = [f'display notification "{_osa_escape(body)}"']
        parts.append(f'with title "{_osa_escape(title)}"')
        if subtitle:
            parts.append(f'subtitle "{_osa_escape(subtitle)}"')
        if sound:
            parts.append(f'sound name "{sound}"')

        script = " ".join(parts)
        subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            timeout=5,
        )
        _save_to_history(title, body, subtitle)
        return True
    except Exception as e:
        logger.warning("Notification failed: %s", e)
        return False


def _osa_escape(text: str) -> str:
    """Escape text for AppleScript string."""
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _save_to_history(title: str, body: str, subtitle: str = "") -> None:
    """Save notification to history file."""
    try:
        TESSERA_DIR.mkdir(parents=True, exist_ok=True)
        history = load_history()
        history.append({
            "title": title,
            "body": body,
            "subtitle": subtitle,
            "timestamp": datetime.now().isoformat(),
        })
        # Keep only last MAX_HISTORY
        history = history[-MAX_HISTORY:]
        HISTORY_FILE.write_text(
            json.dumps(history, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        logger.debug("Failed to save notification history: %s", e)


def load_history() -> list[dict]:
    """Load notification history."""
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def clear_history() -> None:
    """Clear notification history."""
    if HISTORY_FILE.exists():
        HISTORY_FILE.unlink()
