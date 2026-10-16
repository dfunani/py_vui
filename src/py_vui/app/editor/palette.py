"""Toolbox: categorised, searchable widget palette (drag onto the canvas or double-click)."""

from __future__ import annotations

from PySide6.QtCore import QMimeData, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QDrag
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from py_vui.app.editor.editor_theme import current_palette
from py_vui.app.editor.icons import glyph_icon
from py_vui.app.editor.mime import MIME_WIDGET
from py_vui.core.registry import WidgetSpec, all_specs

CATEGORIES = ("Window", "Layout", "Input", "Display", "Data", "Plugins")
ROLE_TYPE = Qt.ItemDataRole.UserRole


class PaletteList(QListWidget):
    """One category's widgets. Starts drags carrying the widget type id."""

    def __init__(self) -> None:
        super().__init__()
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setMovement(QListView.Movement.Static)
        self.setUniformItemSizes(True)
        self.setWordWrap(True)
        self.setSpacing(2)
        self.set_grid(True)

    def set_grid(self, grid: bool) -> None:
        if grid:
            self.setViewMode(QListView.ViewMode.IconMode)
            self.setIconSize(QSize(26, 26))
            self.setGridSize(QSize(78, 62))
        else:
            self.setViewMode(QListView.ViewMode.ListMode)
            self.setIconSize(QSize(18, 18))
            self.setGridSize(QSize())
        self.fit_height()

    def fit_height(self) -> None:
        n = sum(1 for i in range(self.count()) if not self.item(i).isHidden())
        if self.viewMode() == QListView.ViewMode.IconMode:
            cols = max(1, (self.viewport().width() or 240) // 78)
            rows = max(1, -(-n // cols))
            self.setFixedHeight(rows * 66 + 6)
        else:
            self.setFixedHeight(max(1, n) * 26 + 6)

    def resizeEvent(self, ev) -> None:
        super().resizeEvent(ev)
        QTimer.singleShot(0, self.fit_height)

    def startDrag(self, supported) -> None:
        item = self.currentItem()
        if item is None or not (item.flags() & Qt.ItemFlag.ItemIsDragEnabled):
            return
        mime = QMimeData()
        mime.setData(MIME_WIDGET, str(item.data(ROLE_TYPE)).encode())
        mime.setText(str(item.data(ROLE_TYPE)))
        drag = QDrag(self)
        drag.setMimeData(mime)
        px = item.icon().pixmap(32, 32)
        drag.setPixmap(px)
        drag.exec(Qt.DropAction.CopyAction)


class Palette(QWidget):
    #: double-click / Enter on a widget: insert it into the current container
    widgetActivated = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.framework = "tkinter"
        self._grid = True
        self._lists: dict[str, PaletteList] = {}
        self._headers: dict[str, QToolButton] = {}
        self._holders: dict[str, QWidget] = {}

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search widgets…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._apply_filter)
        self.view_btn = QToolButton()
        self.view_btn.setCheckable(True)
        self.view_btn.setChecked(True)
        self.view_btn.setText("▦")
        self.view_btn.setToolTip("Toggle icon grid / list")
        self.view_btn.toggled.connect(self.set_grid_mode)

        top = QHBoxLayout()
        top.setContentsMargins(6, 6, 6, 4)
        top.addWidget(self.search, 1)
        top.addWidget(self.view_btn)

        self._body = QWidget()
        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(0, 0, 0, 0)
        self._body_layout.setSpacing(0)
        self._empty = QLabel("No matching widgets")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.hide()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(self._body)
        self._scroll = scroll

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addLayout(top)
        outer.addWidget(scroll, 1)
        self.refresh()

    # -- population
    def set_framework(self, framework: str) -> None:
        if framework != self.framework:
            self.framework = framework
            self.refresh()

    def set_grid_mode(self, grid: bool) -> None:
        self._grid = grid
        self.view_btn.setText("▦" if grid else "☰")
        for lst in self._lists.values():
            lst.set_grid(grid)

    def refresh(self) -> None:
        """Rebuild from the registry (call after plugins are enabled/disabled)."""
        while self._body_layout.count():
            w = self._body_layout.takeAt(0).widget()
            if w is not None and w is not self._empty:
                w.deleteLater()
        self._lists.clear()
        self._headers.clear()
        self._holders.clear()
        by_cat: dict[str, list[WidgetSpec]] = {}
        for spec in all_specs():
            by_cat.setdefault(spec.category, []).append(spec)
        pal = current_palette()
        for cat in [*CATEGORIES, *[c for c in by_cat if c not in CATEGORIES]]:
            specs = by_cat.get(cat)
            if not specs:
                continue
            header = QToolButton()
            header.setObjectName("categoryHeader")
            header.setCheckable(True)
            header.setChecked(True)
            header.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            header.setSizePolicy(
                header.sizePolicy().horizontalPolicy(), header.sizePolicy().verticalPolicy()
            )
            header.setText(f"▾  {cat}")
            lst = PaletteList()
            lst.set_grid(self._grid)
            for spec in specs:
                lst.addItem(self._make_item(spec, pal.muted))
            lst.itemDoubleClicked.connect(self._on_activated)
            lst.itemActivated.connect(self._on_activated)
            header.toggled.connect(lambda on, h=header, c=cat, w=lst: self._toggle(h, c, w, on))
            holder = QWidget()
            hl = QVBoxLayout(holder)
            hl.setContentsMargins(0, 0, 0, 0)
            hl.setSpacing(0)
            hl.addWidget(header)
            hl.addWidget(lst)
            self._body_layout.addWidget(holder)
            self._lists[cat], self._headers[cat], self._holders[cat] = lst, header, holder
        self._body_layout.addWidget(self._empty)
        self._body_layout.addStretch(1)
        self._apply_filter()

    def _make_item(self, spec: WidgetSpec, muted: str) -> QListWidgetItem:
        item = QListWidgetItem(glyph_icon(spec.icon, size=26), spec.label)
        item.setData(ROLE_TYPE, spec.type)
        supported = spec.supports(self.framework)
        tip = spec.description or spec.label
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if spec.type == "window":
            tip = "The main window already exists in every project."
            item.setForeground(QBrush(QColor(muted)))
        elif not supported:
            tip = f"{spec.label} is not supported by {self.framework}; a placeholder is generated."
            item.setForeground(QBrush(QColor(muted)))
            item.setIcon(glyph_icon(spec.icon, size=26, color=muted))
        else:
            flags |= Qt.ItemFlag.ItemIsDragEnabled
        if spec.plugin:
            tip += "\n(plugin widget)"
        item.setFlags(flags)
        item.setToolTip(tip)
        item.setData(Qt.ItemDataRole.UserRole + 1, supported)
        item.setSizeHint(QSize(76, 60) if self._grid else QSize(100, 24))
        return item

    def _toggle(self, header: QToolButton, cat: str, lst: PaletteList, on: bool) -> None:
        header.setText(("▾  " if on else "▸  ") + cat)
        lst.setVisible(on)

    def _on_activated(self, item: QListWidgetItem) -> None:
        if item.flags() & Qt.ItemFlag.ItemIsDragEnabled:
            self.widgetActivated.emit(str(item.data(ROLE_TYPE)))

    # -- filter
    def _apply_filter(self) -> None:
        q = self.search.text().strip().lower()
        any_visible = False
        for cat, lst in self._lists.items():
            shown = 0
            for i in range(lst.count()):
                it = lst.item(i)
                hay = f"{it.text()} {it.data(ROLE_TYPE)} {cat}".lower()
                match = not q or q in hay
                it.setHidden(not match)
                shown += match
            self._holders[cat].setVisible(shown > 0)
            lst.fit_height()
            any_visible = any_visible or shown > 0
        self._empty.setVisible(not any_visible)

    def visible_types(self) -> list[str]:
        out = []
        for lst in self._lists.values():
            out.extend(
                str(lst.item(i).data(ROLE_TYPE))
                for i in range(lst.count())
                if not lst.item(i).isHidden()
            )
        return out

    def item_for(self, type_id: str) -> QListWidgetItem | None:
        for lst in self._lists.values():
            for i in range(lst.count()):
                if lst.item(i).data(ROLE_TYPE) == type_id:
                    return lst.item(i)
        return None
