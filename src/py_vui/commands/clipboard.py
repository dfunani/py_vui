"""Copy / paste / duplicate of node subtrees (JSON clipboard payload)."""

from __future__ import annotations

import json
from typing import Any

from py_vui.commands.base import Command
from py_vui.commands.builtins import AddNodes, Batch, SetHandler
from py_vui.core.document import ProjectDocument, new_id
from py_vui.core.model import HandlerDef, Node

CLIPBOARD_MIME = "application/x-py-vui-nodes"


def copy_nodes(doc: ProjectDocument, ids: list[str]) -> str:
    """Serialise the given nodes (plus descendants) to a JSON string."""
    wanted: list[str] = []
    for i in ids:
        for sid in doc.subtree_ids(i):
            if sid not in wanted:
                wanted.append(sid)
    nodes = [doc.project.nodes[i].model_dump(mode="json", by_alias=True) for i in wanted]
    handlers = {}
    for i in wanted:
        for h in doc.project.nodes[i].events.values():
            if h in doc.project.handlers:
                handlers[h] = doc.project.handlers[h].model_dump()
    return json.dumps({"py_vui": 2, "roots": ids, "nodes": nodes, "handlers": handlers})


def build_paste(
    doc: ProjectDocument,
    payload: str,
    target_parent_id: str,
    *,
    offset: float = 16.0,
) -> tuple[Command, list[str]]:
    """Return (command, new_root_ids) pasting ``payload`` under ``target_parent_id``."""
    data: dict[str, Any] = json.loads(payload)
    if data.get("py_vui") != 2:
        msg = "clipboard does not contain py_vui nodes"
        raise ValueError(msg)
    raw_nodes = {n["id"]: n for n in data["nodes"]}
    id_map = {old: new_id() for old in raw_nodes}
    roots = [r for r in data["roots"] if r in raw_nodes]
    clones: list[Node] = []
    for old, raw in raw_nodes.items():
        raw = json.loads(json.dumps(raw))  # deep copy
        raw["id"] = id_map[old]
        if old in roots:
            raw["parentId"] = target_parent_id
            raw["box"]["x"] += offset
            raw["box"]["y"] += offset
            raw["name"] = doc.unique_name(raw["name"])
        else:
            raw["parentId"] = id_map.get(raw["parentId"], target_parent_id)
        clones.append(Node.model_validate(raw))
    cmds: list[Command] = [AddNodes(clones, label="Paste")]
    for name, h in data.get("handlers", {}).items():
        if name not in doc.project.handlers:
            cmds.append(SetHandler(name, HandlerDef.model_validate(h)))
    return Batch(cmds, label="Paste"), [id_map[r] for r in roots]
