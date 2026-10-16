"""Layout tab: geometry, anchors, state flags, container layout, flex item, grid cell, page."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtWidgets import QFormLayout, QLabel, QVBoxLayout, QWidget

from py_vui.app.editor.edit_context import EditContext, box_command
from py_vui.app.editor.prop_editors import (
    BoolEdit,
    ChoiceEdit,
    ListEdit,
    NumberEdit,
    RadioEdit,
    SplitterLabel,
    TextEdit,
    ValueEditor,
)
from py_vui.commands import Command, SetAttr
from py_vui.core.model import Anchors, ContainerLayout, Node
from py_vui.core.registry import get_spec

Getter = Callable[[Node], Any]
Maker = Callable[[Node, Any], Command]

_STICKY_ORDER = "nsew"


def _layout_of(n: Node) -> ContainerLayout:
    return (n.layout or ContainerLayout()).model_copy(deep=True)


def layout_field(name: str) -> tuple[Getter, Maker]:
    def get(n: Node) -> Any:
        return getattr(n.layout or ContainerLayout(), name)

    def make(n: Node, v: Any) -> Command:
        lay = _layout_of(n)
        setattr(lay, name, v)
        return SetAttr(n.id, "layout", lay, label="Change layout")

    return get, make


def layout_padding(side: str) -> tuple[Getter, Maker]:
    def get(n: Node) -> Any:
        return getattr((n.layout or ContainerLayout()).padding, side)

    def make(n: Node, v: Any) -> Command:
        lay = _layout_of(n)
        lay.padding = lay.padding.model_copy(update={side: float(v)})
        return SetAttr(n.id, "layout", lay, label="Change padding")

    return get, make


def flex_field(name: str) -> tuple[Getter, Maker]:
    def get(n: Node) -> Any:
        return getattr(n.flex, name)

    def make(n: Node, v: Any) -> Command:
        return SetAttr(n.id, "flex", n.flex.model_copy(update={name: v}), label="Change flex item")

    return get, make


def flex_margin(side: str) -> tuple[Getter, Maker]:
    def get(n: Node) -> Any:
        return getattr(n.flex.margin, side)

    def make(n: Node, v: Any) -> Command:
        fx = n.flex.model_copy(deep=True)
        fx.margin = fx.margin.model_copy(update={side: float(v)})
        return SetAttr(n.id, "flex", fx, label="Change margin")

    return get, make


def cell_field(name: str) -> tuple[Getter, Maker]:
    def get(n: Node) -> Any:
        return getattr(n.cell, name)

    def make(n: Node, v: Any) -> Command:
        return SetAttr(n.id, "cell", n.cell.model_copy(update={name: v}), label="Change cell")

    return get, make


def sticky_field(letter: str) -> tuple[Getter, Maker]:
    def get(n: Node) -> bool:
        return letter in n.cell.sticky

    def make(n: Node, v: Any) -> Command:
        chars = set(n.cell.sticky)
        (chars.add if v else chars.discard)(letter)
        sticky = "".join(c for c in _STICKY_ORDER if c in chars)
        return SetAttr(n.id, "cell", n.cell.model_copy(update={"sticky": sticky}),
                       label="Change sticky")

    return get, make


def anchor_field(side: str) -> tuple[Getter, Maker]:
    def get(n: Node) -> bool:
        return bool(getattr(n.anchors, side))

    def make(n: Node, v: Any) -> Command:
        a: Anchors = n.anchors.model_copy(update={side: bool(v)})
        return SetAttr(n.id, "anchors", a, label="Change anchors")

    return get, make


def attr_field(name: str) -> tuple[Getter, Maker]:
    def get(n: Node) -> Any:
        return getattr(n, name)

    def make(n: Node, v: Any) -> Command:
        return SetAttr(n.id, name, v, label=f"Change {name}")

    return get, make


class LayoutPage(QWidget):
    """Everything about *where* and *how* the selected widgets sit."""

    def __init__(self, ctx: EditContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self._building = True
        self._bound: list[tuple[ValueEditor, Getter]] = []
        self._named: dict[str, ValueEditor] = {}
        self._box_editors: dict[str, NumberEdit] = {}
        self._sig: tuple | None = None
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(8, 4, 8, 8)
        self._content: QWidget | None = None
        self._rebuild()

    # ------------------------------------------------------------- structure
    def _signature(self) -> tuple:
        doc = self.ctx.doc
        out = []
        for n in self.ctx.nodes:
            parent = doc.project.nodes.get(n.parent_id) if n.parent_id else None
            out.append((
                n.type, n.layout.mode if n.layout else None,
                parent.layout.mode if parent and parent.layout else None,
                parent.type if parent else None,
                len(n.layout.row_weights) if n.layout else 0,
                len(n.layout.column_weights) if n.layout else 0,
                len(parent.props.get("tabs", [])) if parent else 0,
            ))
        return tuple(out)

    def _rebuild(self) -> None:
        self._building = True
        if self._content is not None:
            self._outer.removeWidget(self._content)
            self._content.setParent(None)
            self._content.deleteLater()
        self._bound.clear()
        self._named.clear()
        self._box_editors.clear()
        self._content = QWidget()
        lay = QVBoxLayout(self._content)
        lay.setContentsMargins(0, 0, 0, 0)
        self._outer.insertWidget(0, self._content)
        self._sig = self._signature()
        nodes = self.ctx.nodes
        if not nodes:
            self._building = False
            return
        doc = self.ctx.doc
        parents = [doc.project.nodes.get(n.parent_id) if n.parent_id else None for n in nodes]
        pmodes = {p.layout.mode if p and p.layout else "absolute" for p in parents}
        pmode = pmodes.pop() if len(pmodes) == 1 else None
        is_window = all(n.type in ("window", "toplevel") for n in nodes)
        all_container = all(get_spec(n.type).container for n in nodes)

        # geometry
        if not is_window:
            self._geometry(lay, pmode)
            if pmode in (None, "absolute"):
                self._anchors(lay)
        self._state(lay)
        if all_container and len({n.type for n in nodes}) >= 1:
            self._container(lay)
        if pmode == "flex":
            self._flex_item(lay)
        if pmode == "grid":
            self._grid_cell(lay)
        paged = {bool(p and get_spec(p.type).paged) for p in parents}
        if paged == {True} and len({p.id for p in parents if p}) == 1:
            self._page(lay, parents[0])  # type: ignore[arg-type]
        lay.addStretch(1)
        self._building = False
        self.refresh()

    # ------------------------------------------------------------- binders
    def _form(self, lay: QVBoxLayout, title: str) -> QFormLayout:
        lay.addWidget(SplitterLabel(title))
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        lay.addLayout(form)
        return form

    def _bind(self, form: QFormLayout, text: str, editor: ValueEditor,
              fm: tuple[Getter, Maker], *, discrete: bool = False, name: str | None = None,
              ) -> ValueEditor:
        get, make = fm
        if text:
            form.addRow(text, editor)
        else:
            form.addRow(editor)
        self._bound.append((editor, get))
        if name:
            self._named[name] = editor
        editor.valueChanged.connect(lambda v: self._apply(make, v, discrete))
        return editor

    def _apply(self, make: Maker, value: Any, discrete: bool) -> None:
        if self._building:
            return
        self.ctx.push([make(n, value) for n in self.ctx.nodes], discrete=discrete)

    def editor(self, name: str) -> ValueEditor:
        return self._named[name]

    # ------------------------------------------------------------- sections
    def _geometry(self, lay: QVBoxLayout, pmode: str | None) -> None:
        form = self._form(lay, "Position & size")
        for key, label, lo in (("x", "X", None), ("y", "Y", None), ("w", "Width", 1),
                               ("h", "Height", 1)):
            ed = NumberEdit(minimum=lo)
            ed.valueChanged.connect(lambda v, k=key: self._box_edit(k, v))
            form.addRow(ed.scrub_label(label), ed)
            self._box_editors[key] = ed
            if key in "xy" and pmode in ("flex", "grid"):
                ed.setEnabled(False)
                ed.setToolTip("Position is computed by the parent's flex/grid layout.")

    def _box_edit(self, key: str, value: Any) -> None:
        if self._building:
            return
        updates = [(n.id, n.box.model_copy(update={key: float(value)})) for n in self.ctx.nodes]
        self.ctx.push_cmd(box_command(updates))

    def _anchors(self, lay: QVBoxLayout) -> None:
        form = self._form(lay, "Anchors")
        for side in ("left", "top", "right", "bottom"):
            self._bind(form, "", BoolEdit(f"Pin {side}"), anchor_field(side), discrete=True,
                       name=f"anchor_{side}")

    def _state(self, lay: QVBoxLayout) -> None:
        form = self._form(lay, "State")
        self._bind(form, "", BoolEdit("Enabled"), attr_field("enabled"), discrete=True,
                   name="enabled")
        self._bind(form, "", BoolEdit("Visible"), attr_field("visible"), discrete=True,
                   name="visible")
        self._bind(form, "", BoolEdit("Locked (no move/resize)"), attr_field("locked"),
                   discrete=True, name="locked")
        self._bind(form, "Tooltip", TextEdit(), attr_field("tooltip"), name="tooltip")
        tab = NumberEdit(minimum=-1)
        tab.setToolTip("-1 = automatic")
        get, make = attr_field("tab_index")

        def get_tab(n: Node) -> int:
            return -1 if n.tab_index is None else n.tab_index

        def make_tab(n: Node, v: Any) -> Command:
            return make(n, None if int(v) < 0 else int(v))

        self._bind(form, "Tab index", tab, (get_tab, make_tab), name="tab_index")

    def _container(self, lay: QVBoxLayout) -> None:
        form = self._form(lay, "Container layout")
        mode_ed = RadioEdit([("absolute", "Absolute"), ("flex", "Flex"), ("grid", "Grid")])
        self._bind(form, "Mode", mode_ed, layout_field("mode"), discrete=True, name="mode")
        mode = self.ctx.first.layout.mode if self.ctx.first.layout else "absolute"
        if mode == "flex":
            self._bind(form, "Direction", RadioEdit([("row", "Row"), ("column", "Column")]),
                       layout_field("direction"), discrete=True, name="direction")
            self._bind(form, "Gap", NumberEdit(minimum=0, is_float=True, decimals=1),
                       layout_field("gap"), name="gap")
            self._bind(form, "Justify", ChoiceEdit(
                ("start", "center", "end", "space_between", "space_around")),
                layout_field("justify"), discrete=True, name="justify")
            self._bind(form, "Align", ChoiceEdit(("start", "center", "end", "stretch")),
                       layout_field("align"), discrete=True, name="align")
            self._bind(form, "", BoolEdit("Wrap"), layout_field("wrap"), discrete=True,
                       name="wrap")
        elif mode == "grid":
            self._bind(form, "Column gap", NumberEdit(minimum=0, is_float=True, decimals=1),
                       layout_field("column_gap"), name="column_gap")
            self._bind(form, "Row gap", NumberEdit(minimum=0, is_float=True, decimals=1),
                       layout_field("row_gap"), name="row_gap")
            self._bind(form, "Column weights", ListEdit(numeric=True, add_default="1", height=64),
                       layout_field("column_weights"), name="column_weights")
            self._bind(form, "Row weights", ListEdit(numeric=True, add_default="1", height=64),
                       layout_field("row_weights"), name="row_weights")
        if mode in ("flex", "grid"):
            for side in ("top", "right", "bottom", "left"):
                self._bind(form, f"Padding {side}", NumberEdit(minimum=0, is_float=True, decimals=1),
                           layout_padding(side), name=f"padding_{side}")

    def _flex_item(self, lay: QVBoxLayout) -> None:
        form = self._form(lay, "Flex item")
        self._bind(form, "Grow", NumberEdit(is_float=True, minimum=0, decimals=1, step=0.5),
                   flex_field("grow"), name="grow")
        self._bind(form, "Align self",
                   ChoiceEdit(("auto", "start", "center", "end", "stretch")),
                   flex_field("align_self"), discrete=True, name="align_self")
        for side in ("top", "right", "bottom", "left"):
            self._bind(form, f"Margin {side}", NumberEdit(minimum=0, is_float=True, decimals=1),
                       flex_margin(side), name=f"margin_{side}")

    def _grid_cell(self, lay: QVBoxLayout) -> None:
        form = self._form(lay, "Grid cell")
        for key, label in (("row", "Row"), ("column", "Column"), ("row_span", "Row span"),
                           ("column_span", "Column span")):
            lo = 1 if key.endswith("span") else 0
            self._bind(form, label, NumberEdit(minimum=lo, maximum=999), cell_field(key),
                       name=key)
        for letter, text in (("n", "Stick north"), ("s", "Stick south"), ("e", "Stick east"),
                             ("w", "Stick west")):
            self._bind(form, "", BoolEdit(text), sticky_field(letter), discrete=True,
                       name=f"sticky_{letter}")

    def _page(self, lay: QVBoxLayout, parent: Node) -> None:
        form = self._form(lay, "Tab page")
        tabs = list(parent.props.get("tabs", []))
        ed = ChoiceEdit([str(i) for i in range(max(len(tabs), 1))], empty_label="0")
        for i, t in enumerate(tabs):
            ed.combo().setItemText(i, f"{i} - {t}")
        get, make = attr_field("page")

        def make_page(n: Node, v: Any) -> Command:
            return make(n, int(v or 0))

        self._bind(form, "Page", ed, (lambda n: str(n.page), make_page), discrete=True,
                   name="page")
        if not tabs:
            form.addRow(QLabel("Parent has no tabs."))

    # ------------------------------------------------------------- refresh
    def refresh(self) -> None:
        if not self.ctx.nodes:
            return
        if self._signature() != self._sig:
            self._rebuild()
            return
        was, self._building = self._building, True
        try:
            nodes = self.ctx.nodes
            first = nodes[0]
            for key, ed in self._box_editors.items():
                vals = [getattr(n.box, key) for n in nodes]
                ed.set_value(vals[0])
                ed.set_mixed(any(v != vals[0] for v in vals[1:]))
            for ed, get in self._bound:
                vals = [get(n) for n in nodes]
                ed.set_value(get(first))
                ed.set_mixed(any(v != vals[0] for v in vals[1:]))
        finally:
            self._building = was
