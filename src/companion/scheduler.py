"""Background scheduler for periodic tasks — threading.Timer based."""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

TESSERA_DIR = Path.home() / ".tessera"
SCHEDULE_FILE = TESSERA_DIR / "schedule.json"

DEFAULT_SCHEDULE = {
    "insight_interval_min": 30,
    "daily_summary_hour": 9,
    "daily_summary_min": 0,
    "reminder_interval_min": 120,
    "sleep_consolidation_hour": 3,
    "notification_level": "normal",  # many / normal / few / off
}


class CompanionScheduler:
    """Repeating timer-based scheduler for background tasks."""

    def __init__(self, on_insight=None, on_daily_summary=None, on_reminder=None):
        self._timers: list[threading.Timer] = []
        self._running = False
        self._schedule = self._load_schedule()
        self._on_insight = on_insight
        self._on_daily_summary = on_daily_summary
        self._on_reminder = on_reminder
        self._last_insight_ids: set[str] = set()

    def _load_schedule(self) -> dict:
        if SCHEDULE_FILE.exists():
            try:
                data = json.loads(SCHEDULE_FILE.read_text(encoding="utf-8"))
                return {**DEFAULT_SCHEDULE, **data}
            except Exception:
                pass
        return dict(DEFAULT_SCHEDULE)

    def start(self) -> None:
        """Start all scheduled tasks."""
        if self._running:
            return
        self._running = True
        logger.info("Companion scheduler started")

        # Insight check
        interval = self._schedule["insight_interval_min"] * 60
        self._repeat(self._check_insights, interval, "insight")

        # Reminder check
        r_interval = self._schedule["reminder_interval_min"] * 60
        self._repeat(self._check_reminders, r_interval, "reminder")

        # Daily summary — check every 60s if it's time
        self._repeat(self._check_daily_summary, 60, "daily_summary")

    def stop(self) -> None:
        """Stop all scheduled tasks."""
        self._running = False
        for t in self._timers:
            t.cancel()
        self._timers.clear()
        logger.info("Companion scheduler stopped")

    def _repeat(self, fn, interval: float, name: str) -> None:
        """Run fn every interval seconds."""
        if not self._running:
            return

        def wrapper():
            if not self._running:
                return
            try:
                fn()
            except Exception as e:
                logger.warning("Scheduler task '%s' failed: %s", name, e)
            # Reschedule
            if self._running:
                self._repeat(fn, interval, name)

        t = threading.Timer(interval, wrapper)
        t.daemon = True
        t.name = f"tessera-{name}"
        t.start()
        self._timers.append(t)

    def _api_get(self, path: str):
        """Call Tessera HTTP API (GET). Returns parsed data or None."""
        import json as _json
        from urllib.request import Request, urlopen
        try:
            req = Request(f"http://127.0.0.1:8394{path}")
            with urlopen(req, timeout=5) as resp:
                data = _json.loads(resp.read().decode())
                return data.get("data", data)
        except Exception:
            return None

    def _check_insights(self) -> None:
        """Check for new insights and notify via API."""
        if self._schedule["notification_level"] == "off":
            return
        if self._on_insight is None:
            return

        try:
            result = self._api_get("/auto-insights?days=1")
            if result is None:
                return
            result_id = str(hash(str(result)))[:16]
            if result_id not in self._last_insight_ids:
                self._last_insight_ids.add(result_id)
                if len(self._last_insight_ids) > 50:
                    self._last_insight_ids = set(list(self._last_insight_ids)[-25:])
                self._on_insight(result)
        except Exception as e:
            logger.debug("Insight check failed: %s", e)

    def _check_reminders(self) -> None:
        """Check for pending reminders via API."""
        if self._schedule["notification_level"] == "off":
            return
        if self._on_reminder is None:
            return

        try:
            contradictions = self._api_get("/detect-contradictions")

            reminders = []
            if contradictions and "contradiction" in str(contradictions).lower():
                reminders.append({"type": "contradiction", "message": "미확인 모순이 있습니다"})

            if reminders:
                self._on_reminder(reminders)
        except Exception as e:
            logger.debug("Reminder check failed: %s", e)

    def _check_daily_summary(self) -> None:
        """Check if it's time for daily summary."""
        now = datetime.now()
        target_h = self._schedule["daily_summary_hour"]
        target_m = self._schedule["daily_summary_min"]

        if now.hour == target_h and now.minute == target_m:
            if self._on_daily_summary:
                try:
                    self._on_daily_summary()
                except Exception as e:
                    logger.debug("Daily summary failed: %s", e)
