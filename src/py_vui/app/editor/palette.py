from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import QAbstractItemView, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from py_vui.app.editor.canvas import MIME_WIDGET

WIDGET_TYPES = [
    ("frame", "Frame"),
    ("label", "Label"),
    ("button", "Button"),
    ("line_edit", "Line Edit"),
    ("checkbox", "Checkbox"),
]


class WidgetPalette(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self._list = QListWidget()
        self._list.setDragEnabled(True)
        self._list.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        for type_id, label in WIDGET_TYPES:
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, type_id)
            self._list.addItem(item)
        self._list.startDrag = self._start_drag  # type: ignore[method-assign]
        layout.addWidget(self._list)

    def _start_drag(self, supported_actions) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        widget_type = item.data(Qt.ItemDataRole.UserRole)
        drag = QDrag(self._list)
        mime = drag.mimeData()
        mime.setData(MIME_WIDGET, widget_type.encode())
        drag.exec(Qt.DropAction.CopyAction)
