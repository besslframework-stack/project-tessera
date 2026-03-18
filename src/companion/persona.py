"""Persona management — profile image, name, tone customization."""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

TESSERA_DIR = Path.home() / ".tessera"

DEFAULT_PERSONA = {
    "name": "Tessera",
    "avatar": "",
    "tone": "friendly",
    "greeting": "",
    "locale": "ko",
}

TONES = {
    "friendly": {
        "greeting_ko": "좋은 아침이에요!",
        "greeting_en": "Good morning!",
        "insight": "{name}: {message}",
        "reminder": "{name}: {message}",
        "saved": "기억했어요 ✓",
        "summary": "{name}: {message}",
    },
    "formal": {
        "greeting_ko": "좋은 아침입니다.",
        "greeting_en": "Good morning.",
        "insight": "[{name}] {message}",
        "reminder": "[{name}] {message}",
        "saved": "저장 완료.",
        "summary": "[{name}] {message}",
    },
    "casual": {
        "greeting_ko": "좋은 아침~",
        "greeting_en": "Morning!",
        "insight": "{name}: {message}",
        "reminder": "{name}: {message}",
        "saved": "OK 저장~",
        "summary": "{name}: {message}",
    },
    "minimal": {
        "greeting_ko": "",
        "greeting_en": "",
        "insight": "{message}",
        "reminder": "{message}",
        "saved": "✓",
        "summary": "{message}",
    },
}


def _config_path() -> Path:
    return TESSERA_DIR / "persona.json"


def load_persona() -> dict:
    """Load persona config from ~/.tessera/persona.json."""
    path = _config_path()
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            result = {**DEFAULT_PERSONA, **data}
            return result
        except Exception as e:
            logger.warning("Failed to load persona config: %s", e)
    return dict(DEFAULT_PERSONA)


def save_persona(persona: dict) -> Path:
    """Save persona config to ~/.tessera/persona.json."""
    TESSERA_DIR.mkdir(parents=True, exist_ok=True)
    path = _config_path()
    path.write_text(json.dumps(persona, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Persona saved: %s", path)
    return path


def update_persona(**kwargs) -> dict:
    """Update specific persona fields."""
    persona = load_persona()
    for k, v in kwargs.items():
        if k in DEFAULT_PERSONA and v is not None:
            persona[k] = v
    save_persona(persona)
    return persona


def get_tone_templates(tone: str = "friendly") -> dict:
    """Get message templates for a given tone."""
    return TONES.get(tone, TONES["friendly"])


def format_message(
    template_key: str,
    message: str = "",
    persona: dict | None = None,
) -> str:
    """Format a message using persona's tone templates."""
    if persona is None:
        persona = load_persona()
    tone = persona.get("tone", "friendly")
    templates = get_tone_templates(tone)
    template = templates.get(template_key, "{message}")
    return template.format(name=persona.get("name", "Tessera"), message=message)


def get_greeting(persona: dict | None = None) -> str:
    """Get the greeting message based on persona locale and tone."""
    if persona is None:
        persona = load_persona()
    tone = persona.get("tone", "friendly")
    locale = persona.get("locale", "ko")
    templates = get_tone_templates(tone)

    # Custom greeting overrides
    custom = persona.get("greeting", "")
    if custom:
        return custom

    key = f"greeting_{locale}" if f"greeting_{locale}" in templates else "greeting_ko"
    return templates.get(key, "")


def get_avatar_path(persona: dict | None = None) -> str:
    """Get resolved avatar path."""
    if persona is None:
        persona = load_persona()
    avatar = persona.get("avatar", "")
    if avatar:
        p = Path(avatar).expanduser()
        if p.exists():
            return str(p)
    return ""
