"""Design-time painters for interactive controls (buttons, fields, toggles, sliders)."""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPen

from py_vui.app.editor.paint_common import (
    W,
    arrow,
    bevel,
    draw_text,
    is_dark,
    load_pixmap,
    mix,
    placeholder_image,
    qcolor,
    rrect,
)

AL = Qt.AlignmentFlag


def _justify(value: str) -> AL:
    return {"center": AL.AlignHCenter, "right": AL.AlignRight}.get(value, AL.AlignLeft)


# ----------------------------------------------------------------------------- surfaces
def field_surface(p: QPainter, w: W, rect: QRectF | None = None) -> QRectF:
    """Draw a text-field style box; returns the inner content rect."""
    r = rect or w.rect
    look = w.look
    bg = w.field_bg()
    border = w.border
    bw = max(1.0, w.border_width)
    if look.name == "tkinter":
        rrect(p, r, 0, bg, None)
        bevel(p, r, raised=False, width=2)
        return r.adjusted(4, 2, -4, -2)
    if look.name == "customtkinter":
        rrect(p, r, min(w.radius, r.height() / 2), bg, border, max(2.0, bw))
        return r.adjusted(8, 2, -8, -2)
    if look.name == "qt":
        rrect(p, r, 3, bg, mix(border, QColor("#000000"), 0.15), 1)
        return r.adjusted(6, 2, -6, -2)
    rrect(p, r, 0, bg, mix(border, QColor("#000000"), 0.1), 1)
    return r.adjusted(6, 2, -6, -2)


def button_face(p: QPainter, w: W, r: QRectF, color: QColor | None = None) -> None:
    look = w.look
    fill = color or w.bg
    if not w.node.enabled:
        fill = mix(fill, QColor("#999999"), 0.45)
    if look.name == "tkinter":
        rrect(p, r, 0, fill, None)
        bevel(p, r, raised=True, width=2)
    elif look.name == "customtkinter":
        rrect(
            p,
            r,
            min(w.radius, r.height() / 2),
            fill,
            qcolor(w.node.style.get("border_color")) if w.node.style.get("border_color") else None,
            max(1.0, w.border_width),
        )
    elif look.name == "qt":
        p.save()
        grad = QLinearGradient(r.topLeft(), r.bottomLeft())
        grad.setColorAt(0, mix(fill, QColor("#ffffff"), 0.18))
        grad.setColorAt(1, mix(fill, QColor("#000000"), 0.08))
        radius = min(4.0, w.radius or 4.0)
        p.setPen(QPen(mix(fill, QColor("#000000"), 0.35), 1))
        p.setBrush(QBrush(grad))
        p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)
        p.restore()
    else:
        rrect(p, r, 0, fill, None)
        p.fillRect(QRectF(r.left(), r.bottom() - 2, r.width(), 2), QColor(0, 0, 0, 60))


def _icon_and_text(
    p: QPainter, w: W, r: QRectF, text: str, image: str, compound: str = "left"
) -> None:
    px = load_pixmap(image, w.ctx.base_dir) if image else None
    isz = min(r.height() - 8, 20.0)
    font = w.font()
    color = w.fg if w.node.enabled else mix(w.fg, w.bg, 0.5)
    if image and text:
        icon_r = QRectF(r.left() + 8, r.center().y() - isz / 2, isz, isz)
        text_r = r.adjusted(isz + 12, 0, -4, 0)
        if compound == "right":
            icon_r.moveLeft(r.right() - isz - 8)
            text_r = r.adjusted(4, 0, -isz - 12, 0)
        _draw_icon(p, w, icon_r, px)
        draw_text(p, text_r, text, color, font)
    elif image:
        _draw_icon(p, w, QRectF(r.center().x() - isz / 2, r.center().y() - isz / 2, isz, isz), px)
    else:
        draw_text(p, r.adjusted(4, 0, -4, 0), text, color, font)


def _draw_icon(p: QPainter, w: W, r: QRectF, px) -> None:
    if px is not None:
        p.drawPixmap(r.toRect(), px)
    else:
        placeholder_image(p, r.adjusted(-6, -6, 6, 6), w.fg)


def paint_button(p: QPainter, w: W) -> None:
    r = w.rect
    button_face(p, w, r)
    if w.prop("default") and w.look.name != "kivy":
        p.save()
        p.setPen(QPen(w.fg, 1, Qt.PenStyle.DotLine))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(r.adjusted(4, 4, -4, -4))
        p.restore()
    _icon_and_text(
        p, w, r, str(w.prop("text", "")), str(w.prop("image", "")), str(w.prop("compound", "left"))
    )


def paint_tool_button(p: QPainter, w: W) -> None:
    r = w.rect
    checked = bool(w.prop("checkable"))
    face = mix(w.surface, w.border, 0.25)
    if w.look.name == "tkinter":
        rrect(p, r, 0, face, None)
        bevel(p, r, raised=not checked, width=1)
    else:
        rrect(p, r, min(5.0, w.radius or 4.0), face, w.border, 1)
    w.st["foreground"] = w.node.style.get("foreground") or w.theme.text
    _icon_and_text(p, w, r, str(w.prop("text", "")), str(w.prop("image", "")))
    if checked:
        arrow(p, r.right() - 8, r.bottom() - 7, 6, w.muted)


def paint_entry(p: QPainter, w: W) -> None:
    inner = field_surface(p, w)
    text = str(w.prop("text", ""))
    font = w.font()
    if text:
        if w.prop("show"):
            text = str(w.prop("show"))[:1] * len(text)
        draw_text(p, inner, text, w.field_fg(), font, _justify(str(w.prop("justify", "left"))))
    else:
        c = QColor(w.field_fg())
        c.setAlpha(110)
        draw_text(
            p,
            inner,
            str(w.prop("placeholder", "")),
            c,
            font,
            _justify(str(w.prop("justify", "left"))),
        )
    if w.prop("readonly"):
        p.fillRect(w.rect.adjusted(1, 1, -1, -1), QColor(128, 128, 128, 28))


def paint_text(p: QPainter, w: W) -> None:
    inner = field_surface(p, w)
    text = str(w.prop("text", "")) or str(w.prop("placeholder", ""))
    color = w.field_fg()
    if not w.prop("text", ""):
        color = QColor(color)
        color.setAlpha(110)
    wrap = str(w.prop("wrap", "word")) != "none"
    p.save()
    p.setClipRect(inner)
    draw_text(
        p,
        inner.adjusted(0, 3, 0, 0),
        text,
        color,
        w.font(),
        AL.AlignLeft | AL.AlignTop,
        wrap=wrap,
        elide=False,
    )
    p.restore()
    if w.prop("scrollbar", True):
        sb = QRectF(w.rect.right() - 11, w.rect.top() + 2, 9, w.rect.height() - 4)
        track = QColor(w.border)
        track.setAlpha(70)
        p.fillRect(sb, track)
        thumb = QColor(w.muted)
        thumb.setAlpha(150)
        p.fillRect(QRectF(sb.left() + 1, sb.top() + 2, 7, sb.height() * 0.4), thumb)


def _label_right(p: QPainter, w: W, x: float, text: str) -> None:
    draw_text(
        p,
        QRectF(x, 0, w.w - x, w.h),
        text,
        w.fg if w.node.enabled else w.muted,
        w.font(),
        AL.AlignLeft,
    )


def _checked_color(w: W) -> QColor:
    return w.primary if w.node.enabled else mix(w.primary, QColor("#999999"), 0.5)


def paint_checkbox(p: QPainter, w: W) -> None:
    s = min(16.0, w.h - 6)
    box = QRectF(2, (w.h - s) / 2, s, s)
    on = bool(w.prop("checked"))
    if w.look.name == "tkinter":
        rrect(p, box, 0, w.field_bg(), None)
        bevel(p, box, raised=False, width=1)
        mark = w.field_fg()
    elif w.look.name == "customtkinter":
        rrect(p, box, 3, _checked_color(w) if on else None, _checked_color(w), 2)
        mark = QColor("#ffffff")
    elif w.look.name == "qt":
        rrect(p, box, 3, w.field_bg(), mix(w.border, QColor("#000000"), 0.2), 1)
        mark = _checked_color(w)
    else:
        rrect(p, box, 0, _checked_color(w) if on else mix(w.surface, w.border, 0.5), None)
        mark = QColor("#ffffff")
    if on:
        p.save()
        p.setPen(
            QPen(mark, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        )
        p.drawPolyline(
            [
                QPointF(box.left() + s * 0.2, box.center().y()),
                QPointF(box.left() + s * 0.43, box.bottom() - s * 0.25),
                QPointF(box.right() - s * 0.2, box.top() + s * 0.25),
            ]
        )
        p.restore()
    _label_right(p, w, s + 10, str(w.prop("text", "")))


def paint_radio(p: QPainter, w: W) -> None:
    s = min(16.0, w.h - 6)
    box = QRectF(2, (w.h - s) / 2, s, s)
    on = bool(w.prop("checked"))
    p.save()
    ring = (
        _checked_color(w)
        if (on and w.look.name in ("customtkinter", "kivy"))
        else mix(w.border, QColor("#000000"), 0.25)
    )
    p.setPen(QPen(ring, 2 if w.look.name == "customtkinter" else 1))
    p.setBrush(w.field_bg() if w.look.name != "kivy" else mix(w.surface, w.border, 0.4))
    p.drawEllipse(box.adjusted(0.5, 0.5, -0.5, -0.5))
    if on:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_checked_color(w) if w.look.name != "tkinter" else w.field_fg())
        inset = s * (0.22 if w.look.name != "customtkinter" else 0.18)
        p.drawEllipse(box.adjusted(inset, inset, -inset, -inset))
    p.restore()
    _label_right(p, w, s + 10, str(w.prop("text", "")))


def paint_switch(p: QPainter, w: W) -> None:
    sw, sh = min(40.0, w.w * 0.4), min(20.0, w.h - 6)
    track = QRectF(2, (w.h - sh) / 2, sw, sh)
    on = bool(w.prop("checked"))
    off_c = mix(w.surface, w.border, 0.8)
    rrect(p, track, sh / 2 if w.look.pill_switch else 0, _checked_color(w) if on else off_c, None)
    p.save()
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#ffffff"))
    knob = sh - 6
    kx = track.right() - knob - 3 if on else track.left() + 3
    if w.look.pill_switch:
        p.drawEllipse(QRectF(kx, track.top() + 3, knob, knob))
    else:
        p.drawRect(QRectF(kx, track.top() + 3, knob, knob))
    p.restore()
    _label_right(p, w, sw + 10, str(w.prop("text", "")))


def paint_slider(p: QPainter, w: W) -> None:
    lo, hi = float(w.prop("minimum", 0)), float(w.prop("maximum", 100))
    frac = 0.0 if hi <= lo else max(0.0, min(1.0, (float(w.prop("value", 50)) - lo) / (hi - lo)))
    vertical = w.prop("orientation") == "vertical"
    thick = 4.0 if w.look.name != "tkinter" else 6.0
    if vertical:
        cx = w.w / 2
        track = QRectF(cx - thick / 2, 8, thick, w.h - 16)
        kpos = QPointF(cx, track.bottom() - frac * track.height())
        fill = QRectF(track.left(), kpos.y(), thick, track.bottom() - kpos.y())
    else:
        cy = w.h / 2
        track = QRectF(8, cy - thick / 2, w.w - 16 - (28 if w.prop("show_value") else 0), thick)
        kpos = QPointF(track.left() + frac * track.width(), cy)
        fill = QRectF(track.left(), track.top(), kpos.x() - track.left(), thick)
    rrect(
        p, track, thick / 2 if w.look.name != "tkinter" else 0, mix(w.surface, w.border, 0.8), None
    )
    if w.look.name != "tkinter":
        rrect(p, fill, thick / 2, _checked_color(w), None)
    else:
        bevel(p, track, raised=False, width=1)
    p.save()
    kr = 8.0
    if w.look.name == "tkinter":
        rect = (
            QRectF(kpos.x() - 6, kpos.y() - 10, 12, 20)
            if not vertical
            else QRectF(kpos.x() - 10, kpos.y() - 6, 20, 12)
        )
        p.fillRect(rect, mix(w.surface, w.border, 0.5))
        bevel(p, rect, raised=True, width=2)
    else:
        p.setPen(QPen(mix(w.primary, QColor("#000000"), 0.2), 1))
        p.setBrush(QColor("#ffffff") if w.look.name != "kivy" else w.primary)
        p.drawEllipse(kpos, kr, kr)
    p.restore()
    if w.prop("show_value") and not vertical:
        draw_text(
            p,
            QRectF(w.w - 30, 0, 28, w.h),
            f"{float(w.prop('value', 50)):g}",
            w.fg,
            w.font(0.85),
            AL.AlignRight,
        )


def paint_dial(p: QPainter, w: W) -> None:
    lo, hi = float(w.prop("minimum", 0)), float(w.prop("maximum", 100))
    frac = 0.0 if hi <= lo else max(0.0, min(1.0, (float(w.prop("value", 0)) - lo) / (hi - lo)))
    d = min(w.w, w.h) - 8
    r = QRectF((w.w - d) / 2, (w.h - d) / 2, d, d)
    p.save()
    p.setPen(QPen(mix(w.surface, w.border, 0.8), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.drawArc(r, 225 * 16, -270 * 16)
    p.setPen(QPen(_checked_color(w), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.drawArc(r, 225 * 16, int(-270 * frac * 16))
    ang = math.radians(225 - 270 * frac)
    c = r.center()
    p.setPen(QPen(w.fg, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.drawLine(c, QPointF(c.x() + math.cos(ang) * d * 0.32, c.y() - math.sin(ang) * d * 0.32))
    p.restore()


def paint_spinbox(p: QPainter, w: W) -> None:
    inner = field_surface(p, w)
    dec = int(w.prop("decimals", 0))
    txt = f"{float(w.prop('value', 0)):.{dec}f}"
    draw_text(p, inner.adjusted(0, 0, -16, 0), txt, w.field_fg(), w.font(), AL.AlignLeft)
    x = w.w - 12
    arrow(p, x, w.h / 2 - 5, 7, w.muted, "up")
    arrow(p, x, w.h / 2 + 5, 7, w.muted, "down")


def paint_combobox(p: QPainter, w: W) -> None:
    items = [str(i) for i in (w.prop("items", []) or [])]
    cur = int(w.prop("current", 0))
    if w.look.name == "tkinter":
        field_surface(p, w)
    elif w.look.name == "customtkinter":
        rrect(p, w.rect, min(w.radius, w.h / 2), mix(w.surface, w.border, 0.4), None)
    else:
        field_surface(p, w)
    text = items[cur] if 0 <= cur < len(items) else ""
    draw_text(p, w.rect.adjusted(8, 0, -22, 0), text, w.field_fg(), w.font(), AL.AlignLeft)
    arrow(p, w.w - 12, w.h / 2, 8, w.muted if w.look.name != "customtkinter" else w.fg)


def paint_segmented(p: QPainter, w: W) -> None:
    items = [str(i) for i in (w.prop("items", []) or [])] or [""]
    cur = int(w.prop("current", 0))
    seg = w.w / len(items)
    rrect(p, w.rect, min(w.radius, w.h / 2), mix(w.surface, w.border, 0.5), None)
    for i, it in enumerate(items):
        r = QRectF(i * seg, 0, seg, w.h)
        if i == cur:
            rrect(p, r.adjusted(2, 2, -2, -2), min(w.radius, w.h / 2), w.primary, None)
        color = QColor("#ffffff") if i == cur else w.fg
        if i == cur and not is_dark(w.primary):
            color = QColor("#111111")
        draw_text(p, r, it, color, w.font())


def paint_date_entry(p: QPainter, w: W) -> None:
    inner = field_surface(p, w)
    draw_text(
        p,
        inner.adjusted(0, 0, -22, 0),
        str(w.prop("date", "")),
        w.field_fg(),
        w.font(),
        AL.AlignLeft,
    )
    cal = QRectF(w.w - 22, w.h / 2 - 7, 14, 14)
    p.save()
    p.setPen(QPen(w.muted, 1.2))
    p.drawRect(cal)
    p.drawLine(QPointF(cal.left(), cal.top() + 4), QPointF(cal.right(), cal.top() + 4))
    p.restore()


def paint_time_entry(p: QPainter, w: W) -> None:
    inner = field_surface(p, w)
    t = str(w.prop("time", "12:00:00"))
    if not w.prop("show_seconds", True):
        t = t[:5]
    draw_text(p, inner.adjusted(0, 0, -16, 0), t, w.field_fg(), w.font(), AL.AlignLeft)
    x = w.w - 12
    arrow(p, x, w.h / 2 - 5, 7, w.muted, "up")
    arrow(p, x, w.h / 2 + 5, 7, w.muted, "down")


def paint_color_picker(p: QPainter, w: W) -> None:
    button_face(p, w, w.rect, mix(w.surface, w.border, 0.45))
    sw = QRectF(8, w.h / 2 - 7, 14, 14)
    rrect(p, sw, 3, qcolor(str(w.prop("color", "#ff0000"))), w.border, 1)
    draw_text(
        p, w.rect.adjusted(28, 0, -4, 0), str(w.prop("text", "")), w.fg, w.font(), AL.AlignLeft
    )
