"""Preferences, keyboard shortcuts and About dialogs."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from py_vui.app.editor.dialogs.common import (
    FRAMEWORK_INFO,
    add_buttons,
    get_setting,
    make_dialog_base,
    set_setting,
)

PROJECT_URL = "https://github.com/dfunani/py_vui"

SHORTCUTS: list[tuple[str, str, str]] = [
    ("File", "New project", "Ctrl+N"),
    ("File", "Open project", "Ctrl+O"),
    ("File", "Save", "Ctrl+S"),
    ("File", "Save as", "Ctrl+Shift+S"),
    ("File", "Export code", "Ctrl+E"),
    ("File", "Quit", "Ctrl+Q"),
    ("Edit", "Undo", "Ctrl+Z"),
    ("Edit", "Redo", "Ctrl+Shift+Z"),
    ("Edit", "Cut", "Ctrl+X"),
    ("Edit", "Copy", "Ctrl+C"),
    ("Edit", "Paste", "Ctrl+V"),
    ("Edit", "Duplicate", "Ctrl+D"),
    ("Edit", "Delete selection", "Delete"),
    ("Edit", "Select all", "Ctrl+A"),
    ("Canvas", "Nudge selection", "Arrow keys"),
    ("Canvas", "Nudge by 10 px", "Shift+Arrow keys"),
    ("Canvas", "Zoom in / out", "Ctrl+= / Ctrl+-"),
    ("Canvas", "Reset zoom", "Ctrl+0"),
    ("Canvas", "Bring to front / send to back", "Ctrl+] / Ctrl+["),
    ("Canvas", "Group in container", "Ctrl+G"),
    ("Run", "Live preview", "F5"),
    ("Run", "Stop preview", "Shift+F5"),
    ("Code editor", "Find / replace", "Ctrl+F"),
    ("Code editor", "Completion", "Ctrl+Space"),
    ("Code editor", "Indent / dedent", "Tab / Shift+Tab"),
    ("Help", "Keyboard shortcuts", "F1"),
]


class PreferencesDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lay = make_dialog_base(self, "Preferences", (420, 300))
        form = QFormLayout()
        self.theme = QComboBox()
        for v, t in (("system", "System"), ("light", "Light"), ("dark", "Dark")):
            self.theme.addItem(t, v)
        self.autosave = QSpinBox()
        self.autosave.setRange(0, 3600)
        self.autosave.setSuffix(" s")
        self.autosave.setSpecialValueText("Off")
        self.framework = QComboBox()
        for fw, (label, _d) in FRAMEWORK_INFO.items():
            self.framework.addItem(label, fw)
        self.snap = QCheckBox("Snap to grid")
        self.grid = QSpinBox()
        self.grid.setRange(2, 100)
        self.grid.setSuffix(" px")
        form.addRow("Editor theme", self.theme)
        form.addRow("Autosave every", self.autosave)
        form.addRow("Default framework", self.framework)
        form.addRow("", self.snap)
        form.addRow("Grid size", self.grid)
        lay.addLayout(form)
        add_buttons(self, lay)
        self.load()

    def load(self) -> None:
        self.theme.setCurrentIndex(max(self.theme.findData(get_setting("editor_theme", "system")), 0))
        self.autosave.setValue(int(get_setting("autosave_seconds", 60) or 0))
        self.framework.setCurrentIndex(
            max(self.framework.findData(get_setting("default_framework", "tkinter")), 0))
        self.snap.setChecked(bool(get_setting("snap_enabled", True)))
        self.grid.setValue(int(get_setting("grid_size", 8) or 8))

    def values(self) -> dict[str, object]:
        return {
            "editor_theme": self.theme.currentData(),
            "autosave_seconds": self.autosave.value(),
            "default_framework": self.framework.currentData(),
            "snap_enabled": self.snap.isChecked(),
            "grid_size": self.grid.value(),
        }

    def accept(self) -> None:
        for k, v in self.values().items():
            set_setting(k, v)
        super().accept()


class ShortcutsDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lay = make_dialog_base(self, "Keyboard shortcuts", (480, 520))
        self.filter = QLineEdit()
        self.filter.setPlaceholderText("Filter…")
        self.filter.textChanged.connect(self._apply_filter)
        self.table = QTableWidget(len(SHORTCUTS), 3)
        self.table.setHorizontalHeaderLabels(["Area", "Action", "Shortcut"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        for r, row in enumerate(SHORTCUTS):
            for c, text in enumerate(row):
                self.table.setItem(r, c, QTableWidgetItem(text))
        self.table.resizeColumnsToContents()
        lay.addWidget(self.filter)
        lay.addWidget(self.table, 1)
        add_buttons(self, lay, QDialogButtonBox.StandardButton.Close)

    def _apply_filter(self, text: str) -> None:
        t = text.lower()
        for r, row in enumerate(SHORTCUTS):
            self.table.setRowHidden(r, bool(t) and t not in " ".join(row).lower())


def app_version() -> str:
    try:
        from py_vui import __version__

        return __version__
    except ImportError:
        from importlib.metadata import PackageNotFoundError, version

        try:
            return version("py_vui")
        except PackageNotFoundError:
            return "unknown"


class AboutDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lay = make_dialog_base(self, "About py_vui", (420, 300))
        title = QLabel("py_vui")
        f = title.font()
        f.setPointSize(f.pointSize() + 8)
        f.setBold(True)
        title.setFont(f)
        lay.addWidget(title)
        self.version_label = QLabel(f"Version {app_version()}")
        lay.addWidget(self.version_label)
        lay.addWidget(QLabel(
            "Visual drag-and-drop builder that generates Python GUI code for Tkinter,\n"
            "CustomTkinter, PySide6 / PyQt6 and Kivy. Everything is free; no accounts, no network."))
        lic = QLabel("License: MIT")
        lay.addWidget(lic)
        link = QLabel(f'<a href="{PROJECT_URL}">{PROJECT_URL}</a>')
        link.setOpenExternalLinks(True)
        link.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        lay.addWidget(link)
        lay.addWidget(QLabel("Built with Python, Pydantic and Qt for Python (PySide6).\n"
                             "Created by Delali Funani and contributors."))
        lay.addStretch(1)
        add_buttons(self, lay, QDialogButtonBox.StandardButton.Close)
