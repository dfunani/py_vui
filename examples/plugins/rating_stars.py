"""Example py_vui plugin: a clickable 1-5 star rating widget (Tkinter / CustomTkinter).

Install: copy this file to ``~/.py_vui/plugins/`` (all projects) or ``<project>/plugins/``, then
enable it with ``py_vui plugins enable rating_stars`` (or in the editor's Plugins dialog).
See ``py_vui.plugins.api`` for the full plugin guide.
"""

from py_vui.codegen.base import EmitContext, EmitResult
from py_vui.core.registry import PropSpec, WidgetSpec

PLUGIN = {
    "id": "rating_stars",
    "name": "Rating Stars",
    "version": "1.0.0",
    "description": "Clickable star rating (1-10 stars) for Tkinter and CustomTkinter.",
}

_TYPE = "rating_stars"


def _emit_tk(ctx: EmitContext) -> EmitResult:
    p = ctx.node.props
    count = max(1, int(p.get("stars", 5)))
    value = max(0, min(count, int(p.get("value", 3))))
    v = ctx.var
    return EmitResult(
        imports=["import tkinter as tk"],
        lines=[
            f"{v} = tk.Frame({ctx.parent})",
            f"{v}.rating = {value}",
            f"{v}_stars = []",
            f"def {v}_paint(n):",
            f"    {v}.rating = n",
            f"    for i, lbl in enumerate({v}_stars):",
            "        lbl.configure(text='\\u2605' if i < n else '\\u2606')",
            f"for i in range({count}):",
            f"    lbl = tk.Label({v}, text='\\u2606', font=('TkDefaultFont', 16), cursor='hand2')",
            "    lbl.pack(side='left')",
            f"    lbl.bind('<Button-1>', lambda e, n=i + 1: {v}_paint(n))",
            f"    {v}_stars.append(lbl)",
            f"{v}_paint({value})",
        ],
    )


def register(api) -> None:
    api.register_widget(WidgetSpec(
        type=_TYPE, label="Rating Stars", category="Plugins", icon="★",
        default_size=(160, 32), frameworks=frozenset({"tkinter", "customtkinter"}),
        props=(
            PropSpec("stars", "int", 5, "Number of stars", minimum=1, maximum=10),
            PropSpec("value", "int", 3, "Initial rating", minimum=0, maximum=10),
        ),
        description="Read the chosen rating from the widget's ``.rating`` attribute.",
    ))
    api.register_emitter(_TYPE, "tkinter", _emit_tk)
    api.register_emitter(_TYPE, "customtkinter", _emit_tk)
