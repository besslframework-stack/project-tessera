"""LaunchAgent installer for macOS — auto-start on login."""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

PLIST_NAME = "com.tessera.companion"
PLIST_DIR = Path.home() / "Library" / "LaunchAgents"
TESSERA_DIR = Path.home() / ".tessera"


def _plist_path() -> Path:
    return PLIST_DIR / f"{PLIST_NAME}.plist"


def _plist_content() -> str:
    """Generate LaunchAgent plist XML."""
    python = sys.executable
    log_path = TESSERA_DIR / "companion.log"

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{PLIST_NAME}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python}</string>
        <string>-m</string>
        <string>src.companion</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{log_path}</string>
    <key>StandardErrorPath</key>
    <string>{log_path}</string>
    <key>LowPriorityIO</key>
    <true/>
    <key>ProcessType</key>
    <string>Background</string>
</dict>
</plist>"""


def install() -> str:
    """Install LaunchAgent and load it."""
    PLIST_DIR.mkdir(parents=True, exist_ok=True)
    TESSERA_DIR.mkdir(parents=True, exist_ok=True)

    plist = _plist_path()
    plist.write_text(_plist_content(), encoding="utf-8")

    # Load the agent
    try:
        subprocess.run(
            ["launchctl", "load", str(plist)],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception as e:
        logger.warning("launchctl load failed: %s", e)

    return f"Companion installed. LaunchAgent: {plist}"


def uninstall() -> str:
    """Unload and remove LaunchAgent."""
    plist = _plist_path()

    if plist.exists():
        try:
            subprocess.run(
                ["launchctl", "unload", str(plist)],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except Exception:
            pass
        plist.unlink()
        return "Companion uninstalled."
    return "Companion was not installed."


def status() -> dict:
    """Check companion status."""
    plist = _plist_path()
    installed = plist.exists()

    running = False
    if installed:
        try:
            result = subprocess.run(
                ["launchctl", "list", PLIST_NAME],
                capture_output=True,
                text=True,
                timeout=5,
            )
            running = result.returncode == 0
        except Exception:
            pass

    return {
        "installed": installed,
        "running": running,
        "plist_path": str(plist) if installed else None,
        "log_path": str(TESSERA_DIR / "companion.log"),
    }


def start() -> str:
    """Start the companion (load LaunchAgent)."""
    plist = _plist_path()
    if not plist.exists():
        return "Companion not installed. Run: tessera companion install"
    try:
        subprocess.run(["launchctl", "load", str(plist)], capture_output=True, timeout=10)
        return "Companion started."
    except Exception as e:
        return f"Failed to start: {e}"


def stop() -> str:
    """Stop the companion (unload LaunchAgent)."""
    plist = _plist_path()
    if not plist.exists():
        return "Companion not installed."
    try:
        subprocess.run(["launchctl", "unload", str(plist)], capture_output=True, timeout=10)
        return "Companion stopped."
    except Exception as e:
        return f"Failed to stop: {e}"
