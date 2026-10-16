"""Example py_vui plugin: a segmented toggle group for Tkinter and Qt (PySide6 / PyQt6).

Shows one widget with emitters for several frameworks. Items are a list property; the selected
index starts at ``current``.
"""

from py_vui.codegen.base import EmitContext, EmitResult
from py_vui.core.registry import PropSpec, WidgetSpec

PLUGIN = {
    "id": "toggle_group",
    "name": "Toggle Group",
    "version": "1.0.0",
    "description": "Row of mutually exclusive toggle buttons (Tkinter, PySide6, PyQt6).",
}

_TYPE = "toggle_group"


def _items(ctx: EmitContext) -> list[str]:
    items = ctx.node.props.get("items") or ["One", "Two"]
    return [str(i) for i in items]


def _emit_tk(ctx: EmitContext) -> EmitResult:
    v, items = ctx.var, _items(ctx)
    cur = int(ctx.node.props.get("current", 0))
    return EmitResult(
        imports=["import tkinter as tk"],
        lines=[
            f"{v} = tk.Frame({ctx.parent})",
            f"{v}.selected = tk.IntVar(value={cur})",
            f"for i, text in enumerate({items!r}):",
            f"    tk.Radiobutton({v}, text=text, value=i, variable={v}.selected,",
            "                   indicatoron=False, padx=10, pady=4).pack(side='left')",
        ],
    )


def _emit_qt(ctx: EmitContext) -> EmitResult:
    mod = "PySide6" if ctx.framework == "pyside6" else "PyQt6"
    v, items = ctx.var, _items(ctx)
    cur = int(ctx.node.props.get("current", 0))
    return EmitResult(
        imports=[f"from {mod} import QtWidgets"],
        lines=[
            f"{v} = QtWidgets.QWidget({ctx.parent})",
            f"{v}_layout = QtWidgets.QHBoxLayout({v})",
            f"{v}_layout.setContentsMargins(0, 0, 0, 0)",
            f"{v}_layout.setSpacing(0)",
            f"{v}_group = QtWidgets.QButtonGroup({v})",
            f"{v}_group.setExclusive(True)",
            f"for i, text in enumerate({items!r}):",
            "    b = QtWidgets.QPushButton(text)",
            "    b.setCheckable(True)",
            f"    b.setChecked(i == {cur})",
            f"    {v}_group.addButton(b, i)",
            f"    {v}_layout.addWidget(b)",
        ],
    )


def register(api) -> None:
    api.register_widget(WidgetSpec(
        type=_TYPE, label="Toggle Group", category="Plugins", icon="▤",
        default_size=(240, 32), frameworks=frozenset({"tkinter", "pyside6", "pyqt6"}),
        props=(
            PropSpec("items", "list", ["Day", "Week", "Month"], "Options"),
            PropSpec("current", "int", 0, "Selected index", minimum=0),
        ),
    ))
    api.register_emitter(_TYPE, "tkinter", _emit_tk)
    api.register_emitter(_TYPE, "pyside6", _emit_qt)
    api.register_emitter(_TYPE, "pyqt6", _emit_qt)
