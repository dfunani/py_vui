"""Canvas + rulers + window-switcher tab bar, assembled as one widget."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QGridLayout, QTabBar, QVBoxLayout, QWidget

from py_vui.app.editor.canvas import DesignCanvas
from py_vui.app.editor.rulers import RULER_THICKNESS, Ruler
from py_vui.core.document import ProjectDocument

_ADD_TAB_ID = "__add__"


class CanvasHost(QWidget):
    windowSwitched = Signal(str)
    addDialogRequested = Signal()
    closeWindowRequested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.canvas = DesignCanvas()
        self.tabs = QTabBar()
        self.tabs.setExpanding(False)
        self.tabs.setTabsClosable(True)
        self.tabs.setDrawBase(False)
        self.tabs.setDocumentMode(True)
        self._ids: list[str] = []
        self._blocked = False
        self.top_ruler = Ruler(self.canvas, True)
        self.left_ruler = Ruler(self.canvas, False)
        corner = QWidget()
        corner.setFixedSize(RULER_THICKNESS, RULER_THICKNESS)
        self._corner = corner

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(0)
        grid.addWidget(corner, 0, 0)
        grid.addWidget(self.top_ruler, 0, 1)
        grid.addWidget(self.left_ruler, 1, 0)
        grid.addWidget(self.canvas, 1, 1)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self.tabs)
        outer.addLayout(grid)
        self.tabs.currentChanged.connect(self._on_tab)
        self.tabs.tabCloseRequested.connect(self._on_close)

    def set_rulers_visible(self, on: bool) -> None:
        for w in (self.top_ruler, self.left_ruler, self._corner):
            w.setVisible(on)

    # -- tabs
    def rebuild_tabs(self, doc: ProjectDocument, active: str | None) -> None:
        wins = doc.windows()
        ids = [w.id for w in wins]
        names = [str(w.props.get("title") or w.name) for w in wins]
        self._blocked = True
        try:
            # tabs: windows..., then "+"
            while self.tabs.count():
                self.tabs.removeTab(0)
            for w, name in zip(wins, names, strict=False):
                idx = self.tabs.addTab(("🪟 " if w.type == "window" else "🗔 ") + name)
                self.tabs.setTabToolTip(idx, w.name)
                if w.type == "window":
                    self.tabs.setTabButton(idx, QTabBar.ButtonPosition.RightSide, None)
            plus = self.tabs.addTab("＋")
            self.tabs.setTabToolTip(plus, "Add a dialog window")
            self.tabs.setTabButton(plus, QTabBar.ButtonPosition.RightSide, None)
            self._ids = [*ids, _ADD_TAB_ID]
            if active in ids:
                self.tabs.setCurrentIndex(ids.index(active))
        finally:
            self._blocked = False

    def select_tab(self, window_id: str) -> None:
        if window_id in self._ids:
            self._blocked = True
            self.tabs.setCurrentIndex(self._ids.index(window_id))
            self._blocked = False

    def _on_tab(self, index: int) -> None:
        if self._blocked or not 0 <= index < len(self._ids):
            return
        wid = self._ids[index]
        if wid == _ADD_TAB_ID:
            prev = max(0, index - 1)
            self._blocked = True
            self.tabs.setCurrentIndex(prev)
            self._blocked = False
            self.addDialogRequested.emit()
            return
        self.windowSwitched.emit(wid)

    def _on_close(self, index: int) -> None:
        if 0 <= index < len(self._ids) and self._ids[index] != _ADD_TAB_ID:
            self.closeWindowRequested.emit(self._ids[index])

    def keyboard_focus(self) -> None:
        self.canvas.setFocus(Qt.FocusReason.OtherFocusReason)
