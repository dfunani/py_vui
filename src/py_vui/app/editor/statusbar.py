"""Status bar: cursor, selection size, zoom, framework and a clickable diagnostics counter."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QStatusBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from py_vui.core.document import Diagnostic


class DiagnosticsDialog(QDialog):
    """Lists ``ProjectDocument.diagnostics()``; activating a row selects the node."""

    nodeActivated = Signal(str)

    def __init__(
        self, diagnostics: list[Diagnostic], names: dict[str, str], parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Diagnostics")
        self.resize(520, 320)
        lay = QVBoxLayout(self)
        self.list = QListWidget()
        for d in diagnostics:
            who = names.get(d.node_id or "", "")
            icon = "⛔" if d.level == "error" else "⚠"
            item = QListWidgetItem(f"{icon}  {who + ': ' if who else ''}{d.message}")
            item.setData(Qt.ItemDataRole.UserRole, d.node_id)
            self.list.addItem(item)
        if not diagnostics:
            self.list.addItem("No problems found.")
        self.list.itemActivated.connect(self._activate)
        self.list.itemDoubleClicked.connect(self._activate)
        lay.addWidget(self.list)

    def _activate(self, item: QListWidgetItem) -> None:
        nid = item.data(Qt.ItemDataRole.UserRole)
        if nid:
            self.nodeActivated.emit(str(nid))


class EditorStatusBar(QStatusBar):
    diagnosticsClicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.cursor_label = QLabel("x: –  y: –")
        self.sel_label = QLabel("")
        self.zoom_label = QLabel("100%")
        self.fw_label = QLabel("")
        self.diag_btn = QToolButton()
        self.diag_btn.setAutoRaise(True)
        self.diag_btn.setToolTip("Show diagnostics")
        self.diag_btn.clicked.connect(self.diagnosticsClicked.emit)
        self.set_diagnostics(0)
        for w in (self.cursor_label, self.sel_label, self.zoom_label, self.fw_label):
            w.setMinimumWidth(80)
            self.addPermanentWidget(w)
        self.addPermanentWidget(self.diag_btn)

    def set_cursor(self, x: float, y: float) -> None:
        self.cursor_label.setText(f"x: {x:.0f}  y: {y:.0f}")

    def set_selection(self, text: str) -> None:
        self.sel_label.setText(text)

    def set_zoom(self, zoom: float) -> None:
        self.zoom_label.setText(f"{round(zoom * 100)}%")

    def set_framework(self, fw: str) -> None:
        self.fw_label.setText(fw)

    def set_diagnostics(self, count: int) -> None:
        self.diag_btn.setText(f"⚠ {count}" if count else "✓ 0")
        self.diag_btn.setProperty("count", count)
