from __future__ import annotations

import math
from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
)

from py_vui.app.editor.canvas_resize import (
    MIN_WIDGET_H,
    MIN_WIDGET_W,
    ResizeHandle,
    ResizeHandleItem,
    compute_resized_box,
    handle_anchor,
)
from py_vui.app.editor.snap import snap, snap_size
from py_vui.commands import ReplaceNode, SetLayoutBox, SetLayoutBoxes
from py_vui.model.document import ProjectDocument
from py_vui.model.geometry import Rect
from py_vui.model.nodes import ButtonNode, LabelNode, Node, WindowNode
from py_vui.model.theme import resolve_widget_colors

if TYPE_CHECKING:
    from py_vui.commands.history import History

MIME_WIDGET = "application/x-py-vui-widget"

_GRID_SIZE = 16
_GRID_COLOR = QColor(255, 255, 255, 18)
_SEL_COLOR = QColor(249, 115, 22)


class NodeGraphicsItem(QGraphicsRectItem):
    def __init__(
        self,
        node_id: str,
        label: str,
        w: float,
        h: float,
        *,
        node_type: str = "frame",
        movable: bool = True,
        fill: str = "#f0f8ff",
        border: str = "#3c64b4",
        text_color: str = "#0f172a",
        border_radius: int = 4,
        enabled: bool = True,
        font_size: int = 11,
        font_family: str = "Sans Serif",
        primary: str = "#6366f1",
    ) -> None:
        super().__init__(0, 0, w, h)
        self.node_id = node_id
        self._label = label
        self._node_type = node_type
        self._fill_color = QColor(fill)
        self._border_color = QColor(border)
        self._text_color = QColor(text_color)
        self._primary_color = QColor(primary)
        self._border_radius = border_radius
        self._enabled = enabled
        self._font_size = max(8, font_size)
        self._font_family = font_family

        if not enabled:
            self._fill_color.setAlpha(140)
            self._border_color = QColor("#94a3b8")

        self.setBrush(QBrush(self._fill_color))
        self.setPen(QPen(self._border_color, 1.5))

        if movable and enabled:
            self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self._drag_start: QPointF | None = None
        self._start_box: Rect | None = None

    def _base_font(self, size: int | None = None) -> QFont:
        f = QFont()
        if self._font_family:
            f.setFamily(self._font_family)
        f.setPointSize(size or self._font_size)
        return f

    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect()

        dispatch = {
            "window": self._paint_window,
            "button": self._paint_button,
            "label": self._paint_label,
            "line_edit": self._paint_line_edit,
            "text_edit": self._paint_text_edit,
            "checkbox": self._paint_checkbox,
            "radio_button": self._paint_radio_button,
            "combo_box": self._paint_combo_box,
            "slider": self._paint_slider,
            "progress_bar": self._paint_progress_bar,
            "spin_box": self._paint_spin_box,
            "list_widget": self._paint_list_widget,
            "tab_widget": self._paint_tab_widget,
            "group_box": self._paint_group_box,
            "scroll_area": self._paint_scroll_area,
            "frame": self._paint_frame,
            "date_edit": self._paint_date_edit,
            "time_edit": self._paint_time_edit,
            "table_widget": self._paint_table_widget,
            "dial": self._paint_dial,
            "tool_button": self._paint_tool_button,
        }
        paint_fn = dispatch.get(self._node_type, self._paint_default)
        paint_fn(painter, r)

        if self.isSelected():
            sel_pen = QPen(_SEL_COLOR, 2.0)
            painter.setPen(sel_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(
                r.adjusted(-1, -1, 1, 1),
                self._border_radius + 1,
                self._border_radius + 1,
            )

    def _draw_base(self, painter: QPainter, r: QRectF, radius: int | None = None) -> None:
        rad = radius if radius is not None else self._border_radius
        painter.setBrush(QBrush(self._fill_color))
        painter.setPen(QPen(self._border_color, 1.5))
        if rad > 0:
            painter.drawRoundedRect(r, rad, rad)
        else:
            painter.drawRect(r)

    def _draw_text(
        self,
        painter: QPainter,
        r: QRectF,
        text: str,
        *,
        align: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignCenter,
        color: QColor | None = None,
        font_size: int | None = None,
    ) -> None:
        painter.setPen(QPen(color or self._text_color))
        painter.setFont(self._base_font(font_size))
        painter.drawText(r, align | Qt.TextFlag.TextWordWrap, text)

    def _paint_window(self, painter: QPainter, r: QRectF) -> None:
        self._draw_base(painter, r, 6)
        tb_h = min(26.0, r.height() * 0.15)
        tb = QRectF(r.left(), r.top(), r.width(), tb_h)
        grad = QLinearGradient(tb.topLeft(), tb.bottomLeft())
        grad.setColorAt(0, self._primary_color.lighter(110))
        grad.setColorAt(1, self._primary_color)
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(tb, 6, 6)
        fix = QRectF(tb.left(), tb.top() + tb_h * 0.5, tb.width(), tb_h * 0.5)
        painter.drawRect(fix)
        self._draw_text(painter, tb, self._label, color=QColor(255, 255, 255))
        # type badge
        self._draw_type_badge(painter, r, "WIN")

    def _paint_button(self, painter: QPainter, r: QRectF) -> None:
        grad = QLinearGradient(r.topLeft(), r.bottomLeft())
        grad.setColorAt(0, self._fill_color.lighter(115))
        grad.setColorAt(1, self._fill_color)
        painter.setBrush(QBrush(grad))
        painter.setPen(QPen(self._border_color, 1.5))
        painter.drawRoundedRect(r, self._border_radius, self._border_radius)
        self._draw_text(painter, r, self._label, color=self._text_color)

    def _paint_tool_button(self, painter: QPainter, r: QRectF) -> None:
        painter.setBrush(QBrush(self._fill_color))
        painter.setPen(QPen(self._border_color, 1.0))
        painter.drawRoundedRect(r, 3, 3)
        self._draw_text(
            painter,
            r,
            self._label,
            color=self._text_color,
            font_size=self._font_size - 1,
        )

    def _paint_label(self, painter: QPainter, r: QRectF) -> None:
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(r)
        self._draw_text(
            painter,
            r,
            self._label,
            align=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            color=self._text_color,
        )

    def _paint_line_edit(self, painter: QPainter, r: QRectF) -> None:
        self._draw_base(painter, r, 4)
        inner = r.adjusted(6, 0, -6, 0)
        placeholder = self._label if self._label else "Text…"
        ph_color = QColor(self._text_color)
        ph_color.setAlpha(100)
        self._draw_text(
            painter,
            inner,
            placeholder,
            align=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            color=ph_color,
        )
        cursor_x = inner.left() + 2
        cursor_y1 = r.center().y() - r.height() * 0.3
        cursor_y2 = r.center().y() + r.height() * 0.3
        painter.setPen(QPen(self._text_color, 1.5))
        painter.drawLine(QPointF(cursor_x, cursor_y1), QPointF(cursor_x, cursor_y2))

    def _paint_text_edit(self, painter: QPainter, r: QRectF) -> None:
        self._draw_base(painter, r, 4)
        line_color = QColor(self._text_color)
        line_color.setAlpha(40)
        painter.setPen(QPen(line_color, 1))
        line_h = max(14.0, self._font_size * 1.6)
        y = r.top() + 10
        while y + line_h < r.bottom() - 6:
            line_w = r.width() * (0.6 + 0.3 * ((int(y) % 3) / 3))
            painter.drawLine(
                QPointF(r.left() + 6, y + line_h * 0.5),
                QPointF(r.left() + line_w, y + line_h * 0.5),
            )
            y += line_h

    def _paint_checkbox(self, painter: QPainter, r: QRectF) -> None:
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(r)
        box_size = min(14.0, r.height() - 6)
        bx = r.left() + 4
        by = r.center().y() - box_size / 2
        box = QRectF(bx, by, box_size, box_size)
        painter.setBrush(QBrush(self._fill_color))
        painter.setPen(QPen(self._border_color, 1.5))
        painter.drawRoundedRect(box, 2, 2)
        check_c = QColor(self._primary_color)
        painter.setPen(QPen(check_c, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(
            QPointF(bx + box_size * 0.2, by + box_size * 0.5),
            QPointF(bx + box_size * 0.45, by + box_size * 0.75),
        )
        painter.drawLine(
            QPointF(bx + box_size * 0.45, by + box_size * 0.75),
            QPointF(bx + box_size * 0.8, by + box_size * 0.2),
        )
        text_r = QRectF(bx + box_size + 6, r.top(), r.width() - box_size - 14, r.height())
        self._draw_text(
            painter,
            text_r,
            self._label,
            align=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            color=self._text_color,
        )

    def _paint_radio_button(self, painter: QPainter, r: QRectF) -> None:
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(r)
        circle_r = min(7.0, r.height() / 2 - 3)
        cx = r.left() + 4 + circle_r
        cy = r.center().y()
        painter.setBrush(QBrush(self._fill_color))
        painter.setPen(QPen(self._border_color, 1.5))
        painter.drawEllipse(QPointF(cx, cy), circle_r, circle_r)
        dot_r = circle_r * 0.45
        painter.setBrush(QBrush(self._primary_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(cx, cy), dot_r, dot_r)
        text_r = QRectF(cx + circle_r + 6, r.top(), r.width() - cx - circle_r - 10, r.height())
        self._draw_text(
            painter,
            text_r,
            self._label,
            align=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            color=self._text_color,
        )

    def _paint_combo_box(self, painter: QPainter, r: QRectF) -> None:
        self._draw_base(painter, r, 4)
        arrow_w = min(20.0, r.height())
        arrow_r = QRectF(r.right() - arrow_w - 2, r.top(), arrow_w, r.height())
        painter.setBrush(
            QBrush(
                self._border_color.lighter(130)
                if self._border_color.lightness() > 60
                else QColor(60, 60, 80)
            )
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(arrow_r)
        cx = arrow_r.center().x()
        cy = arrow_r.center().y()
        half = 4.0
        arrow = QPolygonF(
            [
                QPointF(cx - half, cy - 2),
                QPointF(cx + half, cy - 2),
                QPointF(cx, cy + 3),
            ]
        )
        painter.setBrush(QBrush(self._text_color))
        painter.drawPolygon(arrow)
        text_r = QRectF(r.left() + 6, r.top(), r.width() - arrow_w - 12, r.height())
        items_label = self._label or "Option 1"
        self._draw_text(
            painter,
            text_r,
            items_label,
            align=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        )

    def _paint_spin_box(self, painter: QPainter, r: QRectF) -> None:
        self._draw_base(painter, r, 4)
        btn_w = min(18.0, r.height() * 0.7)
        up_r = QRectF(r.right() - btn_w - 2, r.top() + 1, btn_w, r.height() / 2 - 1)
        dn_r = QRectF(r.right() - btn_w - 2, r.center().y(), btn_w, r.height() / 2 - 1)
        btn_bg = QColor(60, 60, 80) if self._fill_color.lightness() < 100 else QColor(230, 230, 235)
        for br in (up_r, dn_r):
            painter.setBrush(QBrush(btn_bg))
            painter.setPen(QPen(self._border_color, 0.5))
            painter.drawRect(br)
        # up arrow
        ucx = up_r.center().x()
        ucy = up_r.center().y()
        up_arrow = QPolygonF(
            [
                QPointF(ucx - 3, ucy + 1.5),
                QPointF(ucx + 3, ucy + 1.5),
                QPointF(ucx, ucy - 1.5),
            ]
        )
        painter.setBrush(QBrush(self._text_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(up_arrow)
        # down arrow
        dcx = dn_r.center().x()
        dcy = dn_r.center().y()
        dn_arrow = QPolygonF(
            [
                QPointF(dcx - 3, dcy - 1.5),
                QPointF(dcx + 3, dcy - 1.5),
                QPointF(dcx, dcy + 1.5),
            ]
        )
        painter.drawPolygon(dn_arrow)
        text_r = QRectF(r.left() + 6, r.top(), r.width() - btn_w - 12, r.height())
        self._draw_text(
            painter,
            text_r,
            "0",
            align=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        )

    def _paint_slider(self, painter: QPainter, r: QRectF) -> None:
        self._draw_base(painter, r, 4)
        track_h = 4.0
        cy = r.center().y()
        tx1 = r.left() + 10
        tx2 = r.right() - 10
        track_bg = QColor(self._border_color)
        track_bg.setAlpha(80)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(track_bg))
        painter.drawRoundedRect(QRectF(tx1, cy - track_h / 2, tx2 - tx1, track_h), 2, 2)
        fill_end = tx1 + (tx2 - tx1) * 0.5
        painter.setBrush(QBrush(self._primary_color))
        painter.drawRoundedRect(QRectF(tx1, cy - track_h / 2, fill_end - tx1, track_h), 2, 2)
        knob_r = min(8.0, r.height() * 0.4)
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        painter.setPen(QPen(self._primary_color, 1.5))
        painter.drawEllipse(QPointF(fill_end, cy), knob_r, knob_r)

    def _paint_progress_bar(self, painter: QPainter, r: QRectF) -> None:
        self._draw_base(painter, r, 3)
        fill_w = r.width() * 0.6
        fill_r = QRectF(r.left() + 1, r.top() + 1, fill_w - 2, r.height() - 2)
        painter.setBrush(QBrush(self._primary_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(fill_r, 2, 2)
        self._draw_text(painter, r, "60%", color=QColor(255, 255, 255))

    def _paint_list_widget(self, painter: QPainter, r: QRectF) -> None:
        self._draw_base(painter, r, 4)
        row_h = max(16.0, self._font_size * 1.8)
        items = ["Item 1", "Item 2", "Item 3", "Item 4"]
        for i, item in enumerate(items):
            y = r.top() + i * row_h
            if y + row_h > r.bottom():
                break
            row_r = QRectF(r.left() + 1, y, r.width() - 2, row_h)
            if i == 0:
                hl = QColor(self._primary_color)
                hl.setAlpha(60)
                painter.setBrush(QBrush(hl))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRect(row_r)
            text_r = QRectF(r.left() + 8, y, r.width() - 12, row_h)
            self._draw_text(
                painter,
                text_r,
                item,
                align=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                font_size=self._font_size - 1,
            )
            sep_y = y + row_h
            if sep_y < r.bottom():
                sep_c = QColor(self._border_color)
                sep_c.setAlpha(50)
                painter.setPen(QPen(sep_c, 0.5))
                painter.drawLine(QPointF(r.left() + 2, sep_y), QPointF(r.right() - 2, sep_y))

    def _paint_tab_widget(self, painter: QPainter, r: QRectF) -> None:
        self._draw_base(painter, r, 4)
        tab_h = min(24.0, r.height() * 0.15)
        tabs = ["Tab 1", "Tab 2"]
        tab_w = min(60.0, r.width() / max(len(tabs), 1))
        for i, tab in enumerate(tabs):
            tx = r.left() + i * tab_w
            tab_r = QRectF(tx, r.top(), tab_w, tab_h)
            if i == 0:
                painter.setBrush(QBrush(self._fill_color))
                painter.setPen(QPen(self._border_color, 1.0))
            else:
                bg = QColor(self._fill_color)
                bg.setAlpha(120)
                painter.setBrush(QBrush(bg))
                painter.setPen(QPen(self._border_color, 0.5))
            painter.drawRect(tab_r)
            self._draw_text(painter, tab_r, tab, font_size=self._font_size - 2)
        # separator
        painter.setPen(QPen(self._border_color, 1.0))
        painter.drawLine(QPointF(r.left(), r.top() + tab_h), QPointF(r.right(), r.top() + tab_h))
        self._draw_type_badge(painter, r, "TAB")

    def _paint_group_box(self, painter: QPainter, r: QRectF) -> None:
        title_h = max(18.0, self._font_size * 1.6)
        body_r = QRectF(r.left(), r.top() + title_h, r.width(), r.height() - title_h)
        painter.setBrush(QBrush(self._fill_color))
        painter.setPen(QPen(self._border_color, 1.5))
        painter.drawRoundedRect(r, 4, 4)
        text_r = QRectF(r.left() + 8, r.top(), r.width() - 12, title_h)
        self._draw_text(
            painter,
            text_r,
            self._label,
            align=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            font_size=self._font_size - 1,
        )
        painter.setPen(QPen(self._border_color, 0.5))
        painter.drawLine(
            QPointF(r.left(), r.top() + title_h), QPointF(r.right(), r.top() + title_h)
        )
        _ = body_r  # suppress unused

    def _paint_scroll_area(self, painter: QPainter, r: QRectF) -> None:
        self._draw_base(painter, r, 4)
        scroll_w = 8.0
        sr = QRectF(r.right() - scroll_w - 2, r.top() + 4, scroll_w, r.height() - 8)
        sb = QColor(self._border_color)
        sb.setAlpha(60)
        painter.setBrush(QBrush(sb))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(sr, 3, 3)
        handle_h = sr.height() * 0.4
        handle_r = QRectF(sr.left(), sr.top(), sr.width(), handle_h)
        painter.setBrush(QBrush(self._border_color))
        painter.drawRoundedRect(handle_r, 3, 3)
        self._draw_type_badge(painter, r, "SCROLL")

    def _paint_frame(self, painter: QPainter, r: QRectF) -> None:
        painter.setBrush(QBrush(self._fill_color))
        dash_pen = QPen(self._border_color, 1.5, Qt.PenStyle.DashLine)
        painter.setPen(dash_pen)
        painter.drawRoundedRect(r, 4, 4)
        name_c = QColor(self._text_color)
        name_c.setAlpha(100)
        self._draw_text(
            painter,
            r.adjusted(4, 4, -4, -4),
            self._label,
            align=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            color=name_c,
            font_size=self._font_size - 2,
        )

    def _paint_date_edit(self, painter: QPainter, r: QRectF) -> None:
        self._draw_base(painter, r, 4)
        icon_w = min(18.0, r.height())
        icon_r = QRectF(r.right() - icon_w - 4, r.top() + (r.height() - icon_w) / 2, icon_w, icon_w)
        painter.setPen(QPen(self._text_color, 1.2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(icon_r.adjusted(1, 1, -1, -1), 2, 2)
        top_y = icon_r.top() + icon_w * 0.3
        painter.drawLine(QPointF(icon_r.left() + 1, top_y), QPointF(icon_r.right() - 1, top_y))
        text_r = QRectF(r.left() + 6, r.top(), r.width() - icon_w - 12, r.height())
        self._draw_text(
            painter,
            text_r,
            "2024-01-01",
            align=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        )

    def _paint_time_edit(self, painter: QPainter, r: QRectF) -> None:
        self._draw_base(painter, r, 4)
        icon_w = min(16.0, r.height() - 4)
        cx = r.right() - icon_w / 2 - 6
        cy = r.center().y()
        ir = icon_w / 2
        painter.setPen(QPen(self._text_color, 1.2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(cx, cy), ir, ir)
        painter.drawLine(QPointF(cx, cy), QPointF(cx, cy - ir * 0.7))
        painter.drawLine(QPointF(cx, cy), QPointF(cx + ir * 0.5, cy))
        text_r = QRectF(r.left() + 6, r.top(), r.width() - icon_w - 16, r.height())
        self._draw_text(
            painter,
            text_r,
            "12:00",
            align=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        )

    def _paint_table_widget(self, painter: QPainter, r: QRectF) -> None:
        self._draw_base(painter, r, 2)
        rows, cols = 3, 3
        col_w = r.width() / cols
        hdr_h = min(20.0, r.height() * 0.15)
        hdr_c = QColor(self._border_color)
        hdr_c.setAlpha(100)
        painter.setBrush(QBrush(hdr_c))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(QRectF(r.left(), r.top(), r.width(), hdr_h))
        row_h = (r.height() - hdr_h) / rows
        painter.setPen(QPen(self._border_color, 0.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for col in range(1, cols):
            x = r.left() + col * col_w
            painter.drawLine(QPointF(x, r.top()), QPointF(x, r.bottom()))
        for row in range(1, rows + 1):
            y = r.top() + hdr_h + row * row_h
            painter.drawLine(QPointF(r.left(), y), QPointF(r.right(), y))

    def _paint_dial(self, painter: QPainter, r: QRectF) -> None:
        margin = 6.0
        cr = min(r.width(), r.height()) / 2 - margin
        cx = r.center().x()
        cy = r.center().y()
        self._draw_base(painter, r, int(min(r.width(), r.height()) / 2))
        painter.setPen(QPen(self._border_color, 2.0))
        painter.setBrush(QBrush(self._fill_color.darker(110)))
        painter.drawEllipse(QPointF(cx, cy), cr, cr)
        angle = -135 + 270 * 0.5
        rad_angle = math.radians(angle)
        hand_len = cr * 0.7
        hx = cx + hand_len * math.cos(rad_angle)
        hy = cy + hand_len * math.sin(rad_angle)
        painter.setPen(
            QPen(self._primary_color, 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        )
        painter.drawLine(QPointF(cx, cy), QPointF(hx, hy))
        painter.setPen(QPen(self._primary_color, 3))
        painter.setBrush(QBrush(self._primary_color))
        painter.drawEllipse(QPointF(cx, cy), 3, 3)

    def _paint_default(self, painter: QPainter, r: QRectF) -> None:
        self._draw_base(painter, r)
        self._draw_text(painter, r, self._label)

    def _draw_type_badge(self, painter: QPainter, r: QRectF, badge: str) -> None:
        badge_font = QFont()
        if self._font_family:
            badge_font.setFamily(self._font_family)
        badge_font.setPointSize(7)
        badge_font.setBold(True)
        painter.setFont(badge_font)
        c = QColor(self._text_color)
        c.setAlpha(60)
        painter.setPen(QPen(c))
        bx = r.right() - 40
        by = r.bottom() - 14
        painter.drawText(QRectF(bx, by, 38, 12), Qt.AlignmentFlag.AlignRight, badge)


class DesignCanvas(QGraphicsView):
    selection_changed = Signal(str)
    layout_changed = Signal()
    document_dirty = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setAcceptDrops(True)
        self._scene_bg = QColor(248, 248, 252)
        self.setBackgroundBrush(QBrush(self._scene_bg))
        self._doc: ProjectDocument | None = None
        self._history: History | None = None
        self._items: dict[str, NodeGraphicsItem] = {}
        self._abs_pos: dict[str, QPointF] = {}
        self._rebuild_guard = False
        self._ignore_release = False
        self._palette_drag = False
        self._resize_handles: list[ResizeHandleItem] = []
        self._resize_active = False
        self._resize_node_id: str | None = None
        self._resize_handle: ResizeHandle | None = None
        self._resize_start_scene = QPointF()
        self._resize_start_box = Rect(x=0, y=0, w=0, h=0)

        self._scene.selectionChanged.connect(self._on_selection_changed)

    def drawBackground(self, painter: QPainter, rect) -> None:
        super().drawBackground(painter, rect)
        painter.setPen(QPen(_GRID_COLOR, 1, Qt.PenStyle.SolidLine))
        left = int(rect.left()) - (int(rect.left()) % _GRID_SIZE)
        top = int(rect.top()) - (int(rect.top()) % _GRID_SIZE)
        x = float(left)
        while x < rect.right():
            painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
            x += _GRID_SIZE
        y = float(top)
        while y < rect.bottom():
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
            y += _GRID_SIZE

    def bind(self, doc: ProjectDocument, history: History) -> None:
        self._doc = doc
        self._history = history
        self.rebuild()

    def rebuild(self) -> None:
        if self._doc is None:
            return
        self._rebuild_guard = True
        self._clear_resize_handles()
        self._scene.clear()
        self._items.clear()
        self._abs_pos.clear()

        root = self._doc.get_node(self._doc.project.root_id)
        self._abs_pos[root.id] = QPointF(0, 0)
        self._add_node_recursive(root)

        bg = self._doc.project.theme.background
        self._scene_bg = QColor(bg)
        self.setBackgroundBrush(QBrush(self._scene_bg))
        self._scene.setSceneRect(self._scene.itemsBoundingRect().adjusted(-40, -40, 80, 80))
        self._rebuild_guard = False

    def _add_node_recursive(self, node: Node) -> None:
        box = node.layout.box
        parent_abs = self._abs_pos.get(node.parent_id or "", QPointF(0, 0))
        abs_pos = parent_abs + QPointF(box.x, box.y)
        self._abs_pos[node.id] = abs_pos

        theme = self._doc.project.theme
        fill, border, text = resolve_widget_colors(
            theme=theme,
            node_type=node.type,
            style=node.style,
        )
        radius = theme.button_radius if node.type in ("button", "tool_button") else 4
        if node.style and node.style.border_radius is not None:
            radius = node.style.border_radius
        font_size = node.style.font_size if node.style and node.style.font_size else theme.font_size
        label = node.name
        if isinstance(node, LabelNode) and node.props.text:
            label = node.props.text[:48]
        elif isinstance(node, ButtonNode) and node.props.text:
            label = node.props.text[:48]
        is_root = node.id == self._doc.project.root_id
        if isinstance(node, WindowNode):
            draw_w, draw_h = node.props.width, node.props.height
        else:
            draw_w, draw_h = box.w, box.h
        item = NodeGraphicsItem(
            node.id,
            label,
            draw_w,
            draw_h,
            node_type=node.type,
            movable=not is_root,
            fill=fill,
            border=border,
            text_color=text,
            border_radius=radius,
            enabled=node.enabled,
            font_size=max(8, font_size),
            font_family=theme.font_family,
            primary=theme.primary,
        )
        item.setPos(abs_pos)
        item.setZValue(node.z_index)
        self._scene.addItem(item)
        self._items[node.id] = item

        for child in self._doc.children(node.id):  # type: ignore[union-attr]
            self._add_node_recursive(child)

    def _on_selection_changed(self) -> None:
        self._sync_resize_handles()
        ids = self.selected_node_ids()
        self.selection_changed.emit(ids[0] if ids else "")

    def _clear_resize_handles(self) -> None:
        for handle in self._resize_handles:
            handle.setParentItem(None)
            self._scene.removeItem(handle)
        self._resize_handles.clear()

    def _sync_resize_handles(self) -> None:
        self._clear_resize_handles()
        if self._resize_active or self._palette_drag:
            return
        node_id = self.selected_node_id()
        if not node_id:
            return
        item = self._items.get(node_id)
        if item is None:
            return
        for handle in ResizeHandle:
            rh = ResizeHandleItem(handle, self, item)
            self._resize_handles.append(rh)
        self._layout_resize_handles(item)

    def _layout_resize_handles(self, item: NodeGraphicsItem) -> None:
        rect = item.rect()
        w, h = rect.width(), rect.height()
        for rh in self._resize_handles:
            anchor = handle_anchor(rh._handle, w, h)
            rh.setPos(anchor)

    def _begin_resize(self, node_id: str, handle: ResizeHandle, scene_pos: QPointF) -> None:
        if self._doc is None:
            return
        node = self._doc.get_node(node_id)
        box = node.layout.box
        if isinstance(node, WindowNode):
            box = Rect(x=box.x, y=box.y, w=node.props.width, h=node.props.height)
        self._resize_active = True
        self._resize_node_id = node_id
        self._resize_handle = handle
        self._resize_start_scene = scene_pos
        self._resize_start_box = box
        item = self._items[node_id]
        item.setSelected(True)
        item.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)

    def _update_resize(self, scene_pos: QPointF) -> None:
        if not self._resize_active or self._resize_node_id is None or self._resize_handle is None:
            return
        if self._doc is None:
            return
        node = self._doc.get_node(self._resize_node_id)
        parent_abs = self._abs_pos.get(node.parent_id or "", QPointF(0, 0))
        dx = scene_pos.x() - self._resize_start_scene.x()
        dy = scene_pos.y() - self._resize_start_scene.y()
        start = self._resize_start_box
        min_w = MIN_WIDGET_W
        min_h = MIN_WIDGET_H
        if isinstance(node, WindowNode):
            min_w, min_h = 200.0, 150.0
        x, y, w, h = compute_resized_box(
            self._resize_handle,
            start_x=start.x,
            start_y=start.y,
            start_w=start.w,
            start_h=start.h,
            dx=dx,
            dy=dy,
            min_w=min_w,
            min_h=min_h,
        )
        item = self._items[self._resize_node_id]
        item.setRect(0, 0, w, h)
        item.setPos(parent_abs + QPointF(x, y))
        self._layout_resize_handles(item)

    def _finish_resize(self) -> None:
        for rh in self._resize_handles:
            if rh._grabbing:
                rh.ungrabMouse()
                rh._grabbing = False
        if not self._resize_active or self._resize_node_id is None or self._doc is None:
            return
        if self._history is None:
            self._resize_active = False
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
            return
        node_id = self._resize_node_id
        item = self._items.get(node_id)
        if item is None:
            self._resize_active = False
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
            return
        node = self._doc.get_node(node_id)
        parent_abs = self._abs_pos.get(node.parent_id or "", QPointF(0, 0))
        rect = item.rect()
        local_x = item.pos().x() - parent_abs.x()
        local_y = item.pos().y() - parent_abs.y()
        new_box = Rect(
            x=snap(local_x),
            y=snap(local_y),
            w=snap_size(rect.width()),
            h=snap_size(rect.height()),
        )
        before = node
        if isinstance(node, WindowNode):
            data = node.model_dump()
            data["layout"]["box"]["x"] = new_box.x
            data["layout"]["box"]["y"] = new_box.y
            data["layout"]["box"]["w"] = new_box.w
            data["layout"]["box"]["h"] = new_box.h
            data["props"]["width"] = new_box.w
            data["props"]["height"] = new_box.h
            after = WindowNode.model_validate(data)
            if after.model_dump() != before.model_dump():
                self._history.push(self._doc, ReplaceNode(before=before, after=after))
        elif (
            abs(new_box.x - before.layout.box.x) > 0.5
            or abs(new_box.y - before.layout.box.y) > 0.5
            or abs(new_box.w - before.layout.box.w) > 0.5
            or abs(new_box.h - before.layout.box.h) > 0.5
        ):
            self._history.push(self._doc, SetLayoutBox(node_id=node_id, new_box=new_box))
        self._resize_active = False
        self._resize_node_id = None
        self._resize_handle = None
        self._ignore_release = True
        is_root = node_id == self._doc.project.root_id
        item.setFlag(
            QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable,
            not is_root and before.enabled,
        )
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.rebuild()
        self.select_node(node_id)
        self.layout_changed.emit()

    def selected_node_ids(self) -> list[str]:
        if self._doc is None:
            return []
        return [
            it.node_id
            for it in self._scene.selectedItems()
            if isinstance(it, NodeGraphicsItem) and it.node_id != self._doc.project.root_id
        ]

    def selected_node_id(self) -> str | None:
        ids = self.selected_node_ids()
        return ids[0] if ids else None

    def select_node(self, node_id: str) -> None:
        item = self._items.get(node_id)
        if item:
            self._scene.clearSelection()
            item.setSelected(True)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasFormat(MIME_WIDGET):
            self._palette_drag = True
            self._set_children_movable(False)
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasFormat(MIME_WIDGET):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dragLeaveEvent(self, event) -> None:
        if self._palette_drag:
            self._palette_drag = False
            self._set_children_movable(True)
        super().dragLeaveEvent(event)

    def _set_children_movable(self, movable: bool) -> None:
        if self._doc is None:
            return
        root_id = self._doc.project.root_id
        for node_id, item in self._items.items():
            if node_id != root_id:
                item.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable, movable)

    def dropEvent(self, event) -> None:
        if not event.mimeData().hasFormat(MIME_WIDGET) or self._doc is None:
            return
        widget_type = bytes(event.mimeData().data(MIME_WIDGET)).decode()
        if widget_type == "window":
            event.ignore()
            return

        scene_pos = self.mapToScene(event.position().toPoint())
        parent_id = self._parent_at(scene_pos) or self._doc.project.root_id
        x, y, w, h = self._drop_geometry(parent_id, scene_pos, widget_type)

        from py_vui.app.editor.factory import create_node
        from py_vui.commands import AddNode

        parent_node = self._doc.get_node(parent_id)
        node = create_node(
            widget_type,
            parent_id=parent_id,
            parent=parent_node,
            x=x,
            y=y,
            w=w,
            h=h,
        )
        self._ignore_release = True
        self._palette_drag = False
        self._set_children_movable(True)
        if self._history:
            self._history.push(self._doc, AddNode(node))
        else:
            self._doc.project.nodes[node.id] = node
        self.rebuild()
        self.select_node(node.id)
        self._sync_resize_handles()
        self.document_dirty.emit()
        event.acceptProposedAction()

    def _parent_inner_size(self, parent_id: str) -> tuple[float, float]:
        parent = self._doc.get_node(parent_id)  # type: ignore[union-attr]
        if isinstance(parent, WindowNode):
            return parent.props.width, parent.props.height
        box = parent.layout.box
        return box.w, box.h

    def _drop_geometry(
        self, parent_id: str, scene_pos: QPointF, widget_type: str
    ) -> tuple[float, float, float, float]:
        parent_abs = self._abs_pos.get(parent_id, QPointF(0, 0))
        rel = scene_pos - parent_abs
        pw, ph = self._parent_inner_size(parent_id)

        defaults: dict[str, tuple[float, float]] = {
            "frame": (200.0, 150.0),
            "line_edit": (160.0, 28.0),
            "text_edit": (160.0, 80.0),
            "combo_box": (140.0, 28.0),
            "tab_widget": (280.0, 200.0),
            "group_box": (280.0, 200.0),
            "list_widget": (140.0, 100.0),
            "slider": (160.0, 28.0),
            "progress_bar": (160.0, 24.0),
            "date_edit": (120.0, 28.0),
            "time_edit": (100.0, 28.0),
            "table_widget": (240.0, 160.0),
            "dial": (80.0, 80.0),
            "scroll_area": (160.0, 100.0),
            "spin_box": (100.0, 28.0),
            "tool_button": (80.0, 32.0),
        }
        default_w, default_h = defaults.get(widget_type, (120.0, 32.0))

        margin = 8.0
        max_w = max(40.0, pw - margin * 2)
        max_h = max(24.0, ph - margin * 2)
        w = snap_size(min(default_w, max_w))
        h = snap_size(min(default_h, max_h))
        x = snap(max(margin, min(rel.x(), pw - w - margin)))
        y = snap(max(margin, min(rel.y(), ph - h - margin)))
        return x, y, w, h

    def _parent_at(self, scene_pos: QPointF) -> str | None:
        if self._doc is None:
            return None
        for hit in self._scene.items(scene_pos):
            item: NodeGraphicsItem | None = None
            if isinstance(hit, NodeGraphicsItem):
                item = hit
            else:
                parent = hit.parentItem()
                if isinstance(parent, NodeGraphicsItem):
                    item = parent
            if item is None:
                continue
            if item.node_id != self._doc.project.root_id:
                return item.node_id
        for hit in self._scene.items(scene_pos):
            if isinstance(hit, NodeGraphicsItem):
                return hit.node_id
            parent = hit.parentItem()
            if isinstance(parent, NodeGraphicsItem):
                return parent.node_id
        return None

    def mouseMoveEvent(self, event) -> None:
        if self._resize_active:
            self._update_resize(self.mapToScene(event.position().toPoint()))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._resize_active:
            self._finish_resize()
            event.accept()
            return
        super().mouseReleaseEvent(event)
        if self._ignore_release:
            self._ignore_release = False
            return
        if self._rebuild_guard or self._doc is None or self._history is None:
            return
        moved_ids = self.selected_node_ids()
        if not moved_ids:
            return
        updates: list[tuple[str, Rect]] = []
        for moved_id in moved_ids:
            item = self._items.get(moved_id)
            if item is None:
                continue
            node = self._doc.get_node(moved_id)
            parent_abs = self._abs_pos.get(node.parent_id or "", QPointF(0, 0))
            box = node.layout.box
            expected = parent_abs + QPointF(box.x, box.y)
            actual = item.pos()
            if abs(actual.x() - expected.x()) < 0.5 and abs(actual.y() - expected.y()) < 0.5:
                continue
            new_x = snap(actual.x() - parent_abs.x())
            new_y = snap(actual.y() - parent_abs.y())
            if abs(new_x - box.x) > 0.5 or abs(new_y - box.y) > 0.5:
                updates.append((moved_id, Rect(x=new_x, y=new_y, w=box.w, h=box.h)))
        if not updates:
            return
        if len(updates) == 1:
            self._history.push(
                self._doc, SetLayoutBox(node_id=updates[0][0], new_box=updates[0][1])
            )
        else:
            self._history.push(self._doc, SetLayoutBoxes(updates=updates))
        self.rebuild()
        for nid, _ in updates:
            self.select_node(nid)
        self.layout_changed.emit()

    def nudge_selected(self, dx: int, dy: int) -> None:
        if self._doc is None or self._history is None:
            return
        ids = self.selected_node_ids()
        if not ids:
            return
        updates = []
        for node_id in ids:
            box = self._doc.get_node(node_id).layout.box
            updates.append((node_id, Rect(x=box.x + dx, y=box.y + dy, w=box.w, h=box.h)))
        if len(updates) == 1:
            self._history.push(
                self._doc, SetLayoutBox(node_id=updates[0][0], new_box=updates[0][1])
            )
        else:
            self._history.push(self._doc, SetLayoutBoxes(updates=updates))
        self.rebuild()
        for nid, _ in updates:
            self.select_node(nid)
        self.layout_changed.emit()

    def keyPressEvent(self, event) -> None:
        step = 8 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1
        if event.key() == Qt.Key.Key_Left:
            self.nudge_selected(-step, 0)
            event.accept()
            return
        if event.key() == Qt.Key.Key_Right:
            self.nudge_selected(step, 0)
            event.accept()
            return
        if event.key() == Qt.Key.Key_Up:
            self.nudge_selected(0, -step)
            event.accept()
            return
        if event.key() == Qt.Key.Key_Down:
            self.nudge_selected(0, step)
            event.accept()
            return
        if event.key() == Qt.Key.Key_Delete and self._doc and self._history:
            node_id = self.selected_node_id()
            if node_id and node_id != self._doc.project.root_id:
                from py_vui.commands import RemoveSubtree

                self._history.push(self._doc, RemoveSubtree(root_id=node_id))
                self.rebuild()
                self.document_dirty.emit()
                return
        super().keyPressEvent(event)
