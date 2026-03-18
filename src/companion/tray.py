"""macOS menu bar application using rumps.

Uses HTTP API (port 8394) to communicate with Tessera core,
avoiding heavy dependency imports (lancedb, fastembed, etc.).
"""

from __future__ import annotations

import json
import logging
import webbrowser
from urllib.error import URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

API_BASE = "http://127.0.0.1:8394"


def _api_get(path: str) -> dict | list | str | None:
    """Call Tessera HTTP API (GET). Returns parsed JSON or None on failure."""
    try:
        req = Request(f"{API_BASE}{path}")
        with urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            return data.get("data", data)
    except Exception:
        return None


def _api_post(path: str, body: dict | None = None) -> dict | list | str | None:
    """Call Tessera HTTP API (POST). Returns parsed JSON or None on failure."""
    try:
        payload = json.dumps(body or {}).encode()
        req = Request(f"{API_BASE}{path}", data=payload, method="POST")
        req.add_header("Content-Type", "application/json")
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            return data.get("data", data)
    except Exception:
        return None


def _api_available() -> bool:
    """Check if the API server is reachable."""
    try:
        req = Request(f"{API_BASE}/health")
        with urlopen(req, timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False


class TesseraMenuBar:
    """Menu bar icon + dropdown for Tessera Companion.

    Uses rumps for macOS native menu bar integration.
    Communicates with Tessera via HTTP API (no direct core imports).
    """

    def __init__(self):
        import rumps

        self._persona = self._load_persona()
        name = self._persona.get("name", "Tessera")

        self.app = rumps.App(
            name,
            title="◆",
            quit_button=None,
        )

        # Apply avatar as menu bar icon
        self._apply_avatar()

        # Build menu
        self.app.menu = [
            rumps.MenuItem(f"◆ {name}", callback=self._on_status),
            None,  # separator
            rumps.MenuItem("Quick Memo", callback=self._quick_memo),
            rumps.MenuItem("Quick Search", callback=self._quick_search),
            None,
            rumps.MenuItem("Dashboard", callback=self._open_dashboard),
            rumps.MenuItem("Notification History", callback=self._show_history),
            None,
            rumps.MenuItem("API Server", callback=self._toggle_api),
            None,
            rumps.MenuItem("Persona Settings", callback=self._open_persona_settings),
            rumps.MenuItem("Set Avatar", callback=self._set_avatar),
            rumps.MenuItem("Schedule Settings", callback=self._open_schedule_settings),
            None,
            rumps.MenuItem("Quit Tessera Companion", callback=self._quit),
        ]

        # State
        self._api_running = False
        self._api_process = None
        self._scheduler = None

    def _load_persona(self) -> dict:
        try:
            from src.companion.persona import load_persona
            return load_persona()
        except Exception:
            return {"name": "Tessera", "tone": "friendly"}

    def _apply_avatar(self) -> None:
        """Set menu bar icon from persona avatar image."""
        try:
            from src.companion.persona import get_avatar_path
            avatar = get_avatar_path(self._persona)
            if avatar:
                self.app.icon = avatar
                self.app.title = None  # icon replaces text
            else:
                self.app.icon = None
                self.app.title = "◆"
        except Exception as e:
            logger.debug("Avatar apply failed: %s", e)

    def run(self) -> None:
        """Start the menu bar app + background scheduler."""
        self._start_scheduler()
        self.app.run()

    def _start_scheduler(self) -> None:
        try:
            from src.companion.scheduler import CompanionScheduler
            self._scheduler = CompanionScheduler(
                on_insight=self._on_insight,
                on_daily_summary=self._on_daily_summary,
                on_reminder=self._on_reminder,
            )
            self._scheduler.start()
        except Exception as e:
            logger.warning("Failed to start scheduler: %s", e)

    # --- Quick Actions ---

    def _quick_memo(self, _) -> None:
        """Quick memo: save a thought via API."""
        import rumps
        response = rumps.Window(
            title="Quick Memo",
            message="Type a memo to save:",
            default_text="",
            ok="Save",
            cancel="Cancel",
            dimensions=(320, 100),
        ).run()
        if response.clicked and response.text.strip():
            if not _api_available():
                rumps.alert(title="Error", message="API server not running.\nStart it from the menu first.")
                return
            result = _api_post("/remember", {"content": response.text.strip()})
            if result is not None:
                from src.companion.persona import format_message
                msg = format_message("saved", "", self._persona)
                self._notify("Memo Saved", msg)
            else:
                rumps.alert(title="Error", message="Failed to save memo.")

    def _quick_search(self, _) -> None:
        """Quick search via API."""
        import rumps
        response = rumps.Window(
            title="Quick Search",
            message="Search your knowledge:",
            default_text="",
            ok="Search",
            cancel="Cancel",
            dimensions=(320, 40),
        ).run()
        if response.clicked and response.text.strip():
            if not _api_available():
                rumps.alert(title="Error", message="API server not running.\nStart it from the menu first.")
                return
            from urllib.parse import quote
            results = _api_get(f"/recall?query={quote(response.text.strip())}&top_k=5")
            if not results:
                rumps.alert(title="Search Results", message="No results found.")
                return
            if isinstance(results, str):
                rumps.alert(title=f"Search: {response.text.strip()[:30]}", message=results[:600])
            else:
                rumps.alert(title=f"Search: {response.text.strip()[:30]}", message=str(results)[:600])

    # --- Callbacks ---

    def _on_status(self, _) -> None:
        """Show status summary via API."""
        import rumps
        if not _api_available():
            rumps.alert(
                title=f"◆ {self._persona.get('name', 'Tessera')}",
                message="API server is not running.\nStart it from the menu to see stats.",
            )
            return
        stats = _api_get("/knowledge-stats")
        if stats:
            summary = str(stats)[:400]
            rumps.alert(
                title=f"◆ {self._persona.get('name', 'Tessera')}",
                message=summary,
            )
        else:
            rumps.alert(title="Status", message="Could not fetch stats.")

    def _open_dashboard(self, _) -> None:
        """Open dashboard in browser."""
        webbrowser.open(f"{API_BASE}/dashboard")

    def _show_history(self, _) -> None:
        """Show notification history."""
        import rumps
        try:
            from src.companion.notifier import load_history
            history = load_history()
            if not history:
                rumps.alert(title="Notification History", message="No notifications yet.")
                return
            lines = []
            for n in history[-10:]:
                ts = n.get("timestamp", "")[:16]
                title = n.get("title", "")
                body = n.get("body", "")[:80]
                lines.append(f"[{ts}] {title}: {body}")
            rumps.alert(
                title="Notification History",
                message="\n".join(lines),
            )
        except Exception as e:
            rumps.alert(title="History", message=f"Error: {e}")

    def _toggle_api(self, sender) -> None:
        """Start/stop the API server."""
        import subprocess
        import sys

        if self._api_running and self._api_process:
            self._api_process.terminate()
            self._api_process = None
            self._api_running = False
            sender.title = "API Server"
            self._notify("API Server", "API server stopped")
        else:
            try:
                self._api_process = subprocess.Popen(
                    [sys.executable, "-m", "uvicorn", "src.http_server:app",
                     "--host", "127.0.0.1", "--port", "8394"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self._api_running = True
                sender.title = "API Server ✓"
                self._notify("API Server", "API server started on port 8394")
            except Exception as e:
                logger.warning("Failed to start API server: %s", e)

    def _open_persona_settings(self, _) -> None:
        """Open persona settings dialog."""
        import rumps
        try:
            from src.companion.persona import load_persona, update_persona

            persona = load_persona()
            avatar_display = persona.get("avatar", "") or "(not set)"

            response = rumps.Window(
                title="Persona Settings",
                message=(
                    f"Name: {persona.get('name', 'Tessera')}\n"
                    f"Tone: {persona.get('tone', 'friendly')}\n"
                    f"Avatar: {avatar_display}\n\n"
                    "Enter new name (or leave blank to keep current):"
                ),
                default_text=persona.get("name", "Tessera"),
                ok="Save",
                cancel="Cancel",
            ).run()

            if response.clicked:
                new_name = response.text.strip()
                if new_name:
                    update_persona(name=new_name)
                    self._persona = load_persona()
                    self._notify("Settings", f"Persona updated: {new_name}")
        except Exception as e:
            rumps.alert(title="Error", message=str(e))

    def _set_avatar(self, _) -> None:
        """Set avatar image via file dialog."""
        import rumps
        import subprocess
        try:
            script = (
                'set chosenFile to choose file with prompt '
                '"Choose an avatar image (PNG, JPG, ICNS):" '
                'of type {"public.image"}\n'
                'return POSIX path of chosenFile'
            )
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode == 0 and result.stdout.strip():
                avatar_path = result.stdout.strip()
                from src.companion.persona import update_persona
                update_persona(avatar=avatar_path)
                self._persona = self._load_persona()
                self._apply_avatar()
                self._notify("Settings", f"Avatar set: {avatar_path}")
        except Exception as e:
            rumps.alert(title="Error", message=f"Failed to set avatar: {e}")

    def _open_schedule_settings(self, _) -> None:
        """Show schedule info."""
        import rumps
        try:
            from src.companion.scheduler import DEFAULT_SCHEDULE
            lines = [f"  {k}: {v}" for k, v in DEFAULT_SCHEDULE.items()]
            rumps.alert(
                title="Schedule Settings",
                message="Current schedule:\n" + "\n".join(lines) + "\n\nEdit ~/.tessera/schedule.json to change.",
            )
        except Exception as e:
            rumps.alert(title="Error", message=str(e))

    def _quit(self, _) -> None:
        """Quit the companion."""
        if self._scheduler:
            self._scheduler.stop()
        if self._api_process:
            self._api_process.terminate()
        import rumps
        rumps.quit_application()

    # --- Notification handlers ---

    def _notify(self, title: str, body: str) -> None:
        """Send OS notification with persona name."""
        try:
            from src.companion.notifier import send_notification
            persona_name = self._persona.get("name", "Tessera")
            send_notification(persona_name, body, subtitle=title)
        except Exception as e:
            logger.debug("Notification failed: %s", e)

    def _on_insight(self, insight_data) -> None:
        """Handle new insight from scheduler."""
        from src.companion.persona import format_message
        msg = format_message("insight", str(insight_data)[:200], self._persona)
        self._notify("New Insight", msg)

    def _on_daily_summary(self) -> None:
        """Generate and send daily summary."""
        try:
            from src.companion.persona import get_greeting
            greeting = get_greeting(self._persona)

            parts = [greeting] if greeting else []
            stats = _api_get("/knowledge-stats")
            if stats and isinstance(stats, dict):
                mem_count = stats.get("memory_count", "?")
                parts.append(f"{mem_count} memories stored.")
            else:
                parts.append("Daily summary ready.")

            self._notify("Daily Briefing", " ".join(parts))
        except Exception as e:
            logger.debug("Daily summary failed: %s", e)

    def _on_reminder(self, reminders: list[dict]) -> None:
        """Handle reminders from scheduler."""
        for r in reminders[:3]:
            from src.companion.persona import format_message
            msg = format_message("reminder", r.get("message", ""), self._persona)
            self._notify("Reminder", msg)
