"""Alignment, distribution, z-order and grid helpers (all return plain Commands)."""

from __future__ import annotations

from typing import Literal

from py_vui.commands.base import Command
from py_vui.commands.builtins import Batch, ReorderChildren, SetAttr, SetBoxes
from py_vui.core.document import ProjectDocument
from py_vui.core.model import Box, GridCell

AlignMode = Literal["left", "center", "right", "top", "middle", "bottom"]
ZMode = Literal["front", "back", "forward", "backward"]


def _parent_size(doc: ProjectDocument, node_id: str) -> tuple[float, float]:
    parent = doc.project.nodes[doc.project.nodes[node_id].parent_id or doc.project.root_id]
    if parent.type in ("window", "toplevel"):
        return float(parent.props.get("width", parent.box.w)), float(parent.props.get("height", parent.box.h))
    return parent.box.w, parent.box.h


def align_nodes(
    doc: ProjectDocument, ids: list[str], mode: AlignMode, *, to_parent: bool | None = None
) -> Command:
    """Align several nodes to each other (or a single node to its parent)."""
    nodes = [doc.project.nodes[i] for i in ids]
    to_parent = len(nodes) == 1 if to_parent is None else to_parent
    updates: list[tuple[str, Box]] = []
    if to_parent:
        for n in nodes:
            pw, ph = _parent_size(doc, n.id)
            b = n.box
            x, y = b.x, b.y
            if mode == "left":
                x = 0
            elif mode == "center":
                x = (pw - b.w) / 2
            elif mode == "right":
                x = pw - b.w
            elif mode == "top":
                y = 0
            elif mode == "middle":
                y = (ph - b.h) / 2
            else:
                y = ph - b.h
            updates.append((n.id, Box(x=x, y=y, w=b.w, h=b.h)))
    else:
        left = min(n.box.x for n in nodes)
        right = max(n.box.x + n.box.w for n in nodes)
        top = min(n.box.y for n in nodes)
        bottom = max(n.box.y + n.box.h for n in nodes)
        for n in nodes:
            b = n.box
            x, y = b.x, b.y
            if mode == "left":
                x = left
            elif mode == "center":
                x = (left + right - b.w) / 2
            elif mode == "right":
                x = right - b.w
            elif mode == "top":
                y = top
            elif mode == "middle":
                y = (top + bottom - b.h) / 2
            else:
                y = bottom - b.h
            updates.append((n.id, Box(x=x, y=y, w=b.w, h=b.h)))
    cmd = SetBoxes(updates, label=f"Align {mode}")
    return cmd


def distribute_nodes(
    doc: ProjectDocument, ids: list[str], axis: Literal["horizontal", "vertical"]
) -> Command:
    nodes = sorted(
        (doc.project.nodes[i] for i in ids),
        key=lambda n: n.box.x if axis == "horizontal" else n.box.y,
    )
    updates: list[tuple[str, Box]] = []
    if len(nodes) >= 3:
        if axis == "horizontal":
            start, end = nodes[0].box.x, nodes[-1].box.x + nodes[-1].box.w
            gap = (end - start - sum(n.box.w for n in nodes)) / (len(nodes) - 1)
            pos = start
            for n in nodes:
                updates.append((n.id, Box(x=pos, y=n.box.y, w=n.box.w, h=n.box.h)))
                pos += n.box.w + gap
        else:
            start, end = nodes[0].box.y, nodes[-1].box.y + nodes[-1].box.h
            gap = (end - start - sum(n.box.h for n in nodes)) / (len(nodes) - 1)
            pos = start
            for n in nodes:
                updates.append((n.id, Box(x=n.box.x, y=pos, w=n.box.w, h=n.box.h)))
                pos += n.box.h + gap
    return SetBoxes(updates, label=f"Distribute {axis}ly")


def match_size(doc: ProjectDocument, ids: list[str], *, width: bool, height: bool) -> Command:
    ref = doc.project.nodes[ids[0]].box
    updates = []
    for i in ids[1:]:
        b = doc.project.nodes[i].box
        updates.append((i, Box(x=b.x, y=b.y, w=ref.w if width else b.w, h=ref.h if height else b.h)))
    return SetBoxes(updates, label="Match size")


def change_z(doc: ProjectDocument, node_id: str, mode: ZMode) -> Command:
    node = doc.project.nodes[node_id]
    sibs = [c.id for c in doc.children(node.parent_id or doc.project.root_id)]
    idx = sibs.index(node_id)
    sibs.pop(idx)
    if mode == "front":
        sibs.append(node_id)
    elif mode == "back":
        sibs.insert(0, node_id)
    elif mode == "forward":
        sibs.insert(min(idx + 1, len(sibs)), node_id)
    else:
        sibs.insert(max(idx - 1, 0), node_id)
    return ReorderChildren(sibs, label=f"Bring {mode}")


def auto_grid(doc: ProjectDocument, container_id: str) -> Command:
    """Assign grid cells from the current absolute positions (row/column clustering)."""
    kids = doc.children(container_id)
    rows = sorted({round(k.box.y / 24) for k in kids})
    cols = sorted({round(k.box.x / 48) for k in kids})
    cmds: list[Command] = []
    for k in kids:
        cell = GridCell(row=rows.index(round(k.box.y / 24)), column=cols.index(round(k.box.x / 48)))
        cmds.append(SetAttr(k.id, "cell", cell, label="Auto grid"))
    return Batch(cmds, label="Auto grid")
