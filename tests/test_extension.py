"""Tests for Chrome extension structure (Phase 7c)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


EXTENSION_DIR = Path(__file__).parent.parent / "extension"


class TestExtensionManifest:
    def test_manifest_exists(self):
        assert (EXTENSION_DIR / "manifest.json").exists()

    def test_manifest_valid_json(self):
        manifest = json.loads((EXTENSION_DIR / "manifest.json").read_text())
        assert manifest["manifest_version"] == 3
        assert "Tessera" in manifest["name"]

    def test_manifest_has_required_fields(self):
        manifest = json.loads((EXTENSION_DIR / "manifest.json").read_text())
        assert "permissions" in manifest
        assert "contextMenus" in manifest["permissions"]
        assert "storage" in manifest["permissions"]
        assert "background" in manifest
        assert "action" in manifest

    def test_manifest_references_existing_files(self):
        manifest = json.loads((EXTENSION_DIR / "manifest.json").read_text())
        # Background script
        bg = manifest["background"]["service_worker"]
        assert (EXTENSION_DIR / bg).exists()
        # Popup
        popup = manifest["action"]["default_popup"]
        assert (EXTENSION_DIR / popup).exists()
        # Content scripts
        for cs in manifest["content_scripts"]:
            for js in cs["js"]:
                assert (EXTENSION_DIR / js).exists()
            for css in cs.get("css", []):
                assert (EXTENSION_DIR / css).exists()

    def test_host_permissions_localhost(self):
        manifest = json.loads((EXTENSION_DIR / "manifest.json").read_text())
        hosts = manifest.get("host_permissions", [])
        assert any("localhost:8394" in h for h in hosts)


class TestExtensionFiles:
    def test_background_js_exists(self):
        assert (EXTENSION_DIR / "background.js").exists()

    def test_popup_html_exists(self):
        assert (EXTENSION_DIR / "popup.html").exists()

    def test_popup_js_exists(self):
        assert (EXTENSION_DIR / "popup.js").exists()

    def test_content_js_exists(self):
        assert (EXTENSION_DIR / "content.js").exists()

    def test_icons_exist(self):
        for size in [16, 48, 128]:
            assert (EXTENSION_DIR / f"icon{size}.png").exists()

    def test_background_has_tessera_api_calls(self):
        bg = (EXTENSION_DIR / "background.js").read_text()
        assert "/remember" in bg
        assert "/recall" in bg
        assert "/health" in bg

    def test_popup_has_save_and_search(self):
        popup = (EXTENSION_DIR / "popup.js").read_text()
        assert "tessera-save" in popup
        assert "tessera-search" in popup

    def test_no_hardcoded_api_keys(self):
        """Extension should not contain hardcoded API keys."""
        for f in EXTENSION_DIR.glob("*.js"):
            content = f.read_text()
            assert "sk-" not in content
            assert "api_key" not in content.lower() or "apikey" in content.lower() or "apiKey" in content

    def test_xss_prevention_in_popup(self):
        """Popup should escape HTML in search results."""
        popup = (EXTENSION_DIR / "popup.js").read_text()
        assert "escapeHtml" in popup
