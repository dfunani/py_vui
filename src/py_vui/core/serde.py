from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from py_vui.core.migrate import migrate
from py_vui.core.model import Project


def load_json(data: str | bytes) -> Project:
    raw: Any = json.loads(data)
    if not isinstance(raw, dict):
        msg = "project file must contain a JSON object"
        raise ValueError(msg)
    return Project.model_validate(migrate(raw))


def load_file(path: str | Path) -> Project:
    return load_json(Path(path).read_bytes())


def dump_json(project: Project, *, indent: int | None = 2) -> str:
    data = project.model_dump(mode="json", by_alias=True)
    return json.dumps(data, indent=indent, sort_keys=True, ensure_ascii=False)


def dump_json_bytes(project: Project, *, indent: int | None = 2) -> bytes:
    return dump_json(project, indent=indent).encode("utf-8")
