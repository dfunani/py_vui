"""The design canvas: a zoomable, pannable QGraphicsView that edits the document."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QPainter
from PySide6.QtWidgets import QGraphicsView, QLineEdit

from py_vui.app.editor import canvas_overlays as ov
from py_vui.app.editor.canvas_add import AddWidgetsMixin
from py_vui.app.editor.canvas_commands import MergeableBoxes, SetWindowSize, new_drag_key
from py_vui.app.editor.canvas_drop import (
    DropPlan,
    container_mode,
    content_origin_abs,
    plan_in_container,
)
from py_vui.app.editor.canvas_edit import InlineEditMixin
from py_vui.app.editor.canvas_geometry import (
    current_page,
    grid_geometry,
    tab_at,
    visible_children,
)
from py_vui.app.editor.canvas_items import DesignScene, NodeItem
from py_vui.app.editor.canvas_resize import cursor_for, hit_handle
from py_vui.app.editor.canvas_tools import (
    GuideTool,
    MoveTool,
    PanTool,
    ResizeTool,
    RubberBandTool,
    Tool,
    WindowResizeTool,
    guides_command,
)
from py_vui.app.editor.editor_theme import EditorPalette, current_palette
from py_vui.app.editor.mime import MIME_WIDGET
from py_vui.app.editor.snap import SnapSettings
from py_vui.commands import (
    Batch,
    Command,
    History,
    ReorderChildren,
    SetAttr,
    SetField,
)
from py_vui.core.document import ProjectDocument
from py_vui.core.model import Box, Node
from py_vui.core.registry import get_spec, has_spec

ZOOM_MIN, ZOOM_MAX = 0.1, 4.0
_TEXT_KEYS = {
    "label": "text",
    "button": "text",
    "tool_button": "text",
    "checkbox": "text",
    "radio": "text",
    "switch": "text",
    "entry": "text",
    "color_picker": "text",
    "label_frame": "title",
    "window": "title",
    "toplevel": "title",
    "chart": "title",
}


class DesignCanvas(AddWidgetsMixin, InlineEditMixin, QGraphicsView):
    selectionChanged = Signal(list)
    zoomChanged = Signal(float)
    cursorMoved = Signal(float, float)
    documentEdited = Signal()
    sizeChanged = Signal(int, int)
    contextMenuRequested = Signal(object, QPoint)
    filesDropped = Signal(list, QPointF)
    windowRequested = Signal(str)
    message = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.scene_ = DesignScene()
        self.setScene(self.scene_)
        self.doc: ProjectDocument | None = None
        self.history: History | None = None
        self.window_id: str | None = None
        self.selection: list[str] = []
        self.hover_id: str | None = None
        self._zoom = 1.0
        self._tool: Tool | None = None
        self._space = False
        self._plan: DropPlan | None = None
        self._guide_preview: tuple[str, int | None, float] | None = None
        self._edit: QLineEdit | None = None
        self._edit_target: tuple[str, str, int | None] | None = None
        self._fitted_for: str | None = None
        # editing options (grid_size / show_grid live on the scene: the window paints its dots)
        self.snap_to_grid = True
        self.smart_guides = True
        self.show_guides = True

        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.SmartViewportUpdate)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.setMouseTracking(True)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.viewport().grabGesture(Qt.GestureType.PinchGesture)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.horizontalScrollBar().valueChanged.connect(self.viewport().update)
        self.verticalScrollBar().valueChanged.connect(self.viewport().update)

    @property
    def grid_size(self) -> int:
        return self.scene_.grid_size

    @grid_size.setter
    def grid_size(self, value: int) -> None:
        self.scene_.grid_size = max(2, int(value))
        self.scene_.update()

    @property
    def show_grid(self) -> bool:
        return self.scene_.show_grid

    @show_grid.setter
    def show_grid(self, value: bool) -> None:
        self.scene_.show_grid = bool(value)
        self.scene_.update()

    # ----------------------------------------------------------------------------- binding
    def palette_(self) -> EditorPalette:
        return current_palette()

    def bind(self, doc: ProjectDocument, history: History, window_id: str | None = None) -> None:
        self.cancel_inline_edit()
        self._tool = None
        self.doc, self.history = doc, history
        self.selection = []
        self.scene_.set_document(doc)
        self.window_id = None
        self.set_window(window_id or doc.project.root_id)
        self.set_selection([self.window_id] if self.window_id else [], emit=True)

    def set_base_dir(self, path: Path | None) -> None:
        if path != self.scene_.base_dir:
            self.scene_.base_dir = path
            self.refresh()

    def set_window(self, window_id: str) -> None:
        if self.doc is None or window_id not in self.doc.project.nodes:
            return
        changed = window_id != self.window_id
        self.window_id = window_id
        self.scene_.set_window(window_id)
        self.scene_.sync()
        if changed:
            self.selection = [s for s in self.selection if self._in_window(s)]
            if self._fitted_for != window_id:
                self._fitted_for = window_id
                self.fit()
            self.viewport().update()

    def _in_window(self, node_id: str) -> bool:
        return node_id in self.scene_.items_by_id

    def refresh(self) -> None:
        """Re-sync the scene with the document (cheap: only changed nodes repaint)."""
        if self.doc is None:
            return
        if self.window_id not in self.doc.project.nodes:
            self.window_id = self.doc.project.root_id
            self.scene_.set_window(self.window_id)
        self.scene_.sync()
        keep = [s for s in self.selection if s in self.scene_.items_by_id]
        if keep != self.selection:
            self.selection = keep
            self.selectionChanged.emit(list(self.selection))
        if (
            self._edit is not None
            and self._edit_target
            and self._edit_target[0] not in self.scene_.items_by_id
        ):
            self.cancel_inline_edit()
        self.viewport().update()

    def push(self, cmd: Command) -> bool:
        """Push a command through History, refresh, and notify the host."""
        if self.doc is None or self.history is None:
            return False
        try:
            self.history.push(self.doc, cmd)
        except ValueError as exc:
            self.message.emit(f"Cannot do that: {exc}")
            self.refresh()
            return False
        self.refresh()
        self.documentEdited.emit()
        return True

    def undo_last(self) -> None:
        if self.doc is not None and self.history is not None and self.history.undo(self.doc):
            self.refresh()
            self.documentEdited.emit()

    # ----------------------------------------------------------------------- item lookups
    def item_for(self, node_id: str) -> NodeItem | None:
        return self.scene_.items_by_id.get(node_id)

    def node_scene_rect(self, node_id: str) -> QRectF:
        item = self.item_for(node_id)
        if item is None:
            return QRectF()
        w, h = item.size
        return item.mapToScene(QRectF(0, 0, w, h)).boundingRect()

    def hit_node(self, pt: QPointF) -> str | None:
        root = self.scene_.root_item
        return self._hit(root, pt, None) if root is not None else None

    def container_at(self, pt: QPointF, exclude: set[str] | None = None) -> Node:
        assert self.doc is not None
        root = self.scene_.root_item
        res = self._hit(root, pt, exclude or set(), containers_only=True) if root else None
        return self.doc.get_node(res or self.window_id or self.doc.project.root_id)

    def _hit(
        self, item: NodeItem, pt: QPointF, exclude: set[str] | None, containers_only: bool = False
    ) -> str | None:
        if exclude and item.node_id in exclude:
            return None
        local = item.mapFromScene(pt)
        w, h = item.size
        if not (0 <= local.x() <= w and 0 <= local.y() <= h):
            return None
        for child in sorted(item.childItems(), key=lambda c: c.zValue(), reverse=True):
            if isinstance(child, NodeItem) and child.isVisible():
                r = self._hit(child, pt, exclude, containers_only)
                if r:
                    return r
        node = self.scene_.node(item.node_id)
        if containers_only and (node is None or not get_spec(node.type).container):
            return None
        return item.node_id

    def container_content_origin(self, container: Node) -> tuple[float, float]:
        assert self.doc is not None
        return content_origin_abs(self.doc, container)

    # ------------------------------------------------------------------------- settings
    def snap_settings(self) -> SnapSettings:
        return SnapSettings(
            grid=self.grid_size,
            use_grid=self.snap_to_grid,
            use_smart=self.smart_guides,
            use_guides=self.show_guides,
            threshold=6.0 / max(self._zoom, 0.01),
        )

    def guides(self) -> tuple[list[float], list[float]]:
        if self.doc is None or self.window_id is None:
            return [], []
        g = dict(self.doc.project.editor.get("guides", {})).get(self.window_id, {})
        return list(g.get("v", [])), list(g.get("h", []))

    def guides_for_origin(self, ox: float, oy: float) -> tuple[list[float], list[float]]:
        if not self.show_guides:
            return [], []
        v, h = self.guides()
        return [x - ox for x in v], [y - oy for y in h]

    def set_option(self, name: str, value: object) -> None:
        setattr(self, name, value)
        self.viewport().update()

    # ------------------------------------------------------------------------ selection
    def set_selection(self, ids: list[str], emit: bool = True) -> None:
        ids = [i for i in dict.fromkeys(ids) if i in self.scene_.items_by_id]
        if ids == self.selection:
            return
        self.selection = ids
        self.viewport().update()
        if emit:
            self.selectionChanged.emit(list(ids))

    def select_all(self) -> None:
        if self.doc is None:
            return
        parent = self.doc.get_node(self.selection[-1]).parent_id if self.selection else None
        container = parent or self.window_id
        assert container is not None
        self.set_selection([k.id for k in visible_children(self.doc, self.doc.get_node(container))])

    def movable_ids(self) -> list[str]:
        """Selected nodes that may be moved (not locked / window / inside another selected node)."""
        if self.doc is None:
            return []
        sel = set(self.selection)
        out = []
        for i in self.selection:
            node = self.doc.get_node(i)
            if node.type in ("window", "toplevel") or node.locked:
                continue
            if any(a.id in sel for a in self.doc.ancestors(i)):
                continue
            out.append(i)
        return out

    def dim_items(self, ids: list[str], on: bool) -> None:
        for i in ids:
            item = self.item_for(i)
            node = self.scene_.node(i)
            if item is not None and node is not None:
                item.setOpacity(0.25 if on else (1.0 if node.enabled else 0.55))

    def clear_overlays(self) -> None:
        self._plan = None
        self._guide_preview = None
        self.viewport().update()

    # ----------------------------------------------------------------------------- zoom
    @property
    def zoom(self) -> float:
        return self._zoom

    def set_zoom(self, z: float, anchor: QPoint | None = None) -> None:
        z = max(ZOOM_MIN, min(ZOOM_MAX, z))
        anchor = (
            anchor
            if anchor is not None
            else QPoint(self.viewport().width() // 2, self.viewport().height() // 2)
        )
        before = self.mapToScene(anchor)
        self._zoom = z
        self.resetTransform()
        self.scale(z, z)
        shift = self.mapFromScene(before) - anchor
        self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() + shift.x())
        self.verticalScrollBar().setValue(self.verticalScrollBar().value() + shift.y())
        self.zoomChanged.emit(z)
        self.viewport().update()

    def zoom_in(self) -> None:
        self.set_zoom(self._zoom * 1.25)

    def zoom_out(self) -> None:
        self.set_zoom(self._zoom / 1.25)

    def actual_size(self) -> None:
        self.set_zoom(1.0)
        self.center_window()

    def window_rect(self) -> QRectF:
        root = self.scene_.root_item
        if root is None:
            return QRectF(0, 0, 640, 480)
        return root.mapRectToScene(root.boundingRect())

    def center_window(self) -> None:
        self.centerOn(self.window_rect().center())

    def fit(self) -> None:
        rect = self.window_rect().adjusted(-40, -40, 40, 40)
        vw, vh = max(1, self.viewport().width()), max(1, self.viewport().height())
        self.set_zoom(min(vw / rect.width(), vh / rect.height(), 1.0))
        self.centerOn(rect.center())

    def resizeEvent(self, ev) -> None:
        super().resizeEvent(ev)
        self.viewport().update()

    # ------------------------------------------------------------------------ geometry
    def _edge_handle_at(self, pt: QPointF) -> str | None:
        """Window-resize handle (e / s / se) near the bottom-right of the window."""
        r = self.window_rect()
        top = self.scene_.root_item
        if top is None:
            return None
        r = QRectF(0, 0, *top.size)
        s = self._zoom
        near_x = r.right() - 3 / s <= pt.x() <= r.right() + 9 / s
        near_y = r.bottom() - 3 / s <= pt.y() <= r.bottom() + 9 / s
        in_x = -2 / s <= pt.x() <= r.right() + 9 / s
        in_y = -2 / s <= pt.y() <= r.bottom() + 9 / s
        if near_x and near_y:
            return "se"
        if near_x and in_y and pt.x() >= r.right() - 1 / s:
            return "e"
        if near_y and in_x and pt.y() >= r.bottom() - 1 / s:
            return "s"
        return None

    def _guide_at(self, pt: QPointF) -> tuple[str, int] | None:
        if not self.show_guides:
            return None
        v, h = self.guides()
        tol = 4 / self._zoom
        for i, x in enumerate(v):
            if abs(pt.x() - x) <= tol:
                return "v", i
        for i, y in enumerate(h):
            if abs(pt.y() - y) <= tol:
                return "h", i
        return None

    # ---------------------------------------------------------------------- mouse input
    def mousePressEvent(self, ev: QMouseEvent) -> None:
        self.setFocus()
        if self.doc is None:
            return
        self.commit_inline_edit()
        view_pos = ev.position().toPoint()
        pt = self.mapToScene(view_pos)
        btn = ev.button()
        if btn == Qt.MouseButton.MiddleButton or (btn == Qt.MouseButton.LeftButton and self._space):
            self._tool = PanTool(self, view_pos)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return
        if btn != Qt.MouseButton.LeftButton:
            return
        # guides
        g = self._guide_at(pt)
        if g is not None:
            v, h = self.guides()
            self._tool = GuideTool(self, g[0], g[1], (v if g[0] == "v" else h)[g[1]])
            return
        # window edge / corner
        edge = self._edge_handle_at(pt)
        if edge is not None and self.window_id is not None:
            self._tool = WindowResizeTool(self, edge, pt)
            self.setCursor(cursor_for(edge))
            return
        # resize handles of a single selected widget
        if len(self.selection) == 1:
            node = self.doc.get_node(self.selection[0])
            if node.type not in ("window", "toplevel") and not node.locked:
                handle = hit_handle(self.node_scene_rect(node.id), pt, self._zoom)
                if handle:
                    self._tool = ResizeTool(self, node.id, handle, pt)
                    self.setCursor(cursor_for(handle))
                    return
        hit = self.hit_node(pt)
        mods = ev.modifiers()
        toggle = bool(
            mods
            & (
                Qt.KeyboardModifier.ShiftModifier
                | Qt.KeyboardModifier.ControlModifier
                | Qt.KeyboardModifier.MetaModifier
            )
        )
        if hit is None:
            hit = self.window_id
            if hit is None:
                return
        node = self.doc.get_node(hit)
        if node.type == "tabview":
            ax, ay = (
                self.node_scene_rect(hit).topLeft().x(),
                self.node_scene_rect(hit).topLeft().y(),
            )
            tab = tab_at(node, pt.x() - ax, pt.y() - ay)
            if tab is not None and tab != current_page(node):
                self.push(
                    SetField(
                        hit,
                        "props",
                        "current",
                        tab,
                        label="Switch tab",
                        merge_key=new_drag_key("tab"),
                    )
                )
        if node.type in ("window", "toplevel"):
            self._tool = RubberBandTool(self, pt, hit, toggle, view_pos)
            if not toggle:
                self.set_selection([hit])
            return
        if toggle:
            sel = list(self.selection)
            if hit in sel:
                sel.remove(hit)
            else:
                sel.append(hit)
            self.set_selection(sel)
            return
        if hit not in self.selection:
            self.set_selection([hit])
        ids = self.movable_ids()
        if any(hit in self.doc.subtree_ids(i) for i in ids):
            self._tool = MoveTool(self, ids, pt, view_pos, hit)

    def mouseMoveEvent(self, ev: QMouseEvent) -> None:
        if self.doc is None:
            return
        view_pos = ev.position().toPoint()
        pt = self.mapToScene(view_pos)
        self.cursorMoved.emit(pt.x(), pt.y())
        if self._tool is not None:
            self._tool.move(pt, ev)
            return
        self._update_hover(pt)

    def _update_hover(self, pt: QPointF) -> None:
        cur: Qt.CursorShape | None = None
        if self._space:
            cur = Qt.CursorShape.OpenHandCursor
        elif self._guide_at(pt):
            g = self._guide_at(pt)
            cur = Qt.CursorShape.SplitHCursor if g and g[0] == "v" else Qt.CursorShape.SplitVCursor
        elif (edge := self._edge_handle_at(pt)) is not None:
            cur = cursor_for(edge)
        elif len(self.selection) == 1 and self.doc is not None:
            node = self.doc.get_node(self.selection[0])
            if node.type not in ("window", "toplevel") and not node.locked:
                h = hit_handle(self.node_scene_rect(node.id), pt, self._zoom)
                if h:
                    cur = cursor_for(h)
        if cur is None:
            self.unsetCursor()
        else:
            self.setCursor(cur)
        hid = self.hit_node(pt)
        if hid != self.hover_id:
            self.hover_id = hid
            self.viewport().update()

    def mouseReleaseEvent(self, ev: QMouseEvent) -> None:
        tool, self._tool = self._tool, None
        if tool is not None:
            pt = self.mapToScene(ev.position().toPoint())
            tool.release(pt, ev)
            if isinstance(tool, (PanTool, WindowResizeTool)):
                self.unsetCursor()
            self.viewport().update()
        if self._space:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            self.unsetCursor()

    def mouseDoubleClickEvent(self, ev: QMouseEvent) -> None:
        if self.doc is None or ev.button() != Qt.MouseButton.LeftButton:
            return
        pt = self.mapToScene(ev.position().toPoint())
        hit = self.hit_node(pt)
        if hit:
            self.begin_inline_edit(hit, pt)

    def leaveEvent(self, ev) -> None:
        self.hover_id = None
        self.viewport().update()
        super().leaveEvent(ev)

    def contextMenuEvent(self, ev) -> None:
        if self.doc is None:
            return
        pt = self.mapToScene(ev.pos())
        hit = self.hit_node(pt) or self.window_id
        if hit and hit not in self.selection:
            self.set_selection([hit])
        self.contextMenuRequested.emit(hit, ev.globalPos())

    def wheelEvent(self, ev) -> None:
        if ev.modifiers() & (
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier
        ):
            delta = ev.angleDelta().y() or ev.pixelDelta().y()
            self.set_zoom(self._zoom * (1.0015**delta), ev.position().toPoint())
            ev.accept()
            return
        super().wheelEvent(ev)

    def viewportEvent(self, ev: QEvent) -> bool:
        if ev.type() == QEvent.Type.NativeGesture:
            if ev.gestureType() == Qt.NativeGestureType.ZoomNativeGesture:
                self.set_zoom(self._zoom * (1 + ev.value()), ev.position().toPoint())
                return True
        elif ev.type() == QEvent.Type.Gesture:
            pinch = ev.gesture(Qt.GestureType.PinchGesture)
            if pinch is not None:
                self.set_zoom(self._zoom * pinch.scaleFactor() / max(pinch.lastScaleFactor(), 1e-3))
                return True
        return super().viewportEvent(ev)

    # --------------------------------------------------------------------------- keyboard
    def keyPressEvent(self, ev: QKeyEvent) -> None:
        key = ev.key()
        if key == Qt.Key.Key_Space and not ev.isAutoRepeat():
            self._space = True
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            return
        if key == Qt.Key.Key_Escape:
            if self._tool is not None:
                self._tool.cancel()
                self._tool = None
                self.clear_overlays()
                self.refresh()
            elif self._edit is not None:
                self.cancel_inline_edit()
            else:
                self.set_selection([self.window_id] if self.window_id else [])
            return
        arrows = {
            Qt.Key.Key_Left: (-1, 0),
            Qt.Key.Key_Right: (1, 0),
            Qt.Key.Key_Up: (0, -1),
            Qt.Key.Key_Down: (0, 1),
        }
        if key in arrows and self.selection:
            step = 10 if ev.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1
            self.nudge(arrows[key][0] * step, arrows[key][1] * step)
            return
        super().keyPressEvent(ev)

    def keyReleaseEvent(self, ev: QKeyEvent) -> None:
        if ev.key() == Qt.Key.Key_Space and not ev.isAutoRepeat():
            self._space = False
            self.unsetCursor()
            return
        super().keyReleaseEvent(ev)

    def nudge(self, dx: int, dy: int) -> None:
        """Arrow-key move: pixels (absolute), sibling order (flex) or cell (grid)."""
        if self.doc is None:
            return
        ids = self.movable_ids()
        if not ids:
            return
        doc = self.doc
        parents = {doc.get_node(i).parent_id for i in ids}
        if len(parents) != 1:
            return
        parent = doc.get_node(next(iter(parents)))  # type: ignore[arg-type]
        mode = container_mode(parent)
        if mode == "absolute":
            updates = []
            for i in ids:
                b = doc.get_node(i).box
                updates.append((i, Box(x=b.x + dx, y=b.y + dy, w=b.w, h=b.h)))
            self.push(MergeableBoxes(updates, label="Nudge", merge_key="nudge:" + ",".join(ids)))
        elif mode == "flex" and len(ids) == 1:
            row = parent.layout is not None and parent.layout.direction == "row"
            step = (dx if row else dy) or (dy if row else dx)
            order = [k.id for k in doc.children(parent.id)]
            at = order.index(ids[0])
            new = max(0, min(len(order) - 1, at + (1 if step > 0 else -1)))
            if new != at:
                order.insert(new, order.pop(at))
                self.push(Batch([ReorderChildren(order, label="Reorder")], label="Reorder"))
        elif mode == "grid" and len(ids) == 1:
            cell = doc.get_node(ids[0]).cell
            new = cell.model_copy(
                update={"column": max(0, cell.column + dx), "row": max(0, cell.row + dy)}
            )
            if new != cell:
                self.push(
                    Batch([SetAttr(ids[0], "cell", new, label="Move cell")], label="Move cell")
                )

    # ------------------------------------------------------------------ window resizing
    def apply_window_size(
        self, size: tuple[int, int], key: str | None = None, live: bool = False
    ) -> None:
        if self.doc is None or self.window_id is None:
            return
        cmd = SetWindowSize(self.window_id, int(size[0]), int(size[1]), merge_key=key)
        self.push(cmd) if not live else self._push_quiet(cmd)

    def _push_quiet(self, cmd: Command) -> None:
        assert self.doc is not None and self.history is not None
        try:
            self.history.push(self.doc, cmd)
        except ValueError:
            return
        self.refresh()

    def finish_window_resize(self) -> None:
        self.documentEdited.emit()

    # ---------------------------------------------------------------------------- guides
    def preview_guide(self, orient: str | None, index: int | None, pos: float) -> None:
        self._guide_preview = (orient, index, pos) if orient else None
        self.viewport().update()

    def commit_guide(self, orient: str, index: int | None, pos: float) -> None:
        assert self.doc is not None and self.window_id is not None
        self._guide_preview = None
        v, h = self.guides()
        lst = v if orient == "v" else h
        w, hgt = self.scene_.root_item.size if self.scene_.root_item else (0, 0)
        limit = w if orient == "v" else hgt
        outside = pos < 0 or pos > limit
        if index is not None:
            if outside:
                lst.pop(index)
            else:
                lst[index] = pos
        elif not outside:
            lst.append(pos)
        self.push(guides_command(self.doc, self.window_id, v, h))

    def start_guide_from_ruler(self, orient: str) -> None:
        self._tool = GuideTool(self, orient, None, 0)

    def begin_ruler_drag(self, orient: str, scene_pos: float) -> None:
        self._tool = GuideTool(self, orient, None, scene_pos)
        self._tool.move(QPointF(scene_pos, scene_pos), None)

    def update_ruler_drag(self, pt: QPointF) -> None:
        if isinstance(self._tool, GuideTool):
            self._tool.move(pt, None)

    def end_ruler_drag(self, pt: QPointF) -> None:
        tool, self._tool = self._tool, None
        if isinstance(tool, GuideTool):
            tool.move(pt, None)
            tool.release(pt, None)

    # ------------------------------------------------------------------------ drag & drop
    def dragEnterEvent(self, ev) -> None:
        md = ev.mimeData()
        if md.hasFormat(MIME_WIDGET) or md.hasUrls():
            ev.acceptProposedAction()

    def dragMoveEvent(self, ev) -> None:
        md = ev.mimeData()
        if self.doc is None:
            return
        pt = self.mapToScene(ev.position().toPoint())
        if md.hasFormat(MIME_WIDGET):
            type_id = bytes(md.data(MIME_WIDGET)).decode()
            if has_spec(type_id) and type_id not in ("window", "toplevel"):
                container = self.container_at(pt)
                self._plan = plan_in_container(
                    self.doc, container, pt, get_spec(type_id).default_size
                )
                ev.acceptProposedAction()
                self.viewport().update()
                return
            ev.acceptProposedAction()
            return
        if md.hasUrls():
            ev.acceptProposedAction()

    def dragLeaveEvent(self, ev) -> None:
        self.clear_overlays()
        super().dragLeaveEvent(ev)

    def dropEvent(self, ev) -> None:
        md = ev.mimeData()
        pt = self.mapToScene(ev.position().toPoint())
        self.clear_overlays()
        if md.hasFormat(MIME_WIDGET):
            type_id = bytes(md.data(MIME_WIDGET)).decode()
            self.add_widget(type_id, pt)
            self.setFocus()
            ev.acceptProposedAction()
        elif md.hasUrls():
            paths = [u.toLocalFile() for u in md.urls() if u.isLocalFile()]
            if paths:
                self.filesDropped.emit(paths, pt)
                ev.acceptProposedAction()

    # -------------------------------------------------------------------------- painting
    def drawBackground(self, p: QPainter, rect: QRectF) -> None:
        pal = self.palette_()
        p.fillRect(rect, pal.color("canvas"))
        wr = self.window_rect()
        if self.scene_.root_item is not None:
            for i in range(1, 5):
                c = QColor(0, 0, 0, 22 - i * 4)
                p.fillRect(wr.adjusted(-i, -i + 3, i, i + 5), c)

    def drawForeground(self, p: QPainter, rect: QRectF) -> None:
        root = self.scene_.root_item
        if root is None or self.doc is None:
            return
        pal = self.palette_()
        s = self._zoom
        wrect = QRectF(0, 0, *root.size)
        if self.show_guides:
            v, h = self.guides()
            if self._guide_preview and self._guide_preview[0]:
                orient, idx, pos = self._guide_preview
                lst = v if orient == "v" else h
                if idx is not None and idx < len(lst):
                    lst = list(lst)
                    lst[idx] = pos
                else:
                    lst = [*lst, pos]
                v, h = (lst, h) if orient == "v" else (v, lst)
            ov.draw_user_guides(p, v, h, wrect, pal)
        self._paint_grid_tracks(p, pal)
        # hover
        if self.hover_id and self.hover_id not in self.selection and self._tool is None:
            ov.draw_hover(p, self.node_scene_rect(self.hover_id), pal)
        # selection
        rects = []
        for i in self.selection:
            node = self.doc.project.nodes.get(i)
            if node is None or i not in self.scene_.items_by_id:
                continue
            rects.append((self.node_scene_rect(i), i == self.selection[-1], node.locked))
        ov.draw_selection(p, rects, pal)
        if len(self.selection) == 1 and self._tool is None:
            node = self.doc.project.nodes.get(self.selection[0])
            if node is not None and node.type not in ("window", "toplevel") and not node.locked:
                ov.draw_handles(p, self.node_scene_rect(node.id), s, pal)
        ov.draw_window_grip(p, wrect, s, pal, isinstance(self._tool, WindowResizeTool))
        # drop preview (palette drag) and active tool
        if self._plan is not None:
            if self._plan.target_rect is not None:
                ov.draw_drop_target(p, self._plan.target_rect, pal)
            if self._plan.cell_rect is not None:
                ov.draw_cell_highlight(p, self._plan.cell_rect, pal)
            if self._plan.insertion is not None:
                ov.draw_insertion(p, self._plan.insertion[0], self._plan.insertion[1], s, pal)
        if self._tool is not None:
            self._tool.paint(p, s)

    def _paint_grid_tracks(self, p: QPainter, pal: EditorPalette) -> None:
        assert self.doc is not None
        ids: set[str] = set()
        for i in self.selection:
            node = self.doc.project.nodes.get(i)
            if node is None:
                continue
            ids.add(i)
            if node.parent_id:
                ids.add(node.parent_id)
        if self._plan is not None:
            ids.add(self._plan.container_id)
        for i in ids:
            node = self.doc.project.nodes.get(i)
            if node is None or i not in self.scene_.items_by_id or container_mode(node) != "grid":
                continue
            ox, oy = content_origin_abs(self.doc, node)
            gg = grid_geometry(self.doc, node)
            ov.draw_grid_tracks(p, QPointF(ox, oy), gg.xs, gg.ys, gg.col_w, gg.row_h, pal)
