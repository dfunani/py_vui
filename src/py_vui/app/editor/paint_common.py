"""Shared primitives for the design-time widget painter (fonts, colours, looks, surfaces)."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetricsF,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)

from py_vui.core.model import Node
from py_vui.core.theme import ProjectTheme, resolve_style, theme_for_preset

FONT_SCALE = 1.25


@dataclass(frozen=True)
class Look:
    """Per-framework rendering personality."""

    name: str
    #: 0 = square corners, 1 = use the style's corner radius, 0.5 = half
    radius: float
    bevel: bool  # classic 3D relief (tk)
    flat: bool  # no borders on buttons / fields (kivy, ctk buttons)
    field_border: bool = True
    soft_gradient: bool = False  # subtle top-light gradient (Fusion)
    pill_switch: bool = True


LOOKS: dict[str, Look] = {
    "tkinter": Look("tkinter", 0.0, True, False),
    "customtkinter": Look("customtkinter", 1.0, False, True, True),
    "pyside6": Look("qt", 0.35, False, False, True, True),
    "pyqt6": Look("qt", 0.35, False, False, True, True),
    "kivy": Look("kivy", 0.0, False, True, False, False, False),
}


@lru_cache(maxsize=1024)
def qcolor(value: str | None, fallback: str = "#888888") -> QColor:
    c = QColor(value or fallback)
    return c if c.isValid() else QColor(fallback)


def mix(a: QColor, b: QColor, t: float) -> QColor:
    return QColor(
        round(a.red() + (b.red() - a.red()) * t),
        round(a.green() + (b.green() - a.green()) * t),
        round(a.blue() + (b.blue() - a.blue()) * t),
    )


def is_dark(c: QColor) -> bool:
    return c.lightnessF() < 0.5


@lru_cache(maxsize=256)
def make_font(family: str, size: float, bold: bool, italic: bool, underline: bool) -> QFont:
    f = QFont(family)
    f.setPixelSize(max(6, round(size * FONT_SCALE)))
    f.setBold(bold)
    f.setItalic(italic)
    f.setUnderline(underline)
    return f


@lru_cache(maxsize=256)
def font_metrics(font: QFont) -> QFontMetricsF:
    return QFontMetricsF(font)


_PIXMAPS: dict[tuple[str, float], QPixmap | None] = {}


def load_pixmap(path: str, base_dir: Path | None) -> QPixmap | None:
    """Load an image asset (cached by path + mtime). Returns None when missing/unreadable."""
    if not path:
        return None
    p = Path(path)
    if not p.is_absolute() and base_dir is not None:
        p = base_dir / path
    try:
        key = (str(p), p.stat().st_mtime)
    except OSError:
        return None
    if key not in _PIXMAPS:
        if len(_PIXMAPS) > 128:
            _PIXMAPS.clear()
        px = QPixmap(str(p))
        _PIXMAPS[key] = None if px.isNull() else px
    return _PIXMAPS[key]


@dataclass
class PaintCtx:
    """Per-scene painting context (rebuilt when framework / theme / project dir change)."""

    framework: str
    theme: ProjectTheme
    base_dir: Path | None = None
    look: Look = field(init=False)
    eff_theme: ProjectTheme = field(init=False)

    def __post_init__(self) -> None:
        self.look = LOOKS.get(self.framework, LOOKS["tkinter"])
        t = self.theme
        if self.framework == "kivy" and t.appearance != "dark":
            dark = theme_for_preset("dark")
            t = dark.model_copy(
                update={
                    "primary": t.primary,
                    "primary_hover": t.primary_hover,
                    "font_family": t.font_family,
                    "font_size": t.font_size,
                }
            )
        self.eff_theme = t


class W:
    """Everything a painter needs about one widget, resolved once per paint."""

    def __init__(self, node: Node, ctx: PaintCtx, w: float, h: float) -> None:
        self.node = node
        self.ctx = ctx
        self.w = w
        self.h = h
        self.rect = QRectF(0, 0, w, h)
        self.st: dict[str, Any] = resolve_style(ctx.eff_theme, node.type, node.style)
        self.look = ctx.look
        self.theme = ctx.eff_theme
        self.props = node.props

    def prop(self, key: str, default: Any = None) -> Any:
        v = self.props.get(key, default)
        return default if v is None else v

    @property
    def bg(self) -> QColor:
        return qcolor(self.st["background"])

    @property
    def fg(self) -> QColor:
        return qcolor(self.st["foreground"])

    @property
    def border(self) -> QColor:
        return qcolor(self.st["border_color"])

    @property
    def primary(self) -> QColor:
        return qcolor(self.theme.primary)

    @property
    def surface(self) -> QColor:
        return qcolor(self.theme.surface)

    @property
    def muted(self) -> QColor:
        return qcolor(self.theme.muted_text)

    @property
    def radius(self) -> float:
        return float(self.st["corner_radius"]) * self.look.radius

    @property
    def border_width(self) -> float:
        return float(self.st["border_width"])

    def font(self, scale: float = 1.0, **over: bool) -> QFont:
        st = self.st
        return make_font(
            str(st["font_family"]),
            float(st["font_size"]) * scale,
            bool(over.get("bold", st["bold"])),
            bool(st["italic"]),
            bool(st["underline"]),
        )

    def field_bg(self) -> QColor:
        explicit = self.node.style.get("background")
        if explicit:
            return qcolor(explicit)
        if self.ctx.framework == "kivy":
            return QColor("#f2f2f2") if not is_dark(self.surface) else QColor("#2b2b2b")
        return self.surface

    def field_fg(self) -> QColor:
        explicit = self.node.style.get("foreground")
        if explicit:
            return qcolor(explicit)
        if self.ctx.framework == "kivy":
            return QColor("#111111") if not is_dark(self.surface) else QColor("#f0f0f0")
        return qcolor(self.theme.text)


# --------------------------------------------------------------------------- drawing helpers
def set_pen(p: QPainter, color: QColor | str, width: float = 1.0) -> None:
    pen = QPen(qcolor(color) if isinstance(color, str) else color, width)
    pen.setCosmetic(False)
    p.setPen(pen)


def rrect(
    p: QPainter,
    r: QRectF,
    radius: float,
    fill: QColor | None,
    line: QColor | None,
    width: float = 1.0,
) -> None:
    """Rounded rectangle with a crisp inset border."""
    p.save()
    if line is not None and width > 0:
        p.setPen(QPen(line, width))
        r = r.adjusted(width / 2, width / 2, -width / 2, -width / 2)
    else:
        p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(fill) if fill is not None else Qt.BrushStyle.NoBrush)
    radius = min(radius, r.height() / 2, r.width() / 2)
    if radius > 0.5:
        p.drawRoundedRect(r, radius, radius)
    else:
        p.drawRect(r)
    p.restore()


def bevel(p: QPainter, r: QRectF, raised: bool, width: float = 2.0) -> None:
    """Classic Tk 3-D border."""
    light, dark = QColor(255, 255, 255, 190), QColor(0, 0, 0, 110)
    if not raised:
        light, dark = dark, light
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    x0, y0, x1, y1 = r.left(), r.top(), r.right(), r.bottom()
    for i in range(int(width)):
        p.setPen(light)
        p.drawLine(QPointF(x0 + i, y0 + i), QPointF(x1 - i - 1, y0 + i))
        p.drawLine(QPointF(x0 + i, y0 + i), QPointF(x0 + i, y1 - i - 1))
        p.setPen(dark)
        p.drawLine(QPointF(x1 - i - 1, y0 + i), QPointF(x1 - i - 1, y1 - i - 1))
        p.drawLine(QPointF(x0 + i, y1 - i - 1), QPointF(x1 - i - 1, y1 - i - 1))
    p.restore()


def draw_text(
    p: QPainter,
    r: QRectF,
    text: str,
    color: QColor,
    font: QFont,
    align: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignCenter,
    *,
    wrap: bool = False,
    elide: bool = True,
) -> None:
    p.save()
    p.setFont(font)
    p.setPen(color)
    flags = (
        align | Qt.AlignmentFlag.AlignVCenter
        if not (align & Qt.AlignmentFlag.AlignVertical_Mask)
        else align
    )
    if wrap:
        p.drawText(r, int(flags | Qt.TextFlag.TextWordWrap), text)
    else:
        if elide:
            text = font_metrics(font).elidedText(
                text, Qt.TextElideMode.ElideRight, max(1.0, r.width())
            )
        p.drawText(r, int(flags), text)
    p.restore()


def arrow(
    p: QPainter, cx: float, cy: float, size: float, color: QColor, direction: str = "down"
) -> None:
    s = size / 2
    path = QPainterPath()
    if direction == "down":
        path.moveTo(cx - s, cy - s / 2)
        path.lineTo(cx + s, cy - s / 2)
        path.lineTo(cx, cy + s / 2)
    elif direction == "up":
        path.moveTo(cx - s, cy + s / 2)
        path.lineTo(cx + s, cy + s / 2)
        path.lineTo(cx, cy - s / 2)
    elif direction == "right":
        path.moveTo(cx - s / 2, cy - s)
        path.lineTo(cx - s / 2, cy + s)
        path.lineTo(cx + s / 2, cy)
    path.closeSubpath()
    p.save()
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(color)
    p.drawPath(path)
    p.restore()


def hatch(p: QPainter, r: QRectF, color: QColor) -> None:
    """Warning hatch used for widgets the active framework cannot render."""
    p.save()
    p.setClipRect(r)
    brush = QBrush(color, Qt.BrushStyle.BDiagPattern)
    p.fillRect(r, brush)
    p.restore()


def placeholder_image(p: QPainter, r: QRectF, color: QColor) -> None:
    """Schematic landscape picture glyph."""
    p.save()
    p.setPen(QPen(color, 1.5))
    p.setBrush(Qt.BrushStyle.NoBrush)
    s = min(r.width(), r.height()) * 0.5
    box = QRectF(r.center().x() - s / 2, r.center().y() - s / 2, s, s * 0.8)
    p.drawRect(box)
    p.drawEllipse(QPointF(box.left() + s * 0.28, box.top() + s * 0.24), s * 0.08, s * 0.08)
    path = QPainterPath(QPointF(box.left(), box.bottom()))
    path.lineTo(box.left() + s * 0.35, box.top() + s * 0.42)
    path.lineTo(box.left() + s * 0.6, box.bottom() - s * 0.2)
    path.lineTo(box.left() + s * 0.75, box.bottom() - s * 0.32)
    path.lineTo(box.right(), box.bottom())
    p.drawPath(path)
    p.restore()


def scrollbar(p: QPainter, r: QRectF, vertical: bool, frac: float, w: W) -> None:
    track = QColor(w.border)
    track.setAlpha(60)
    thumb = QColor(w.muted)
    thumb.setAlpha(170)
    p.save()
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(track)
    p.drawRect(r)
    p.setBrush(thumb)
    if vertical:
        th = max(14.0, r.height() * frac)
        p.drawRoundedRect(QRectF(r.left() + 2, r.top() + 2, r.width() - 4, th - 4), 3, 3)
    else:
        tw = max(14.0, r.width() * frac)
        p.drawRoundedRect(QRectF(r.left() + 2, r.top() + 2, tw - 4, r.height() - 4), 3, 3)
    p.restore()
