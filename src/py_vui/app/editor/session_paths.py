from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

SESSION_DOCUMENT = "py_vui.json"
SESSION_META = "session.meta.json"
APP_SUBDIR = "app"
SESSION_FORMAT = "py_vui-session-v1"


def sanitize_project_slug(name: str) -> str:
    slug = re.sub(r"[^\w\- ]+", "", name.strip())
    slug = re.sub(r"[\s_]+", "-", slug).strip("-").lower()
    return slug or "untitled"


def resolve_project_dir(
    parent: Path, project_name: str, *, current: Path | None = None
) -> Path:
    """Pick <parent>/<slug> or <parent>/<slug>-2 if taken (reuse current folder)."""
    parent = parent.resolve()
    slug = sanitize_project_slug(project_name)
    preferred = parent / slug
    if not preferred.exists() or (
        current is not None and preferred.resolve() == current.resolve()
    ):
        return preferred
    for n in range(2, 1000):
        candidate = parent / f"{slug}-{n}"
        if not candidate.exists():
            return candidate
    msg = f"could not allocate project folder under {parent}"
    raise ValueError(msg)


def export_project_dir(parent: Path, project_name: str) -> Path:
    """`<parent>/<project-slug>/` for exported runnable code."""
    return parent.resolve() / sanitize_project_slug(project_name)


def find_session_file(folder: Path) -> Path | None:
    folder = folder.resolve()
    direct = folder / SESSION_DOCUMENT
    if direct.is_file():
        return direct
    return None


def write_session_meta(project_dir: Path, *, project_name: str, app_version: str = "0.1.0") -> Path:
    meta_path = project_dir / SESSION_META
    payload = {
        "format": SESSION_FORMAT,
        "project_name": project_name,
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "py_vui_version": app_version,
        "document": SESSION_DOCUMENT,
        "app_output_dir": APP_SUBDIR,
    }
    meta_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return meta_path
