"""Plugin hooks: extensibility points for custom scripts and integrations.

Inspired by Claudel's plugin system (pre_scan, post_scan hooks).
Users can register local scripts or Python callables that fire on events.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

# Hook event types
EVENTS = (
    "on_memory_created",
    "on_memory_deleted",
    "on_search",
    "on_session_start",
    "on_session_end",
    "on_ingest_complete",
    "on_contradiction_found",
)

# Registry: event_name -> list of hook functions/scripts
_hooks: dict[str, list[dict]] = {event: [] for event in EVENTS}


def register_hook(
    event: str,
    handler: Callable[..., Any] | str,
    name: str | None = None,
) -> bool:
    """Register a hook for an event.

    Args:
        event: Event name (must be one of EVENTS).
        handler: Python callable or path to shell script.
        name: Optional name for identification.

    Returns:
        True if registered, False if invalid event.
    """
    if event not in _hooks:
        logger.warning("Unknown hook event: %s. Valid events: %s", event, ", ".join(EVENTS))
        return False

    hook = {
        "name": name or (handler if isinstance(handler, str) else handler.__name__),
        "handler": handler,
        "type": "script" if isinstance(handler, str) else "callable",
    }

    _hooks[event].append(hook)
    logger.info("Hook registered: %s -> %s", event, hook["name"])
    return True


def unregister_hook(event: str, name: str) -> bool:
    """Remove a hook by name.

    Args:
        event: Event name.
        name: Hook name to remove.

    Returns:
        True if found and removed.
    """
    if event not in _hooks:
        return False

    before = len(_hooks[event])
    _hooks[event] = [h for h in _hooks[event] if h["name"] != name]
    return len(_hooks[event]) < before


def fire_event(event: str, **context) -> list[dict]:
    """Fire all hooks registered for an event.

    Args:
        event: Event name.
        **context: Context data passed to handlers.

    Returns:
        List of results from each hook execution.
    """
    if event not in _hooks:
        return []

    hooks = _hooks[event]
    if not hooks:
        return []

    results = []
    for hook in hooks:
        try:
            if hook["type"] == "callable":
                result = hook["handler"](**context)
                results.append({
                    "name": hook["name"],
                    "status": "ok",
                    "result": result,
                })
            elif hook["type"] == "script":
                result = _run_script(hook["handler"], context)
                results.append({
                    "name": hook["name"],
                    "status": "ok",
                    "result": result,
                })
        except Exception as exc:
            logger.warning("Hook %s failed on %s: %s", hook["name"], event, exc)
            results.append({
                "name": hook["name"],
                "status": "error",
                "error": str(exc),
            })

    return results


def _run_script(script_path: str, context: dict) -> str:
    """Execute a shell script with context as environment variables.

    Args:
        script_path: Path to the script.
        context: Dict of context values (converted to env vars with TESSERA_ prefix).

    Returns:
        Script stdout (truncated to 1000 chars).
    """
    path = Path(script_path)
    if not path.exists():
        raise FileNotFoundError(f"Hook script not found: {script_path}")

    env_vars = {}
    for key, value in context.items():
        env_key = f"TESSERA_{key.upper()}"
        env_vars[env_key] = str(value)[:500]

    import os
    full_env = {**os.environ, **env_vars}

    result = subprocess.run(
        [str(path)],
        capture_output=True,
        text=True,
        timeout=10,
        env=full_env,
    )

    if result.returncode != 0:
        logger.warning("Hook script %s exited with code %d: %s", script_path, result.returncode, result.stderr[:200])

    return result.stdout[:1000]


def list_hooks() -> dict[str, list[str]]:
    """List all registered hooks by event.

    Returns:
        Dict mapping event names to lists of hook names.
    """
    return {
        event: [h["name"] for h in hooks]
        for event, hooks in _hooks.items()
        if hooks
    }


def clear_hooks(event: str | None = None) -> int:
    """Clear hooks for an event or all events.

    Args:
        event: Specific event to clear, or None for all.

    Returns:
        Number of hooks removed.
    """
    count = 0
    if event:
        if event in _hooks:
            count = len(_hooks[event])
            _hooks[event] = []
    else:
        for evt in _hooks:
            count += len(_hooks[evt])
            _hooks[evt] = []
    return count


def load_hooks_from_config(config_path: Path | None = None) -> int:
    """Load hooks from workspace configuration.

    Looks for hooks section in workspace.yaml:
        hooks:
          on_memory_created:
            - /path/to/script.sh
          on_search:
            - /path/to/notify.sh

    Args:
        config_path: Path to workspace.yaml. Auto-detected if None.

    Returns:
        Number of hooks loaded.
    """
    if config_path is None:
        config_path = Path(__file__).parent.parent / "workspace.yaml"

    if not config_path.exists():
        return 0

    try:
        import yaml
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}
    except Exception as exc:
        logger.debug("Could not load hooks config: %s", exc)
        return 0

    hooks_config = config.get("hooks", {})
    if not isinstance(hooks_config, dict):
        return 0

    count = 0
    for event, scripts in hooks_config.items():
        if not isinstance(scripts, list):
            scripts = [scripts]
        for script in scripts:
            if isinstance(script, str) and register_hook(event, script):
                count += 1

    return count
