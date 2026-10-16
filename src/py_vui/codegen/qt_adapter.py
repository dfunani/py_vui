"""PySide6 / PyQt6 code generator (one emitter, two bindings).

Generated project layout::

    main.py            QApplication + theme + show
    ui.py              build_ui() -> root widget; WIDGETS / WINDOWS (/ ACTIONS) registries
    theme.py           STYLESHEET + palette generated from the project theme
    handlers.py        user callbacks (merge safe)           custom.py   never overwritten
    requirements.txt   README.md

``GenOptions.layout == "single"`` produces one self-contained ``main.py`` instead.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from py_vui.codegen import qt_helpers, qt_plugins
from py_vui.codegen.base import (
    HEADER,
    Adapter,
    EmitContext,
    GeneratedFile,
    GenOptions,
    handlers_file,
    plugin_emitter,
    register_adapter,
)
from py_vui.codegen.merge_regions import render_handlers_module
from py_vui.codegen.qt_common import (
    CURSORS,
    PYQT6,
    PYSIDE6,
    Binding,
    asset_path,
    import_lines,
    lit,
    node_qss,
    num,
    py_names,
    theme_code,
    to_int,
)
from py_vui.core.document import ProjectDocument, slug
from py_vui.core.model import ContainerLayout, Node, Project
from py_vui.core.registry import get_spec, has_spec

AF = "Qt.AlignmentFlag."
_BUTTON_LIKE = {"button", "tool_button", "checkbox", "radio", "switch"}

#: Qt class used for the placeholder of widgets a framework cannot render
_PLACEHOLDER = "QLabel"


def _amp(text: Any) -> str:
    """Escape ``&`` so Qt does not turn it into a keyboard mnemonic."""
    return str(text).replace("&", "&&")


def _r(v: float) -> int:
    return int(round(v))


@dataclass
class Ctx:
    """Where the children of a container go."""

    node: Node
    widget: str
    mode: str  # absolute | flex | grid | splitter
    layout: str | None = None
    spec: ContainerLayout | None = None
    design: tuple[float, float] = (0.0, 0.0)
    anchors: str | None = None
    flow: bool = False
    grow: bool = False
    count: int = 0
    #: python expression for the design size when it is only known at run time
    design_expr: str | None = None


@dataclass
class _Sig:
    target: str
    signal: str
    params: str
    arg: str


class QtEmitter:
    """Builds the python source for one project and one Qt binding."""

    def __init__(self, project: Project, binding: Binding, *, single: bool) -> None:
        self.project = project
        self.b = binding
        self.single = single
        self.doc = ProjectDocument(project)
        self.names = py_names(self.doc.variable_names())
        self.theme = project.theme
        self.body: list[str] = []
        self.helpers: set[str] = set()
        self.extra_imports: list[str] = []
        self.qss: list[str] = []
        self.dialogs: list[str] = []
        self.radio_groups: dict[str, str] = {}
        self.group_names: dict[str, str] = {}
        self.has_menus = False
        self._counter = 0
        self.node_vars: dict[str, str] = {}
        self.root = project.nodes[project.root_id]

    # ------------------------------------------------------------------ plumbing
    def w(self, text: str = "") -> None:
        for ln in text.split("\n"):
            self.body.append(ln)

    def uid(self, prefix: str) -> str:
        self._counter += 1
        return f"_{prefix}{self._counter}"

    def href(self, name: str) -> str:
        return name if self.single else f"handlers.{name}"

    def has_handler(self, name: str | None) -> bool:
        return bool(name) and name in self.project.handlers

    def props(self, node: Node) -> dict[str, Any]:
        p = get_spec(node.type).default_props()
        p.update(node.props)
        return p

    def asset(self, value: str) -> str:
        self.helpers.add("asset")
        return f"_asset({asset_path(self.project, value)!r})"

    # --------------------------------------------------------------------- driver
    def emit_ui_body(self) -> None:
        self.emit_window(self.root, None)

    def emit_window(self, node: Node, parent_var: str | None) -> None:
        var = self.names[node.id]
        p = self.props(node)
        is_main = parent_var is None
        menus = p.get("menus") if is_main else None
        if is_main:
            cls = "QMainWindow" if menus else "QWidget"
            self.w(f"{var} = {cls}()")
        else:
            cls = "QDialog"
            self.w(f"{var} = QDialog({parent_var})")
        self.w(f"{var}.setObjectName({var!r})")
        self.w(f"{var}.setWindowTitle({str(p.get('title', ''))!r})")
        if p.get("icon"):
            self.w(f"{var}.setWindowIcon(QIcon({self.asset(p['icon'])}))")
        if p.get("always_on_top"):
            self.w(f"{var}.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)")
        if node.tooltip:
            self.w(f"{var}.setToolTip({node.tooltip!r})")
        if not is_main:
            if p.get("modal"):
                self.w(f"{var}.setModal(True)")
            self.w(f"{var}.setProperty('start_visible', {not p.get('start_hidden')!r})")
        elif p.get("maximized"):
            self.w(f"{var}.setWindowState({var}.windowState() | Qt.WindowState.WindowMaximized)")
        if cls == "QWidget":
            self.w(f"{var}.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)")
        width, height = to_int(p.get("width"), 640), to_int(p.get("height"), 480)
        central = var
        if cls == "QMainWindow":
            central = f"_{var}_central"
            self.w(f"{central} = QWidget({var})")
            self.w(f"{central}.setObjectName({var + '_central'!r})")
            self.w(f"{var}.setCentralWidget({central})")
        ctx = self.make_ctx(node, central, (width, height))
        self.qss.append(node_qss(self.theme, node, var))
        self.w(f"WIDGETS[{var!r}] = {var}")
        self.w(f"WINDOWS[{var!r}] = {var}")
        self.emit_children(node, ctx)
        self.finish_ctx(ctx)
        if is_main:
            for dlg in self.doc.children(node.id):
                if dlg.type == "toplevel":
                    self.emit_window(dlg, var)
        if menus:
            self.emit_menus(var, menus)
        self.window_geometry(var, p, width, height, bool(menus))
        self.wire_events(node, var)
        if not is_main:
            self.dialogs.append(var)

    def window_geometry(self, var: str, p: dict, width: int, height: int, menus: bool) -> None:
        h_expr = str(height)
        if menus:
            self.w(f"_{var}_menu_height = {var}.menuBar().sizeHint().height()")
            h_expr = f"{height} + _{var}_menu_height"
        rx, ry = p.get("resizable_x", True), p.get("resizable_y", True)
        if rx and ry:
            self.w(f"{var}.resize({width}, {h_expr})")
        elif not rx and not ry:
            self.w(f"{var}.setFixedSize({width}, {h_expr})")
        elif not rx:
            self.w(f"{var}.resize({width}, {h_expr})")
            self.w(f"{var}.setFixedWidth({width})")
        else:
            self.w(f"{var}.resize({width}, {h_expr})")
            self.w(f"{var}.setFixedHeight({h_expr})")
        mw, mh = to_int(p.get("min_width")), to_int(p.get("min_height"))
        if (mw or mh) and (rx and ry):
            self.w(f"{var}.setMinimumSize({mw}, {mh})")

    # --------------------------------------------------------------- containers
    def make_ctx(self, node: Node, widget: str, design: tuple[float, float]) -> Ctx:
        lay = node.layout or ContainerLayout()
        mode = lay.mode
        ctx = Ctx(node, widget, mode, spec=lay, design=design)
        pad = lay.padding
        margins = f"{_r(pad.left)}, {_r(pad.top)}, {_r(pad.right)}, {_r(pad.bottom)}"
        lv = "_" + widget.lstrip("_") + "_layout"
        if mode == "flex":
            ctx.layout = lv
            ctx.grow = any(k.flex.grow > 0 for k in self.doc.children(node.id))
            if lay.wrap:
                ctx.flow = True
                self.helpers.add("flow")
                gap = _r(lay.gap)
                vertical = ", True" if lay.direction == "column" else ""
                self.w(f"{lv} = _FlowLayout({widget}, ({margins}), {gap}, {gap}{vertical})")
            else:
                cls = "QHBoxLayout" if lay.direction == "row" else "QVBoxLayout"
                self.w(f"{lv} = {cls}({widget})")
                self.w(f"{lv}.setSpacing({_r(lay.gap)})")
                self.w(f"{lv}.setContentsMargins({margins})")
        elif mode == "grid":
            ctx.layout = lv
            self.w(f"{lv} = QGridLayout({widget})")
            self.w(f"{lv}.setContentsMargins({margins})")
            self.w(f"{lv}.setHorizontalSpacing({_r(lay.column_gap)})")
            self.w(f"{lv}.setVerticalSpacing({_r(lay.row_gap)})")
            for i, wt in enumerate(lay.column_weights):
                if wt:
                    self.w(f"{lv}.setColumnStretch({i}, {int(wt)})")
            for i, wt in enumerate(lay.row_weights):
                if wt:
                    self.w(f"{lv}.setRowStretch({i}, {int(wt)})")
        leading = lay.justify in ("center", "end", "space_around")
        if mode == "flex" and not ctx.flow and not ctx.grow and leading:
            self.w(f"{lv}.addStretch(1)")
        return ctx

    def finish_ctx(self, ctx: Ctx | list[Ctx]) -> None:
        if isinstance(ctx, list):
            for c in ctx:
                self.finish_ctx(c)
            return
        if ctx.mode == "flex" and not ctx.flow and not ctx.grow and ctx.spec:
            if ctx.spec.justify in ("start", "center", "space_around"):
                self.w(f"{ctx.layout}.addStretch(1)")
        elif ctx.mode == "splitter":
            node = ctx.node
            sizes = [to_int(s) for s in (node.props.get("sizes") or []) if str(s).strip()]
            if not sizes:
                horiz = node.props.get("orientation", "horizontal") == "horizontal"
                sizes = [
                    _r(k.box.w if horiz else k.box.h) for k in self.doc.children(node.id)
                ]
            if sizes:
                self.w(f"{ctx.widget}.setSizes({sizes!r})")

    def emit_children(self, parent: Node, ctxs: Ctx | list[Ctx]) -> None:
        for child in self.doc.children(parent.id):
            if child.type == "toplevel":
                continue
            if isinstance(ctxs, list):
                ctx = ctxs[max(0, min(child.page, len(ctxs) - 1))]
            else:
                ctx = ctxs
            self.emit_node(child, ctx)

    # --------------------------------------------------------------- one widget
    def emit_node(self, node: Node, ctx: Ctx) -> None:
        var = self.names[node.id]
        self.node_vars[node.id] = var
        spec = get_spec(node.type)
        parent = ctx.widget
        item = var
        wrap = None
        m = node.flex.margin
        if ctx.mode == "flex" and (m.top or m.right or m.bottom or m.left):
            wrap = f"_{var}_wrap"
            self.w(f"{wrap} = QWidget({parent})")
            self.w(f"{wrap}_layout = QVBoxLayout({wrap})")
            self.w(f"{wrap}_layout.setSpacing(0)")
            self.w(
                f"{wrap}_layout.setContentsMargins({_r(m.left)}, {_r(m.top)}, "
                f"{_r(m.right)}, {_r(m.bottom)})"
            )
            parent = wrap
            item = wrap
        self.w("")
        self.w(f"# {node.name} ({node.type})")
        props = self.props(node)
        box = None  # extra container around the widget (slider value label / scroll area)
        if node.type == "slider" and props.get("show_value"):
            box = f"_{var}_box"
            vertical = props.get("orientation") == "vertical"
            self.w(f"{box} = QWidget({parent})")
            self.w(f"{box}_layout = {'QVBoxLayout' if vertical else 'QHBoxLayout'}({box})")
            self.w(f"{box}_layout.setContentsMargins(0, 0, 0, 0)")
            self.w(f"{box}_layout.setSpacing(6)")
            parent_w = box
        else:
            parent_w = parent
        qcls, child_ctx, placeholder = self.create(node, var, parent_w)
        inner = var
        if box:
            lab = f"_{var}_value"
            vertical = props.get("orientation") == "vertical"
            self.w(f"{box}_layout.addWidget({var}, 1)")
            self.w(f"{lab} = QLabel(str({var}.value()), {box})")
            self.w(f"{lab}.setMinimumWidth(32)")
            align = "AlignHCenter" if vertical else "AlignRight"
            self.w(f"{lab}.setAlignment({AF}{align} | {AF}AlignVCenter)")
            self.w(f"{box}_layout.addWidget({lab})")
            self.w(f"{var}.valueChanged.connect(lambda _v, _l={lab}: _l.setText(str(_v)))")
            inner = box
        elif node.type == "canvas" and props.get("scrollable") and qcls == "QWidget":
            scroll = f"_{var}_scroll"
            self.w(f"{scroll} = QScrollArea({parent})")
            self.w(f"{scroll}.setFrameShape(QFrame.Shape.NoFrame)")
            self.w(f"{var}.resize({_r(node.box.w)}, {_r(node.box.h)})")
            self.w(f"{scroll}.setWidget({var})")
            inner = scroll
        if wrap:
            self.w(f"{wrap}_layout.addWidget({inner})")
            item = wrap
        else:
            item = inner
        self.common(node, var)
        if inner != var and not node.visible:
            self.w(f"{inner}.setVisible(False)")
        self.qss.append(node_qss(self.theme, node, var, placeholder=placeholder))
        self.place(node, item, ctx, inner)
        self.w(f"WIDGETS[{var!r}] = {var}")
        self.wire_events(node, var, qcls)
        if spec.container and child_ctx is not None:
            self.emit_children(node, child_ctx)
            self.finish_ctx(child_ctx)
            self.post_container(node, var)

    def post_container(self, node: Node, var: str) -> None:
        if node.type == "tabview":
            cur = to_int(self.props(node).get("current"), 0)
            if cur:
                self.w(f"{var}.setCurrentIndex({cur})")

    def common(self, node: Node, var: str) -> None:
        self.w(f"{var}.setObjectName({var!r})")
        if node.tooltip:
            self.w(f"{var}.setToolTip({node.tooltip!r})")
        if not node.enabled:
            self.w(f"{var}.setEnabled(False)")
        if not node.visible:
            self.w(f"{var}.setVisible(False)")
        cur = CURSORS.get(str(node.style.get("cursor") or ""))
        if cur:
            self.w(f"{var}.setCursor(Qt.CursorShape.{cur})")

    # ------------------------------------------------------------------ placing
    def place(self, node: Node, item: str, ctx: Ctx, var: str) -> None:
        if ctx.mode == "absolute":
            b = node.box
            self.w(f"{item}.setGeometry({_r(b.x)}, {_r(b.y)}, {_r(b.w)}, {_r(b.h)})")
            a = node.anchors
            if not (a.left and a.top and not a.right and not a.bottom):
                if ctx.anchors is None:
                    ctx.anchors = f"_{ctx.widget.lstrip('_')}_anchors"
                    self.helpers.add("anchors")
                    dw, dh = ctx.design
                    size = ctx.design_expr or f"({_r(dw)}, {_r(dh)})"
                    self.w(f"{ctx.anchors} = _Anchors({ctx.widget}, {size})")
                self.w(
                    f"{ctx.anchors}.add({item}, {_r(b.x)}, {_r(b.y)}, {_r(b.w)}, {_r(b.h)}, "
                    f"{a.left}, {a.top}, {a.right}, {a.bottom})"
                )
        elif ctx.mode == "splitter":
            self.w(f"{ctx.widget}.addWidget({item})")
        elif ctx.mode == "flex":
            self.place_flex(node, item, ctx, var)
        elif ctx.mode == "grid":
            self.place_grid(node, item, ctx)

    def _policy(self, item: str, horizontal: bool, vertical: bool) -> None:
        """Let ``item`` grow along the given axes (Qt buttons etc. are Fixed by default)."""
        e = "QSizePolicy.Policy.Expanding"
        if horizontal and vertical:
            self.w(f"{item}.setSizePolicy({e}, {e})")
        elif horizontal:
            self.w(f"{item}.setSizePolicy({e}, {item}.sizePolicy().verticalPolicy())")
        elif vertical:
            self.w(f"{item}.setSizePolicy({item}.sizePolicy().horizontalPolicy(), {e})")

    def _flex_size(self, target: str, node: Node, ctx: Ctx, wd: int, ht: int) -> str | None:
        """Size constraints for one flex item; returns the cross-axis alignment flag."""
        lay = ctx.spec or ContainerLayout()
        row = lay.direction == "row"
        grow = node.flex.grow
        main_w, main_name = (wd, "Width") if row else (ht, "Height")
        cross_w, cross_name = (ht, "Height") if row else (wd, "Width")
        align = lay.align if node.flex.align_self == "auto" else node.flex.align_self
        if grow > 0:
            self.w(f"{target}.setMinimum{main_name}({main_w})")
        else:
            self.w(f"{target}.setFixed{main_name}({main_w})")
        flag = None
        if align != "stretch":
            self.w(f"{target}.setFixed{cross_name}({cross_w})")
            flag = {
                ("column", "start"): "AlignLeft", ("column", "center"): "AlignHCenter",
                ("column", "end"): "AlignRight", ("row", "start"): "AlignTop",
                ("row", "center"): "AlignVCenter", ("row", "end"): "AlignBottom",
            }[(lay.direction, align)]
        main_grow = grow > 0
        cross_fill = align == "stretch"
        self._policy(target, main_grow if row else cross_fill, cross_fill if row else main_grow)
        return flag

    def place_flex(self, node: Node, item: str, ctx: Ctx, var: str) -> None:
        lay = ctx.spec or ContainerLayout()
        lv = ctx.layout
        m = node.flex.margin
        wd = _r(node.box.w + m.left + m.right)
        ht = _r(node.box.h + m.top + m.bottom)
        if ctx.flow:
            self.w(f"{item}.setFixedSize({wd}, {ht})")
            self.w(f"{lv}.addWidget({item})")
            return
        if node.visible and ctx.count > 0 and not ctx.grow:
            if lay.justify == "space_between":
                self.w(f"{lv}.addStretch(1)")
            elif lay.justify == "space_around":
                self.w(f"{lv}.addStretch(2)")
        if node.visible:
            ctx.count += 1
        flag = self._flex_size(item, node, ctx, wd, ht)
        if item != var:  # wrapped (per-child margin): the widget itself follows the same rules
            self._flex_size(var, node, ctx, _r(node.box.w), _r(node.box.h))
        args = [item]
        grow = node.flex.grow
        stretch = max(1, _r(grow)) if grow > 0 else 0
        if flag:
            args += [str(stretch), AF + flag]
        elif stretch:
            args.append(str(stretch))
        self.w(f"{lv}.addWidget({', '.join(args)})")

    def place_grid(self, node: Node, item: str, ctx: Ctx) -> None:
        c = node.cell
        s = c.sticky.lower()
        fill_h = "e" in s and "w" in s
        fill_v = "n" in s and "s" in s
        flags = []
        if not fill_h:
            flags.append("AlignRight" if "e" in s else "AlignLeft" if "w" in s else "AlignHCenter")
        if not fill_v:
            flags.append("AlignBottom" if "s" in s else "AlignTop" if "n" in s else "AlignVCenter")
        wd, ht = _r(node.box.w), _r(node.box.h)
        self.w(f"{item}.setMinimumWidth({wd})" if fill_h else f"{item}.setFixedWidth({wd})")
        self.w(f"{item}.setMinimumHeight({ht})" if fill_v else f"{item}.setFixedHeight({ht})")
        self._policy(item, fill_h, fill_v)
        args = [item, str(c.row), str(c.column), str(c.row_span), str(c.column_span)]
        if flags:
            args.append(" | ".join(AF + f for f in flags))
        self.w(f"{ctx.layout}.addWidget({', '.join(args)})")

    # -------------------------------------------------------------- widget factory
    def create(self, node: Node, var: str, parent: str) -> tuple[str, Any, bool]:
        """Emit the constructor + props. Returns (qt class, child ctx(s) or None, placeholder?)."""
        spec = get_spec(node.type)
        fw = self.b.framework
        fn = plugin_emitter(node.type, fw)
        if fn is not None:
            return self.create_plugin(node, var, parent, fn)
        if not spec.supports(fw):
            return self.create_placeholder(node, var, parent)
        method = getattr(self, f"_c_{node.type}", None)
        if method is None:
            return self.create_placeholder(node, var, parent)
        qcls, ctx = method(node, var, parent, self.props(node))
        return qcls, ctx, False

    def create_placeholder(self, node: Node, var: str, parent: str) -> tuple[str, Any, bool]:
        spec = get_spec(node.type)
        msg = f"{spec.label}: not available in {self.b.framework}"
        self.w(f"{var} = {_PLACEHOLDER}({msg!r}, {parent})")
        self.w(f"{var}.setAlignment({AF}AlignCenter)")
        self.w(f"{var}.setWordWrap(True)")
        return "QLabel", None, True

    def create_plugin(self, node: Node, var: str, parent: str, fn: Any) -> tuple[str, Any, bool]:
        res = fn(EmitContext(self.project, node, var, parent, self.b.framework))
        self.extra_imports.extend(res.imports)
        for name in getattr(fn, "qt_helpers", ()):
            self.helpers.add(name)
        self.w("\n".join(res.lines))
        self.plugin_fn[node.id] = fn
        return "QWidget", None, False

    plugin_fn: dict[str, Any]

    # ---- containers
    def _c_frame(self, n: Node, v: str, par: str, p: dict) -> tuple[str, Any]:
        self.w(f"{v} = QFrame({par})")
        self.w(f"{v}.setFrameShape(QFrame.Shape.NoFrame)")
        return "QFrame", self.make_ctx(n, v, (n.box.w, n.box.h))

    def _c_label_frame(self, n: Node, v: str, par: str, p: dict) -> tuple[str, Any]:
        self.w(f"{v} = QGroupBox({_amp(p['title'])!r}, {par})")
        align = {"left": "AlignLeft", "center": "AlignHCenter", "right": "AlignRight"}
        if p.get("title_align") in ("center", "right"):
            self.w(f"{v}.setAlignment({AF}{align[p['title_align']]})")
        return "QGroupBox", self.make_ctx(n, v, (n.box.w, n.box.h))

    def _c_tabview(self, n: Node, v: str, par: str, p: dict) -> tuple[str, Any]:
        titles = [str(t) for t in (p.get("tabs") or [])]
        kids = self.doc.children(n.id)
        count = max(len(titles), max((k.page for k in kids), default=-1) + 1, 1)
        self.w(f"{v} = QTabWidget({par})")
        ctxs = []
        for i in range(count):
            page = f"_{v}_page{i}"
            title = titles[i] if i < len(titles) else f"Tab {i + 1}"
            self.w(f"{page} = QWidget()")
            self.w(f"{page}.setObjectName({f'{v}_page{i}'!r})")
            self.w(f"{v}.addTab({page}, {_amp(title)!r})")
            pc = self.make_ctx(n, page, (n.box.w, n.box.h))
            bw = 2 * max(self.theme.border_width, 0)
            pc.design_expr = (
                f"lambda: ({_r(n.box.w) - bw}, {_r(n.box.h) - bw} - {v}.tabBar().sizeHint().height())"
            )
            ctxs.append(pc)
        return "QTabWidget", ctxs

    def _c_scroll_frame(self, n: Node, v: str, par: str, p: dict) -> tuple[str, Any]:
        orient = p.get("orientation", "vertical")
        kids = [k for k in self.doc.children(n.id) if k.type != "toplevel"]
        lay = n.layout or ContainerLayout()
        ext_w = max((k.box.x + k.box.w for k in kids), default=0)
        ext_h = max((k.box.y + k.box.h for k in kids), default=0)
        cw = to_int(p.get("content_width"))
        ch = to_int(p.get("content_height"))
        if lay.mode == "absolute":
            cw = cw or _r(max(ext_w, n.box.w) if orient != "vertical" else n.box.w)
            ch = ch or _r(max(ext_h, n.box.h) if orient != "horizontal" else n.box.h)
        content = f"_{v}_content"
        self.w(f"{v} = QScrollArea({par})")
        self.w(f"{v}.setFrameShape(QFrame.Shape.NoFrame)")
        self.w(f"{content} = QWidget()")
        self.w(f"{content}.setObjectName({v + '_content'!r})")
        if orient == "vertical":
            self.w(f"{v}.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)")
        elif orient == "horizontal":
            self.w(f"{v}.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)")
        if lay.mode == "absolute":
            self.w(f"{content}.resize({cw}, {ch})")
            self.w(f"{v}.setWidget({content})")
        else:
            self.w(f"{v}.setWidgetResizable(True)")
            self.w(f"{v}.setWidget({content})")
            if cw:
                self.w(f"{content}.setMinimumWidth({cw})")
            if ch:
                self.w(f"{content}.setMinimumHeight({ch})")
        ctx = self.make_ctx(n, content, (cw or n.box.w, ch or n.box.h))
        return "QScrollArea", ctx

    def _c_paned_window(self, n: Node, v: str, par: str, p: dict) -> tuple[str, Any]:
        o = "Horizontal" if p.get("orientation") != "vertical" else "Vertical"
        self.w(f"{v} = QSplitter(Qt.Orientation.{o}, {par})")
        self.w(f"{v}.setChildrenCollapsible(False)")
        return "QSplitter", Ctx(n, v, "splitter")

    # ---- display
    def _c_label(self, n: Node, v: str, par: str, p: dict) -> tuple[str, Any]:
        self.w(f"{v} = QLabel({str(p['text'])!r}, {par})")
        wrap = to_int(p.get("wrap_length"))
        horiz = p.get("anchor", "w")
        if wrap:
            horiz = {"left": "w", "center": "center", "right": "e"}.get(p.get("justify"), horiz)
        flag = {"w": "AlignLeft", "center": "AlignHCenter", "e": "AlignRight"}.get(horiz, "AlignLeft")
        self.w(f"{v}.setAlignment({AF}{flag} | {AF}AlignVCenter)")
        if wrap:
            self.w(f"{v}.setWordWrap(True)")
        if p.get("image"):
            self.w(f"{v}.setPixmap(QPixmap({self.asset(p['image'])}))")
        return "QLabel", None

    def _c_image(self, n: Node, v: str, par: str, p: dict) -> tuple[str, Any]:
        self.helpers.add("image")
        src = self.asset(p["source"]) if p.get("source") else "''"
        self.w(f"{v} = _ImageLabel({src}, {p.get('fit', 'contain')!r}, {str(p['alt_text'])!r}, {par})")
        return "QLabel", None

    def _c_separator(self, n: Node, v: str, par: str, p: dict) -> tuple[str, Any]:
        self.w(f"{v} = QFrame({par})")
        self.w(f"{v}.setFrameShape(QFrame.Shape.NoFrame)")
        self.w(f"{v}.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)")
        return "QFrame", None

    def _c_progressbar(self, n: Node, v: str, par: str, p: dict) -> tuple[str, Any]:
        o = "Vertical" if p.get("orientation") == "vertical" else "Horizontal"
        self.w(f"{v} = QProgressBar({par})")
        self.w(f"{v}.setOrientation(Qt.Orientation.{o})")
        if p.get("mode") == "indeterminate":
            self.w(f"{v}.setRange(0, 0)")
        else:
            self.w(f"{v}.setRange(0, {to_int(p['maximum'], 100)})")
            self.w(f"{v}.setValue({to_int(p['value'])})")
        self.w(f"{v}.setTextVisible({bool(p.get('show_text'))})")
        return "QProgressBar", None

    def _c_canvas(self, n: Node, v: str, par: str, p: dict) -> tuple[str, Any]:
        self.helpers.add("canvas")
        h = n.events.get("paint")
        cb = f"lambda _e: {self.href(h)}(_e)" if self.has_handler(h) else "None"
        self.w(f"{v} = _Canvas({par}, {cb})")
        return "QWidget", None

    # ---- input
    def _icon_lines(self, v: str, p: dict) -> None:
        if p.get("image"):
            self.w(f"{v}.setIcon(QIcon({self.asset(p['image'])}))")

    def _c_button(self, n: Node, v: str, par: str, p: dict) -> tuple[str, Any]:
        if p.get("image") and p.get("compound") in ("top", "bottom"):
            self.helpers.add("stacked")
            below = p["compound"] == "bottom"
            self.w(
                f"{v} = _StackedButton({_amp(p['text'])!r}, QIcon({self.asset(p['image'])}), "
                f"{below}, {par})"
            )
            if p.get("default"):
                self.w(f"{v}.setDefault(True)")
            return "QPushButton", None
        self.w(f"{v} = QPushButton({_amp(p['text'])!r}, {par})")
        self._icon_lines(v, p)
        if p.get("image") and p.get("compound") == "right":
            self.w(f"{v}.setLayoutDirection(Qt.LayoutDirection.RightToLeft)")
        if p.get("default"):
            self.w(f"{v}.setDefault(True)")
        return "QPushButton", None

    def _c_tool_button(self, n: Node, v: str, par: str, p: dict) -> tuple[str, Any]:
        self.w(f"{v} = QToolButton({par})")
        self.w(f"{v}.setText({_amp(p['text'])!r})")
        self._icon_lines(v, p)
        style = "ToolButtonTextOnly"
        if p.get("image"):
            style = (
                "ToolButtonTextUnderIcon" if p.get("compound") in ("top", "bottom")
                else "ToolButtonTextBesideIcon"
            )
        self.w(f"{v}.setToolButtonStyle(Qt.ToolButtonStyle.{style})")
        if p.get("checkable"):
            self.w(f"{v}.setCheckable(True)")
        return "QToolButton", None

    def _c_entry(self, n: Node, v: str, par: str, p: dict) -> tuple[str, Any]:
        self.w(f"{v} = QLineEdit({par})")
        if p.get("text"):
            self.w(f"{v}.setText({str(p['text'])!r})")
        if p.get("placeholder"):
            self.w(f"{v}.setPlaceholderText({str(p['placeholder'])!r})")
        if p.get("show"):
            self.w(f"{v}.setEchoMode(QLineEdit.EchoMode.Password)")
            self.qss.append(f"#{v} {{ lineedit-password-character: {ord(str(p['show'])[0])}; }}")
        if p.get("readonly"):
            self.w(f"{v}.setReadOnly(True)")
        flag = {"left": "AlignLeft", "center": "AlignHCenter", "right": "AlignRight"}[
            p.get("justify", "left")
        ]
        if flag != "AlignLeft":
            self.w(f"{v}.setAlignment({AF}{flag} | {AF}AlignVCenter)")
        if to_int(p.get("max_length")) > 0:
            self.w(f"{v}.setMaxLength({to_int(p['max_length'])})")
        return "QLineEdit", None

    def _c_text(self, n: Node, v: str, par: str, p: dict) -> tuple[str, Any]:
        self.w(f"{v} = QPlainTextEdit({par})")
        if p.get("text"):
            self.w(f"{v}.setPlainText({str(p['text'])!r})")
        if p.get("placeholder"):
            self.w(f"{v}.setPlaceholderText({str(p['placeholder'])!r})")
        if p.get("readonly"):
            self.w(f"{v}.setReadOnly(True)")
        wrap = p.get("wrap", "word")
        if wrap == "none":
            self.w(f"{v}.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)")
        elif wrap == "char":
            self.w(f"{v}.setWordWrapMode(QTextOption.WrapMode.WrapAnywhere)")
        if not p.get("scrollbar", True):
            self.w(f"{v}.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)")
        return "QPlainTextEdit", None

    def _c_checkbox(self, n: Node, v: str, par: str, p: dict) -> tuple[str, Any]:
        self.w(f"{v} = QCheckBox({_amp(p['text'])!r}, {par})")
        if p.get("checked"):
            self.w(f"{v}.setChecked(True)")
        return "QCheckBox", None

    def _c_radio(self, n: Node, v: str, par: str, p: dict) -> tuple[str, Any]:
        self.w(f"{v} = QRadioButton({_amp(p['text'])!r}, {par})")
        group = str(p.get("group") or "group1")
        gv = self.radio_groups.get(group)
        if gv is None:
            base = "_group_" + slug(group, "group").lstrip("_")
            gv, i = base, 2
            while gv in self.radio_groups.values():
                gv = f"{base}_{i}"
                i += 1
            self.radio_groups[group] = gv
            self.w(f"{gv} = QButtonGroup({par})")
        self.w(f"{gv}.addButton({v})")
        self.w(f"{v}.setProperty('value', {str(p.get('value') or p['text'])!r})")
        if p.get("checked"):
            self.w(f"{v}.setChecked(True)")
        return "QRadioButton", None

    def _c_switch(self, n: Node, v: str, par: str, p: dict) -> tuple[str, Any]:
        self.helpers.add("switch")
        from py_vui.codegen.qt_common import css_color

        on = css_color(n.style.get("background"), self.theme.primary)
        off = css_color(self.theme.border, "#d4d4d8")
        self.w(f"{v} = _Switch({str(p['text'])!r}, {par}, {on!r}, {off!r})")
        if p.get("checked"):
            self.w(f"{v}.setChecked(True)")
        return "QCheckBox", None

    def _c_slider(self, n: Node, v: str, par: str, p: dict) -> tuple[str, Any]:
        o = "Vertical" if p.get("orientation") == "vertical" else "Horizontal"
        self.w(f"{v} = QSlider(Qt.Orientation.{o}, {par})")
        self.w(f"{v}.setRange({to_int(p['minimum'])}, {to_int(p['maximum'], 100)})")
        self.w(f"{v}.setSingleStep({max(1, to_int(p['step'], 1))})")
        self.w(f"{v}.setValue({to_int(p['value'])})")
        return "QSlider", None

    def _c_dial(self, n: Node, v: str, par: str, p: dict) -> tuple[str, Any]:
        self.w(f"{v} = QDial({par})")
        self.w(f"{v}.setRange({to_int(p['minimum'])}, {to_int(p['maximum'], 100)})")
        self.w(f"{v}.setValue({to_int(p['value'])})")
        self.w(f"{v}.setNotchesVisible(True)")
        return "QDial", None

    def _c_spinbox(self, n: Node, v: str, par: str, p: dict) -> tuple[str, Any]:
        dec = to_int(p.get("decimals"))
        if dec > 0:
            self.w(f"{v} = QDoubleSpinBox({par})")
            self.w(f"{v}.setDecimals({dec})")
            self.w(f"{v}.setRange({num(p['minimum'])}, {num(p['maximum'], 100)})")
            self.w(f"{v}.setSingleStep({num(p['step'], 1)})")
            self.w(f"{v}.setValue({num(p['value'])})")
            qcls = "QDoubleSpinBox"
        else:
            self.w(f"{v} = QSpinBox({par})")
            self.w(f"{v}.setRange({to_int(p['minimum'])}, {to_int(p['maximum'], 100)})")
            self.w(f"{v}.setSingleStep({max(1, to_int(p['step'], 1))})")
            self.w(f"{v}.setValue({to_int(p['value'])})")
            qcls = "QSpinBox"
        if p.get("wrap"):
            self.w(f"{v}.setWrapping(True)")
        return qcls, None

    def _c_combobox(self, n: Node, v: str, par: str, p: dict) -> tuple[str, Any]:
        items = [str(i) for i in (p.get("items") or [])]
        self.w(f"{v} = QComboBox({par})")
        if p.get("editable"):
            self.w(f"{v}.setEditable(True)")
        if items:
            self.w(f"{v}.addItems({lit(items)})")
        cur = to_int(p.get("current"))
        if items and cur >= 0 or p.get("editable") and cur < 0:
            self.w(f"{v}.setCurrentIndex({min(cur, len(items) - 1) if cur >= 0 else -1})")
        return "QComboBox", None

    def _c_listbox(self, n: Node, v: str, par: str, p: dict) -> tuple[str, Any]:
        items = [str(i) for i in (p.get("items") or [])]
        self.w(f"{v} = QListWidget({par})")
        if items:
            self.w(f"{v}.addItems({lit(items)})")
        mode = {"single": "SingleSelection", "multiple": "MultiSelection",
                "extended": "ExtendedSelection"}.get(p.get("selection_mode"), "SingleSelection")
        self.w(f"{v}.setSelectionMode(QAbstractItemView.SelectionMode.{mode})")
        return "QListWidget", None

    def _c_segmented_button(self, n: Node, v: str, par: str, p: dict) -> tuple[str, Any]:
        items = [str(i) for i in (p.get("items") or [])]
        cur = to_int(p.get("current"))
        self.w(f"{v} = QWidget({par})")
        lay, grp = f"_{v}_layout", f"_{v}_group"
        self.w(f"{lay} = QHBoxLayout({v})")
        self.w(f"{lay}.setContentsMargins(0, 0, 0, 0)")
        self.w(f"{lay}.setSpacing(0)")
        self.w(f"{grp} = QButtonGroup({v})")
        self.w(f"{grp}.setExclusive(True)")
        for i, text in enumerate(items):
            b = f"_{v}_segment{i}"
            seg = "only" if len(items) == 1 else "first" if i == 0 else (
                "last" if i == len(items) - 1 else "middle")
            self.w(f"{b} = QPushButton({_amp(text)!r}, {v})")
            self.w(f"{b}.setCheckable(True)")
            self.w(f"{b}.setProperty('segment', {seg!r})")
            if i == cur:
                self.w(f"{b}.setChecked(True)")
            self.w(f"{grp}.addButton({b}, {i})")
            self.w(f"{lay}.addWidget({b})")
        return "QWidget", None

    def _c_date_entry(self, n: Node, v: str, par: str, p: dict) -> tuple[str, Any]:
        self.w(f"{v} = QDateEdit({par})")
        self.w(f"{v}.setCalendarPopup(True)")
        pat = re.sub(r"m+", lambda m: "M" * len(m.group()), str(p.get("pattern") or "yyyy-MM-dd"))
        self.w(f"{v}.setDisplayFormat({pat!r})")
        self.w(f"{v}.setDate({self.qdate(p.get('date'))})")
        return "QDateEdit", None

    def qdate(self, value: Any) -> str:
        try:
            d = datetime.strptime(str(value), "%Y-%m-%d").date()
        except ValueError:
            return "QDate.currentDate()"
        return f"QDate({d.year}, {d.month}, {d.day})"

    def _c_time_entry(self, n: Node, v: str, par: str, p: dict) -> tuple[str, Any]:
        self.w(f"{v} = QTimeEdit({par})")
        secs = bool(p.get("show_seconds", True))
        self.w(f"{v}.setDisplayFormat({'HH:mm:ss' if secs else 'HH:mm'!r})")
        parts = str(p.get("time") or "").split(":")
        try:
            hh, mm, ss = (int(parts[i]) if i < len(parts) else 0 for i in range(3))
            if not (0 <= hh < 24 and 0 <= mm < 60 and 0 <= ss < 60):
                raise ValueError
            self.w(f"{v}.setTime(QTime({hh}, {mm}, {ss}))")
        except ValueError:
            pass
        return "QTimeEdit", None

    # ---- data
    def _c_table(self, n: Node, v: str, par: str, p: dict) -> tuple[str, Any]:
        self.helpers.add("fill")
        cols = [str(c) for c in (p.get("columns") or [])]
        rows = [list(r) for r in (p.get("rows") or []) if isinstance(r, (list, tuple))]
        ncols = max(len(cols), *[len(r) for r in rows])
        cols += [""] * (ncols - len(cols))
        self.w(f"{v} = QTableWidget({len(rows)}, {ncols}, {par})")
        self.w(f"{v}.setHorizontalHeaderLabels({lit(cols)})")
        if rows:
            self.w(f"_fill_table({v}, {lit([[str(c) for c in r] for r in rows])})")
        self.w(f"{v}.horizontalHeader().setStretchLastSection(True)")
        if not p.get("show_header", True):
            self.w(f"{v}.horizontalHeader().setVisible(False)")
        self.w(f"{v}.verticalHeader().setVisible(False)")
        if not p.get("editable"):
            self.w(f"{v}.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)")
        mode = {"single": "SingleSelection", "multiple": "ExtendedSelection",
                "none": "NoSelection"}.get(p.get("selection_mode"), "SingleSelection")
        self.w(f"{v}.setSelectionMode(QAbstractItemView.SelectionMode.{mode})")
        self.w(f"{v}.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)")
        return "QTableWidget", None

    def _c_tree_view(self, n: Node, v: str, par: str, p: dict) -> tuple[str, Any]:
        self.helpers.add("fill")
        self.w(f"{v} = QTreeWidget({par})")
        self.w(f"{v}.setHeaderLabels([{str(p.get('header') or '')!r}])")
        if not p.get("show_header"):
            self.w(f"{v}.setHeaderHidden(True)")
        items = p.get("items") or []
        if items:
            self.w(f"_fill_tree({v}, {lit(items)})")
            self.w(f"{v}.expandAll()")
        return "QTreeWidget", None

    def _c_calendar(self, n: Node, v: str, par: str, p: dict) -> tuple[str, Any]:
        self.w(f"{v} = QCalendarWidget({par})")
        self.w(f"{v}.setSelectedDate({self.qdate(p.get('date'))})")
        day = "Sunday" if p.get("first_weekday") == "sunday" else "Monday"
        self.w(f"{v}.setFirstDayOfWeek(Qt.DayOfWeek.{day})")
        fmt = "ISOWeekNumbers" if p.get("show_week_numbers", True) else "NoVerticalHeader"
        self.w(f"{v}.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.{fmt})")
        # the stock navigation arrows are fixed black icons: use text glyphs that follow the theme
        self.w("for _name, _glyph in (('qt_calendar_prevmonth', '\u2039'), "
               "('qt_calendar_nextmonth', '\u203a')):")
        self.w(f"    _button = {v}.findChild(QToolButton, _name)")
        self.w("    if _button is not None:")
        self.w("        _button.setIcon(QIcon())")
        self.w("        _button.setText(_glyph)")
        self.w("        _button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)")
        return "QCalendarWidget", None

    # ---------------------------------------------------------------- tab order
    def emit_tab_order(self) -> None:
        proj = self.project
        order = list(proj.tab_order)
        if not order:
            ordered = [n for n in proj.nodes.values() if n.tab_index is not None]
            order = [n.id for n in sorted(ordered, key=lambda n: (n.tab_index, n.id))]
        vars_ = [
            self.node_vars[i] for i in order
            if i in self.node_vars and proj.nodes[i].type not in ("window", "toplevel")
        ]
        if len(vars_) > 1:
            self.w("")
            for a, b in zip(vars_, vars_[1:], strict=False):
                self.w(f"QWidget.setTabOrder({a}, {b})")

    # -------------------------------------------------------------------- menus
    def emit_menus(self, root: str, menus: list) -> None:
        self.has_menus = True
        self.w("")
        self.w("# menu bar")
        bar = f"_{root}_menubar"
        self.w(f"{bar} = {root}.menuBar()")
        self.w(f"{bar}.setNativeMenuBar(False)")
        for menu in menus:
            if not isinstance(menu, dict):
                continue
            mv = self.uid("menu")
            self.w(f"{mv} = {bar}.addMenu({str(menu.get('title', ''))!r})")
            self.menu_items(root, mv, menu.get("items") or [], str(menu.get("title", "")))

    def menu_items(self, root: str, mv: str, items: list, path: str) -> None:
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("separator"):
                self.w(f"{mv}.addSeparator()")
                continue
            label = str(item.get("label", ""))
            key = f"{path}/{label}"
            if item.get("items"):
                sv = self.uid("menu")
                self.w(f"{sv} = {mv}.addMenu({label!r})")
                self.menu_items(root, sv, item["items"], key)
                continue
            av = self.uid("action")
            self.w(f"{av} = QAction({label!r}, {root})")
            if item.get("shortcut"):
                self.w(f"{av}.setShortcut(QKeySequence({str(item['shortcut'])!r}))")
            checkable = bool(item.get("checkable"))
            if checkable:
                self.w(f"{av}.setCheckable(True)")
                if item.get("checked"):
                    self.w(f"{av}.setChecked(True)")
            if item.get("enabled") is False:
                self.w(f"{av}.setEnabled(False)")
            self.w(f"{mv}.addAction({av})")
            self.w(f"ACTIONS[{key!r}] = {av}")
            h = item.get("handler")
            if self.has_handler(h):
                if checkable:
                    self.w(f"{av}.triggered.connect(lambda _checked=False, *_: "
                           f"{self.href(h)}(_checked))")
                else:
                    self.w(f"{av}.triggered.connect(lambda *_: {self.href(h)}())")

    # ------------------------------------------------------------------- events
    def native(self, node: Node, ev: str, var: str) -> _Sig | None:
        t = node.type
        grp = f"_{var}_group"
        table: dict[tuple[str, str], _Sig] = {}

        def add(types: tuple[str, ...], event: str, target: str, sig: str, params: str, arg: str):
            for ty in types:
                table[(ty, event)] = _Sig(target, sig, params, arg)

        add(("button", "tool_button", "checkbox", "radio", "switch"), "click", var, "clicked",
            "*_", "")
        add(("checkbox", "radio", "switch"), "toggle", var, "toggled", "_v, *_", "_v")
        add(("entry",), "change", var, "textChanged", "_v, *_", "_v")
        add(("entry",), "submit", var, "returnPressed", "*_", f"{var}.text()")
        add(("text",), "change", var, "textChanged", "*_", f"{var}.toPlainText()")
        add(("slider", "dial", "spinbox"), "change", var, "valueChanged", "_v, *_", "_v")
        add(("combobox",), "change", var, "currentTextChanged", "_v, *_", "_v")
        add(("listbox",), "select", var, "itemSelectionChanged", "*_",
            f"[_i.text() for _i in {var}.selectedItems()]")
        add(("segmented_button",), "change", grp, "buttonClicked", "_b, *_", "_b.text()")
        add(("date_entry",), "change", var, "dateChanged", "_d, *_", '_d.toString("yyyy-MM-dd")')
        add(("time_entry",), "change", var, "timeChanged", "_t, *_", '_t.toString("HH:mm:ss")')
        add(("table",), "select", var, "itemSelectionChanged", "*_",
            f"sorted({{_i.row() for _i in {var}.selectedItems()}})")
        add(("table",), "cell_change", var, "cellChanged", "_r, _c, *_", "(_r, _c)")
        add(("tree_view",), "select", var, "itemSelectionChanged", "*_",
            f"[_i.text(0) for _i in {var}.selectedItems()]")
        add(("calendar",), "change", var, "selectionChanged", "*_",
            f'{var}.selectedDate().toString("yyyy-MM-dd")')
        add(("tabview",), "tab_change", var, "currentChanged", "_i, *_", "_i")
        sig = table.get((t, ev))
        if sig is not None:
            if not get_spec(t).supports(self.b.framework):
                return None
            return sig
        fn = self.plugin_fn.get(node.id)
        if fn is not None:
            mapping = getattr(fn, "qt_signals", {}) or {}
            if ev in mapping:
                name, params, arg = mapping[ev]
                return _Sig(var, name, params, arg.replace("{w}", var))
        return None

    def wire_events(self, node: Node, var: str, qcls: str = "") -> None:
        generic: dict[str, str] = {}
        lines: list[str] = []
        for ev, hname in node.events.items():
            if not self.has_handler(hname) or ev == "paint":
                continue
            sig = self.native(node, ev, var)
            if sig is not None:
                call = f"{self.href(hname)}({sig.arg})"
                lines.append(
                    f"{sig.target}.{sig.signal}.connect(lambda {sig.params}: {call})"
                )
            elif node.type in self._third_party and ev in ("click", "change"):
                self.helpers.add("connect_any")
                names = (["clicked"] if ev == "click" else
                         ["valueChanged", "textChanged", "currentIndexChanged", "changed",
                          "toggled"])
                lines.append(
                    f"_connect_any({var}, {names!r}, lambda *_: {self.href(hname)}())"
                )
            else:
                generic[ev] = hname
        for ln in lines:
            self.w(ln)
        if generic:
            self.helpers.add("events")
            if len(generic) == 1:
                ev, hname = next(iter(generic.items()))
                self.w(f"_Events({var}, {{{ev!r}: lambda _e: {self.href(hname)}(_e)}})")
            else:
                self.w(f"_Events({var}, {{")
                for ev in sorted(generic):
                    self.w(f"    {ev!r}: lambda _e: {self.href(generic[ev])}(_e),")
                self.w("})")

    _third_party: set[str]

    def run(self) -> str:
        """Return the body of ``build_ui`` (unindented)."""
        self.plugin_fn = {}
        self._third_party = {
            n.type for n in self.project.nodes.values()
            if has_spec(n.type) and plugin_emitter(n.type, self.b.framework) is not None
            and n.type not in {"chart", "color_picker"}
        }
        self.emit_ui_body()
        self.emit_tab_order()
        self.w("")
        self.w("# theme")
        self.w("_stylesheet = STYLESHEET + NODE_STYLES")
        self.w("for _window in WINDOWS.values():")
        self.w("    _window.setPalette(make_palette())")
        self.w("    _window.setStyleSheet(_stylesheet)")
        self.w("")
        self.w(f"return {self.names[self.root.id]}")
        return "\n".join(self.body)


# =============================================================================== assembly
def _indent(text: str, n: int = 4) -> str:
    pad = " " * n
    return "\n".join((pad + ln) if ln.strip() else "" for ln in text.split("\n"))


def _ui_section(em: QtEmitter) -> str:
    """Module-level ui code (registries, styles, helpers, build_ui, start, open_*)."""
    body = em.run()
    qss = "\n".join(q for q in em.qss if q)
    head = ["WIDGETS = {}", "WINDOWS = {}"]
    if em.has_menus:
        head.append("ACTIONS = {}")
    head += ["", f'NODE_STYLES = """\n{qss}\n"""']
    parts = ["\n".join(head)]
    helpers = qt_helpers.render(em.helpers, em.b.signal)
    if helpers:
        parts.append(helpers.rstrip())
    func = ["def build_ui():", '    """Build the widget tree and return the main window."""',
            "    WIDGETS.clear()", "    WINDOWS.clear()"]
    if em.has_menus:
        func.append("    ACTIONS.clear()")
    func.append(_indent(body))
    parts.append("\n".join(func))
    start = [
        "def start(root):",
        '    """Show the main window plus every dialog that does not start hidden."""',
        "    root.show()",
        "    for window in WINDOWS.values():",
        "        if window is not root and window.property('start_visible'):",
        "            window.show()",
        "    return root",
    ]
    parts.append("\n".join(start))
    for dv in em.dialogs:
        parts.append(
            f"def open_{dv}():\n"
            f'    """Show the {dv!r} dialog and bring it to the front."""\n'
            f"    dialog = WINDOWS[{dv!r}]\n"
            "    dialog.show()\n"
            "    dialog.raise_()\n"
            "    dialog.activateWindow()\n"
            "    return dialog"
        )
    return "\n\n\n".join(parts) + "\n"


def _title(project: Project) -> str:
    return project.meta.name or "py_vui app"


_EXCEPTHOOK = (
    "def _excepthook(kind, value, tb):\n"
    '    """Print uncaught errors instead of letting PyQt6 abort the process."""\n'
    "    traceback.print_exception(kind, value, tb)"
)


def _main_code(project: Project, binding: Binding, single: bool) -> str:
    hook = binding.framework == "pyqt6"
    lines = [
        "def main():",
        "    app = QApplication(sys.argv)",
        f"    app.setApplicationName({_title(project)!r})",
        "    apply_theme(app)" if single else "    theme.apply_theme(app)",
        "    root = build_ui()" if single else "    root = ui.build_ui()",
    ]
    if single:
        lines.append("    start(root)")
    else:
        lines += ["    custom.setup(app, root)", "    ui.start(root)"]
    lines.append("    return app.exec()")
    tail = ['if __name__ == "__main__":']
    if hook:
        tail.append("    sys.excepthook = _excepthook")
    tail.append("    sys.exit(main())")
    parts = ([_EXCEPTHOOK] if hook else []) + ["\n".join(lines), "\n".join(tail)]
    return "\n\n\n".join(parts)


def _import_block(text: str, binding: Binding, extra: list[str]) -> list[str]:
    std: set[str] = set()
    if re.search(r"\bos\.", text) or "import os" in extra:
        std.add("os")
    if re.search(r"\bsys\.", text):
        std.add("sys")
    if re.search(r"\btraceback\.", text):
        std.add("traceback")
    lines = [f"import {m}" for m in sorted(std)]
    qt = import_lines(text, binding)
    ext = [e for e in dict.fromkeys(extra)
           if not e.startswith(f"from {binding.package}.") and e != "import os"]
    out = list(lines)
    if lines and (qt or ext):
        out.append("")
    out += qt + ext
    return out


def _module(doc: str, imports: list[str], *sections: str) -> str:
    out = [HEADER, f'"""{doc}"""', "", *imports, "", ""]
    out.append("\n\n\n".join(s.strip("\n") for s in sections if s.strip()))
    return "\n".join(out).rstrip() + "\n"


def _with_qt_imports(project: Project, binding: Binding) -> Project:
    """Make ``Qt`` (enums) importable from handlers by default, inside the editable region."""
    code = project.custom_code
    if binding.package in code:
        return project
    pkg = binding.package
    header = (
        f"from {pkg}.QtCore import Qt  # noqa: F401  (e.g. Qt.AlignmentFlag.AlignCenter)\n"
        f"# from {pkg}.QtWidgets import QFileDialog, QMessageBox  # optional dialogs\n"
    )
    return project.model_copy(update={"custom_code": header + code})


def _hoist_future(code: str) -> tuple[str, str]:
    fut, rest = [], []
    for ln in code.split("\n"):
        (fut if ln.startswith("from __future__ import") else rest).append(ln)
    return "\n".join(fut), "\n".join(rest)


class QtAdapter(Adapter):
    binding: Binding = PYSIDE6

    def base_requirements(self) -> list[str]:
        return [self.binding.requirement]

    def generate(self, project: Project, options: GenOptions) -> list[GeneratedFile]:
        single = options.layout == "single"
        em = QtEmitter(project, self.binding, single=single)
        ui_code = _ui_section(em)
        if single:
            files = [self._single(project, options, em, ui_code)]
        else:
            files = self._project(project, options, em, ui_code)
        files.append(GeneratedFile("requirements.txt", "\n".join(self.requirements(project)) + "\n"))
        if options.readme:
            files.append(GeneratedFile("README.md", _readme(project, self.binding, single)))
        return files

    def _project(self, project: Project, options: GenOptions, em: QtEmitter, ui_code: str):
        b = self.binding
        theme = theme_code(project)
        imports = _import_block(ui_code, b, em.extra_imports)
        local = ["import handlers"] if "handlers." in ui_code else []
        local.append("from theme import STYLESHEET, make_palette")
        ui_py = _module("UI generated by py_vui: build_ui() returns the main window.",
                        [*imports, "", *local], ui_code)
        theme_py = _module("Theme generated by py_vui: stylesheet + palette.",
                           _import_block(theme, b, []), theme)
        main_code = _main_code(project, b, False)
        main_imports = _import_block(main_code + "\nQApplication", b, [])
        main_imports += ["", "import custom", "import theme", "import ui"]
        main_py = _module(f"Entry point of {_title(project)}.", main_imports, main_code)
        custom = (
            f"{HEADER}\n"
            '"""Your own code. py_vui never overwrites this file."""\n\n\n'
            "def setup(app, root):\n"
            '    """Called once after the UI is built and before it is shown."""\n'
        )
        return [
            GeneratedFile("main.py", main_py),
            GeneratedFile("ui.py", ui_py),
            GeneratedFile("theme.py", theme_py),
            self._handlers(project, options),
            GeneratedFile("custom.py", custom, overwrite=False),
        ]

    def _handlers(self, project: Project, options: GenOptions) -> GeneratedFile:
        f = handlers_file(_with_qt_imports(project, self.binding), options)
        return GeneratedFile(f.path, f"{HEADER}\n{f.content}", f.overwrite)

    def _single(self, project: Project, options: GenOptions, em: QtEmitter, ui_code: str):
        b = self.binding
        existing = options.existing.get("main.py") if options.preserve_user_code else None
        hmod = render_handlers_module(_with_qt_imports(project, b), existing).split("\n", 1)[1].lstrip("\n")
        future, hmod = _hoist_future(hmod)
        theme = theme_code(project)
        main_code = _main_code(project, b, True)
        generated = "\n\n\n".join([theme.strip("\n"), ui_code.strip("\n"), main_code])
        imports = _import_block(generated + "\nQApplication", b, em.extra_imports)
        bar = "-" * 60
        out = [HEADER, f'"""{_title(project)}: single-file app generated by py_vui."""']
        if future:
            out += ["", future]
        out += ["", *imports, "", "", f"# --- handlers {bar}", hmod.rstrip(), "", "",
                f"# --- theme {bar}", "", generated, ""]
        return GeneratedFile("main.py", "\n".join(out))


def _readme(project: Project, b: Binding, single: bool) -> str:
    name = _title(project)
    layout = (
        "* `main.py`: everything in one file (handlers are inlined)"
        if single else
        "* `main.py`: entry point\n"
        "* `ui.py`: generated widget tree; `build_ui()` returns the main window, "
        "`ui.WIDGETS` / `ui.WINDOWS` map names to widgets\n"
        "* `theme.py`: generated stylesheet and palette\n"
        "* `handlers.py`: your event handlers (edit between the `py_vui` markers)\n"
        "* `custom.py`: your own code, never overwritten (`setup(app, root)` runs at start-up)"
    )
    registry = "WIDGETS" if single else "ui.WIDGETS"
    access = (
        "Handlers can reach any widget by its variable name:\n\n```python\n"
        + ("" if single else "import ui\n\n")
        + f"def on_click(event=None):\n    {registry}['my_label'].setText('Hello')\n```\n"
    )
    return (
        f"# {name}\n\n{project.meta.description}\n\n"
        f"Generated by [py_vui](https://github.com/dfunani/py_vui) for **{b.label}**.\n\n"
        f"## Run\n\n```bash\npip install -r requirements.txt\npython main.py\n```\n\n"
        f"## Files\n\n{layout}\n\n## Using widgets\n\n{access}"
    )


class PySide6Adapter(QtAdapter):
    framework = "pyside6"
    label = "PySide6"
    binding = PYSIDE6


class PyQt6Adapter(QtAdapter):
    framework = "pyqt6"
    label = "PyQt6"
    binding = PYQT6


qt_plugins.register()
register_adapter(PySide6Adapter())
register_adapter(PyQt6Adapter())

__all__ = ["PyQt6Adapter", "PySide6Adapter", "QtAdapter", "QtEmitter"]
