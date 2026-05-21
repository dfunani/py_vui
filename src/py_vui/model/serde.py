from __future__ import annotations

import json
from typing import Any

from pydantic import TypeAdapter

from py_vui.model.project import py_vuiProject

_project_adapter = TypeAdapter(py_vuiProject)


def load_json(data: str | bytes) -> py_vuiProject:
    raw: Any = json.loads(data)
    return _project_adapter.validate_python(raw)


def load_json_bytes(data: bytes) -> py_vuiProject:
    return load_json(data.decode("utf-8"))


def dump_json(project: py_vuiProject, *, indent: int | None = 2) -> str:
    data = project.model_dump(mode="json", by_alias=True)
    return json.dumps(data, indent=indent, sort_keys=True)


def dump_json_bytes(project: py_vuiProject, *, indent: int | None = 2) -> bytes:
    return dump_json(project, indent=indent).encode("utf-8")
