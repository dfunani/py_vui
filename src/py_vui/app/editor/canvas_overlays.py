"""Overlay painting for the design canvas (drawn in scene coordinates, constant pixel size)."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPen

from py_vui.app.editor.canvas_resize import HANDLE_PX, handle_points
from py_vui.app.editor.editor_theme import EditorPalette
from py_vui.app.editor.snap import GuideLine


def _pen(
    color: QColor | str, width: float = 1.0, style: Qt.PenStyle = Qt.PenStyle.SolidLine
) -> QPen:
    pen = QPen(QColor(color), width, style)
    pen.setCosmetic(True)
    return pen


def draw_dot_grid(p: QPainter, rect: QRectF, grid: float, scale: float, pal: EditorPalette) -> None:
    """Dots on the window area (skipped when they would be denser than ~5 screen px)."""
    if grid * scale < 5:
        return
    step = grid
    while step * scale < 8:
        step *= 2
    p.save()
    p.setPen(
        _pen(QColor(pal.canvas_dot).lighter(120) if pal.name == "dark" else pal.canvas_dot, 1.4)
    )
    pts = []
    x = 0.0
    while x <= rect.width():
        y = 0.0
        while y <= rect.height():
            pts.append(QPointF(rect.left() + x, rect.top() + y))
            y += step
        x += step
    if len(pts) < 40000:
        p.drawPoints(pts)
    p.restore()


def draw_selection(p: QPainter, rects: list[tuple[QRectF, bool, bool]], pal: EditorPalette) -> None:
    """Outline each selected rect. Tuples are (rect, is_primary, is_locked)."""
    p.save()
    for rect, primary, locked in rects:
        color = QColor("#f59e0b") if locked else QColor(pal.selection)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(
            _pen(
                color,
                1.5 if primary else 1.0,
                Qt.PenStyle.SolidLine if primary else Qt.PenStyle.DashLine,
            )
        )
        p.drawRect(rect)
    p.restore()


def draw_hover(p: QPainter, rect: QRectF, pal: EditorPalette) -> None:
    p.save()
    c = QColor(pal.selection)
    c.setAlpha(120)
    p.setPen(_pen(c, 1.0))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRect(rect)
    p.restore()


def draw_handles(p: QPainter, rect: QRectF, scale: float, pal: EditorPalette, names=None) -> None:
    size = HANDLE_PX / scale
    p.save()
    p.setPen(_pen(pal.selection, 1.0))
    p.setBrush(QBrush(QColor("#ffffff")))
    pts = handle_points(rect)
    small = min(rect.width(), rect.height()) * scale <= 36
    for name, pt in pts.items():
        if names is not None and name not in names:
            continue
        if small and len(name) == 1:
            continue
        p.drawRect(QRectF(pt.x() - size / 2, pt.y() - size / 2, size, size))
    p.restore()


def draw_window_grip(
    p: QPainter, rect: QRectF, scale: float, pal: EditorPalette, hot: bool
) -> None:
    """Corner grip used to resize the window itself."""
    s = 12.0 / scale
    p.save()
    p.setPen(_pen(pal.accent if hot else pal.muted, 1.5))
    for i in range(1, 4):
        k = i * s / 3.5
        p.drawLine(
            QPointF(rect.right() + 2 / scale - k, rect.bottom() + 2 / scale),
            QPointF(rect.right() + 2 / scale, rect.bottom() + 2 / scale - k),
        )
    p.restore()


def draw_snap_lines(p: QPainter, lines: list[GuideLine], pal: EditorPalette) -> None:
    p.save()
    for ln in lines:
        color = QColor(pal.guide if ln.kind == "guide" else pal.smart)
        p.setPen(
            _pen(color, 1.0, Qt.PenStyle.SolidLine if ln.kind != "bounds" else Qt.PenStyle.DashLine)
        )
        if ln.orient == "v":
            p.drawLine(QPointF(ln.pos, ln.a), QPointF(ln.pos, ln.b))
        else:
            p.drawLine(QPointF(ln.a, ln.pos), QPointF(ln.b, ln.pos))
    p.restore()


def draw_user_guides(
    p: QPainter,
    vguides: list[float],
    hguides: list[float],
    rect: QRectF,
    pal: EditorPalette,
    hot: tuple[str, int] | None = None,
) -> None:
    p.save()
    ext = 4000.0
    for i, x in enumerate(vguides):
        p.setPen(_pen(pal.guide, 2.0 if hot == ("v", i) else 1.0, Qt.PenStyle.DashLine))
        p.drawLine(
            QPointF(rect.left() + x, rect.top() - ext),
            QPointF(rect.left() + x, rect.bottom() + ext),
        )
    for i, y in enumerate(hguides):
        p.setPen(_pen(pal.guide, 2.0 if hot == ("h", i) else 1.0, Qt.PenStyle.DashLine))
        p.drawLine(
            QPointF(rect.left() - ext, rect.top() + y), QPointF(rect.right() + ext, rect.top() + y)
        )
    p.restore()


def draw_drop_target(p: QPainter, rect: QRectF, pal: EditorPalette) -> None:
    """Highlight the container that will receive the dragged widget."""
    p.save()
    c = QColor(pal.accent)
    p.setPen(_pen(c, 2.0))
    c.setAlpha(30)
    p.setBrush(c)
    p.drawRect(rect)
    p.restore()


def draw_insertion(p: QPainter, a: QPointF, b: QPointF, scale: float, pal: EditorPalette) -> None:
    p.save()
    p.setPen(_pen(pal.accent, 3.0))
    p.drawLine(a, b)
    r = 3.5 / scale
    p.setBrush(QColor(pal.accent))
    p.drawEllipse(a, r, r)
    p.drawEllipse(b, r, r)
    p.restore()


def draw_grid_tracks(
    p: QPainter,
    origin: QPointF,
    xs: list[float],
    ys: list[float],
    col_w: list[float],
    row_h: list[float],
    pal: EditorPalette,
) -> None:
    """Dashed track lines of a grid container (``origin`` = container content origin, scene)."""
    p.save()
    c = QColor(pal.accent)
    c.setAlpha(140)
    p.setPen(_pen(c, 1.0, Qt.PenStyle.DashLine))
    top, bottom = ys[0], ys[-1] + row_h[-1]
    left, right = xs[0], xs[-1] + col_w[-1]
    for x, w in zip(xs, col_w, strict=False):
        p.drawLine(
            QPointF(origin.x() + x, origin.y() + top), QPointF(origin.x() + x, origin.y() + bottom)
        )
        p.drawLine(
            QPointF(origin.x() + x + w, origin.y() + top),
            QPointF(origin.x() + x + w, origin.y() + bottom),
        )
    for y, h in zip(ys, row_h, strict=False):
        p.drawLine(
            QPointF(origin.x() + left, origin.y() + y), QPointF(origin.x() + right, origin.y() + y)
        )
        p.drawLine(
            QPointF(origin.x() + left, origin.y() + y + h),
            QPointF(origin.x() + right, origin.y() + y + h),
        )
    p.restore()


def draw_cell_highlight(p: QPainter, rect: QRectF, pal: EditorPalette) -> None:
    p.save()
    c = QColor(pal.accent)
    p.setPen(_pen(c, 2.0))
    c.setAlpha(60)
    p.setBrush(c)
    p.drawRect(rect)
    p.restore()


def draw_rubber_band(p: QPainter, rect: QRectF, pal: EditorPalette) -> None:
    p.save()
    c = QColor(pal.selection)
    p.setPen(_pen(c, 1.0))
    c.setAlpha(40)
    p.setBrush(c)
    p.drawRect(rect)
    p.restore()
