"""Bundled project templates (``py_vui/templates/*.json``, schema v2).

A template file is ``{"template": {name, description, category, tags}, "project": <v2 project>}``.
Node ids inside the file are human readable; :func:`load_template` replaces them with fresh
UUIDs on every call so two projects made from one template never share ids.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib import resources
from typing import Any
from uuid import uuid4

from py_vui.core.model import Project
from py_vui.core.serde import load_json


@dataclass
class TemplateInfo:
    id: str
    name: str
    description: str
    category: str
    tags: list[str] = field(default_factory=list)
    widget_types: list[str] = field(default_factory=list)


def _files() -> dict[str, Any]:
    root = resources.files("py_vui").joinpath("templates")
    return {p.name[:-5]: p for p in root.iterdir() if p.name.endswith(".json")}


def _read(template_id: str) -> dict[str, Any]:
    files = _files()
    if template_id not in files:
        msg = f"unknown template {template_id!r}; available: {', '.join(sorted(files))}"
        raise KeyError(msg)
    return json.loads(files[template_id].read_text(encoding="utf-8"))


def list_templates() -> list[TemplateInfo]:
    out: list[TemplateInfo] = []
    for tid in _files():
        raw = _read(tid)
        meta = raw.get("template", {})
        types = sorted({n["type"] for n in raw["project"]["nodes"].values()})
        out.append(TemplateInfo(
            id=tid, name=meta.get("name", tid), description=meta.get("description", ""),
            category=meta.get("category", "General"), tags=list(meta.get("tags", [])),
            widget_types=types,
        ))
    out.sort(key=lambda t: (t.id != "empty", t.category, t.name))
    return out


def _fresh_ids(proj: dict[str, Any]) -> dict[str, Any]:
    ids = {old: str(uuid4()) for old in proj["nodes"]}
    nodes = {}
    for old, node in proj["nodes"].items():
        node = dict(node)
        node["id"] = ids[old]
        if node.get("parentId") is not None:
            node["parentId"] = ids[node["parentId"]]
        nodes[ids[old]] = node
    proj = dict(proj)
    proj["nodes"] = nodes
    proj["rootId"] = ids[proj["rootId"]]
    proj["tabOrder"] = [ids[i] for i in proj.get("tabOrder", []) if i in ids]
    return proj


def load_template(id: str, framework: str | None = None) -> Project:
    """Instantiate a template. ``framework`` defaults to the template's (tkinter)."""
    proj = _fresh_ids(_read(id)["project"])
    if framework:
        proj["framework"] = framework
    return load_json(json.dumps(proj))
