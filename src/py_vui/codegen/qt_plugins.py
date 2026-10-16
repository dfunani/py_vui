"""Qt plugin emitters for the built-in "plugin" widgets (chart, color_picker).

They use the public ``register_plugin_emitter`` hook, exactly like third-party plugins.
Optional attributes on an emitter function are understood by the Qt adapter:

* ``qt_helpers``: names of runtime helper snippets the emitted code needs (see ``qt_helpers``)
* ``qt_signals``: ``{event_id: (signal_name, lambda_params, handler_arg_expr)}`` used to bind
  node events (``{w}`` in the expression stands for the widget variable)
"""

from __future__ import annotations

from py_vui.codegen.base import EmitContext, EmitResult, register_plugin_emitter
from py_vui.codegen.qt_common import asset_path, css_color, lit  # noqa: F401


def _numbers(values: list) -> list:
    out: list = []
    for v in values:
        try:
            out.append(float(v))
        except (TypeError, ValueError):
            return [str(x) for x in values]
    return out


def _pkg(ctx: EmitContext) -> str:
    return "PySide6" if ctx.framework == "pyside6" else "PyQt6"


def emit_chart(ctx: EmitContext) -> EmitResult:
    node = ctx.node
    p = node.props  # type: ignore[attr-defined]
    kind = p.get("kind", "line")
    x = _numbers(list(p.get("x") or []))
    y = [v if isinstance(v, float) else 0.0 for v in _numbers(list(p.get("y") or []))]
    if not x:
        x = list(range(len(y)))
    if kind != "hist":
        n = min(len(x), len(y))
        x, y = x[:n], y[:n]
    plot = {
        "line": "_axes.plot(_x, _y, marker='o')",
        "bar": "_axes.bar(_x, _y)",
        "scatter": "_axes.scatter(_x, _y)",
        "pie": "_axes.pie(_y, labels=[str(v) for v in _x], autopct='%1.0f%%')",
        "hist": "_axes.hist(_y)",
    }.get(kind, "_axes.plot(_x, _y)")
    pkg = _pkg(ctx)
    v, par = ctx.var, ctx.parent
    lines = [
        "try:",
        "    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as _FigureCanvas",
        "    from matplotlib.figure import Figure as _Figure",
        "",
        "    _figure = _Figure(layout='tight')",
        "    _axes = _figure.add_subplot(111)",
        f"    _x = {lit(x)}",
        f"    _y = {lit(y)}",
        f"    {plot}",
    ]
    if p.get("title"):
        lines.append(f"    _axes.set_title({p['title']!r})")
    if p.get("x_label") and kind not in {"pie"}:
        lines.append(f"    _axes.set_xlabel({p['x_label']!r})")
    if p.get("y_label") and kind not in {"pie"}:
        lines.append(f"    _axes.set_ylabel({p['y_label']!r})")
    lines += [
        f"    {v} = _FigureCanvas(_figure)",
        f"    {v}.setParent({par})",
        "except ImportError:",
        f"    {v} = QLabel('Install matplotlib to show this chart', {par})",
        f"    {v}.setAlignment(Qt.AlignmentFlag.AlignCenter)",
        f"    {v}.setWordWrap(True)",
    ]
    return EmitResult(
        imports=[
            "import os",
            f'os.environ.setdefault("QT_API", "{ctx.framework}")',
            f"from {pkg}.QtCore import Qt",
            f"from {pkg}.QtWidgets import QLabel",
        ],
        lines=lines,
        requirements=["matplotlib>=3.8"],
    )


emit_chart.qt_helpers = ()  # type: ignore[attr-defined]
emit_chart.qt_signals = {}  # type: ignore[attr-defined]


def emit_color_picker(ctx: EmitContext) -> EmitResult:
    p = ctx.node.props  # type: ignore[attr-defined]
    color = css_color(p.get("color"), "#ff0000")
    line = f"{ctx.var} = _ColorButton({p.get('text', 'Pick color')!r}, {color!r}, {ctx.parent})"
    return EmitResult(lines=[line])


emit_color_picker.qt_helpers = ("color_button",)  # type: ignore[attr-defined]
emit_color_picker.qt_signals = {  # type: ignore[attr-defined]
    "change": ("colorChanged", "_c, *_", "_c"),
}


def register() -> None:
    for fw in ("pyside6", "pyqt6"):
        register_plugin_emitter("chart", fw, emit_chart)
        register_plugin_emitter("color_picker", fw, emit_color_picker)
