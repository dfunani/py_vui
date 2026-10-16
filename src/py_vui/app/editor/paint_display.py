"""Design-time painters for containers and display widgets."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen

from py_vui.app.editor.canvas_geometry import GROUP_TITLE_H, TAB_HEADER_H, current_page, tab_rects
from py_vui.app.editor.paint_common import (
    W,
    bevel,
    draw_text,
    load_pixmap,
    mix,
    placeholder_image,
    qcolor,
    rrect,
    scrollbar,
)

AL = Qt.AlignmentFlag


# ------------------------------------------------------------------------------ containers
def paint_window(p: QPainter, w: W) -> None:
    p.fillRect(w.rect, w.bg)


def _design_outline(p: QPainter, w: W) -> None:
    """Faint dashed edge so empty containers stay discoverable on the design surface."""
    p.save()
    c = mix(w.border, w.muted, 0.4)
    c.setAlpha(150)
    p.setPen(QPen(c, 1, Qt.PenStyle.DashLine))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRect(w.rect.adjusted(0.5, 0.5, -0.5, -0.5))
    p.restore()


def paint_frame(p: QPainter, w: W) -> None:
    _paint_frame_body(p, w)
    if w.node.style.get("border_width") in (None, -1):
        _design_outline(p, w)


def _paint_frame_body(p: QPainter, w: W) -> None:
    look = w.look
    explicit_border = w.node.style.get("border_width") not in (None, -1)
    if look.name == "tkinter":
        rrect(p, w.rect, 0, w.bg, None)
        relief = w.st.get("relief") or "flat"
        if relief in ("raised", "sunken", "groove", "ridge"):
            bevel(p, w.rect, relief in ("raised", "ridge"), 2)
        elif relief == "solid" or explicit_border:
            rrect(p, w.rect, 0, None, w.border, max(1.0, w.border_width))
        else:
            p.save()
            p.setPen(QPen(mix(w.bg, w.border, 0.35), 1, Qt.PenStyle.DotLine))
            p.drawRect(w.rect.adjusted(0.5, 0.5, -0.5, -0.5))
            p.restore()
    elif look.name == "customtkinter":
        rrect(
            p,
            w.rect,
            w.radius,
            mix(w.bg, w.border, 0.12),
            w.border if explicit_border else None,
            max(1.0, w.border_width),
        )
    elif look.name == "qt":
        rrect(p, w.rect, 0, w.bg, mix(w.border, QColor("#000000"), 0.05), 1)
    else:
        rrect(p, w.rect, 0, mix(w.bg, QColor("#000000"), 0.12), None)


def paint_label_frame(p: QPainter, w: W) -> None:
    r = w.rect.adjusted(0, GROUP_TITLE_H / 2, 0, 0)
    fill = w.bg if w.look.name != "customtkinter" else mix(w.bg, w.border, 0.1)
    if w.look.name == "tkinter":
        rrect(p, r, 0, fill, None)
        bevel(p, r, raised=False, width=1)
    else:
        rrect(p, r, 4 if w.look.name == "qt" else w.radius, fill, w.border, 1)
    title = str(w.prop("title", ""))
    if title:
        font = w.font()
        tw = min(w.w - 20, font_width(font, title) + 10)
        align = str(w.prop("title_align", "left"))
        x = {"left": 10.0, "center": (w.w - tw) / 2, "right": w.w - tw - 10}.get(align, 10.0)
        tr = QRectF(x, 0, tw, GROUP_TITLE_H)
        p.fillRect(QRectF(tr.left(), tr.top() + GROUP_TITLE_H / 2 - 1, tr.width(), 3), fill)
        draw_text(p, tr, title, w.fg, font)


def font_width(font, text: str) -> float:
    from py_vui.app.editor.paint_common import font_metrics

    return font_metrics(font).horizontalAdvance(text)


def paint_tabview(p: QPainter, w: W) -> None:
    node = w.node
    cur = current_page(node)
    page = QRectF(0, TAB_HEADER_H - 1, w.w, w.h - TAB_HEADER_H + 1)
    fill = w.bg if w.look.name != "customtkinter" else mix(w.bg, w.border, 0.1)
    if w.look.name == "customtkinter":
        rrect(p, page, w.radius, fill, None)
    elif w.look.name == "tkinter":
        rrect(p, page, 0, fill, None)
        bevel(p, page, raised=True, width=1)
    else:
        rrect(p, page, 0 if w.look.name == "kivy" else 3, fill, w.border, 1)
    for i, (x, y, tw, th) in enumerate(tab_rects(node)):
        r = QRectF(x, y, tw, th)
        sel = i == cur
        if w.look.name == "customtkinter":
            rrect(
                p,
                r.adjusted(2, 2, -2, -2),
                min(w.radius, 14),
                w.primary if sel else mix(w.surface, w.border, 0.5),
                None,
            )
            color = QColor("#ffffff") if sel else w.fg
        elif w.look.name == "tkinter":
            r = r.adjusted(0, 0 if sel else 3, 0, 0)
            rrect(p, r, 0, w.bg if sel else mix(w.bg, QColor("#000000"), 0.1), None)
            bevel(p, r, raised=True, width=1)
            color = w.fg
        else:
            rrect(
                p,
                r.adjusted(1, 2, -1, 0),
                0 if w.look.name == "kivy" else 4,
                w.bg if sel else mix(w.bg, QColor("#000000"), 0.12),
                w.border,
                1,
            )
            if sel and w.look.name == "kivy":
                p.fillRect(QRectF(r.left() + 1, r.bottom() - 3, r.width() - 2, 3), w.primary)
            color = w.fg
        tabs = w.prop("tabs", []) or []
        draw_text(p, r, str(tabs[i]), color, w.font(), AL.AlignHCenter)


def paint_scroll_frame(p: QPainter, w: W) -> None:
    paint_frame(p, w)
    orient = str(w.prop("orientation", "vertical"))
    sb = 12.0
    if orient in ("vertical", "both"):
        scrollbar(
            p, QRectF(w.w - sb - 1, 1, sb, w.h - 2 - (sb if orient == "both" else 0)), True, 0.45, w
        )
    if orient in ("horizontal", "both"):
        scrollbar(
            p,
            QRectF(1, w.h - sb - 1, w.w - 2 - (sb if orient == "both" else 0), sb),
            False,
            0.55,
            w,
        )


def paint_paned(p: QPainter, w: W) -> None:
    paint_frame(p, w)
    horizontal = str(w.prop("orientation", "horizontal")) == "horizontal"
    sizes = [float(s) for s in (w.prop("sizes", []) or []) if str(s).replace(".", "").isdigit()]
    total = w.w if horizontal else w.h
    cuts = []
    acc = 0.0
    for s in sizes[:-1]:
        acc += s
        cuts.append(acc)
    if not cuts:
        cuts = [total / 2]
    p.save()
    p.setPen(QPen(mix(w.border, w.muted, 0.4), 1))
    for c in cuts:
        if horizontal:
            p.fillRect(QRectF(c - 2, 0, 4, w.h), mix(w.bg, w.border, 0.5))
            for k in (-6, 0, 6):
                p.drawPoint(QPointF(c, w.h / 2 + k))
        else:
            p.fillRect(QRectF(0, c - 2, w.w, 4), mix(w.bg, w.border, 0.5))
            for k in (-6, 0, 6):
                p.drawPoint(QPointF(w.w / 2 + k, c))
    p.restore()


# ---------------------------------------------------------------------------------- display
def paint_label(p: QPainter, w: W) -> None:
    text = str(w.prop("text", ""))
    anchor = str(w.prop("anchor", "w"))
    just = str(w.prop("justify", "left"))
    explicit_bg = w.node.style.get("background")
    if explicit_bg:
        p.fillRect(w.rect, qcolor(explicit_bg))
    r = w.rect
    px = load_pixmap(str(w.prop("image", "")), w.ctx.base_dir) if w.prop("image") else None
    if w.prop("image"):
        isz = min(w.h - 4, 24.0)
        ir = QRectF(2, (w.h - isz) / 2, isz, isz)
        if px is not None:
            p.drawPixmap(ir.toRect(), px)
        else:
            placeholder_image(p, ir.adjusted(-4, -4, 4, 4), w.muted)
        r = r.adjusted(isz + 6, 0, 0, 0)
    flag = {"w": AL.AlignLeft, "e": AL.AlignRight}.get(anchor, AL.AlignHCenter)
    if just == "center" or just == "right":
        flag = AL.AlignHCenter if just == "center" else AL.AlignRight
    color = w.fg if w.node.enabled else w.muted
    wrap = int(w.prop("wrap_length", 0)) > 0
    draw_text(
        p, r, text, color, w.font(), flag | (AL.AlignTop if wrap else AL.AlignVCenter), wrap=wrap
    )


def paint_image(p: QPainter, w: W) -> None:
    px = load_pixmap(str(w.prop("source", "")), w.ctx.base_dir)
    fit = str(w.prop("fit", "contain"))
    if px is not None:
        if fit == "stretch":
            p.drawPixmap(w.rect.toRect(), px)
        elif fit == "none":
            p.save()
            p.setClipRect(w.rect)
            p.drawPixmap(0, 0, px)
            p.restore()
        else:
            scaled = px.size().scaled(int(w.w), int(w.h), Qt.AspectRatioMode.KeepAspectRatio)
            x, y = (w.w - scaled.width()) / 2, (w.h - scaled.height()) / 2
            p.drawPixmap(QRectF(x, y, scaled.width(), scaled.height()).toRect(), px)
        return
    rrect(p, w.rect, 0, mix(w.surface, w.border, 0.25), w.border, 1)
    placeholder_image(p, w.rect, w.muted)
    alt = str(w.prop("alt_text", ""))
    if alt:
        draw_text(p, QRectF(0, w.h - 22, w.w, 20), alt, w.muted, w.font(0.85))


def paint_separator(p: QPainter, w: W) -> None:
    color = w.border if not w.node.style.get("background") else qcolor(w.node.style["background"])
    if str(w.prop("orientation", "horizontal")) == "horizontal":
        y = w.h / 2
        p.fillRect(QRectF(0, y - 0.5, w.w, 1), color)
    else:
        p.fillRect(QRectF(w.w / 2 - 0.5, 0, 1, w.h), color)


def paint_progress(p: QPainter, w: W) -> None:
    mx = max(1.0, float(w.prop("maximum", 100)))
    frac = max(0.0, min(1.0, float(w.prop("value", 0)) / mx))
    vertical = str(w.prop("orientation", "horizontal")) == "vertical"
    r = w.rect
    track = mix(w.surface, w.border, 0.8)
    radius = r.height() / 2 if not vertical else r.width() / 2
    if w.look.name in ("tkinter", "kivy"):
        radius = 0
    rrect(p, r, radius, track, None)
    indeterminate = str(w.prop("mode", "determinate")) == "indeterminate"
    if indeterminate:
        frac = 0.3
    if vertical:
        fill = QRectF(0, r.height() * (1 - frac), r.width(), r.height() * frac)
    else:
        start = r.width() * 0.35 if indeterminate else 0
        fill = QRectF(start, 0, r.width() * frac, r.height())
    rrect(p, fill, radius, w.primary, None)
    if w.look.name == "tkinter":
        bevel(p, r, raised=False, width=1)
    if w.prop("show_text") and not indeterminate:
        draw_text(
            p, r, f"{round(frac * 100)}%", w.fg if frac < 0.5 else QColor("#ffffff"), w.font(0.85)
        )


def paint_canvas(p: QPainter, w: W) -> None:
    bg = qcolor(w.node.style.get("background") or "#ffffff")
    rrect(p, w.rect, 0, bg, w.border, 1)
    p.save()
    p.setPen(QPen(mix(bg, QColor("#888888"), 0.35), 1, Qt.PenStyle.DotLine))
    p.drawLine(QPointF(0, w.h / 2), QPointF(w.w, w.h / 2))
    p.drawLine(QPointF(w.w / 2, 0), QPointF(w.w / 2, w.h))
    p.setPen(QPen(w.muted, 1.5))
    p.drawEllipse(QPointF(w.w * 0.5, w.h * 0.5), min(w.w, w.h) * 0.2, min(w.w, w.h) * 0.2)
    p.restore()
    draw_text(p, QRectF(6, 4, w.w - 12, 18), "Canvas", w.muted, w.font(0.8), AL.AlignLeft)
