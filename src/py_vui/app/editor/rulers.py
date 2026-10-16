"""Pixel rulers around the canvas; dragging from a ruler creates a guide."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QWidget

from py_vui.app.editor.editor_theme import current_palette

if TYPE_CHECKING:
    from py_vui.app.editor.canvas import DesignCanvas

RULER_THICKNESS = 20
_STEPS = (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000)


class Ruler(QWidget):
    def __init__(self, canvas: DesignCanvas, horizontal: bool) -> None:
        super().__init__()
        self.canvas = canvas
        self.horizontal = horizontal
        self._cursor = 0.0
        self._dragging = False
        if horizontal:
            self.setFixedHeight(RULER_THICKNESS)
        else:
            self.setFixedWidth(RULER_THICKNESS)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.SplitVCursor if horizontal else Qt.CursorShape.SplitHCursor)
        self.setToolTip("Drag into the canvas to create a guide")
        canvas.zoomChanged.connect(self.update)
        canvas.horizontalScrollBar().valueChanged.connect(self.update)
        canvas.verticalScrollBar().valueChanged.connect(self.update)
        canvas.cursorMoved.connect(self._on_cursor)

    def _on_cursor(self, x: float, y: float) -> None:
        self._cursor = x if self.horizontal else y
        self.update()

    def _to_view(self, scene_value: float) -> float:
        pt = self.canvas.mapFromScene(QPointF(scene_value, scene_value))
        return pt.x() if self.horizontal else pt.y()

    def paintEvent(self, ev) -> None:
        pal = current_palette()
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(pal.ruler))
        zoom = self.canvas.zoom
        length = self.width() if self.horizontal else self.height()
        origin = self._to_view(0.0)
        step = next((s for s in _STEPS if s * zoom >= 60), _STEPS[-1])
        minor = step / 5 if step >= 5 else step
        font = QFont()
        font.setPixelSize(9)
        p.setFont(font)
        first = math.floor((0 - origin) / zoom / minor) * minor
        v = first
        pen_minor = QPen(QColor(pal.muted), 1)
        while True:
            pos = origin + v * zoom
            if pos > length:
                break
            if pos >= -50:
                major = abs(v % step) < 1e-6
                p.setPen(QPen(QColor(pal.text), 1) if major else pen_minor)
                tick = RULER_THICKNESS if major else (7 if abs(v % (step / 2)) < 1e-6 else 4)
                if self.horizontal:
                    p.drawLine(QPointF(pos, RULER_THICKNESS - tick), QPointF(pos, RULER_THICKNESS))
                    if major:
                        p.setPen(QColor(pal.muted))
                        p.drawText(QRectF(pos + 2, 0, 50, 10), Qt.AlignmentFlag.AlignLeft, f"{v:g}")
                else:
                    p.drawLine(QPointF(RULER_THICKNESS - tick, pos), QPointF(RULER_THICKNESS, pos))
                    if major:
                        p.save()
                        p.translate(1, pos - 2)
                        p.rotate(-90)
                        p.setPen(QColor(pal.muted))
                        p.drawText(QRectF(0, 0, 50, 10), Qt.AlignmentFlag.AlignLeft, f"{v:g}")
                        p.restore()
            v += minor
        # cursor marker
        cp = self._to_view(self._cursor)
        p.setPen(QPen(QColor(pal.accent), 1))
        if self.horizontal:
            p.drawLine(QPointF(cp, 0), QPointF(cp, RULER_THICKNESS))
        else:
            p.drawLine(QPointF(0, cp), QPointF(RULER_THICKNESS, cp))
        p.setPen(QPen(QColor(pal.border), 1))
        if self.horizontal:
            p.drawLine(0, RULER_THICKNESS - 1, self.width(), RULER_THICKNESS - 1)
        else:
            p.drawLine(RULER_THICKNESS - 1, 0, RULER_THICKNESS - 1, self.height())
        p.end()

    # guide creation ---------------------------------------------------------------
    def _scene_pt(self, ev: QMouseEvent) -> QPointF:
        vp = self.canvas.viewport().mapFromGlobal(ev.globalPosition().toPoint())
        return self.canvas.mapToScene(vp)

    def mousePressEvent(self, ev: QMouseEvent) -> None:
        if ev.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            pt = self._scene_pt(ev)
            self.canvas.begin_ruler_drag(
                "h" if self.horizontal else "v", pt.y() if self.horizontal else pt.x()
            )

    def mouseMoveEvent(self, ev: QMouseEvent) -> None:
        if self._dragging:
            self.canvas.update_ruler_drag(self._scene_pt(ev))

    def mouseReleaseEvent(self, ev: QMouseEvent) -> None:
        if self._dragging:
            self._dragging = False
            self.canvas.end_ruler_drag(self._scene_pt(ev))
