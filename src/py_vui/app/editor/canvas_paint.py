"""Design-time rendering of every registry widget type, adapted to the project framework."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF

from py_vui.app.editor import paint_controls as C
from py_vui.app.editor import paint_data as D
from py_vui.app.editor import paint_display as S
from py_vui.app.editor.canvas_geometry import MENUBAR_H, TITLEBAR_H
from py_vui.app.editor.paint_common import (
    PaintCtx,
    W,
    draw_text,
    font_metrics,
    hatch,
    make_font,
    mix,
    qcolor,
)
from py_vui.core.model import Node
from py_vui.core.registry import get_spec, has_spec

Painter = Callable[[QPainter, W], None]

PAINTERS: dict[str, Painter] = {
    "window": S.paint_window,
    "toplevel": S.paint_window,
    "frame": S.paint_frame,
    "label_frame": S.paint_label_frame,
    "tabview": S.paint_tabview,
    "scroll_frame": S.paint_scroll_frame,
    "paned_window": S.paint_paned,
    "label": S.paint_label,
    "image": S.paint_image,
    "separator": S.paint_separator,
    "progressbar": S.paint_progress,
    "canvas": S.paint_canvas,
    "button": C.paint_button,
    "tool_button": C.paint_tool_button,
    "entry": C.paint_entry,
    "text": C.paint_text,
    "checkbox": C.paint_checkbox,
    "radio": C.paint_radio,
    "switch": C.paint_switch,
    "slider": C.paint_slider,
    "dial": C.paint_dial,
    "spinbox": C.paint_spinbox,
    "combobox": C.paint_combobox,
    "listbox": D.paint_listbox,
    "segmented_button": C.paint_segmented,
    "date_entry": C.paint_date_entry,
    "time_entry": C.paint_time_entry,
    "table": D.paint_table,
    "tree_view": D.paint_tree,
    "calendar": D.paint_calendar,
    "time_picker": D.paint_time_picker,
    "map_view": D.paint_map,
    "chart": D.paint_chart,
    "video_player": D.paint_video,
    "pandas_table": D.paint_pandas_table,
    "color_picker": C.paint_color_picker,
}


def paint_generic(p: QPainter, w: W) -> None:
    """Fallback for plugin widgets without a dedicated painter."""
    spec = get_spec(w.node.type) if has_spec(w.node.type) else None
    S.rrect(p, w.rect, 4, mix(w.surface, w.border, 0.2), w.border, 1)
    draw_text(
        p,
        w.rect,
        f"{spec.icon if spec else '?'}  {spec.label if spec else w.node.type}",
        w.fg,
        w.font(),
    )


def paint_widget(p: QPainter, node: Node, ctx: PaintCtx, w: float, h: float) -> None:
    """Paint ``node`` into the rectangle (0, 0, w, h) of ``p``."""
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    bundle = W(node, ctx, w, h)
    PAINTERS.get(node.type, paint_generic)(p, bundle)
    if has_spec(node.type) and not get_spec(node.type).supports(ctx.framework):
        paint_unsupported(p, bundle)


def paint_unsupported(p: QPainter, w: W) -> None:
    amber = QColor("#f59e0b")
    amber.setAlpha(70)
    hatch(p, w.rect, amber)
    p.save()
    p.setPen(QPen(QColor("#d97706"), 1.2, Qt.PenStyle.DashLine))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRect(w.rect.adjusted(0.5, 0.5, -0.5, -0.5))
    s = min(16.0, w.w - 4, w.h - 4)
    if s >= 8:
        x, y = w.w - s - 2, 2.0
        p.setPen(QPen(QColor("#92400e"), 1))
        p.setBrush(QColor("#fbbf24"))
        p.drawPolygon(QPolygonF([QPointF(x + s / 2, y), QPointF(x + s, y + s), QPointF(x, y + s)]))
        p.setPen(QPen(QColor("#92400e"), 1.4))
        p.drawLine(QPointF(x + s / 2, y + s * 0.38), QPointF(x + s / 2, y + s * 0.7))
        p.drawPoint(QPointF(x + s / 2, y + s * 0.86))
    p.restore()


def paint_locked_badge(p: QPainter, w: float) -> None:
    """Small padlock in the top-right corner of locked widgets."""
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    x, y = max(0.0, w - 13), 2.0
    p.setPen(QPen(QColor("#111827"), 1))
    p.setBrush(QColor("#fbbf24"))
    p.drawRoundedRect(QRectF(x, y + 5, 10, 7), 1.5, 1.5)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawArc(QRectF(x + 2, y, 6, 8), 0, 180 * 16)
    p.restore()


# ------------------------------------------------------------------------------- window chrome
def window_chrome_height(node: Node) -> float:
    menus = node.props.get("menus") if node.type == "window" else None
    return TITLEBAR_H + (MENUBAR_H if menus else 0.0)


def paint_window_chrome(p: QPainter, node: Node, ctx: PaintCtx, width: float) -> None:
    """Title bar (+ menu bar) drawn *above* the client area (negative y)."""
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    menus = node.props.get("menus") if node.type == "window" else None
    top = -window_chrome_height(node)
    dark = ctx.eff_theme.appearance == "dark"
    bar = QColor("#2b2d36") if dark else QColor("#e9eaee")
    fg = QColor("#d5d7e0") if dark else QColor("#2a2c35")
    p.fillRect(QRectF(0, top, width, TITLEBAR_H), bar)
    for i, c in enumerate(("#ef4444", "#f59e0b", "#22c55e")):
        p.setBrush(QColor(c))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(14 + i * 18, top + TITLEBAR_H / 2), 5.5, 5.5)
    title = str(node.props.get("title", node.name))
    font = make_font(ctx.theme.font_family, 11, False, False, False)
    draw_text(p, QRectF(70, top, max(10.0, width - 90), TITLEBAR_H), title, fg, font)
    if menus:
        mb = QRectF(0, top + TITLEBAR_H, width, MENUBAR_H)
        p.fillRect(mb, mix(bar, QColor("#ffffff") if dark else QColor("#000000"), 0.04))
        x = 8.0
        fm = font_metrics(font)
        for m in menus:
            t = str(m.get("title", "")) if isinstance(m, dict) else ""
            tw = fm.horizontalAdvance(t) + 16
            draw_text(p, QRectF(x, mb.top(), tw, MENUBAR_H), t, fg, font)
            x += tw
    p.setPen(QPen(qcolor("#00000040"), 1))
    p.drawLine(QPointF(0, 0), QPointF(width, 0))
