"""Glyph icons rendered on demand (no binary resources) and tinted for the active theme."""

from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap

from py_vui.app.editor.editor_theme import current_palette


@lru_cache(maxsize=512)
def _pixmap(glyph: str, color: str, size: int, dpr: float) -> QPixmap:
    px = QPixmap(int(size * dpr), int(size * dpr))
    px.setDevicePixelRatio(dpr)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    font = QFont()
    font.setPixelSize(int(size * 0.72))
    p.setFont(font)
    p.setPen(QColor(color))
    p.drawText(QRectF(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, glyph)
    p.end()
    return px


def glyph_icon(glyph: str, *, size: int = 18, color: str | None = None) -> QIcon:
    """An icon drawn from a text glyph in ``color`` (defaults to the theme text colour)."""
    col = color or current_palette().text
    icon = QIcon()
    icon.addPixmap(_pixmap(glyph, col, size, 2.0), QIcon.Mode.Normal)
    icon.addPixmap(_pixmap(glyph, current_palette().muted, size, 2.0), QIcon.Mode.Disabled)
    return icon


def clear_icon_cache() -> None:
    _pixmap.cache_clear()
