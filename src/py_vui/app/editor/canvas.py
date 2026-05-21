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

from py_vui.commands import SetLayoutBox
from py_vui.model.document import ProjectDocument
from py_vui.model.geometry import Rect
from py_vui.model.nodes import Node, WindowNode

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
    ) -> None:
        super().__init__(0, 0, w, h)
        self.node_id = node_id
        self.setBrush(QBrush(QColor(240, 248, 255, 180)))
        self.setPen(QPen(QColor(60, 100, 180), 1.5))
        if movable:
            self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self._label = QGraphicsSimpleTextItem(label, self)
        self._label.setFont(QFont("Sans", 9))
        self._label.setPos(4, 4)
        self._drag_start: QPointF | None = None
        self._start_box: Rect | None = None

    def paint(self, painter, option, widget=None) -> None:
        super().paint(painter, option, widget)
        if self.isSelected():
            painter.setPen(QPen(QColor(255, 120, 0), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
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
        self.setBackgroundBrush(QBrush(QColor(248, 248, 252)))
        self._doc: ProjectDocument | None = None
        self._history: History | None = None
        self._items: dict[str, NodeGraphicsItem] = {}
        self._abs_pos: dict[str, QPointF] = {}
        self._rebuild_guard = False
        self._ignore_release = False
        self._palette_drag = False

        self._scene.selectionChanged.connect(self._on_selection_changed)

    def bind(self, doc: ProjectDocument, history: History) -> None:
        self._doc = doc
        self._history = history
        self.rebuild()

    def rebuild(self) -> None:
        if self._doc is None:
            return
        self._rebuild_guard = True
        self._scene.clear()
        self._items.clear()
        self._abs_pos.clear()

        root = self._doc.get_node(self._doc.project.root_id)
        self._abs_pos[root.id] = QPointF(0, 0)
        self._add_node_recursive(root)

        self._scene.setSceneRect(self._scene.itemsBoundingRect().adjusted(-40, -40, 80, 80))
        self._rebuild_guard = False

    def _add_node_recursive(self, node: Node) -> None:
        box = node.layout.box
        parent_abs = self._abs_pos.get(node.parent_id or "", QPointF(0, 0))
        abs_pos = parent_abs + QPointF(box.x, box.y)
        self._abs_pos[node.id] = abs_pos

        label = f"{node.name} ({node.type})"
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
        )
        item.setPos(abs_pos)
        item.setZValue(node.z_index)
        self._scene.addItem(item)
        self._items[node.id] = item

        for child in self._doc.children(node.id):  # type: ignore[union-attr]
            self._add_node_recursive(child)

    def _on_selection_changed(self) -> None:
        selected = self._scene.selectedItems()
        if len(selected) == 1 and isinstance(selected[0], NodeGraphicsItem):
            self.selection_changed.emit(selected[0].node_id)
        else:
            self.selection_changed.emit("")

    def selected_node_id(self) -> str | None:
        selected = self._scene.selectedItems()
        if len(selected) == 1 and isinstance(selected[0], NodeGraphicsItem):
            return selected[0].node_id
        return None

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
        else:
            default_w, default_h = 120.0, 32.0

        margin = 8.0
        max_w = max(40.0, pw - margin * 2)
        max_h = max(24.0, ph - margin * 2)
        w = min(default_w, max_w)
        h = min(default_h, max_h)
        x = max(margin, min(rel.x(), pw - w - margin))
        y = max(margin, min(rel.y(), ph - h - margin))
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

    def mouseReleaseEvent(self, event) -> None:
        super().mouseReleaseEvent(event)
        if self._ignore_release:
            self._ignore_release = False
            return
        if self._rebuild_guard or self._doc is None or self._history is None:
            return
        moved_id = self.selected_node_id()
        if not moved_id or moved_id == self._doc.project.root_id:
            return
        item = self._items.get(moved_id)
        if item is None:
            return
        node = self._doc.get_node(moved_id)
        parent_abs = self._abs_pos.get(node.parent_id or "", QPointF(0, 0))
        box = node.layout.box
        expected = parent_abs + QPointF(box.x, box.y)
        actual = item.pos()
        if abs(actual.x() - expected.x()) < 0.5 and abs(actual.y() - expected.y()) < 0.5:
            return
        new_x = actual.x() - parent_abs.x()
        new_y = actual.y() - parent_abs.y()
        if abs(new_x - box.x) > 0.5 or abs(new_y - box.y) > 0.5:
            new_box = Rect(x=new_x, y=new_y, w=box.w, h=box.h)
            self._history.push(
                self._doc,
                SetLayoutBox(node_id=moved_id, new_box=new_box),
            )
            self.rebuild()
            self.select_node(moved_id)
            self.layout_changed.emit()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Delete and self._doc and self._history:
            node_id = self.selected_node_id()
            if node_id and node_id != self._doc.project.root_id:
                from py_vui.commands import RemoveSubtree

                self._history.push(self._doc, RemoveSubtree(root_id=node_id))
                self.rebuild()
                self.document_dirty.emit()
                return
        super().keyPressEvent(event)
