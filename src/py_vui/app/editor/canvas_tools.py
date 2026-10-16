"""Mouse interaction tools for the design canvas (move, resize, window resize, rubber band…)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QPainter

from py_vui.app.editor import canvas_overlays as ov
from py_vui.app.editor.canvas_commands import MergeableBoxes, new_drag_key
from py_vui.app.editor.canvas_drop import DropPlan, container_mode, move_command, plan_in_container
from py_vui.app.editor.canvas_geometry import (
    content_size,
    grid_geometry,
    visible_children,
)
from py_vui.app.editor.canvas_resize import cursor_for, resize_rect
from py_vui.app.editor.snap import GuideLine, snap_move, snap_resize
from py_vui.commands import Batch, SetAttr, SetProjectAttr
from py_vui.core.model import Box, GridCell
from py_vui.core.registry import get_spec

if TYPE_CHECKING:
    from py_vui.app.editor.canvas import DesignCanvas

DRAG_THRESHOLD_PX = 3.0


def paint_item_tree(p: QPainter, item) -> None:
    """Paint ``item`` and its (visible) children at the painter's current origin."""
    from PySide6.QtWidgets import QStyleOptionGraphicsItem

    p.save()
    p.translate(item.pos())
    item.paint(p, QStyleOptionGraphicsItem(), None)
    w, h = item.size
    p.setClipRect(QRectF(0, 0, w, h))
    for child in sorted(item.childItems(), key=lambda c: c.zValue()):
        if child.isVisible():
            paint_item_tree(p, child)
    p.restore()


class Tool:
    cursor: Qt.CursorShape | None = None

    def __init__(self, canvas: DesignCanvas) -> None:
        self.c = canvas

    def press(self, pt: QPointF, ev) -> None:
        pass

    def move(self, pt: QPointF, ev) -> None:
        pass

    def release(self, pt: QPointF, ev) -> None:
        pass

    def cancel(self) -> None:
        pass

    def paint(self, p: QPainter, scale: float) -> None:
        pass


# --------------------------------------------------------------------------------------- move
class MoveTool(Tool):
    """Drag one or many widgets: free move, flex reorder, grid cell, or reparent."""

    def __init__(
        self, canvas: DesignCanvas, ids: list[str], press_pt: QPointF, press_view, clicked: str
    ) -> None:
        super().__init__(canvas)
        doc = canvas.doc
        assert doc is not None
        self.ids = ids
        self.clicked = clicked
        self.start = press_pt
        self.press_view = press_view
        self.moved = False
        self.plan: DropPlan | None = None
        self.lines: list[GuideLine] = []
        self.start_rects = {i: canvas.node_scene_rect(i) for i in ids}
        u = QRectF()
        for r in self.start_rects.values():
            u = u.united(r)
        self.union0 = u
        self.new_boxes: dict[str, Box] = {}
        self.ghost_delta = QPointF()
        self.exclude: set[str] = set()
        for i in ids:
            self.exclude.update(doc.subtree_ids(i))

    def move(self, pt: QPointF, ev) -> None:
        c = self.c
        doc = c.doc
        assert doc is not None
        if not self.moved:
            d = ev.position().toPoint() - self.press_view
            if abs(d.x()) + abs(d.y()) < DRAG_THRESHOLD_PX:
                return
            self.moved = True
            c.dim_items(self.ids, True)
            c.setCursor(Qt.CursorShape.ClosedHandCursor)
        container = c.container_at(pt, self.exclude)
        grab = (self.start.x() - self.union0.x(), self.start.y() - self.union0.y())
        plan = plan_in_container(
            doc, container, pt, (self.union0.width(), self.union0.height()), grab, set(self.ids)
        )
        self.lines = []
        delta = QPointF(pt - self.start)
        if plan.mode == "absolute" and plan.box is not None:
            others = [
                (k.box.x, k.box.y, k.box.w, k.box.h)
                for k in visible_children(doc, container)
                if k.id not in self.exclude
            ]
            cw, ch = content_size(doc, container)
            ox, oy = plan.target_rect.x(), plan.target_rect.y()  # type: ignore[union-attr]
            gx, gy = c.guides_for_origin(ox, oy)
            rect = (plan.box.x, plan.box.y, plan.box.w, plan.box.h)
            settings = c.snap_settings()
            if ev.modifiers() & Qt.KeyboardModifier.AltModifier:  # Alt = free move, no snapping
                settings.use_grid = settings.use_smart = settings.use_guides = False
            snap = snap_move(rect, others, (0, 0, cw, ch), settings, gx, gy)
            nx, ny = plan.box.x + snap.dx, plan.box.y + snap.dy
            plan.box = Box(x=nx, y=ny, w=plan.box.w, h=plan.box.h)
            # lines are in container coords: shift to scene coords
            self.lines = [
                GuideLine(
                    ln.orient,
                    ln.pos + (ox if ln.orient == "v" else oy),
                    ln.a + (oy if ln.orient == "v" else ox),
                    ln.b + (oy if ln.orient == "v" else ox),
                    ln.kind,
                )
                for ln in snap.lines
            ]
            self.new_boxes = {}
            for i in self.ids:
                off = self.start_rects[i].topLeft() - self.union0.topLeft()
                node = doc.get_node(i)
                self.new_boxes[i] = Box(
                    x=round(nx + off.x()), y=round(ny + off.y()), w=node.box.w, h=node.box.h
                )
            delta = QPointF(ox + nx - self.union0.x(), oy + ny - self.union0.y())
        self.plan = plan
        self.ghost_delta = delta
        c.viewport().update()

    def release(self, pt: QPointF, ev) -> None:
        c = self.c
        c.dim_items(self.ids, False)
        c.unsetCursor()
        if not self.moved:
            # plain click on an already-selected item narrows the selection to it
            if len(self.ids) > 1 or c.selection != [self.clicked]:
                c.set_selection([self.clicked])
            return
        plan = self.plan
        c.clear_overlays()
        if plan is None or c.doc is None:
            return
        cmd = move_command(c.doc, self.ids, plan, self.new_boxes)
        if cmd is not None:
            c.push(cmd)
        c.refresh()

    def cancel(self) -> None:
        self.c.dim_items(self.ids, False)
        self.c.unsetCursor()

    def paint(self, p: QPainter, scale: float) -> None:
        pal = self.c.palette_()
        plan = self.plan
        if not self.moved or plan is None:
            return
        if plan.target_rect is not None:
            ov.draw_drop_target(p, plan.target_rect, pal)
        if plan.cell_rect is not None:
            ov.draw_cell_highlight(p, plan.cell_rect, pal)
        if plan.insertion is not None:
            ov.draw_insertion(p, plan.insertion[0], plan.insertion[1], scale, pal)
        ov.draw_snap_lines(p, self.lines, pal)
        p.save()
        p.setOpacity(0.8)
        for i in self.ids:
            item = self.c.item_for(i)
            if item is None:
                continue
            r0 = self.start_rects[i]
            p.save()
            p.translate(r0.topLeft() + self.ghost_delta - item.pos())
            paint_item_tree(p, item)
            p.restore()
        p.restore()


# ------------------------------------------------------------------------------------ resize
class ResizeTool(Tool):
    """Resize one widget by a handle; honours absolute / flex / grid parents."""

    def __init__(self, canvas: DesignCanvas, node_id: str, handle: str, press_pt: QPointF) -> None:
        super().__init__(canvas)
        doc = canvas.doc
        assert doc is not None
        self.id = node_id
        self.handle = handle
        self.start = press_pt
        self.node = doc.get_node(node_id)
        self.start_rect = canvas.node_scene_rect(node_id)
        self.rect = QRectF(self.start_rect)
        self.parent = doc.get_node(self.node.parent_id) if self.node.parent_id else None
        self.mode = container_mode(self.parent) if self.parent else "absolute"
        self.spec = get_spec(self.node.type)
        self.lines: list[GuideLine] = []
        self.cell: GridCell | None = None
        self.cell_rect: QRectF | None = None
        self.moved = False
        self.cursor = cursor_for(handle)

    def move(self, pt: QPointF, ev) -> None:
        c = self.c
        doc = c.doc
        assert doc is not None and self.parent is not None
        self.moved = True
        dx, dy = pt.x() - self.start.x(), pt.y() - self.start.y()
        mw, mh = self.spec.min_size
        keep = bool(ev.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        rect = resize_rect(self.handle, self.start_rect, dx, dy, max(mw, 8), max(mh, 8), keep)
        self.lines = []
        if self.mode == "grid":
            self._grid_resize(pt)
            return
        if self.mode == "absolute":
            ox, oy = c.container_content_origin(self.parent)
            others = [
                (k.box.x, k.box.y, k.box.w, k.box.h)
                for k in visible_children(doc, self.parent)
                if k.id != self.id
            ]
            cw, ch = content_size(doc, self.parent)
            local = (rect.x() - ox, rect.y() - oy, rect.width(), rect.height())
            gx, gy = c.guides_for_origin(ox, oy)
            snapped, lines = snap_resize(
                local, self.handle, others, (0, 0, cw, ch), c.snap_settings(), gx, gy
            )
            w = max(snapped[2], max(mw, 8))
            h = max(snapped[3], max(mh, 8))
            x = snapped[0] if "w" not in self.handle else snapped[0] + snapped[2] - w
            y = snapped[1] if "n" not in self.handle else snapped[1] + snapped[3] - h
            rect = QRectF(ox + x, oy + y, w, h)
            self.lines = [
                GuideLine(
                    ln.orient,
                    ln.pos + (ox if ln.orient == "v" else oy),
                    ln.a + (oy if ln.orient == "v" else ox),
                    ln.b + (oy if ln.orient == "v" else ox),
                    ln.kind,
                )
                for ln in lines
            ]
        self.rect = rect
        c.viewport().update()

    def _grid_resize(self, pt: QPointF) -> None:
        c = self.c
        doc = c.doc
        assert doc is not None and self.parent is not None
        ox, oy = c.container_content_origin(self.parent)
        gg = grid_geometry(doc, self.parent)
        row, col = gg.cell_at(pt.x() - ox, pt.y() - oy)
        cell = self.node.cell
        r0, c0 = cell.row, cell.column
        r1, c1 = r0 + cell.row_span - 1, c0 + cell.column_span - 1
        if "e" in self.handle:
            c1 = max(c0, col)
        if "w" in self.handle:
            c0 = min(c1, col)
        if "s" in self.handle:
            r1 = max(r0, row)
        if "n" in self.handle:
            r0 = min(r1, row)
        self.cell = cell.model_copy(
            update={"row": r0, "column": c0, "row_span": r1 - r0 + 1, "column_span": c1 - c0 + 1}
        )
        cx, cy, cw, ch = gg.cell_rect(r0, c0, r1 - r0 + 1, c1 - c0 + 1)
        self.cell_rect = QRectF(ox + cx, oy + cy, cw, ch)
        self.c.viewport().update()

    def release(self, pt: QPointF, ev) -> None:
        c = self.c
        doc = c.doc
        assert doc is not None
        c.clear_overlays()
        if not self.moved:
            return
        if self.mode == "grid":
            if self.cell is not None and self.cell != self.node.cell:
                c.push(
                    Batch(
                        [SetAttr(self.id, "cell", self.cell, label="Resize cell span")],
                        label="Resize cell span",
                    )
                )
            c.refresh()
            return
        assert self.parent is not None
        if self.mode == "absolute":
            ox, oy = c.container_content_origin(self.parent)
            box = Box(
                x=round(self.rect.x() - ox),
                y=round(self.rect.y() - oy),
                w=round(self.rect.width()),
                h=round(self.rect.height()),
            )
        else:  # flex: only the basis size is stored; position is layout-driven
            box = Box(
                x=self.node.box.x,
                y=self.node.box.y,
                w=round(self.rect.width()),
                h=round(self.rect.height()),
            )
        if box != self.node.box:
            c.push(
                MergeableBoxes([(self.id, box)], label="Resize", merge_key=new_drag_key("resize"))
            )
        c.refresh()

    def paint(self, p: QPainter, scale: float) -> None:
        pal = self.c.palette_()
        if self.cell_rect is not None:
            ov.draw_cell_highlight(p, self.cell_rect, pal)
            return
        ov.draw_snap_lines(p, self.lines, pal)
        p.save()
        p.setOpacity(0.35)
        p.fillRect(self.rect, pal.color("selection"))
        p.restore()
        ov.draw_selection(p, [(self.rect, True, False)], pal)


class WindowResizeTool(Tool):
    """Resize the window itself by dragging its right/bottom edge or corner."""

    def __init__(self, canvas: DesignCanvas, handle: str, press_pt: QPointF) -> None:
        super().__init__(canvas)
        doc = canvas.doc
        assert doc is not None and canvas.window_id is not None
        node = doc.get_node(canvas.window_id)
        self.node = node
        self.handle = handle
        self.start = press_pt
        self.w0 = int(node.props.get("width", node.box.w))
        self.h0 = int(node.props.get("height", node.box.h))
        self.size = (self.w0, self.h0)
        self.key = new_drag_key("winsize")
        self.moved = False
        self.cursor = cursor_for(handle)

    def move(self, pt: QPointF, ev) -> None:
        c = self.c
        self.moved = True
        w, h = self.w0, self.h0
        grid = c.snap_settings().grid if c.snap_to_grid else 1
        if "e" in self.handle:
            w = max(100, round((self.w0 + pt.x() - self.start.x()) / grid) * grid)
        if "s" in self.handle:
            h = max(100, round((self.h0 + pt.y() - self.start.y()) / grid) * grid)
        if (w, h) != self.size:
            self.size = (int(w), int(h))
            c.apply_window_size(self.size, self.key, live=True)
        c.sizeChanged.emit(*self.size)

    def release(self, pt: QPointF, ev) -> None:
        if self.moved and self.size != (self.w0, self.h0):
            self.c.finish_window_resize()

    def cancel(self) -> None:
        if self.moved:
            self.c.undo_last()


# ------------------------------------------------------------------------------ rubber band
class RubberBandTool(Tool):
    def __init__(
        self, canvas: DesignCanvas, press_pt: QPointF, container_id: str, additive: bool, press_view
    ) -> None:
        super().__init__(canvas)
        self.start = press_pt
        self.container_id = container_id
        self.base = list(canvas.selection) if additive else []
        self.rect = QRectF(press_pt, press_pt)
        self.press_view = press_view
        self.moved = False

    def move(self, pt: QPointF, ev) -> None:
        if not self.moved:
            d = ev.position().toPoint() - self.press_view
            if abs(d.x()) + abs(d.y()) < DRAG_THRESHOLD_PX:
                return
            self.moved = True
        self.rect = QRectF(self.start, pt).normalized()
        doc = self.c.doc
        assert doc is not None
        hits = [
            k.id
            for k in visible_children(doc, doc.get_node(self.container_id))
            if self.c.node_scene_rect(k.id).intersects(self.rect)
        ]
        sel = [*self.base, *[h for h in hits if h not in self.base]]
        self.c.set_selection(sel)
        self.c.viewport().update()

    def release(self, pt: QPointF, ev) -> None:
        if not self.moved and not self.base:
            self.c.set_selection([self.container_id])
        self.c.clear_overlays()

    def paint(self, p: QPainter, scale: float) -> None:
        if self.moved:
            ov.draw_rubber_band(p, self.rect, self.c.palette_())


# --------------------------------------------------------------------------------- guides
class GuideTool(Tool):
    """Create (from a ruler) or move a user guide; dropping it outside the window deletes it."""

    def __init__(self, canvas: DesignCanvas, orient: str, index: int | None, pos: float) -> None:
        super().__init__(canvas)
        self.orient = orient
        self.index = index
        self.pos = pos
        self.cursor = Qt.CursorShape.SplitHCursor if orient == "v" else Qt.CursorShape.SplitVCursor
        self.original = pos

    def move(self, pt: QPointF, ev) -> None:
        self.pos = round(pt.x() if self.orient == "v" else pt.y())
        self.c.preview_guide(self.orient, self.index, self.pos)

    def release(self, pt: QPointF, ev) -> None:
        self.c.commit_guide(self.orient, self.index, self.pos)

    def cancel(self) -> None:
        self.c.preview_guide(None, None, 0)


class PanTool(Tool):
    cursor = Qt.CursorShape.ClosedHandCursor

    def __init__(self, canvas: DesignCanvas, view_pos) -> None:
        super().__init__(canvas)
        self.last = view_pos

    def move(self, pt: QPointF, ev) -> None:
        pos = ev.position().toPoint()
        d = pos - self.last
        self.last = pos
        hb, vb = self.c.horizontalScrollBar(), self.c.verticalScrollBar()
        hb.setValue(hb.value() - d.x())
        vb.setValue(vb.value() - d.y())


def guides_command(doc, window_id: str, vguides: list[float], hguides: list[float]):
    editor = dict(doc.project.editor)
    all_guides = {k: dict(v) for k, v in dict(editor.get("guides", {})).items()}
    if vguides or hguides:
        all_guides[window_id] = {"v": list(vguides), "h": list(hguides)}
    else:
        all_guides.pop(window_id, None)
    editor["guides"] = all_guides
    return SetProjectAttr("editor", editor, label="Move guide")
