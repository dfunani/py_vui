"""Example py_vui plugin: a coloured status LED (Tkinter canvas / Qt label)."""

from py_vui.codegen.base import EmitContext, EmitResult
from py_vui.core.registry import PropSpec, WidgetSpec

PLUGIN = {
    "id": "status_led",
    "name": "Status LED",
    "version": "1.0.0",
    "description": "A round indicator light with a configurable colour.",
}

_TYPE = "status_led"


def _emit_tk(ctx: EmitContext) -> EmitResult:
    v, color = ctx.var, str(ctx.node.props.get("color", "#22c55e"))
    return EmitResult(
        imports=["import tkinter as tk"],
        lines=[
            f"{v} = tk.Canvas({ctx.parent}, width=24, height=24, highlightthickness=0)",
            f"{v}.create_oval(3, 3, 21, 21, fill={color!r}, outline='')",
        ],
    )


def _emit_qt(ctx: EmitContext) -> EmitResult:
    mod = "PySide6" if ctx.framework == "pyside6" else "PyQt6"
    v, color = ctx.var, str(ctx.node.props.get("color", "#22c55e"))
    return EmitResult(
        imports=[f"from {mod} import QtWidgets"],
        lines=[
            f"{v} = QtWidgets.QLabel({ctx.parent})",
            f"{v}.setFixedSize(24, 24)",
            f"{v}.setStyleSheet('background: {color}; border-radius: 12px;')",
        ],
    )


def register(api) -> None:
    api.register_widget(WidgetSpec(
        type=_TYPE, label="Status LED", category="Plugins", icon="●",
        default_size=(24, 24), frameworks=frozenset({"tkinter", "pyside6", "pyqt6"}),
        props=(PropSpec("color", "color", "#22c55e", "Colour"),),
    ))
    api.register_emitter(_TYPE, "tkinter", _emit_tk)
    api.register_emitter(_TYPE, "pyside6", _emit_qt)
    api.register_emitter(_TYPE, "pyqt6", _emit_qt)
