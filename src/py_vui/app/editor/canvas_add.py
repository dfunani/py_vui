"""Adding widgets to the canvas: the single code path for drops, double-click and file drops."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF

from py_vui.app.editor.canvas_drop import (
    DropPlan,
    add_command,
    container_mode,
    plan_in_container,
)
from py_vui.app.editor.canvas_geometry import (
    current_page,
    grid_geometry,
    is_paged,
    visible_children,
)
from py_vui.app.editor.snap import snap_value
from py_vui.commands import AddNodes, Batch
from py_vui.core.document import make_node
from py_vui.core.model import Box, GridCell, Node
from py_vui.core.registry import get_spec, has_spec

if TYPE_CHECKING:
    from py_vui.app.editor.canvas import DesignCanvas


class AddWidgetsMixin:
    def add_widget(
        self: DesignCanvas,
        type_id: str,
        scene_pt: QPointF | None = None,
        *,
        container_id: str | None = None,
        props: dict | None = None,
        select: bool = True,
        size: tuple[int, int] | None = None,
        index: int | None = None,
    ) -> str | None:
        """Create a widget — the single code path for palette drops, double-click and file drops."""
        if self.doc is None or self.window_id is None or not has_spec(type_id):
            return None
        doc = self.doc
        spec = get_spec(type_id)
        if type_id == "window":
            self.message.emit("A project has exactly one main window; add a Dialog Window instead.")
            return None
        if type_id == "toplevel":
            return self.add_dialog()
        dsize = (int(size[0]), int(size[1])) if size else spec.default_size
        if scene_pt is not None:
            container = doc.get_node(container_id) if container_id else self.container_at(scene_pt)
            plan = plan_in_container(doc, container, scene_pt, dsize)
        else:
            container = doc.get_node(container_id) if container_id else self._default_container()
            plan = self._auto_plan(container, dsize)
        if index is not None:
            plan.index = index
        if plan.mode == "absolute" and plan.box is not None:
            x, y = max(0.0, plan.box.x), max(0.0, plan.box.y)
            if self.snap_to_grid and scene_pt is not None:
                x, y = snap_value(x, self.grid_size), snap_value(y, self.grid_size)
            plan.box = Box(x=x, y=y, w=plan.box.w, h=plan.box.h)
        node = make_node(
            type_id,
            parent_id=container.id,
            name=doc.unique_name(spec.label),
            w=size[0] if size else None,
            h=size[1] if size else None,
            **(props or {}),
        )
        if not self.push(add_command(doc, node, plan, label=f"Add {spec.label}")):
            return None
        if select:
            self.set_selection([node.id])
        return node.id

    def add_dialog(self: DesignCanvas) -> str | None:
        assert self.doc is not None
        doc = self.doc
        spec = get_spec("toplevel")
        node = make_node(
            "toplevel",
            parent_id=doc.project.root_id,
            name=doc.unique_name("Dialog"),
            title="Dialog",
        )
        node.box = Box(x=0, y=0, w=float(node.props["width"]), h=float(node.props["height"]))
        node.z_index = len(doc.windows())
        if self.push(Batch([AddNodes([node], label="Add dialog")], label=f"Add {spec.label}")):
            self.windowRequested.emit(node.id)
            return node.id
        return None

    def _default_container(self: DesignCanvas) -> Node:
        assert self.doc is not None and self.window_id is not None
        for i in reversed(self.selection):
            n = self.doc.get_node(i)
            if get_spec(n.type).container and n.type != "toplevel" or n.id == self.window_id:
                return n
            if n.parent_id:
                return self.doc.get_node(n.parent_id)
        return self.doc.get_node(self.window_id)

    def _auto_plan(self: DesignCanvas, container: Node, size: tuple[int, int]) -> DropPlan:
        """Free spot for a widget added without a drop position (double-click insert)."""
        assert self.doc is not None
        doc = self.doc
        mode = container_mode(container)
        kids = visible_children(doc, container)
        plan = DropPlan(container.id, mode)
        if is_paged(container):
            plan.page = current_page(container)
        if mode == "flex":
            plan.index = len(doc.children(container.id))
        elif mode == "grid":
            used = {(k.cell.row, k.cell.column) for k in kids}
            gg = grid_geometry(doc, container)
            cols = max(1, gg.cols)
            row = col = 0
            while (row, col) in used:
                col += 1
                if col >= cols:
                    col, row = 0, row + 1
            plan.cell = GridCell(row=row, column=col)
        else:
            rects = [(k.box.x, k.box.y, k.box.w, k.box.h) for k in kids]
            cw, ch = (
                (container.box.w, container.box.h)
                if container.type not in ("window", "toplevel")
                else (
                    float(container.props.get("width", 640)),
                    float(container.props.get("height", 480)),
                )
            )
            x = y = 16.0
            step = max(8, self.grid_size)
            found = False
            while y + size[1] <= ch and not found:
                x = 16.0
                while x + size[0] <= cw:
                    if not any(
                        x < rx + rw and x + size[0] > rx and y < ry + rh and y + size[1] > ry
                        for rx, ry, rw, rh in rects
                    ):
                        found = True
                        break
                    x += step * 2
                if not found:
                    y += step * 2
            if not found:
                x = y = 16.0 + 16 * (len(kids) % 10)
            plan.box = Box(x=x, y=y, w=size[0], h=size[1])
        return plan
