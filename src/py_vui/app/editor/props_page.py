"""Properties / Style tabs: a form generated from PropSpecs, grouped by ``PropSpec.group``."""

from __future__ import annotations

from typing import Any

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from py_vui.app.editor.edit_context import EditContext
from py_vui.app.editor.prop_editors import (
    ColorEdit,
    FileEdit,
    FontEdit,
    JsonEdit,
    SplitterLabel,
    ValueEditor,
    make_editor,
)
from py_vui.commands import SetField
from py_vui.core.registry import PropSpec
from py_vui.core.theme import resolve_style

_COLOR_TOKEN = {
    "background": "background",
    "foreground": "foreground",
    "border_color": "border_color",
    "hover_color": "hover_color",
}
_DISCRETE_KINDS = {"bool", "choice"}


class _Row:
    def __init__(self, spec: PropSpec, editor: ValueEditor, label: QLabel,
                 reset: QToolButton | None) -> None:
        self.spec = spec
        self.editor = editor
        self.label = label
        self.reset = reset


class PropertiesPage(QWidget):
    """Edits ``node.props`` (section="props") or ``node.style`` (section="style")."""

    def __init__(self, ctx: EditContext, specs: tuple[PropSpec, ...], section: str,
                 *, hidden: frozenset[str] = frozenset(), parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self.section = section
        self._rows: dict[str, _Row] = {}
        self._building = True
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 4, 8, 8)
        groups: dict[str, list[PropSpec]] = {}
        for sp in specs:
            if sp.name in hidden:
                continue
            groups.setdefault(sp.group, []).append(sp)
        if section == "style" and len(groups) == 1:
            groups = self._style_groups(next(iter(groups.values())))
        for gname, gspecs in groups.items():
            if len(groups) > 1 or gname != "General":
                outer.addWidget(SplitterLabel(gname))
            form = QFormLayout()
            form.setContentsMargins(0, 0, 0, 0)
            form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
            for sp in gspecs:
                self._add_row(form, sp)
            outer.addLayout(form)
        outer.addStretch(1)
        self._building = False
        self.refresh()

    @staticmethod
    def _style_groups(specs: list[PropSpec]) -> dict[str, list[PropSpec]]:
        buckets = {
            "Colors": ("background", "foreground", "border_color", "hover_color"),
            "Font": ("font_family", "font_size", "bold", "italic", "underline"),
            "Shape": ("border_width", "corner_radius", "relief", "cursor"),
        }
        by_name = {s.name: s for s in specs}
        out: dict[str, list[PropSpec]] = {}
        used: set[str] = set()
        for g, names in buckets.items():
            items = [by_name[n] for n in names if n in by_name]
            if items:
                out[g] = items
                used.update(s.name for s in items)
        rest = [s for s in specs if s.name not in used]
        if rest:
            out["Other"] = rest
        return out

    def _add_row(self, form: QFormLayout, sp: PropSpec) -> None:
        if sp.name == "font_family" and self.section == "style":
            editor: ValueEditor = FontEdit()
        else:
            editor = make_editor(sp, importer=self.ctx.asset_importer)
        if isinstance(editor, FileEdit):
            editor.project_dir = self.ctx.project_dir
            editor.importer = self.ctx.asset_importer
        label = QLabel(sp.title)
        if sp.help:
            label.setToolTip(sp.help)
            editor.setToolTip(sp.help)
        reset: QToolButton | None = None
        field: QWidget = editor
        if self.section == "style":
            reset = QToolButton()
            reset.setText("↺")
            reset.setToolTip("Reset to theme")
            reset.clicked.connect(lambda _=False, n=sp.name: self._reset(n))
            holder = QWidget()
            hl = QHBoxLayout(holder)
            hl.setContentsMargins(0, 0, 0, 0)
            hl.setSpacing(2)
            hl.addWidget(editor, 1)
            hl.addWidget(reset)
            field = holder
        form.addRow(label, field)
        self._rows[sp.name] = _Row(sp, editor, label, reset)
        editor.valueChanged.connect(lambda v, n=sp.name: self._edited(n, v))

    # ----------------------------------------------------------------- values
    def _store(self, node: Any) -> dict[str, Any]:
        return node.props if self.section == "props" else node.style

    def _current(self, node: Any, sp: PropSpec) -> Any:
        return self._store(node).get(sp.name, sp.default)

    def refresh(self) -> None:
        nodes = self.ctx.nodes
        if not nodes:
            return
        theme = self.ctx.doc.project.theme
        resolved = resolve_style(theme, nodes[0].type, nodes[0].style)
        for name, row in self._rows.items():
            values = [self._current(n, row.spec) for n in nodes]
            row.editor.set_value(values[0])
            mixed = any(v != values[0] for v in values[1:])
            row.editor.set_mixed(mixed)
            f: QFont = row.label.font()
            f.setItalic(mixed)
            row.label.setFont(f)
            if isinstance(row.editor, ColorEdit) and self.section == "style":
                token = _COLOR_TOKEN.get(name)
                row.editor.set_fallback(str(resolved.get(token, "")) if token else "")
            if row.reset is not None:
                row.reset.setEnabled(any(name in n.style for n in nodes))

    def editor(self, name: str) -> ValueEditor:
        return self._rows[name].editor

    # ----------------------------------------------------------------- edits
    def _edited(self, name: str, value: Any) -> None:
        if self._building:
            return
        row = self._rows[name]
        if isinstance(row.editor, JsonEdit) and not row.editor.is_valid():
            return
        sp = row.spec
        if self.section == "style" and value == sp.default:
            value = None  # equal to "inherit": drop the key instead of storing a no-op
        cmds = [
            SetField(n.id, self.section, name, value, label=f"Change {sp.title}")  # type: ignore[arg-type]
            for n in self.ctx.nodes
        ]
        self.ctx.push(cmds, discrete=sp.kind in _DISCRETE_KINDS)
        if row.reset is not None:
            row.reset.setEnabled(any(name in n.style for n in self.ctx.nodes))
        if isinstance(row.editor, ColorEdit) and self.section == "style":
            self.refresh()

    def _reset(self, name: str) -> None:
        cmds = [
            SetField(n.id, "style", name, None, label="Reset to theme")
            for n in self.ctx.nodes if name in n.style
        ]
        self.ctx.push(cmds, discrete=True)
        self.refresh()
