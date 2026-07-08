from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from py_vui.commands.base import Command
from py_vui.model.document import ProjectDocument
from py_vui.model.nodes import Node


def _new_id() -> str:
    return str(uuid4())


def subtree_root_id(nodes: dict[str, Node]) -> str:
    ids = set(nodes)
    for nid, node in nodes.items():
        if node.parent_id not in ids:
            return nid
    msg = "could not find subtree root"
    raise ValueError(msg)


def remap_subtree(
    nodes: dict[str, Node], *, offset_x: float = 16, offset_y: float = 16
) -> tuple[str, list[Node]]:
    """Clone a subtree dict (id-keyed) with fresh ids and nudged positions."""
    id_map = {old_id: _new_id() for old_id in nodes}
    clones: list[Node] = []
    for old_id, node in nodes.items():
        data = node.model_dump()
        data["id"] = id_map[old_id]
        if data.get("parentId") is not None:
            data["parentId"] = id_map.get(data["parentId"], data["parentId"])
        box = data["layout"]["box"]
        box["x"] = float(box["x"]) + offset_x
        box["y"] = float(box["y"]) + offset_y
        clones.append(node.__class__.model_validate(data))
    return id_map[subtree_root_id(nodes)], clones


@dataclass
class AddNodes(Command):
    nodes: list[Node]

    def apply(self, doc: ProjectDocument) -> None:
        for node in self.nodes:
            if node.id in doc.project.nodes:
                msg = f"duplicate node id {node.id!r}"
                raise ValueError(msg)
            doc.project.nodes[node.id] = node

    def revert(self, doc: ProjectDocument) -> None:
        for node in self.nodes:
            del doc.project.nodes[node.id]
