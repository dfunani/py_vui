from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from py_vui.commands.base import Command
from py_vui.model.document import ProjectDocument
from py_vui.model.geometry import Rect
from py_vui.model.nodes import WindowNode

AlignMode = Literal["left", "center", "right", "top", "middle", "bottom"]


@dataclass
class AlignInParent(Command):
    node_id: str
    mode: AlignMode
    _old_box: Rect | None = None

    def apply(self, doc: ProjectDocument) -> None:
        node = doc.project.nodes[self.node_id]
        parent_id = node.parent_id
        if parent_id is None:
            return
        parent = doc.project.nodes[parent_id]
        if isinstance(parent, WindowNode):
            pw, ph = parent.props.width, parent.props.height
        else:
            pw, ph = parent.layout.box.w, parent.layout.box.h
        box = node.layout.box
        self._old_box = box.model_copy(deep=True)
        x, y, w, h = box.x, box.y, box.w, box.h
        margin = 8.0
        if self.mode == "left":
            x = margin
        elif self.mode == "center":
            x = max(margin, (pw - w) / 2)
        elif self.mode == "right":
            x = max(margin, pw - w - margin)
        elif self.mode == "top":
            y = margin
        elif self.mode == "middle":
            y = max(margin, (ph - h) / 2)
        elif self.mode == "bottom":
            y = max(margin, ph - h - margin)
        node.layout.box = Rect(x=x, y=y, w=w, h=h)

    def revert(self, doc: ProjectDocument) -> None:
        if self._old_box is None:
            return
        doc.project.nodes[self.node_id].layout.box = self._old_box


@dataclass
class DistributeNodes(Command):
    node_ids: list[str]
    axis: Literal["horizontal", "vertical"]
    _old_boxes: dict[str, Rect] | None = None

    def apply(self, doc: ProjectDocument) -> None:
        if len(self.node_ids) < 2:
            return
        self._old_boxes = {}
        nodes = [doc.project.nodes[nid] for nid in self.node_ids]
        for node in nodes:
            self._old_boxes[node.id] = node.layout.box.model_copy(deep=True)
        if self.axis == "horizontal":
            nodes.sort(key=lambda n: n.layout.box.x)
            left = nodes[0].layout.box.x
            right = nodes[-1].layout.box.x + nodes[-1].layout.box.w
            total_w = sum(n.layout.box.w for n in nodes)
            gap = (right - left - total_w) / max(1, len(nodes) - 1)
            x = left
            for node in nodes:
                box = node.layout.box
                node.layout.box = Rect(x=x, y=box.y, w=box.w, h=box.h)
                x += box.w + gap
        else:
            nodes.sort(key=lambda n: n.layout.box.y)
            top = nodes[0].layout.box.y
            bottom = nodes[-1].layout.box.y + nodes[-1].layout.box.h
            total_h = sum(n.layout.box.h for n in nodes)
            gap = (bottom - top - total_h) / max(1, len(nodes) - 1)
            y = top
            for node in nodes:
                box = node.layout.box
                node.layout.box = Rect(x=box.x, y=y, w=box.w, h=box.h)
                y += box.h + gap

    def revert(self, doc: ProjectDocument) -> None:
        if not self._old_boxes:
            return
        for nid, box in self._old_boxes.items():
            doc.project.nodes[nid].layout.box = box


@dataclass
class SetLayoutBoxes(Command):
    updates: list[tuple[str, Rect]]
    _old: list[tuple[str, Rect]] | None = None

    def apply(self, doc: ProjectDocument) -> None:
        self._old = []
        for node_id, new_box in self.updates:
            node = doc.project.nodes[node_id]
            self._old.append((node_id, node.layout.box.model_copy(deep=True)))
            node.layout.box = new_box.model_copy(deep=True)

    def revert(self, doc: ProjectDocument) -> None:
        if not self._old:
            return
        for node_id, box in self._old:
            doc.project.nodes[node_id].layout.box = box


@dataclass
class BumpZIndex(Command):
    node_id: str
    delta: int
    _old_z: int = 0

    def apply(self, doc: ProjectDocument) -> None:
        node = doc.project.nodes[self.node_id]
        self._old_z = node.z_index
        node.z_index = max(0, node.z_index + self.delta)

    def revert(self, doc: ProjectDocument) -> None:
        doc.project.nodes[self.node_id].z_index = self._old_z
