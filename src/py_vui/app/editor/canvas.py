from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPen
from PySide6.QtWidgets import (
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
)

from py_vui.app.editor.canvas_resize import (
    MIN_WIDGET_H,
    MIN_WIDGET_W,
    ResizeHandle,
    ResizeHandleItem,
    compute_resized_box,
    handle_anchor,
)
from py_vui.app.editor.snap import snap, snap_size
from py_vui.commands import ReplaceNode, SetLayoutBox, SetLayoutBoxes
from py_vui.model.document import ProjectDocument
from py_vui.model.geometry import Rect
from py_vui.model.nodes import ButtonNode, LabelNode, Node, WindowNode
from py_vui.model.theme import resolve_widget_colors

if TYPE_CHECKING:
    from py_vui.commands.history import History

MIME_WIDGET = "application/x-py-vui-widget"


class NodeGraphicsItem(QGraphicsRectItem):
    def __init__(
        self,
        node_id: str,
        label: str,
        w: float,
        h: float,
        *,
        movable: bool = True,
        fill: str = "#f0f8ff",
        border: str = "#3c64b4",
        text_color: str = "#0f172a",
        border_radius: int = 4,
        enabled: bool = True,
        font_size: int = 11,
        font_family: str = "Sans Serif",
    ) -> None:
        super().__init__(0, 0, w, h)
        self.node_id = node_id
        fill_q = QColor(fill)
        if not enabled:
            fill_q.setAlpha(140)
        self.setBrush(QBrush(fill_q))
        border_q = QColor(border)
        if not enabled:
            border_q = QColor("#94a3b8")
        self.setPen(QPen(border_q, 1.5))
        if movable and enabled:
            self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self._label = QGraphicsSimpleTextItem(label, self)
        label_font = QFont()
        if font_family:
            label_font.setFamily(font_family)
        label_font.setPointSize(font_size)
        self._label.setFont(label_font)
        self._label.setBrush(QBrush(QColor(text_color)))
        self._label.setPos(6, 6)
        self._border_radius = border_radius
        self._drag_start: QPointF | None = None
        self._start_box: Rect | None = None

    def paint(self, painter, option, widget=None) -> None:
        painter.setPen(self.pen())
        painter.setBrush(self.brush())
        if self._border_radius > 0:
            painter.drawRoundedRect(self.rect(), self._border_radius, self._border_radius)
        else:
            painter.drawRect(self.rect())
        if self.isSelected():
            painter.setPen(QPen(QColor(255, 120, 0), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            if self._border_radius > 0:
                painter.drawRoundedRect(self.rect(), self._border_radius, self._border_radius)
            else:
                painter.drawRect(self.rect())


class DesignCanvas(QGraphicsView):
    selection_changed = Signal(str)
    layout_changed = Signal()
    document_dirty = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        from PySide6.QtGui import QPainter

        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setAcceptDrops(True)
        self._scene_bg = QColor(248, 248, 252)
        self.setBackgroundBrush(QBrush(self._scene_bg))
        self._doc: ProjectDocument | None = None
        self._history: History | None = None
        self._items: dict[str, NodeGraphicsItem] = {}
        self._abs_pos: dict[str, QPointF] = {}
        self._rebuild_guard = False
        self._ignore_release = False
        self._palette_drag = False
        self._resize_handles: list[ResizeHandleItem] = []
        self._resize_active = False
        self._resize_node_id: str | None = None
        self._resize_handle: ResizeHandle | None = None
        self._resize_start_scene = QPointF()
        self._resize_start_box = Rect(x=0, y=0, w=0, h=0)

        self._scene.selectionChanged.connect(self._on_selection_changed)

    def bind(self, doc: ProjectDocument, history: History) -> None:
        self._doc = doc
        self._history = history
        self.rebuild()

    def rebuild(self) -> None:
        if self._doc is None:
            return
        self._rebuild_guard = True
        self._clear_resize_handles()
        self._scene.clear()
        self._items.clear()
        self._abs_pos.clear()

        root = self._doc.get_node(self._doc.project.root_id)
        self._abs_pos[root.id] = QPointF(0, 0)
        self._add_node_recursive(root)

        bg = self._doc.project.theme.background
        self._scene_bg = QColor(bg)
        self.setBackgroundBrush(QBrush(self._scene_bg))
        self._scene.setSceneRect(self._scene.itemsBoundingRect().adjusted(-40, -40, 80, 80))
        self._rebuild_guard = False

    def _add_node_recursive(self, node: Node) -> None:
        box = node.layout.box
        parent_abs = self._abs_pos.get(node.parent_id or "", QPointF(0, 0))
        abs_pos = parent_abs + QPointF(box.x, box.y)
        self._abs_pos[node.id] = abs_pos

        theme = self._doc.project.theme
        fill, border, text = resolve_widget_colors(
            theme=theme,
            node_type=node.type,
            style=node.style,
        )
        radius = theme.button_radius if node.type == "button" else 4
        if node.style and node.style.border_radius is not None:
            radius = node.style.border_radius
        font_size = node.style.font_size if node.style and node.style.font_size else theme.font_size
        label = node.name
        if isinstance(node, LabelNode) and node.props.text:
            label = node.props.text[:48]
        elif isinstance(node, ButtonNode) and node.props.text:
            label = node.props.text[:48]
        is_root = node.id == self._doc.project.root_id
        if isinstance(node, WindowNode):
            draw_w, draw_h = node.props.width, node.props.height
        else:
            draw_w, draw_h = box.w, box.h
        item = NodeGraphicsItem(
            node.id,
            label,
            draw_w,
            draw_h,
            movable=not is_root,
            fill=fill,
            border=border,
            text_color=text,
            border_radius=radius,
            enabled=node.enabled,
            font_size=max(8, font_size),
            font_family=theme.font_family,
        )
        item.setPos(abs_pos)
        item.setZValue(node.z_index)
        self._scene.addItem(item)
        self._items[node.id] = item

        for child in self._doc.children(node.id):  # type: ignore[union-attr]
            self._add_node_recursive(child)

    def _on_selection_changed(self) -> None:
        self._sync_resize_handles()
        ids = self.selected_node_ids()
        self.selection_changed.emit(ids[0] if ids else "")

    def _clear_resize_handles(self) -> None:
        for handle in self._resize_handles:
            handle.setParentItem(None)
            self._scene.removeItem(handle)
        self._resize_handles.clear()

    def _sync_resize_handles(self) -> None:
        self._clear_resize_handles()
        if self._resize_active or self._palette_drag:
            return
        node_id = self.selected_node_id()
        if not node_id:
            return
        item = self._items.get(node_id)
        if item is None:
            return
        for handle in ResizeHandle:
            rh = ResizeHandleItem(handle, self, item)
            self._resize_handles.append(rh)
        self._layout_resize_handles(item)

    def _layout_resize_handles(self, item: NodeGraphicsItem) -> None:
        rect = item.rect()
        w, h = rect.width(), rect.height()
        for rh in self._resize_handles:
            anchor = handle_anchor(rh._handle, w, h)
            rh.setPos(anchor)

    def _begin_resize(self, node_id: str, handle: ResizeHandle, scene_pos: QPointF) -> None:
        if self._doc is None:
            return
        node = self._doc.get_node(node_id)
        box = node.layout.box
        if isinstance(node, WindowNode):
            box = Rect(x=box.x, y=box.y, w=node.props.width, h=node.props.height)
        self._resize_active = True
        self._resize_node_id = node_id
        self._resize_handle = handle
        self._resize_start_scene = scene_pos
        self._resize_start_box = box
        item = self._items[node_id]
        item.setSelected(True)
        item.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)

    def _update_resize(self, scene_pos: QPointF) -> None:
        if not self._resize_active or self._resize_node_id is None or self._resize_handle is None:
            return
        if self._doc is None:
            return
        node = self._doc.get_node(self._resize_node_id)
        parent_abs = self._abs_pos.get(node.parent_id or "", QPointF(0, 0))
        dx = scene_pos.x() - self._resize_start_scene.x()
        dy = scene_pos.y() - self._resize_start_scene.y()
        start = self._resize_start_box
        min_w = MIN_WIDGET_W
        min_h = MIN_WIDGET_H
        if isinstance(node, WindowNode):
            min_w, min_h = 200.0, 150.0
        x, y, w, h = compute_resized_box(
            self._resize_handle,
            start_x=start.x,
            start_y=start.y,
            start_w=start.w,
            start_h=start.h,
            dx=dx,
            dy=dy,
            min_w=min_w,
            min_h=min_h,
        )
        item = self._items[self._resize_node_id]
        item.setRect(0, 0, w, h)
        item.setPos(parent_abs + QPointF(x, y))
        self._layout_resize_handles(item)

    def _finish_resize(self) -> None:
        for rh in self._resize_handles:
            if rh._grabbing:
                rh.ungrabMouse()
                rh._grabbing = False
        if not self._resize_active or self._resize_node_id is None or self._doc is None:
            return
        if self._history is None:
            self._resize_active = False
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
            return
        node_id = self._resize_node_id
        item = self._items.get(node_id)
        if item is None:
            self._resize_active = False
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
            return
        node = self._doc.get_node(node_id)
        parent_abs = self._abs_pos.get(node.parent_id or "", QPointF(0, 0))
        rect = item.rect()
        local_x = item.pos().x() - parent_abs.x()
        local_y = item.pos().y() - parent_abs.y()
        new_box = Rect(
            x=snap(local_x),
            y=snap(local_y),
            w=snap_size(rect.width()),
            h=snap_size(rect.height()),
        )
        before = node
        if isinstance(node, WindowNode):
            data = node.model_dump()
            data["layout"]["box"]["x"] = new_box.x
            data["layout"]["box"]["y"] = new_box.y
            data["layout"]["box"]["w"] = new_box.w
            data["layout"]["box"]["h"] = new_box.h
            data["props"]["width"] = new_box.w
            data["props"]["height"] = new_box.h
            after = WindowNode.model_validate(data)
            if after.model_dump() != before.model_dump():
                self._history.push(self._doc, ReplaceNode(before=before, after=after))
        elif (
            abs(new_box.x - before.layout.box.x) > 0.5
            or abs(new_box.y - before.layout.box.y) > 0.5
            or abs(new_box.w - before.layout.box.w) > 0.5
            or abs(new_box.h - before.layout.box.h) > 0.5
        ):
            self._history.push(self._doc, SetLayoutBox(node_id=node_id, new_box=new_box))
        self._resize_active = False
        self._resize_node_id = None
        self._resize_handle = None
        self._ignore_release = True
        is_root = node_id == self._doc.project.root_id
        item.setFlag(
            QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable,
            not is_root and before.enabled,
        )
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.rebuild()
        self.select_node(node_id)
        self.layout_changed.emit()

    def selected_node_ids(self) -> list[str]:
        if self._doc is None:
            return []
        return [
            it.node_id
            for it in self._scene.selectedItems()
            if isinstance(it, NodeGraphicsItem) and it.node_id != self._doc.project.root_id
        ]

    def selected_node_id(self) -> str | None:
        ids = self.selected_node_ids()
        return ids[0] if ids else None

    def select_node(self, node_id: str) -> None:
        item = self._items.get(node_id)
        if item:
            self._scene.clearSelection()
            item.setSelected(True)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasFormat(MIME_WIDGET):
            self._palette_drag = True
            self._set_children_movable(False)
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasFormat(MIME_WIDGET):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dragLeaveEvent(self, event) -> None:
        if self._palette_drag:
            self._palette_drag = False
            self._set_children_movable(True)
        super().dragLeaveEvent(event)

    def _set_children_movable(self, movable: bool) -> None:
        if self._doc is None:
            return
        root_id = self._doc.project.root_id
        for node_id, item in self._items.items():
            if node_id != root_id:
                item.setFlag(
                    QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable, movable
                )

    def dropEvent(self, event) -> None:
        if not event.mimeData().hasFormat(MIME_WIDGET) or self._doc is None:
            return
        widget_type = bytes(event.mimeData().data(MIME_WIDGET)).decode()
        if widget_type == "window":
            event.ignore()
            return

        scene_pos = self.mapToScene(event.position().toPoint())
        parent_id = self._parent_at(scene_pos) or self._doc.project.root_id
        x, y, w, h = self._drop_geometry(parent_id, scene_pos, widget_type)

        from py_vui.app.editor.factory import create_node
        from py_vui.commands import AddNode

        parent_node = self._doc.get_node(parent_id)
        node = create_node(
            widget_type,
            parent_id=parent_id,
            parent=parent_node,
            x=x,
            y=y,
            w=w,
            h=h,
        )
        self._ignore_release = True
        self._palette_drag = False
        self._set_children_movable(True)
        if self._history:
            self._history.push(self._doc, AddNode(node))
        else:
            self._doc.project.nodes[node.id] = node
        self.rebuild()
        self.select_node(node.id)
        self._sync_resize_handles()
        self.document_dirty.emit()
        event.acceptProposedAction()

    def _parent_inner_size(self, parent_id: str) -> tuple[float, float]:
        parent = self._doc.get_node(parent_id)  # type: ignore[union-attr]
        if isinstance(parent, WindowNode):
            return parent.props.width, parent.props.height
        box = parent.layout.box
        return box.w, box.h

    def _drop_geometry(
        self, parent_id: str, scene_pos: QPointF, widget_type: str
    ) -> tuple[float, float, float, float]:
        parent_abs = self._abs_pos.get(parent_id, QPointF(0, 0))
        rel = scene_pos - parent_abs
        pw, ph = self._parent_inner_size(parent_id)

        if widget_type == "frame":
            default_w, default_h = 200.0, 150.0
        elif widget_type == "line_edit":
            default_w, default_h = 160.0, 28.0
        elif widget_type == "text_edit":
            default_w, default_h = 160.0, 80.0
        elif widget_type == "combo_box":
            default_w, default_h = 140.0, 28.0
        elif widget_type in ("tab_widget", "group_box"):
            default_w, default_h = 280.0, 200.0
        elif widget_type == "list_widget":
            default_w, default_h = 140.0, 100.0
        elif widget_type == "slider":
            default_w, default_h = 160.0, 28.0
        elif widget_type == "progress_bar":
            default_w, default_h = 160.0, 24.0
        else:
            default_w, default_h = 120.0, 32.0

        margin = 8.0
        max_w = max(40.0, pw - margin * 2)
        max_h = max(24.0, ph - margin * 2)
        w = snap_size(min(default_w, max_w))
        h = snap_size(min(default_h, max_h))
        x = snap(max(margin, min(rel.x(), pw - w - margin)))
        y = snap(max(margin, min(rel.y(), ph - h - margin)))
        return x, y, w, h

    def _parent_at(self, scene_pos: QPointF) -> str | None:
        if self._doc is None:
            return None
        for hit in self._scene.items(scene_pos):
            item: NodeGraphicsItem | None = None
            if isinstance(hit, NodeGraphicsItem):
                item = hit
            else:
                parent = hit.parentItem()
                if isinstance(parent, NodeGraphicsItem):
                    item = parent
            if item is None:
                continue
            if item.node_id != self._doc.project.root_id:
                return item.node_id
        for hit in self._scene.items(scene_pos):
            if isinstance(hit, NodeGraphicsItem):
                return hit.node_id
            parent = hit.parentItem()
            if isinstance(parent, NodeGraphicsItem):
                return parent.node_id
        return None

    def mouseMoveEvent(self, event) -> None:
        if self._resize_active:
            self._update_resize(self.mapToScene(event.position().toPoint()))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._resize_active:
            self._finish_resize()
            event.accept()
            return
        super().mouseReleaseEvent(event)
        if self._ignore_release:
            self._ignore_release = False
            return
        if self._rebuild_guard or self._doc is None or self._history is None:
            return
        moved_ids = self.selected_node_ids()
        if not moved_ids:
            return
        updates: list[tuple[str, Rect]] = []
        for moved_id in moved_ids:
            item = self._items.get(moved_id)
            if item is None:
                continue
            node = self._doc.get_node(moved_id)
            parent_abs = self._abs_pos.get(node.parent_id or "", QPointF(0, 0))
            box = node.layout.box
            expected = parent_abs + QPointF(box.x, box.y)
            actual = item.pos()
            if abs(actual.x() - expected.x()) < 0.5 and abs(actual.y() - expected.y()) < 0.5:
                continue
            new_x = snap(actual.x() - parent_abs.x())
            new_y = snap(actual.y() - parent_abs.y())
            if abs(new_x - box.x) > 0.5 or abs(new_y - box.y) > 0.5:
                updates.append((moved_id, Rect(x=new_x, y=new_y, w=box.w, h=box.h)))
        if not updates:
            return
        if len(updates) == 1:
            self._history.push(self._doc, SetLayoutBox(node_id=updates[0][0], new_box=updates[0][1]))
        else:
            self._history.push(self._doc, SetLayoutBoxes(updates=updates))
        self.rebuild()
        for nid, _ in updates:
            self.select_node(nid)
        self.layout_changed.emit()

    def nudge_selected(self, dx: int, dy: int) -> None:
        if self._doc is None or self._history is None:
            return
        ids = self.selected_node_ids()
        if not ids:
            return
        updates = []
        for node_id in ids:
            box = self._doc.get_node(node_id).layout.box
            updates.append((node_id, Rect(x=box.x + dx, y=box.y + dy, w=box.w, h=box.h)))
        if len(updates) == 1:
            self._history.push(self._doc, SetLayoutBox(node_id=updates[0][0], new_box=updates[0][1]))
        else:
            self._history.push(self._doc, SetLayoutBoxes(updates=updates))
        self.rebuild()
        for nid, _ in updates:
            self.select_node(nid)
        self.layout_changed.emit()

    def keyPressEvent(self, event) -> None:
        step = 8 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1
        if event.key() == Qt.Key.Key_Left:
            self.nudge_selected(-step, 0)
            event.accept()
            return
        if event.key() == Qt.Key.Key_Right:
            self.nudge_selected(step, 0)
            event.accept()
            return
        if event.key() == Qt.Key.Key_Up:
            self.nudge_selected(0, -step)
            event.accept()
            return
        if event.key() == Qt.Key.Key_Down:
            self.nudge_selected(0, step)
            event.accept()
            return
        if event.key() == Qt.Key.Key_Delete and self._doc and self._history:
            node_id = self.selected_node_id()
            if node_id and node_id != self._doc.project.root_id:
                from py_vui.commands import RemoveSubtree

                self._history.push(self._doc, RemoveSubtree(root_id=node_id))
                self.rebuild()
                self.document_dirty.emit()
                return
        super().keyPressEvent(event)
