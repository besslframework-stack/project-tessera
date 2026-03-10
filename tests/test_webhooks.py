"""Tests for webhooks (v0.8.6)."""

from __future__ import annotations

import json
import time
from unittest.mock import MagicMock, patch

import pytest

from src.webhooks import (
    ALL_EVENTS,
    EVENT_MEMORY_CREATED,
    EVENT_SEARCH_PERFORMED,
    _send_webhook,
    fire_event,
    list_webhooks,
    register_webhook,
)


class TestRegisterWebhook:
    def setup_method(self):
        import src.webhooks
        src.webhooks._webhooks = []

    def test_register(self):
        result = register_webhook("https://example.com/hook")
        assert result["registered"] is True
        assert result["url"] == "https://example.com/hook"
        assert len(result["events"]) == len(ALL_EVENTS)

    def test_register_specific_events(self):
        result = register_webhook(
            "https://example.com/hook",
            events={EVENT_MEMORY_CREATED},
        )
        assert result["events"] == [EVENT_MEMORY_CREATED]

    def test_invalid_url(self):
        result = register_webhook("not-a-url")
        assert "error" in result

    def test_list_webhooks(self):
        register_webhook("https://a.com/hook")
        register_webhook("https://b.com/hook")
        hooks = list_webhooks()
        assert len(hooks) == 2


class TestFireEvent:
    def setup_method(self):
        import src.webhooks
        src.webhooks._webhooks = []

    @patch("src.webhooks._send_webhook")
    def test_fires_matching_event(self, mock_send):
        register_webhook("https://example.com/hook", events={EVENT_MEMORY_CREATED})
        fire_event(EVENT_MEMORY_CREATED, {"content": "test"})
        time.sleep(0.1)  # Wait for thread
        mock_send.assert_called_once()
        args = mock_send.call_args[0]
        assert args[0] == "https://example.com/hook"
        assert args[1]["event"] == EVENT_MEMORY_CREATED

    @patch("src.webhooks._send_webhook")
    def test_skips_non_matching_event(self, mock_send):
        register_webhook("https://example.com/hook", events={EVENT_MEMORY_CREATED})
        fire_event(EVENT_SEARCH_PERFORMED)
        time.sleep(0.1)
        mock_send.assert_not_called()

    @patch("src.webhooks._send_webhook")
    def test_no_webhooks(self, mock_send):
        fire_event(EVENT_MEMORY_CREATED)
        mock_send.assert_not_called()

    @patch("src.webhooks._send_webhook")
    def test_multiple_webhooks(self, mock_send):
        register_webhook("https://a.com/hook")
        register_webhook("https://b.com/hook")
        fire_event(EVENT_MEMORY_CREATED)
        time.sleep(0.1)
        assert mock_send.call_count == 2


class TestSendWebhook:
    @patch("src.webhooks.urlopen")
    def test_sends_json(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        _send_webhook("https://example.com/hook", {"event": "test"})
        mock_urlopen.assert_called_once()

    @patch("src.webhooks.urlopen", side_effect=Exception("timeout"))
    def test_handles_error(self, mock_urlopen):
        # Should not raise
        _send_webhook("https://example.com/hook", {"event": "test"})
