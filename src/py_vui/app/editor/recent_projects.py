from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings

_SETTINGS_ORG = "py_vui"
_SETTINGS_APP = "editor"
_KEY = "recent_projects"
_MAX = 8


def load_recent() -> list[Path]:
    settings = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
    raw = settings.value(_KEY, [])
    if not isinstance(raw, list):
        return []
    paths: list[Path] = []
    for item in raw:
        p = Path(str(item))
        if p.is_file():
            paths.append(p)
    return paths


def remember(path: Path) -> None:
    path = path.resolve()
    recent = [p for p in load_recent() if p != path]
    recent.insert(0, path)
    settings = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
    settings.setValue(_KEY, [str(p) for p in recent[:_MAX]])
