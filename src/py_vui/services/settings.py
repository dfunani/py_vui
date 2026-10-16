"""Tiny JSON key/value store for editor settings (``$PY_VUI_HOME/settings.json``)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def home_dir() -> Path:
    """Per-user py_vui directory. ``PY_VUI_HOME`` overrides ``~/.py_vui`` (used by tests)."""
    env = os.environ.get("PY_VUI_HOME")
    return Path(env).expanduser() if env else Path.home() / ".py_vui"


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def write_json(path: Path, data: Any) -> None:
    """Atomically write JSON; failures (read-only home, …) are swallowed on purpose."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        pass


def _path() -> Path:
    return home_dir() / "settings.json"


def _load() -> dict[str, Any]:
    data = read_json(_path(), {})
    return data if isinstance(data, dict) else {}


def get(key: str, default: Any = None) -> Any:
    return _load().get(key, default)


def set(key: str, value: Any) -> None:
    data = _load()
    data[key] = value
    write_json(_path(), data)
