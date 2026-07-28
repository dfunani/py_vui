from __future__ import annotations

from PySide6.QtCore import QMimeData, Qt
from PySide6.QtGui import QDrag, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from py_vui.app.editor.canvas import MIME_WIDGET

WIDGET_CATEGORIES: list[tuple[str, list[tuple[str, str, str]]]] = [
    (
        "Containers",
        [
            ("frame", "Frame", "□"),
            ("group_box", "Group Box", "⊞"),
            ("scroll_area", "Scroll Area", "↕"),
            ("tab_widget", "Tabs", "≡"),
        ],
    ),
    (
        "Controls",
        [
            ("label", "Label", "T"),
            ("button", "Button", "◉"),
            ("tool_button", "Tool Button", "⊙"),
            ("checkbox", "Checkbox", "☑"),
            ("radio_button", "Radio Button", "◎"),
        ],
    ),
    (
        "Inputs",
        [
            ("line_edit", "Line Edit", "▭"),
            ("text_edit", "Text Edit", "≣"),
            ("combo_box", "Combo Box", "▾"),
            ("spin_box", "Spin Box", "⊕"),
            ("slider", "Slider", "⊷"),
            ("date_edit", "Date Edit", "▤"),
            ("time_edit", "Time Edit", "◷"),
        ],
    ),
    (
        "Display",
        [
            ("list_widget", "List Widget", "☰"),
            ("table_widget", "Table Widget", "⊡"),
            ("progress_bar", "Progress Bar", "▬"),
            ("dial", "Dial", "◌"),
        ],
    ),
]

_ALL_WIDGETS: list[tuple[str, str, str]] = [
    item for _, items in WIDGET_CATEGORIES for item in items
]


class WidgetPalette(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("WidgetPalette")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        search_row = QWidget()
        search_row.setObjectName("PaletteSearch")
        search_style = "background: #181825; border-bottom: 1px solid #313244; padding: 0;"
        search_row.setStyleSheet(f"QWidget#PaletteSearch { {search_style} }")
        search_layout = QVBoxLayout(search_row)
        search_layout.setContentsMargins(8, 6, 8, 6)
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search widgets…")
        self._search.setStyleSheet(
            "QLineEdit { background: #1e1e2e; border: 1px solid #45475a; border-radius: 5px;"
            " padding: 4px 8px; color: #cdd6f4; font-size: 12px; }"
            "QLineEdit:focus { border: 1px solid #89b4fa; }"
        )
        self._search.textChanged.connect(self._on_search)
        search_layout.addWidget(self._search)
        outer.addWidget(search_row)

        self._list = QListWidget()
        self._list.setDragEnabled(True)
        self._list.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self._list.setSpacing(0)

        widget_style = "background: #1e1e2e; border: none; outline: none;"
        item_style = "padding: 0; margin: 0;"
        item_hover_style = "background: #313244; border-radius: 5px;"
        item_selected_style = "background: #45475a; border-radius: 5px; color: #cdd6f4;"
        self._list.setStyleSheet(
            f"QListWidget { {widget_style} }"
            f"QListWidget::item { {item_style} }"
            f"QListWidget::item:hover { {item_hover_style} }"
            f"QListWidget::item:selected { {item_selected_style} }"
        )
        self._list.startDrag = self._start_drag  # type: ignore[method-assign]
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        outer.addWidget(self._list)

        self._populate_all()

    def _make_header_item(self, title: str) -> QListWidgetItem:
        item = QListWidgetItem(f"  {title.upper()}")
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        font = QFont()
        font.setPointSize(9)
        font.setBold(True)
        font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 120)
        item.setFont(font)
        item.setForeground(Qt.GlobalColor.darkGray)
        item.setData(Qt.ItemDataRole.UserRole, None)
        return item

    def _make_widget_item(self, type_id: str, label: str, icon: str) -> QListWidgetItem:
        item = QListWidgetItem(f"   {icon}  {label}")
        item.setData(Qt.ItemDataRole.UserRole, type_id)
        font = QFont()
        font.setPointSize(12)
        item.setFont(font)
        return item

    def _populate_all(self) -> None:
        self._list.clear()
        for category, widgets in WIDGET_CATEGORIES:
            self._list.addItem(self._make_header_item(category))
            for type_id, label, icon in widgets:
                self._list.addItem(self._make_widget_item(type_id, label, icon))

    def _on_search(self, text: str) -> None:
        query = text.strip().lower()
        self._list.clear()
        if not query:
            self._populate_all()
            return
        matches = [
            (type_id, label, icon)
            for type_id, label, icon in _ALL_WIDGETS
            if query in label.lower() or query in type_id.lower()
        ]
        if not matches:
            empty = QListWidgetItem("  No results")
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            self._list.addItem(empty)
            return
        for type_id, label, icon in matches:
            self._list.addItem(self._make_widget_item(type_id, label, icon))

    def _start_drag(self, supported_actions) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        widget_type = item.data(Qt.ItemDataRole.UserRole)
        if not widget_type:
            return
        mime = QMimeData()
        mime.setData(MIME_WIDGET, widget_type.encode())
        drag = QDrag(self._list)
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.CopyAction)
