from __future__ import annotations

from dataclasses import dataclass

from py_vui.commands.base import Command
from py_vui.model.document import ProjectDocument
from py_vui.model.geometry import Rect
from py_vui.model.nodes import Node
from py_vui.model.project import py_vuiProject


def collect_subtree_ids(doc: ProjectDocument, root_id: str) -> list[str]:
    out: list[str] = []
    stack = [root_id]
    while stack:
        cur = stack.pop()
        out.append(cur)
        for child in doc.children(cur):
            stack.append(child.id)
    return out


def _remove_ids(project: py_vuiProject, ids: set[str]) -> None:
    for i in ids:
        del project.nodes[i]


@dataclass
class AddNode(Command):
    node: Node

    def apply(self, doc: ProjectDocument) -> None:
        if self.node.id in doc.project.nodes:
            msg = f"duplicate node id {self.node.id!r}"
            raise ValueError(msg)
        if self.node.parent_id is not None and self.node.parent_id not in doc.project.nodes:
            msg = f"missing parent {self.node.parent_id!r}"
            raise ValueError(msg)
        doc.project.nodes[self.node.id] = self.node

    def revert(self, doc: ProjectDocument) -> None:
        del doc.project.nodes[self.node.id]


@dataclass
class RemoveSubtree(Command):
    root_id: str
    _removed: dict[str, Node] | None = None

    def apply(self, doc: ProjectDocument) -> None:
        if self.root_id == doc.project.root_id:
            msg = "cannot remove project root subtree"
            raise ValueError(msg)
        if self.root_id not in doc.project.nodes:
            msg = f"missing node {self.root_id!r}"
            raise ValueError(msg)
        ids = collect_subtree_ids(doc, self.root_id)
        self._removed = {i: doc.project.nodes[i] for i in ids}
        _remove_ids(doc.project, set(ids))

    def revert(self, doc: ProjectDocument) -> None:
        if not self._removed:
            msg = "RemoveSubtree not applied"
            raise RuntimeError(msg)
        doc.project.nodes.update(self._removed)
        self._removed = None


@dataclass
class ReparentNode(Command):
    node_id: str
    new_parent_id: str
    new_z_index: int | None = None
    _old_parent_id: str | None = None
    _old_z_index: int = 0
    _applied: bool = False

    def apply(self, doc: ProjectDocument) -> None:
        node = doc.project.nodes[self.node_id]
        if self.node_id == doc.project.root_id:
            msg = "cannot reparent root"
            raise ValueError(msg)
        if self.new_parent_id not in doc.project.nodes:
            msg = f"missing parent {self.new_parent_id!r}"
            raise ValueError(msg)
        if _is_descendant(doc, self.node_id, self.new_parent_id):
            msg = "cannot reparent a node into its own subtree"
            raise ValueError(msg)

        self._old_parent_id = node.parent_id
        self._old_z_index = node.z_index
        node.parent_id = self.new_parent_id
        if self.new_z_index is not None:
            node.z_index = self.new_z_index
        self._applied = True

    def revert(self, doc: ProjectDocument) -> None:
        if not self._applied:
            msg = "ReparentNode not applied"
            raise RuntimeError(msg)
        node = doc.project.nodes[self.node_id]
        if self._old_parent_id is None:
            msg = "invalid ReparentNode state (missing old parent)"
            raise RuntimeError(msg)
        node.parent_id = self._old_parent_id
        node.z_index = self._old_z_index
        self._applied = False


def _is_descendant(doc: ProjectDocument, ancestor_id: str, target_id: str) -> bool:
    if ancestor_id == target_id:
        return True
    for child in doc.children(ancestor_id):
        if _is_descendant(doc, child.id, target_id):
            return True
    return False


@dataclass
class SetLayoutBox(Command):
    node_id: str
    new_box: Rect
    _old_box: Rect | None = None

    def apply(self, doc: ProjectDocument) -> None:
        node = doc.project.nodes[self.node_id]
        self._old_box = node.layout.box.model_copy(deep=True)
        node.layout.box = self.new_box.model_copy(deep=True)

    def revert(self, doc: ProjectDocument) -> None:
        node = doc.project.nodes[self.node_id]
        if self._old_box is None:
            msg = "SetLayoutBox not applied"
            raise RuntimeError(msg)
        node.layout.box = self._old_box


@dataclass
class ReplaceNode(Command):
    before: Node
    after: Node

    def apply(self, doc: ProjectDocument) -> None:
        if self.before.id != self.after.id:
            msg = "ReplaceNode requires matching ids"
            raise ValueError(msg)
        if self.after.id not in doc.project.nodes:
            msg = f"missing node {self.after.id!r}"
            raise ValueError(msg)
        doc.project.nodes[self.after.id] = self.after

    def revert(self, doc: ProjectDocument) -> None:
        doc.project.nodes[self.before.id] = self.before
