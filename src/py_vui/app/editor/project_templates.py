from __future__ import annotations

from pathlib import Path

from py_vui.model.serde import load_json_bytes
from py_vui.model.project import py_vuiProject

_TEMPLATES_DIR = Path(__file__).resolve().parents[4] / "examples" / "templates"

TEMPLATE_NAMES = {
    "empty": "Empty window",
    "dialog": "Dialog with OK/Cancel",
    "settings": "Settings form",
}


def list_templates() -> list[tuple[str, str]]:
    return [(key, label) for key, label in TEMPLATE_NAMES.items()]


def load_template(key: str) -> py_vuiProject:
    path = _TEMPLATES_DIR / f"{key}.json"
    if not path.is_file():
        msg = f"unknown template: {key!r}"
        raise FileNotFoundError(msg)
    return load_json_bytes(path.read_bytes())
