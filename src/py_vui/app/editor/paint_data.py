"""Design-time painters for data widgets and schematic third-party (plugin) widgets."""

from __future__ import annotations

import calendar as _cal
import datetime as _dt
import math
from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen

from py_vui.app.editor.paint_common import (
    W,
    arrow,
    draw_text,
    mix,
    rrect,
    scrollbar,
)
from py_vui.app.editor.paint_controls import field_surface

AL = Qt.AlignmentFlag
ROW_H = 22.0


def _panel(p: QPainter, w: W) -> QRectF:
    return field_surface(p, w).adjusted(-4, -2, 4, 2) if w.look.name == "tkinter" else _flat(p, w)


def _flat(p: QPainter, w: W) -> QRectF:
    rrect(p, w.rect, 0 if w.look.name in ("tkinter", "kivy") else 4, w.field_bg(), w.border, 1)
    return w.rect


def paint_listbox(p: QPainter, w: W) -> None:
    area = _panel(p, w)
    items = [str(i) for i in (w.prop("items", []) or [])]
    p.save()
    p.setClipRect(area.adjusted(1, 1, -1, -1))
    for i, it in enumerate(items):
        r = QRectF(area.left() + 1, area.top() + 2 + i * ROW_H, area.width() - 2, ROW_H)
        if r.top() > area.bottom():
            break
        fg = w.field_fg()
        if i == 0:
            p.fillRect(r, w.primary)
            fg = QColor("#ffffff")
        draw_text(p, r.adjusted(6, 0, -6, 0), it, fg, w.font(), AL.AlignLeft)
    p.restore()
    if len(items) * ROW_H > w.h:
        scrollbar(p, QRectF(w.w - 11, 1, 10, w.h - 2), True, w.h / (len(items) * ROW_H), w)


def paint_table(p: QPainter, w: W, *, header_label: str = "") -> None:
    area = _panel(p, w)
    cols = [str(c) for c in (w.prop("columns", []) or [])] or ["A", "B"]
    rows: list[Any] = w.prop("rows", []) or []
    show_header = bool(w.prop("show_header", True))
    cw = (area.width() - 2) / len(cols)
    top = area.top() + 1
    p.save()
    p.setClipRect(area.adjusted(1, 1, -1, -1))
    if show_header:
        p.fillRect(
            QRectF(area.left() + 1, top, area.width() - 2, ROW_H), mix(w.surface, w.border, 0.5)
        )
        for i, c in enumerate(cols):
            draw_text(
                p,
                QRectF(area.left() + 1 + i * cw + 6, top, cw - 8, ROW_H),
                c,
                w.field_fg(),
                w.font(bold=True),
                AL.AlignLeft,
            )
        top += ROW_H
    p.setPen(QPen(mix(w.border, w.field_bg(), 0.35), 1))
    y = top
    ri = 0
    while y < area.bottom():
        if ri == 0 and rows and w.prop("selection_mode", "single") != "none":
            p.fillRect(
                QRectF(area.left() + 1, y, area.width() - 2, ROW_H),
                QColor(w.primary).lighter(150 if w.field_bg().lightnessF() > 0.5 else 80),
            )
        p.drawLine(QPointF(area.left() + 1, y + ROW_H), QPointF(area.right() - 1, y + ROW_H))
        row = rows[ri] if ri < len(rows) and isinstance(rows[ri], list | tuple) else []
        for i in range(len(cols)):
            cell = str(row[i]) if i < len(row) else ""
            draw_text(
                p,
                QRectF(area.left() + 1 + i * cw + 6, y, cw - 8, ROW_H),
                cell,
                w.field_fg(),
                w.font(),
                AL.AlignLeft,
            )
        y += ROW_H
        ri += 1
    for i in range(1, len(cols)):
        x = area.left() + 1 + i * cw
        p.drawLine(QPointF(x, area.top() + 1), QPointF(x, area.bottom() - 1))
    p.restore()


def _flatten(items: list[Any], depth: int, out: list[tuple[int, str, bool]]) -> None:
    for it in items:
        if not isinstance(it, dict):
            continue
        kids = it.get("children") or []
        out.append((depth, str(it.get("text", "")), bool(kids)))
        _flatten(kids, depth + 1, out)


def paint_tree(p: QPainter, w: W) -> None:
    area = _panel(p, w)
    rows: list[tuple[int, str, bool]] = []
    _flatten(w.prop("items", []) or [], 0, rows)
    top = area.top() + 1
    p.save()
    p.setClipRect(area.adjusted(1, 1, -1, -1))
    if w.prop("show_header"):
        p.fillRect(
            QRectF(area.left() + 1, top, area.width() - 2, ROW_H), mix(w.surface, w.border, 0.5)
        )
        draw_text(
            p,
            QRectF(area.left() + 8, top, area.width() - 12, ROW_H),
            str(w.prop("header", "")),
            w.field_fg(),
            w.font(bold=True),
            AL.AlignLeft,
        )
        top += ROW_H
    for i, (depth, text, has_kids) in enumerate(rows):
        y = top + i * ROW_H
        if y > area.bottom():
            break
        x = area.left() + 6 + depth * 16
        if has_kids:
            arrow(p, x + 5, y + ROW_H / 2, 7, w.muted, "down")
        draw_text(
            p,
            QRectF(x + 14, y, area.right() - x - 16, ROW_H),
            text,
            w.field_fg(),
            w.font(),
            AL.AlignLeft,
        )
    p.restore()


def paint_pandas_table(p: QPainter, w: W) -> None:
    paint_table_schematic(p, w, ["index", "col_a", "col_b", "col_c"], 6)
    draw_text(
        p, QRectF(w.w - 90, w.h - 20, 86, 16), "DataFrame", w.muted, w.font(0.75), AL.AlignRight
    )


def paint_table_schematic(p: QPainter, w: W, cols: list[str], nrows: int) -> None:
    area = _panel(p, w)
    cw = (area.width() - 2) / len(cols)
    p.save()
    p.setClipRect(area.adjusted(1, 1, -1, -1))
    p.fillRect(
        QRectF(area.left() + 1, area.top() + 1, area.width() - 2, ROW_H),
        mix(w.surface, w.border, 0.5),
    )
    p.setPen(QPen(mix(w.border, w.field_bg(), 0.35), 1))
    for r in range(nrows + 1):
        y = area.top() + 1 + (r + 1) * ROW_H
        p.drawLine(QPointF(area.left() + 1, y), QPointF(area.right() - 1, y))
        if y > area.bottom():
            break
    for i, c in enumerate(cols):
        draw_text(
            p,
            QRectF(area.left() + 1 + i * cw + 6, area.top() + 1, cw - 8, ROW_H),
            c,
            w.field_fg(),
            w.font(bold=True),
            AL.AlignLeft,
        )
        if i:
            x = area.left() + 1 + i * cw
            p.drawLine(QPointF(x, area.top() + 1), QPointF(x, area.bottom() - 1))
    p.restore()


# ----------------------------------------------------------------------------- plugin widgets
def paint_calendar(p: QPainter, w: W) -> None:
    rrect(p, w.rect, 4, w.field_bg(), w.border, 1)
    try:
        d = _dt.date.fromisoformat(str(w.prop("date", "2025-01-01")))
    except ValueError:
        d = _dt.date(2025, 1, 1)
    head_h = 28.0
    p.fillRect(QRectF(1, 1, w.w - 2, head_h), w.primary)
    draw_text(
        p,
        QRectF(0, 1, w.w, head_h),
        f"{_cal.month_name[d.month]} {d.year}",
        QColor("#ffffff"),
        w.font(bold=True),
    )
    arrow(p, 14, head_h / 2 + 1, 8, QColor("#ffffff"), "right")
    first = 0 if str(w.prop("first_weekday", "monday")) == "monday" else 6
    cal = _cal.Calendar(firstweekday=first)
    weeks = cal.monthdayscalendar(d.year, d.month)
    wk = bool(w.prop("show_week_numbers", True))
    left = 22.0 if wk else 0.0
    cw = (w.w - 2 - left) / 7
    rh = (w.h - head_h - 24) / max(6, len(weeks))
    names = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
    if first == 6:
        names = [names[-1], *names[:-1]]
    for i, n in enumerate(names):
        draw_text(p, QRectF(1 + left + i * cw, head_h + 2, cw, 18), n, w.muted, w.font(0.8))
    for r, week in enumerate(weeks):
        y = head_h + 22 + r * rh
        if wk:
            wnum = _dt.date(d.year, d.month, next(x for x in week if x)).isocalendar()[1]
            draw_text(p, QRectF(1, y, left, rh), str(wnum), w.muted, w.font(0.75))
        for c, day in enumerate(week):
            if not day:
                continue
            cell = QRectF(1 + left + c * cw, y, cw, rh)
            color = w.field_fg()
            if day == d.day:
                rrect(p, cell.adjusted(2, 1, -2, -1), 4, w.primary, None)
                color = QColor("#ffffff")
            draw_text(p, cell, str(day), color, w.font(0.9))


def paint_time_picker(p: QPainter, w: W) -> None:
    themes = {
        "navy_blue": ("#0d1b3a", "#ffffff"),
        "dracula": ("#282a36", "#f8f8f2"),
        "purple": ("#4b2a7b", "#ffffff"),
    }
    bg, fg = themes.get(str(w.prop("theme", "navy_blue")), themes["navy_blue"])
    rrect(p, w.rect, 6, QColor(bg), None)
    c = QPointF(w.w / 2, w.h * 0.55)
    rad = min(w.w, w.h * 0.8) * 0.4
    p.save()
    p.setPen(QPen(QColor(fg), 1.5))
    p.drawEllipse(c, rad, rad)
    for i in range(12):
        a = math.radians(i * 30 - 60)
        draw_text(
            p,
            QRectF(
                c.x() + math.cos(a) * rad * 0.8 - 10, c.y() + math.sin(a) * rad * 0.8 - 8, 20, 16
            ),
            str(i + 1 if i < 11 else 12),
            QColor(fg),
            w.font(0.7),
        )
    p.drawLine(c, QPointF(c.x() + rad * 0.5, c.y() - rad * 0.3))
    p.restore()
    h24 = bool(w.prop("hours24", False))
    draw_text(
        p, QRectF(0, 8, w.w, 30), "14:30" if h24 else "02:30 PM", QColor(fg), w.font(1.6, bold=True)
    )


def paint_map(p: QPainter, w: W) -> None:
    rrect(p, w.rect, 0, QColor("#e8efe0"), w.border, 1)
    p.save()
    p.setClipRect(w.rect)
    p.setPen(QPen(QColor("#ffffff"), 5))
    for i in range(-2, 8):
        p.drawLine(QPointF(i * w.w / 5, 0), QPointF(i * w.w / 5 + w.w * 0.3, w.h))
    p.setPen(QPen(QColor("#f5d9a6"), 3))
    p.drawLine(QPointF(0, w.h * 0.65), QPointF(w.w, w.h * 0.3))
    p.setPen(QPen(QColor("#b5d3ea"), 14))
    path = QPainterPath(QPointF(w.w * 0.1, w.h))
    path.cubicTo(
        QPointF(w.w * 0.3, w.h * 0.6), QPointF(w.w * 0.6, w.h * 0.8), QPointF(w.w * 0.9, w.h * 0.2)
    )
    p.drawPath(path)
    pin = QPointF(w.w / 2, w.h / 2)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#e11d48"))
    p.drawEllipse(QPointF(pin.x(), pin.y() - 10), 7, 7)
    tri = QPainterPath(QPointF(pin.x() - 6, pin.y() - 7))
    tri.lineTo(QPointF(pin.x() + 6, pin.y() - 7))
    tri.lineTo(pin)
    p.drawPath(tri)
    p.restore()
    label = str(w.prop("marker_text", "")) or (
        f"{float(w.prop('latitude', 0)):.3f}, {float(w.prop('longitude', 0)):.3f}"
    )
    draw_text(
        p, QRectF(6, w.h - 20, w.w - 12, 16), label, QColor("#333333"), w.font(0.8), AL.AlignLeft
    )
    draw_text(
        p,
        QRectF(w.w - 60, 4, 56, 16),
        f"z{int(w.prop('zoom', 10))}",
        QColor("#555555"),
        w.font(0.75),
        AL.AlignRight,
    )


def _floats(values: Any) -> list[float]:
    out = []
    for v in values or []:
        try:
            out.append(float(v))
        except (TypeError, ValueError):
            out.append(0.0)
    return out


def paint_chart(p: QPainter, w: W) -> None:
    rrect(p, w.rect, 0, w.field_bg(), w.border, 1)
    title = str(w.prop("title", ""))
    top = 26.0 if title else 10.0
    if title:
        draw_text(p, QRectF(0, 2, w.w, 22), title, w.field_fg(), w.font(bold=True))
    plot = QRectF(34, top, w.w - 46, w.h - top - 26)
    kind = str(w.prop("kind", "line"))
    ys = _floats(w.prop("y", [])) or [1, 2, 3]
    xs = _floats(w.prop("x", [])) or list(range(len(ys)))
    n = min(len(xs), len(ys))
    ys, xs = ys[:n], xs[:n]
    lo, hi = min(ys + [0]), max(ys) or 1
    span = (hi - lo) or 1
    col = w.primary
    p.save()
    if kind == "pie":
        d = min(plot.width(), plot.height())
        r = QRectF(plot.center().x() - d / 2, plot.center().y() - d / 2, d, d)
        total = sum(abs(v) for v in ys) or 1
        start = 90 * 16
        for i, v in enumerate(ys):
            ang = int(-abs(v) / total * 360 * 16)
            p.setBrush(QColor.fromHsv(int(i * 360 / max(1, n)) % 360, 150, 220))
            p.setPen(QPen(w.field_bg(), 1))
            p.drawPie(r, start, ang)
            start += ang
        p.restore()
        return
    p.setPen(QPen(w.border, 1))
    p.drawLine(plot.bottomLeft(), plot.bottomRight())
    p.drawLine(plot.bottomLeft(), plot.topLeft())
    for g in range(1, 4):
        y = plot.bottom() - plot.height() * g / 4
        p.setPen(QPen(mix(w.border, w.field_bg(), 0.5), 1, Qt.PenStyle.DotLine))
        p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
    pts = []
    for i, v in enumerate(ys):
        px = plot.left() + (i + 0.5) / max(1, n) * plot.width()
        py = plot.bottom() - (v - lo) / span * plot.height()
        pts.append(QPointF(px, py))
    if kind in ("bar", "hist"):
        bw = plot.width() / max(1, n) * (0.7 if kind == "bar" else 1.0)
        p.setPen(QPen(mix(col, QColor("#000000"), 0.2), 1))
        p.setBrush(col)
        for pt in pts:
            p.drawRect(QRectF(pt.x() - bw / 2, pt.y(), bw, plot.bottom() - pt.y()))
    elif kind == "scatter":
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(col)
        for pt in pts:
            p.drawEllipse(pt, 3.5, 3.5)
    else:
        p.setPen(QPen(col, 2))
        if len(pts) > 1:
            p.drawPolyline(pts)
        p.setBrush(col)
        for pt in pts:
            p.drawEllipse(pt, 3, 3)
    p.restore()
    xl, yl = str(w.prop("x_label", "")), str(w.prop("y_label", ""))
    if xl:
        draw_text(p, QRectF(0, w.h - 20, w.w, 18), xl, w.muted, w.font(0.8))
    if yl:
        p.save()
        p.translate(10, w.h / 2)
        p.rotate(-90)
        draw_text(p, QRectF(-50, -8, 100, 16), yl, w.muted, w.font(0.8))
        p.restore()


def paint_video(p: QPainter, w: W) -> None:
    rrect(p, w.rect, 0, QColor("#111111"), None)
    c = QPointF(w.w / 2, (w.h - (28 if w.prop("controls", True) else 0)) / 2)
    s = min(w.w, w.h) * 0.14
    tri = QPainterPath(QPointF(c.x() - s * 0.6, c.y() - s))
    tri.lineTo(QPointF(c.x() - s * 0.6, c.y() + s))
    tri.lineTo(QPointF(c.x() + s, c.y()))
    tri.closeSubpath()
    p.save()
    p.setPen(QPen(QColor("#ffffff"), 2))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(c, s * 1.5, s * 1.5)
    p.setBrush(QColor("#ffffff"))
    p.drawPath(tri)
    if w.prop("controls", True):
        p.fillRect(QRectF(0, w.h - 26, w.w, 26), QColor(255, 255, 255, 30))
        p.fillRect(QRectF(34, w.h - 14, w.w - 48, 3), QColor(255, 255, 255, 90))
        p.fillRect(QRectF(34, w.h - 14, (w.w - 48) * 0.35, 3), w.primary)
    p.restore()
