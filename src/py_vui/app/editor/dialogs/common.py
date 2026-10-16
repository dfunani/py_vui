"""Shared helpers for the editor dialogs."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout, QWidget

from py_vui.core import catalog  # noqa: F401  (register built-ins)
from py_vui.core.registry import FRAMEWORKS, all_specs

FRAMEWORK_INFO: dict[str, tuple[str, str]] = {
    "tkinter": ("Tkinter", "Python's built-in toolkit. No install needed; classic native look."),
    "customtkinter": ("CustomTkinter", "Modern, themeable Tk widgets with rounded corners."),
    "pyside6": ("PySide6", "Official Qt for Python bindings (LGPL). Rich, native widgets."),
    "pyqt6": ("PyQt6", "Qt 6 bindings by Riverbank. Same widgets as PySide6."),
    "kivy": ("Kivy", "Touch-first, GPU-accelerated UIs for desktop and mobile."),
}
assert set(FRAMEWORK_INFO) == set(FRAMEWORKS)


def supported_count(framework: str) -> tuple[int, int]:
    """``(widgets supported natively, total widgets)`` for a framework."""
    specs = all_specs()
    return sum(1 for s in specs if s.supports(framework)), len(specs)


def get_setting(key: str, default: Any = None) -> Any:
    try:
        from py_vui.services import settings
    except ImportError:
        return default
    try:
        return settings.get(key, default)
    except Exception:
        return default


def set_setting(key: str, value: Any) -> None:
    try:
        from py_vui.services import settings

        settings.set(key, value)
    except Exception:
        pass


def add_buttons(dlg: QDialog, layout: QVBoxLayout, buttons: QDialogButtonBox.StandardButton
                = QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
                ) -> QDialogButtonBox:
    box = QDialogButtonBox(buttons)
    box.accepted.connect(dlg.accept)
    box.rejected.connect(dlg.reject)
    layout.addWidget(box)
    return box


def make_dialog_base(dlg: QDialog, title: str, size: tuple[int, int] | None = None) -> QVBoxLayout:
    dlg.setWindowTitle(title)
    if size:
        dlg.resize(*size)
    return QVBoxLayout(dlg)


def parent_widget(w: QWidget | None) -> QWidget | None:
    return w
