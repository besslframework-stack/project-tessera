"""Tessera Companion — Always-on personal knowledge assistant for macOS.

Menu bar icon + background scheduler + global hotkeys + OS notifications.
"""

from __future__ import annotations

import logging
import sys

logger = logging.getLogger(__name__)


def start_companion() -> None:
    """Entry point for the Tessera Companion process."""
    if sys.platform != "darwin":
        print("Tessera Companion currently supports macOS only.")
        sys.exit(1)

    try:
        import rumps  # noqa: F401
    except ImportError:
        print("Companion requires extra dependencies. Install with:")
        print("  pip install project-tessera[companion]")
        sys.exit(1)

    from src.companion.tray import TesseraMenuBar

    app = TesseraMenuBar()
    app.run()


if __name__ == "__main__":
    start_companion()
