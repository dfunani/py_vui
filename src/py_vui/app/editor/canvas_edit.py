"""Inline text editing on the canvas (double-click a label, button, tab title…)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt
from PySide6.QtWidgets import QLineEdit

from py_vui.app.editor.canvas_geometry import tab_at, tab_rects
from py_vui.commands import SetField

if TYPE_CHECKING:
    from py_vui.app.editor.canvas import DesignCanvas

TEXT_KEYS = {
    "label": "text",
    "button": "text",
    "tool_button": "text",
    "checkbox": "text",
    "radio": "text",
    "switch": "text",
    "entry": "text",
    "color_picker": "text",
    "label_frame": "title",
    "chart": "title",
}


class InlineEditMixin:
    def begin_inline_edit(self: DesignCanvas, node_id: str, pt: QPointF | None = None) -> None:
        if self.doc is None:
            return
        node = self.doc.get_node(node_id)
        rect = self.node_scene_rect(node_id)
        key = TEXT_KEYS.get(node.type)
        index: int | None = None
        if node.type == "tabview" and pt is not None:
            index = tab_at(node, pt.x() - rect.x(), pt.y() - rect.y())
            if index is None:
                return
            tr = tab_rects(node)[index]
            rect = QRectF(rect.x() + tr[0], rect.y() + tr[1], tr[2], tr[3])
            key = "tabs"
            value = str((node.props.get("tabs") or [])[index])
        elif key is not None:
            value = str(node.props.get(key, ""))
            if node.type in ("window", "toplevel"):
                return  # titles are edited in the inspector
        else:
            return
        self.cancel_inline_edit()
        edit = QLineEdit(value, self.viewport())
        top_left = self.mapFromScene(rect.topLeft())
        bottom_right = self.mapFromScene(rect.bottomRight())
        edit.setGeometry(QRectF(top_left, bottom_right).toRect().adjusted(0, 0, 0, 0))
        edit.setMinimumWidth(60)
        edit.setFrame(True)
        edit.selectAll()
        edit.show()
        edit.setFocus()
        edit.editingFinished.connect(self.commit_inline_edit)
        edit.installEventFilter(self)
        self._edit = edit
        self._edit_target = (node_id, key, index)

    def eventFilter(self: DesignCanvas, obj, ev) -> bool:
        if (
            obj is self._edit
            and ev.type() == QEvent.Type.KeyPress
            and ev.key() == Qt.Key.Key_Escape
        ):
            self.cancel_inline_edit()
            return True
        return super().eventFilter(obj, ev)

    def commit_inline_edit(self: DesignCanvas) -> None:
        edit, target = self._edit, self._edit_target
        if edit is None or target is None or self.doc is None:
            return
        self._edit = None
        self._edit_target = None
        node_id, key, index = target
        text = edit.text()
        edit.deleteLater()
        node = self.doc.project.nodes.get(node_id)
        if node is None:
            return
        if index is not None:
            tabs = list(node.props.get("tabs") or [])
            if index < len(tabs) and tabs[index] != text and text:
                tabs[index] = text
                self.push(SetField(node_id, "props", "tabs", tabs, label="Rename tab"))
        elif str(node.props.get(key, "")) != text:
            self.push(SetField(node_id, "props", key, text, label="Edit text"))

    def cancel_inline_edit(self: DesignCanvas) -> None:
        if self._edit is not None:
            edit, self._edit, self._edit_target = self._edit, None, None
            edit.blockSignals(True)
            edit.deleteLater()
