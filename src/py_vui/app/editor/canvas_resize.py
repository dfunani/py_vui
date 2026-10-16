"""Resize-handle geometry (pure helpers + Qt cursors)."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt

HANDLES = ("nw", "n", "ne", "e", "se", "s", "sw", "w")
HANDLE_PX = 8.0  # on-screen size of a handle
HIT_PX = 7.0  # on-screen pick radius

_CURSORS = {
    "nw": Qt.CursorShape.SizeFDiagCursor,
    "se": Qt.CursorShape.SizeFDiagCursor,
    "ne": Qt.CursorShape.SizeBDiagCursor,
    "sw": Qt.CursorShape.SizeBDiagCursor,
    "n": Qt.CursorShape.SizeVerCursor,
    "s": Qt.CursorShape.SizeVerCursor,
    "e": Qt.CursorShape.SizeHorCursor,
    "w": Qt.CursorShape.SizeHorCursor,
}


def cursor_for(handle: str) -> Qt.CursorShape:
    return _CURSORS[handle]


def handle_points(rect: QRectF) -> dict[str, QPointF]:
    cx, cy = rect.center().x(), rect.center().y()
    return {
        "nw": rect.topLeft(),
        "n": QPointF(cx, rect.top()),
        "ne": rect.topRight(),
        "e": QPointF(rect.right(), cy),
        "se": rect.bottomRight(),
        "s": QPointF(cx, rect.bottom()),
        "sw": rect.bottomLeft(),
        "w": QPointF(rect.left(), cy),
    }


def hit_handle(rect: QRectF, pt: QPointF, scale: float) -> str | None:
    """Return the handle under ``pt`` (scene coords), preferring corners over edges."""
    tol = HIT_PX / scale
    pts = handle_points(rect)
    # small boxes: only corners are offered so edges never overlap the move area
    names = HANDLES if min(rect.width(), rect.height()) * scale > 36 else ("nw", "ne", "se", "sw")
    best: tuple[float, str] | None = None
    for name in names:
        q = pts[name]
        d = max(abs(q.x() - pt.x()), abs(q.y() - pt.y()))
        if d <= tol and (best is None or d < best[0]):
            best = (d, name)
    return best[1] if best else None


def resize_rect(
    handle: str,
    start: QRectF,
    dx: float,
    dy: float,
    min_w: float = 8.0,
    min_h: float = 8.0,
    keep_aspect: bool = False,
) -> QRectF:
    x0, y0, x1, y1 = start.left(), start.top(), start.right(), start.bottom()
    if "w" in handle:
        x0 = min(x0 + dx, x1 - min_w)
    if "e" in handle:
        x1 = max(x1 + dx, x0 + min_w)
    if "n" in handle:
        y0 = min(y0 + dy, y1 - min_h)
    if "s" in handle:
        y1 = max(y1 + dy, y0 + min_h)
    rect = QRectF(QPointF(x0, y0), QPointF(x1, y1))
    if keep_aspect and start.height() > 0 and len(handle) == 2:
        ratio = start.width() / start.height()
        w = max(rect.width(), rect.height() * ratio)
        h = w / ratio
        if "w" in handle:
            rect.setLeft(x1 - w)
        else:
            rect.setRight(x0 + w)
        if "n" in handle:
            rect.setTop(y1 - h)
        else:
            rect.setBottom(y0 + h)
    return rect
