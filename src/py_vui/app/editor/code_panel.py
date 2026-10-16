"""Built-in code editor panel: Handlers, Module code, Generated, Requirements."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from py_vui.app.editor.code_tabs import (
    GeneratedTab,
    HandlersTab,
    ModuleTab,
    RequirementsEditor,
)

if TYPE_CHECKING:
    from py_vui.commands import History
    from py_vui.core.document import ProjectDocument


class CodePanel(QWidget):
    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bound = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget()
        self.handlers = HandlersTab()
        self.module = ModuleTab()
        self.generated = GeneratedTab()
        self.requirements = RequirementsEditor()
        self.tabs.addTab(self.handlers, "Handlers")
        self.tabs.addTab(self.module, "Module code")
        self.tabs.addTab(self.generated, "Generated")
        self.tabs.addTab(self.requirements, "Requirements")
        lay.addWidget(self.tabs)
        for t in (self.handlers, self.module, self.requirements):
            t.changed.connect(self._on_edit)
        self.tabs.currentChanged.connect(lambda _i: self._refresh_current())

    def bind(self, doc: ProjectDocument, history: History, service: Any) -> None:
        for t in (self.handlers, self.module, self.generated, self.requirements):
            t.doc, t.history, t.service = doc, history, service
        self._bound = True
        self.refresh()

    def open_handler(self, name: str) -> None:
        """Show the Handlers tab with ``name`` selected and the editor focused."""
        self.tabs.setCurrentWidget(self.handlers)
        if self.handlers.select(name):
            self.handlers.editor.setFocus()

    def refresh(self) -> None:
        if not self._bound:
            return
        # cheap tabs always; the (potentially heavy) generated view only when visible
        self.handlers.refresh()
        self.module.refresh()
        self.requirements.refresh()
        if self.tabs.currentWidget() is self.generated:
            self.generated.refresh()

    def _refresh_current(self) -> None:
        w = self.tabs.currentWidget()
        if self._bound and hasattr(w, "refresh"):
            w.refresh()

    def _on_edit(self) -> None:
        self.changed.emit()
