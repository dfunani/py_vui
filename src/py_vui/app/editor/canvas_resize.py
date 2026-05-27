from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QPen
from PySide6.QtWidgets import QGraphicsRectItem

if TYPE_CHECKING:
    from py_vui.app.editor.canvas import DesignCanvas, NodeGraphicsItem

HANDLE_SIZE = 8.0
MIN_WIDGET_W = 32.0
MIN_WIDGET_H = 20.0


class ResizeHandle(StrEnum):
    NW = "nw"
    N = "n"
    NE = "ne"
    E = "e"
    SE = "se"
    S = "s"
    SW = "sw"
    W = "w"


_HANDLE_CURSORS: dict[ResizeHandle, Qt.CursorShape] = {
    ResizeHandle.NW: Qt.CursorShape.SizeFDiagCursor,
    ResizeHandle.N: Qt.CursorShape.SizeVerCursor,
    ResizeHandle.NE: Qt.CursorShape.SizeBDiagCursor,
    ResizeHandle.E: Qt.CursorShape.SizeHorCursor,
    ResizeHandle.SE: Qt.CursorShape.SizeFDiagCursor,
    ResizeHandle.S: Qt.CursorShape.SizeVerCursor,
    ResizeHandle.SW: Qt.CursorShape.SizeBDiagCursor,
    ResizeHandle.W: Qt.CursorShape.SizeHorCursor,
}


def handle_anchor(handle: ResizeHandle, width: float, height: float) -> QPointF:
    half = HANDLE_SIZE / 2
    anchors: dict[ResizeHandle, QPointF] = {
        ResizeHandle.NW: QPointF(0, 0),
        ResizeHandle.N: QPointF(width / 2, 0),
        ResizeHandle.NE: QPointF(width, 0),
        ResizeHandle.E: QPointF(width, height / 2),
        ResizeHandle.SE: QPointF(width, height),
        ResizeHandle.S: QPointF(width / 2, height),
        ResizeHandle.SW: QPointF(0, height),
        ResizeHandle.W: QPointF(0, height / 2),
    }
    return anchors[handle] - QPointF(half, half)


def compute_resized_box(
    handle: ResizeHandle,
    *,
    start_x: float,
    start_y: float,
    start_w: float,
    start_h: float,
    dx: float,
    dy: float,
    min_w: float = MIN_WIDGET_W,
    min_h: float = MIN_WIDGET_H,
) -> tuple[float, float, float, float]:
    x, y, w, h = start_x, start_y, start_w, start_h

    if handle in (ResizeHandle.E, ResizeHandle.NE, ResizeHandle.SE):
        w = max(min_w, start_w + dx)
    if handle in (ResizeHandle.W, ResizeHandle.NW, ResizeHandle.SW):
        w = max(min_w, start_w - dx)
        x = start_x + (start_w - w)

    if handle in (ResizeHandle.S, ResizeHandle.SE, ResizeHandle.SW):
        h = max(min_h, start_h + dy)
    if handle in (ResizeHandle.N, ResizeHandle.NE, ResizeHandle.NW):
        h = max(min_h, start_h - dy)
        y = start_y + (start_h - h)

    return x, y, w, h


class ResizeHandleItem(QGraphicsRectItem):
    def __init__(
        self,
        handle: ResizeHandle,
        canvas: DesignCanvas,
        parent: NodeGraphicsItem,
    ) -> None:
        super().__init__(parent)
        self._handle = handle
        self._canvas = canvas
        self.setRect(0, 0, HANDLE_SIZE, HANDLE_SIZE)
        self.setBrush(QBrush(QColor(255, 255, 255)))
        self.setPen(QPen(QColor(255, 120, 0), 1.5))
        self.setAcceptHoverEvents(True)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setZValue(10_000)
        self.setCursor(_HANDLE_CURSORS[handle])

    def hoverEnterEvent(self, event) -> None:
        self.setBrush(QBrush(QColor(255, 200, 120)))
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        self.setBrush(QBrush(QColor(255, 255, 255)))
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event) -> None:
        parent = self.parentItem()
        if isinstance(parent, NodeGraphicsItem):
            self._canvas._begin_resize(parent.node_id, self._handle, event.scenePos())
        event.accept()

    def mouseMoveEvent(self, event) -> None:
        self._canvas._update_resize(event.scenePos())
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._canvas._finish_resize()
        event.accept()
