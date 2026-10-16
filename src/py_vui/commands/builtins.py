"""Reversible edit commands. Every mutation of a Project goes through one of these."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Literal

from py_vui.commands.base import Command
from py_vui.core.document import ProjectDocument
from py_vui.core.model import Box, HandlerDef, Node

Section = Literal["props", "style", "events"]
_MISSING = object()


def _get(doc: ProjectDocument, node_id: str) -> Node:
    try:
        return doc.project.nodes[node_id]
    except KeyError as exc:
        msg = f"missing node {node_id!r}"
        raise ValueError(msg) from exc


@dataclass
class AddNodes(Command):
    nodes: list[Node]
    label: str = "Add widget"

    def apply(self, doc: ProjectDocument) -> None:
        for n in self.nodes:
            if n.id in doc.project.nodes:
                msg = f"duplicate node id {n.id!r}"
                raise ValueError(msg)
        for n in self.nodes:
            doc.project.nodes[n.id] = n

    def revert(self, doc: ProjectDocument) -> None:
        for n in self.nodes:
            doc.project.nodes.pop(n.id, None)


def AddNode(node: Node) -> AddNodes:
    return AddNodes([node])


@dataclass
class RemoveSubtree(Command):
    root_id: str
    label: str = "Delete"
    _removed: dict[str, Node] = field(default_factory=dict, repr=False)
    _old_tab_order: list[str] = field(default_factory=list, repr=False)

    def apply(self, doc: ProjectDocument) -> None:
        if self.root_id == doc.project.root_id:
            msg = "cannot remove the main window"
            raise ValueError(msg)
        ids = doc.subtree_ids(self.root_id)
        self._removed = {i: doc.project.nodes[i] for i in ids}
        for i in ids:
            del doc.project.nodes[i]
        order = doc.project.tab_order
        self._old_tab_order = list(order)
        doc.project.tab_order = [i for i in order if i not in self._removed]

    def revert(self, doc: ProjectDocument) -> None:
        doc.project.nodes.update(self._removed)
        doc.project.tab_order = list(self._old_tab_order)
        self._removed = {}


@dataclass
class ReparentNode(Command):
    node_id: str
    new_parent_id: str
    new_z_index: int | None = None
    new_box: Box | None = None
    label: str = "Move into container"
    _old: tuple[str | None, int, Box, int] | None = field(default=None, repr=False)

    def apply(self, doc: ProjectDocument) -> None:
        node = _get(doc, self.node_id)
        if self.node_id == doc.project.root_id:
            msg = "cannot reparent the main window"
            raise ValueError(msg)
        if self.new_parent_id not in doc.project.nodes:
            msg = f"missing parent {self.new_parent_id!r}"
            raise ValueError(msg)
        if self.new_parent_id in doc.subtree_ids(self.node_id):
            msg = "cannot move a node into its own subtree"
            raise ValueError(msg)
        self._old = (node.parent_id, node.z_index, node.box.model_copy(), node.page)
        node.parent_id = self.new_parent_id
        if self.new_z_index is not None:
            node.z_index = self.new_z_index
        if self.new_box is not None:
            node.box = self.new_box.model_copy()

    def revert(self, doc: ProjectDocument) -> None:
        assert self._old is not None
        node = _get(doc, self.node_id)
        node.parent_id, node.z_index, node.box, node.page = self._old


@dataclass
class SetBoxes(Command):
    updates: list[tuple[str, Box]]
    label: str = "Move / resize"
    merge_key: str | None = None
    _old: list[tuple[str, Box]] = field(default_factory=list, repr=False)

    def apply(self, doc: ProjectDocument) -> None:
        self._old = []
        for nid, box in self.updates:
            node = _get(doc, nid)
            self._old.append((nid, node.box.model_copy()))
            node.box = box.model_copy()

    def revert(self, doc: ProjectDocument) -> None:
        for nid, box in self._old:
            _get(doc, nid).box = box


def SetBox(node_id: str, box: Box) -> SetBoxes:
    return SetBoxes([(node_id, box)])


@dataclass
class SetField(Command):
    """Set one key in ``props`` / ``style`` / ``events`` (value ``None`` deletes the key)."""

    node_id: str
    section: Section
    key: str
    value: Any
    label: str = "Change property"
    merge_key: str | None = None
    _old: Any = field(default=_MISSING, repr=False)

    def __post_init__(self) -> None:
        if self.merge_key is None:
            self.merge_key = f"set:{self.node_id}:{self.section}:{self.key}"

    def _store(self, doc: ProjectDocument) -> dict[str, Any]:
        return getattr(_get(doc, self.node_id), self.section)

    def apply(self, doc: ProjectDocument) -> None:
        store = self._store(doc)
        self._old = copy.deepcopy(store.get(self.key, _MISSING))
        if self.value is None:
            store.pop(self.key, None)
        else:
            store[self.key] = copy.deepcopy(self.value)

    def revert(self, doc: ProjectDocument) -> None:
        store = self._store(doc)
        if self._old is _MISSING:
            store.pop(self.key, None)
        else:
            store[self.key] = copy.deepcopy(self._old)

    def merge(self, newer: Command) -> bool:
        if isinstance(newer, SetField) and (newer.node_id, newer.section, newer.key) == (
            self.node_id, self.section, self.key,
        ):
            self.value = newer.value
            return True
        return False


@dataclass
class SetAttr(Command):
    """Set a top-level Node attribute (name, enabled, visible, layout, cell, flex, anchors, …)."""

    node_id: str
    attr: str
    value: Any
    label: str = "Change"
    _old: Any = field(default=None, repr=False)

    def __post_init__(self) -> None:
        self.merge_key = f"attr:{self.node_id}:{self.attr}"

    def apply(self, doc: ProjectDocument) -> None:
        node = _get(doc, self.node_id)
        self._old = copy.deepcopy(getattr(node, self.attr))
        setattr(node, self.attr, copy.deepcopy(self.value))

    def revert(self, doc: ProjectDocument) -> None:
        setattr(_get(doc, self.node_id), self.attr, copy.deepcopy(self._old))

    def merge(self, newer: Command) -> bool:
        if isinstance(newer, SetAttr) and (newer.node_id, newer.attr) == (self.node_id, self.attr):
            self.value = newer.value
            return True
        return False


@dataclass
class ReplaceNode(Command):
    before: Node
    after: Node
    label: str = "Edit widget"

    def apply(self, doc: ProjectDocument) -> None:
        if self.before.id != self.after.id:
            msg = "ReplaceNode requires matching ids"
            raise ValueError(msg)
        doc.project.nodes[self.after.id] = self.after.model_copy(deep=True)

    def revert(self, doc: ProjectDocument) -> None:
        doc.project.nodes[self.before.id] = self.before.model_copy(deep=True)


@dataclass
class SetHandler(Command):
    """Create/update (or with ``handler=None`` delete) a callback definition."""

    name: str
    handler: HandlerDef | None
    label: str = "Edit handler"
    _old: HandlerDef | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        self.merge_key = f"handler:{self.name}"

    def apply(self, doc: ProjectDocument) -> None:
        self._old = doc.project.handlers.get(self.name)
        if self.handler is None:
            doc.project.handlers.pop(self.name, None)
        else:
            doc.project.handlers[self.name] = self.handler.model_copy()

    def revert(self, doc: ProjectDocument) -> None:
        if self._old is None:
            doc.project.handlers.pop(self.name, None)
        else:
            doc.project.handlers[self.name] = self._old

    def merge(self, newer: Command) -> bool:
        if isinstance(newer, SetHandler) and newer.name == self.name:
            self.handler = newer.handler
            return True
        return False


@dataclass
class SetProjectAttr(Command):
    """framework, theme, meta, custom_code, extra_requirements, tab_order, assets, editor."""

    attr: str
    value: Any
    label: str = "Change project"
    _old: Any = field(default=None, repr=False)

    def __post_init__(self) -> None:
        self.merge_key = f"project:{self.attr}"

    def apply(self, doc: ProjectDocument) -> None:
        self._old = copy.deepcopy(getattr(doc.project, self.attr))
        setattr(doc.project, self.attr, copy.deepcopy(self.value))

    def revert(self, doc: ProjectDocument) -> None:
        setattr(doc.project, self.attr, copy.deepcopy(self._old))

    def merge(self, newer: Command) -> bool:
        if isinstance(newer, SetProjectAttr) and newer.attr == self.attr:
            self.value = newer.value
            return True
        return False


@dataclass
class ReorderChildren(Command):
    """Set sibling z-order: ``ordered_ids[0]`` is bottom-most."""

    ordered_ids: list[str]
    label: str = "Reorder"
    _old: dict[str, int] = field(default_factory=dict, repr=False)

    def apply(self, doc: ProjectDocument) -> None:
        self._old = {i: _get(doc, i).z_index for i in self.ordered_ids}
        for z, i in enumerate(self.ordered_ids):
            _get(doc, i).z_index = z

    def revert(self, doc: ProjectDocument) -> None:
        for i, z in self._old.items():
            _get(doc, i).z_index = z


@dataclass
class Batch(Command):
    commands: list[Command]
    label: str = "Edit"
    _done: list[Command] = field(default_factory=list, repr=False)

    def apply(self, doc: ProjectDocument) -> None:
        self._done = []
        try:
            for c in self.commands:
                c.apply(doc)
                self._done.append(c)
        except Exception:
            for c in reversed(self._done):
                c.revert(doc)
            self._done = []
            raise

    def revert(self, doc: ProjectDocument) -> None:
        for c in reversed(self._done):
            c.revert(doc)
        self._done = []
