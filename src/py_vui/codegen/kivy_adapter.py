"""Kivy code generator (pure Python, no .kv files).

Output (``GenOptions.layout == "project"``): ``main.py`` (App subclass), ``ui.py``
(``build_ui()`` + ``WIDGETS`` / ``WINDOWS``), ``handlers.py``, ``custom.py`` (never
overwritten), ``requirements.txt`` and ``README.md``. ``layout == "single"`` produces one
self-contained ``main.py``.

Layout modes map onto Kivy like this:

* absolute -> ``FloatLayout`` + ``_pin()`` (top-left design coordinates, anchors on resize)
* flex     -> ``BoxLayout`` (+ ``AnchorLayout`` cells / spacers for align, margin, justify)
* grid     -> ``FloatLayout`` + ``_grid()`` (weights, spans and sticky like the editor)
"""

from __future__ import annotations

import builtins
import contextlib
import keyword
import re
import textwrap
from collections.abc import Callable
from dataclasses import dataclass, field

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
from py_vui.codegen.kivy_common import (
    HELPERS,
    KIVY_MODULES,
    ORDER,
    mix,
    num,
    parse_color,
    rgba_src,
)
from py_vui.codegen.merge_regions import render_handlers_module
from py_vui.core.document import ProjectDocument
from py_vui.core.model import ContainerLayout, Node, Project
from py_vui.core.registry import get_spec, has_spec
from py_vui.core.theme import resolve_style

TAB_STRIP = 38  # dp, tab header (32dp tabs + 3dp padding above and below)
GROUP_TITLE = 26  # dp, title row of a group box
POPUP_CHROME = (24, 60)  # dp added around a dialog's content (padding, title bar)
MENU_BAR = 48  # dp, ActionBar height

_FOCUSABLE = {"entry", "text", "date_entry", "time_entry"}
_CURSORS = {
    "arrow": "arrow", "hand": "hand", "ibeam": "ibeam", "cross": "crosshair",
    "wait": "wait", "forbidden": "no", "size_all": "size_all",
}
_RESERVED = {"dp", "asset", "os", "re", "sys", "calendar", "datetime", "handlers", "ui", "custom",
             "main", "app", "root", "self", "build_ui", "WIDGETS", "WINDOWS",
             # parameter names used by generated lambdas
             "w", "v", "tv", "node", "tab", "sel", "row", "col", "date", "dt"}
_PRIMARY_CLICK = {"button", "tool_button"}
#: widgets Kivy renders although the catalog does not list the framework for them
_KIVY_EXTRA = {"dial"}
_MONO_HINTS = ("mono", "courier", "consolas", "menlo", "monaco", "fixed", "typewriter", "code")


# ------------------------------------------------------------------------------ data classes
@dataclass
class Body:
    """Where children of a container are added."""

    var: str
    mode: str  # absolute | flex | grid | paned
    layout: ContainerLayout
    w: float
    h: float
    grid_items: list[str] = field(default_factory=list)
    vertical: bool = False  # paned / flex orientation
    pane_sizes: list[float] = field(default_factory=list)
    pane_index: int = 0
    pane_count: int = 0


@dataclass
class Built:
    """Result of a per-type builder."""

    cls: str
    kwargs: list[tuple[str, str]] = field(default_factory=list)
    #: statements run right after creation ("{v}" is the widget variable)
    post: list[str] = field(default_factory=list)
    #: emits the inner structure + children once the widget variable exists
    inner: Callable[[], None] | None = None
    #: skip applying generic placement kwargs / nothing
    plain: bool = False


def q(text: object) -> str:
    return repr(str(text))


def dp(v: float) -> str:
    return f"dp({num(v)})"


def _kw(items: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Later keys override earlier ones, order of first appearance kept."""
    out: dict[str, str] = {}
    for k, v in items:
        out[k] = v
    return list(out.items())


# ------------------------------------------------------------------------------ generator
class _Gen:
    def __init__(self, project: Project, options: GenOptions) -> None:
        self.project = project
        self.options = options
        self.doc = ProjectDocument(project)
        self.theme = project.theme
        self.single = options.layout == "single"
        self.names = self._unique_names()
        self.used: set[str] = set(self.names.values())
        self.lines: list[str] = []
        self.helpers: set[str] = set()
        self.kivy: set[str] = set()
        self.std: set[str] = set()
        self.extra_imports: set[str] = set()
        self.extra_reqs: set[str] = set()
        self.config: list[str] = []
        self.popups: list[tuple[str, str]] = []  # (var, node name)
        self.notes: list[str] = []  # limitations hit by this project (for README)
        self.uses_mouse_buttons = False
        self.root_var = "root"
        self.main_title = project.meta.name
        self.main_icon = ""

    # -------------------------------------------------------------------- names
    def _unique_names(self) -> dict[str, str]:
        out: dict[str, str] = {}
        taken: set[str] = set()
        for nid, name in self.doc.variable_names().items():
            if (name in _RESERVED or keyword.iskeyword(name) or hasattr(builtins, name)
                    or name in KIVY_MODULES):
                name = f"{name}_w"
            base, i = name, 2
            while name in taken:
                name = f"{base}_{i}"
                i += 1
            taken.add(name)
            out[nid] = name
        return out

    def fresh(self, base: str) -> str:
        name, i = base, 2
        while name in self.used:
            name = f"{base}_{i}"
            i += 1
        self.used.add(name)
        return name

    # -------------------------------------------------------------------- emit utils
    def k(self, name: str) -> str:
        self.kivy.add(name)
        return name

    def h(self, name: str) -> None:
        self.helpers.add(name)

    def line(self, text: str = "", indent: int = 1) -> None:
        self.lines.append(("    " * indent + text) if text else "")

    def note(self, text: str) -> None:
        if text not in self.notes:
            self.notes.append(text)

    def call_lines(self, prefix: str, cls: str, kwargs: list[tuple[str, str]]) -> None:
        items = [f"{k}={v}" for k, v in _kw(kwargs)]
        one = f"{prefix}{cls}({', '.join(items)})"
        if len(one) + 4 <= 100:
            self.line(one)
            return
        self.line(f"{prefix}{cls}(")
        for it in items:
            self.line(f"    {it},")
        self.line(")")

    def href(self, name: str) -> str:
        return f"handlers.{name}"

    # -------------------------------------------------------------------- colours / fonts
    def color(self, value: object, fallback: tuple[float, float, float, float]) -> tuple:
        return parse_color(value) or fallback

    def csrc(self, value: object, fallback=(0, 0, 0, 1)) -> str:
        return rgba_src(self.color(value, fallback))

    def font_kw(self, st: dict, *, text_style: bool = True) -> list[tuple[str, str]]:
        kw = [("font_size", dp(float(st["font_size"])))]
        family = str(st.get("font_family") or "")
        low = family.lower()
        if low.endswith((".ttf", ".otf")):
            self.h("asset")
            kw.append(("font_name", f"asset({family!r})"))
        elif any(m in low for m in _MONO_HINTS):
            kw.append(("font_name", q("data/fonts/RobotoMono-Regular.ttf")))
        elif "dejavu" in low:
            kw.append(("font_name", q("data/fonts/DejaVuSans.ttf")))
        if text_style:
            if st.get("bold"):
                kw.append(("bold", "True"))
            if st.get("italic"):
                kw.append(("italic", "True"))
            if st.get("underline"):
                kw.append(("underline", "True"))
        return kw

    def paint_post(self, st: dict, *, hover: bool = False, border: bool = True,
                   fill: object = None) -> str:
        """``_paint(...)`` statement for the node's resolved style."""
        self.h("paint")
        bg = self.csrc(fill if fill is not None else st["background"], (1, 1, 1, 1))
        args = [bg, num(st["corner_radius"])]
        bw = int(st["border_width"]) if border else 0
        if bw > 0:
            args += [num(bw), self.csrc(st["border_color"], (0.8, 0.8, 0.8, 1))]
        if hover:
            args.append(f"hover={self.csrc(st['hover_color'], (0.3, 0.3, 0.9, 1))}")
        return f"_paint({{v}}, {', '.join(args)})"

    # -------------------------------------------------------------------- top level
    def generate_ui_lines(self) -> None:
        root = self.doc.get_node(self.project.root_id)
        self.build_window(root)
        for win in self.doc.windows()[1:]:
            self.line()
            self.build_toplevel(win)
        self.emit_tab_order()
        self.line()
        self.line(f"return {self.root_var}")

    # -------------------------------------------------------------------- windows
    def window_body(self, node: Node, var: str, w: float, h: float) -> tuple[Body, Built]:
        layout = node.layout or ContainerLayout()
        mode = self.eff_mode(node)
        built = self.container_built(layout, mode)
        body = Body(var=var, mode=mode, layout=layout, w=w, h=h)
        return body, built

    def eff_mode(self, node: Node) -> str:
        """absolute | flex (BoxLayout) | flexh (helper: wrap / grow with basis) | grid."""
        layout = node.layout or ContainerLayout()
        if layout.mode != "flex":
            return layout.mode
        kids = self.doc.children(node.id)
        if layout.wrap or any(k.flex.grow > 0 for k in kids):
            return "flexh"
        return "flex"

    def container_built(self, layout: ContainerLayout, mode: str | None = None) -> Built:
        if (mode or layout.mode) == "flex":
            p = layout.padding
            vertical = layout.direction == "column"
            return Built(self.k("BoxLayout"), [
                ("orientation", q("vertical" if vertical else "horizontal")),
                ("spacing", dp(layout.gap)),
                ("padding", f"[{dp(p.left)}, {dp(p.top)}, {dp(p.right)}, {dp(p.bottom)}]"),
            ])
        return Built(self.k("FloatLayout"))

    def build_window(self, node: Node) -> None:
        var = self.names[node.id]
        p = node.props
        w, h = float(p.get("width", 640)), float(p.get("height", 480))
        menus = p.get("menus") or []
        st = resolve_style(self.theme, "window", node.style)
        self.main_title = str(p.get("title", "Window"))
        icon = str(p.get("icon") or "")
        self.main_icon = icon
        total_h = h + (MENU_BAR if menus else 0)
        self.config += [
            f"Config.set('graphics', 'width', {q(int(w))})",
            f"Config.set('graphics', 'height', {q(int(total_h))})",
        ]
        self.k("Config")
        lock_axes = None
        resizable = bool(p.get("resizable_x", True) or p.get("resizable_y", True))
        if not resizable:
            self.config.append("Config.set('graphics', 'resizable', '0')")
        elif not (p.get("resizable_x", True) and p.get("resizable_y", True)):
            self.note("Kivy has no per-axis resizable flag: a window locked in one direction is "
                      "snapped back to its size on resize (`_lock_axes`), which can flicker.")
            lock_axes = (not p.get("resizable_x", True), not p.get("resizable_y", True))
        if p.get("min_width"):
            self.config.append(f"Config.set('graphics', 'minimum_width', {q(int(p['min_width']))})")
        if p.get("min_height"):
            self.config.append(
                f"Config.set('graphics', 'minimum_height', {q(int(p['min_height']))})")
        self.k("Window")
        self.line('"""Create the widget tree and return the root widget of the main window."""')
        self.line("WIDGETS.clear()")
        self.line("WINDOWS.clear()")
        self.line(f"Window.size = ({num(w)}, {num(total_h)})")
        self.line(f"Window.clearcolor = {self.csrc(st['background'], (0.95, 0.95, 0.95, 1))}")
        self.line(f"Window.title = {q(self.main_title)}")
        if icon:
            self.h("asset")
            self.line("try:")
            self.line(f"    Window.set_icon(asset({icon!r}))", 1)
            self.line("except Exception:  # missing icon file / unsupported provider")
            self.line("    pass")
        if lock_axes:
            self.h("lock")
            self.line(f"_lock_axes({lock_axes[0]}, {lock_axes[1]}, {num(w)}, {num(total_h)})")
        if p.get("maximized"):
            self.line("Window.maximize()")
        if p.get("always_on_top"):
            self.line("Window.always_on_top = True")
        self.line()
        body, built = self.window_body(node, var, w, h)
        self.line(f"# {node.name} (window)")
        built.kwargs = _kw(built.kwargs)
        self.call_lines(f"{var} = ", built.cls, built.kwargs)
        self.line(f"WIDGETS[{var!r}] = {var}")
        if menus:
            self.root_var = "root"
            self.build_menus(menus, var)
        else:
            self.root_var = var
        self.line(f"WINDOWS[{var!r}] = {self.root_var}")
        self.emit_children(node, body)
        self.emit_node_extras(node, var, event_target="Window", mouse_target=var,
                              skip_visual=True)

    def build_menus(self, menus: list, body_var: str) -> None:
        bar, view = self.fresh("menubar"), self.fresh("menuview")
        bl = self.k("BoxLayout")
        self.line(f"root = {bl}(orientation='vertical')")
        self.used.add("root")
        self.call_lines(f"{bar} = ", self.k("ActionBar"),
                        [("size_hint_y", "None"), ("height", dp(MENU_BAR))])
        self.line(f"{view} = {self.k('ActionView')}()")
        self.line(f"{bar}.add_widget({view})")
        prev = self.k("ActionPrevious")
        self.line(f"{view}.add_widget({prev}(title={q(self.main_title)}, with_previous=False, "
                  f"app_icon={q('')}, size_hint_x=None, width=dp(160)))")
        self.k("dp")
        for mi, menu in enumerate(menus):
            if not isinstance(menu, dict):
                continue
            group = self.fresh(f"menu_{mi}")
            self.line(f"{group} = {self.k('ActionGroup')}(text={q(menu.get('title', 'Menu'))})")
            self.line(f"{view}.add_widget({group})")
            self.menu_items(group, menu.get("items") or [], "")
        self.line(f"root.add_widget({bar})")
        self.line(f"root.add_widget({body_var})")

    def menu_items(self, group: str, items: list, prefix: str) -> None:
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("separator"):
                continue
            label = f"{prefix}{item.get('label', '')}"
            if item.get("items"):
                self.menu_items(group, item["items"], f"{label} > ")
                continue
            shortcut = str(item.get("shortcut") or "")
            text = f"{label}    ({shortcut})" if shortcut else label
            cls = self.k("ActionToggleButton" if item.get("checkable") else "ActionButton")
            btn = self.fresh("menu_item")
            self.line(f"{btn} = {cls}(text={q(text)})")
            self.line(f"{group}.add_widget({btn})")
            handler = item.get("handler")
            if handler and handler in self.project.handlers:
                self.h("event")
                ref = self.href(handler)
                self.line(f"{btn}.bind(on_release=lambda w: _fire({ref}, w))")
                if shortcut:
                    self.h("shortcut")
                    self.line(f"_shortcut({shortcut!r}, {ref})")
            elif handler:
                self.line(f"# handler {handler!r} is not defined")

    def build_toplevel(self, node: Node) -> None:
        var = self.names[node.id]
        p = node.props
        w, h = float(p.get("width", 420)), float(p.get("height", 300))
        st = resolve_style(self.theme, "toplevel", node.style)
        body_var = self.fresh(f"{var}_content")
        body, built = self.window_body(node, body_var, w, h)
        self.line(f"# {node.name} (dialog window; open with open_{var}())")
        self.call_lines(f"{body_var} = ", built.cls, _kw(built.kwargs))
        self.emit_children(node, body)
        popup = self.k("Popup")
        self.note("Dialog windows are sized from the design size plus the popup title bar "
                  "(the content area can differ by a few dp between platforms).")
        self.call_lines(f"{var} = ", popup, [
            ("title", q(p.get("title", "Dialog"))),
            ("content", body_var),
            ("size_hint", "(None, None)"),
            ("size", f"({dp(w + POPUP_CHROME[0])}, {dp(h + POPUP_CHROME[1])})"),
            ("auto_dismiss", "False" if p.get("modal") else "True"),
            ("background", q("")),
            ("background_color", self.csrc(st["background"], (1, 1, 1, 1))),
            ("title_color", self.csrc(st["foreground"])),
            ("separator_color", self.csrc(self.theme.primary)),
        ])
        self.line(f"WIDGETS[{var!r}] = {var}")
        self.line(f"WINDOWS[{var!r}] = {var}")
        self.popups.append((var, node.name))
        self.emit_node_extras(node, var, event_target=var, mouse_target=body_var, skip_visual=True)
        if not p.get("start_hidden", False):
            self.k("Clock")
            self.line(f"Clock.schedule_once(lambda dt: {var}.open(), 0)")

    # -------------------------------------------------------------------- tree walk
    def emit_children(self, parent: Node, body: Body, kids: list[Node] | None = None) -> None:
        kids = self.doc.children(parent.id) if kids is None else kids
        if body.mode == "paned":
            body.pane_count = len(kids)
            sizes = [float(s) for s in (parent.props.get("sizes") or []) if str(s).strip()]
            extent = body.h if body.vertical else body.w
            even = extent / max(1, len(kids))
            body.pane_sizes = [sizes[i] if i < len(sizes) else even for i in range(len(kids))]
        spacer_plan = self.spacer_plan(body, kids)
        for i, kid in enumerate(kids):
            if body.mode == "flex" and spacer_plan.get(i):
                self.spacer(body, spacer_plan[i])
            body.pane_index = i
            self.emit_node(kid, body)
        if body.mode == "flex" and spacer_plan.get(len(kids)):
            self.spacer(body, spacer_plan[len(kids)])
        if body.mode == "flexh" and body.grid_items:
            self.h("flexh")
            lay = body.layout
            pad = lay.padding
            self.line("_flex(")
            self.line(f"    {body.var},")
            self.line("    [")
            for item in body.grid_items:
                self.line(f"        {item},")
            self.line("    ],")
            self.line(f"    {lay.direction == 'row'}, {num(lay.gap)}, {lay.justify!r}, "
                      f"{lay.align!r}, {bool(lay.wrap)},")
            self.line(f"    ({num(pad.top)}, {num(pad.right)}, {num(pad.bottom)}, "
                      f"{num(pad.left)}),")
            self.line(")")
        if body.mode == "grid" and body.grid_items:
            self.h("grid")
            lay = body.layout
            pad = lay.padding
            self.line("_grid(")
            self.line(f"    {body.var},", 1)
            self.line("    [")
            for item in body.grid_items:
                self.line(f"        {item},")
            self.line("    ],")
            self.line(f"    {list(lay.column_weights)!r}, {list(lay.row_weights)!r},")
            self.line(f"    {num(lay.column_gap)}, {num(lay.row_gap)},")
            self.line(f"    ({num(pad.top)}, {num(pad.right)}, {num(pad.bottom)}, "
                      f"{num(pad.left)}),")
            self.line(")")

    def spacer_plan(self, body: Body, kids: list[Node]) -> dict[int, float]:
        """Flex ``justify``: weight of the spacer Widget inserted before child i."""
        if body.mode != "flex" or not kids or any(k.flex.grow > 0 for k in kids):
            return {}
        n, j = len(kids), body.layout.justify
        if j == "start":  # BoxLayout packs a column from the bottom: push the leftover below
            return {n: 1} if body.layout.direction == "column" else {}
        if j == "center":
            return {0: 1, n: 1}
        if j == "end":
            return {0: 1}
        if j == "space_between":
            return {i: 1 for i in range(1, n)}
        if j == "space_around":
            return {**{i: 1 for i in range(1, n)}, 0: 0.5, n: 0.5}
        return {}

    def spacer(self, body: Body, weight: float) -> None:
        hint = "size_hint_y" if body.layout.direction == "column" else "size_hint_x"
        self.line(f"{body.var}.add_widget({self.k('Widget')}({hint}={num(weight)}))")

    def emit_node(self, node: Node, body: Body) -> None:
        var = self.names[node.id]
        spec = get_spec(node.type) if has_spec(node.type) else None
        st = resolve_style(self.theme, node.type, node.style)
        label = spec.label if spec else node.type
        self.line()
        self.line(f"# {node.name} ({node.type})")
        pk, wrapper = self.place_kwargs(node, body)
        plugin = plugin_emitter(node.type, "kivy") if spec is not None else None
        if plugin is not None:
            self.build_plugin(node, var, body, plugin)
            built = None
        else:
            builder = getattr(self, f"b_{node.type}", None)
            if spec is None or builder is None or not (
                    spec.supports("kivy") or node.type in _KIVY_EXTRA):
                built = self.b_placeholder(node, st, label)
            else:
                built = builder(node, st)
            built.kwargs = _kw([*built.kwargs, *self.state_kwargs(node), *pk])
            self.call_lines(f"{var} = ", built.cls, built.kwargs)
            for stmt in built.post:
                self.line(stmt.replace("{v}", var))
            if built.inner:
                built.inner()
        self.attach(node, var, body, wrapper)
        self.line(f"WIDGETS[{var!r}] = {var}")
        self.emit_node_extras(node, var, event_target=var, mouse_target=var)

    def state_kwargs(self, node: Node) -> list[tuple[str, str]]:
        kw = []
        if not node.enabled:
            kw.append(("disabled", "True"))
        if not node.visible:
            kw.append(("opacity", "0"))
            if node.enabled:
                kw.append(("disabled", "True"))
        return kw

    # -------------------------------------------------------------------- placement
    def place_kwargs(self, node: Node, body: Body) -> tuple[list[tuple[str, str]], dict | None]:
        b = node.box
        if body.mode == "absolute":
            return [("size_hint", "(None, None)"), ("size", f"({dp(b.w)}, {dp(b.h)})")], None
        if body.mode in ("grid", "flexh"):
            return [("size_hint", "(None, None)"), ("size", f"({dp(b.w)}, {dp(b.h)})")], None
        if body.mode == "paned":
            return [], None
        # flex
        lay = body.layout
        col = lay.direction == "column"
        m = node.flex.margin
        has_margin = any((m.top, m.right, m.bottom, m.left))
        align = lay.align if node.flex.align_self == "auto" else node.flex.align_self
        wrapped = has_margin or align != "stretch"
        main_hint, main_size = ("size_hint_y", "height") if col else ("size_hint_x", "width")
        cross_hint, cross_size = ("size_hint_x", "width") if col else ("size_hint_y", "height")
        main_len = b.h if col else b.w
        cross_len = b.w if col else b.h
        grow = node.flex.grow
        main_margin = (m.top + m.bottom) if col else (m.left + m.right)
        if not wrapped:
            kw = [(main_hint, num(grow))] if grow > 0 else [(main_hint, "None"),
                                                             (main_size, dp(main_len))]
            return [*kw, (cross_hint, "1")], None
        # wrapped in an AnchorLayout cell that owns the margins and the alignment
        inner = [("size_hint", "(1, 1)")] if align == "stretch" else [
            (main_hint, "1"), (cross_hint, "None"), (cross_size, dp(cross_len))]
        if align == "stretch":
            inner = [(main_hint, "1"), (cross_hint, "1")]
        anchor = {"start": 0, "center": 1, "end": 2}.get(align, 0)
        if col:
            ax = ("left", "center", "right")[anchor]
            wkw = [("anchor_x", q(ax)), ("anchor_y", q("center"))]
        else:
            ay = ("top", "center", "bottom")[anchor]
            wkw = [("anchor_x", q("center")), ("anchor_y", q(ay))]
        wkw.append(("padding", f"[{dp(m.left)}, {dp(m.top)}, {dp(m.right)}, {dp(m.bottom)}]"))
        if grow > 0:
            wkw.append((main_hint, num(grow)))
        else:
            wkw += [(main_hint, "None"), (main_size, dp(main_len + main_margin))]
        wkw.append((cross_hint, "1"))
        return inner, {"kwargs": wkw}

    def attach(self, node: Node, var: str, body: Body, wrapper: dict | None) -> None:
        b = node.box
        if body.mode == "absolute":
            self.h("pin")
            anchors = node.anchors
            flags = (anchors.left, anchors.top, anchors.right, anchors.bottom)
            a = "".join(c for c, on in zip("ltrb", flags, strict=True) if on)
            self.line(f"{body.var}.add_widget({var})")
            extra = "" if a == "lt" else f", {a!r}"
            self.line(f"_pin({var}, {body.var}, {num(b.x)}, {num(b.y)}, {num(b.w)}, {num(b.h)}, "
                      f"{num(body.w)}, {num(body.h)}{extra})")
        elif body.mode == "flexh":
            m = node.flex.margin
            self.line(f"{body.var}.add_widget({var})")
            body.grid_items.append(
                f"({var}, {num(b.w)}, {num(b.h)}, {num(node.flex.grow)}, "
                f"{node.flex.align_self!r}, ({num(m.top)}, {num(m.right)}, {num(m.bottom)}, "
                f"{num(m.left)}))")
        elif body.mode == "grid":
            c = node.cell
            self.line(f"{body.var}.add_widget({var})")
            sticky = (c.sticky or "").lower()
            body.grid_items.append(
                f"({var}, {c.row}, {c.column}, {c.row_span}, {c.column_span}, {sticky!r}, "
                f"{num(b.w)}, {num(b.h)})")
        elif body.mode == "paned":
            idx = body.pane_index
            if idx < body.pane_count - 1:
                size = body.pane_sizes[idx]
                sp = self.fresh(f"{var}_pane")
                side, hint = ("bottom", "(1, None)") if body.vertical else ("right", "(None, 1)")
                dim = "height" if body.vertical else "width"
                self.call_lines(f"{sp} = ", self.k("Splitter"), [
                    ("sizable_from", q(side)), ("min_size", dp(40)), ("strip_size", dp(6)),
                    ("size_hint", hint), (dim, dp(size))])
                self.line(f"{sp}.add_widget({var})")
                self.line(f"{body.var}.add_widget({sp})")
            else:
                self.line(f"{body.var}.add_widget({var})")
        elif wrapper is not None:
            cell = self.fresh(f"{var}_cell")
            self.call_lines(f"{cell} = ", self.k("AnchorLayout"), wrapper["kwargs"])
            self.line(f"{cell}.add_widget({var})")
            self.line(f"{body.var}.add_widget({cell})")
        else:
            self.line(f"{body.var}.add_widget({var})")

    # -------------------------------------------------------------------- events & extras
    def emit_node_extras(self, node: Node, var: str, *, event_target: str, mouse_target: str,
                         skip_visual: bool = False) -> None:
        if node.tooltip:
            self.h("tip")
            self.line(f"_tip({var}, {node.tooltip!r})")
        cursor = _CURSORS.get(str(node.style.get("cursor") or ""))
        if cursor and not skip_visual:
            self.h("cursor")
            self.line(f"_cursor({var}, {cursor!r})")
        for ev in sorted(node.events):
            handler = node.events[ev]
            if handler not in self.project.handlers:
                self.line(f"# {ev}: handler {handler!r} is not defined")
                continue
            self.emit_event(node, var, ev, self.href(handler), event_target, mouse_target)

    def emit_event(self, node: Node, var: str, ev: str, h: str, target: str, mouse: str) -> None:
        t = node.type
        self.h("event")
        f = f"_fire({h}, w"  # prefix of the common call

        def bind(prop: str, lam: str) -> None:
            self.line(f"{var}.bind({prop}={lam})")

        if t in ("window", "toplevel"):
            if ev in ("close", "show", "hide", "resize", "key_press", "key_release",
                      "focus_in", "focus_out"):
                self.h("on")
                self.line(f"_on({target}, {ev!r}, {h})")
                return
            self.mouse_event(mouse, ev, h)
            return
        if ev == "click" and t in _PRIMARY_CLICK:
            bind("on_release", f"lambda w: {f})")
        elif t in ("entry", "text", "date_entry", "time_entry") and ev == "change":
            if t == "date_entry":
                self.h("dates")
                fmt = self.date_format(node)
                bind("text", f"lambda w, v: (d := _parse_date(v, {fmt!r})) and "
                             f"_fire({h}, w, value=d, text=v)")
            elif t == "time_entry":
                self.std.add("re")
                pattern = r"\d\d:\d\d(:\d\d)?"
                bind("text", f"lambda w, v: re.fullmatch({pattern!r}, v) and _fire({h}, w, value=v)")
            else:
                bind("text", f"lambda w, v: _fire({h}, w, value=v)")
        elif t == "entry" and ev == "submit":
            bind("on_text_validate", f"lambda w: _fire({h}, w, value=w.text)")
        elif t in ("checkbox", "switch") and ev == "toggle":
            bind("active", f"lambda w, v: _fire({h}, w, value=v)")
        elif t == "radio" and ev == "toggle":
            bind("active", f"lambda w, v: v and _fire({h}, w, value=v)")
        elif t in ("checkbox", "radio", "switch") and ev == "click":
            bind("on_click", f"lambda w: {f})")
        elif t in ("slider", "spinbox", "dial") and ev == "change":
            bind("value", f"lambda w, v: _fire({h}, w, value=v)")
        elif t == "combobox" and ev == "change":
            bind("text", f"lambda w, v: _fire({h}, w, value=v, "
                         "index=w.values.index(v) if v in w.values else -1)")
        elif t == "segmented_button" and ev == "change":
            bind("current", f"lambda w, v: _fire({h}, w, value=v, index=int(v))")
        elif t == "listbox" and ev == "select":
            bind("on_select", f"lambda w, sel: _fire({h}, w, selection=sel, "
                              "items=[w.items[i] for i in sel])")
        elif t == "table" and ev == "select":
            bind("on_select", f"lambda w, row, values: _fire({h}, w, row=row, values=values)")
        elif t == "table" and ev == "cell_change":
            bind("on_cell_change", f"lambda w, row, col, v: _fire({h}, w, row=row, column=col, "
                                   "value=v)")
        elif t == "tree_view" and ev == "select":
            self.line(f"{var}.tree.bind(selected_node=lambda tv, node: _fire({h}, {var}, "
                      "node=node, text=getattr(node, 'text', '')))")
        elif t == "tabview" and ev == "tab_change":
            bind("current_tab", f"lambda w, tab: _fire({h}, w, title=tab.text, "
                                f"index={var}_tabs.index(tab))")
        elif t == "canvas" and ev == "paint":
            self.line(f"{var}.painter = lambda w: _fire({h}, w)")
            self.line(f"{var}.repaint()")
        elif t == "calendar" and ev == "change":
            bind("on_change", f"lambda w, date: _fire({h}, w, value=date)")
        elif ev in ("focus_in", "focus_out", "resize", "key_press", "key_release", "click"):
            self.h("on")
            self.line(f"_on({var}, {ev!r}, {h})")
        else:
            self.mouse_event(var, ev, h)

    def mouse_event(self, target: str, ev: str, h: str) -> None:
        if ev in ("right_click", "middle_click", "double_click", "mouse_press", "mouse_release"):
            self.uses_mouse_buttons = True
        if ev in ("click", "double_click", "right_click", "middle_click", "mouse_press",
                  "mouse_release", "mouse_move", "mouse_enter", "mouse_leave", "mouse_wheel",
                  "key_press", "key_release", "focus_in", "focus_out", "resize", "show", "hide",
                  "close"):
            self.h("on")
            self.line(f"_on({target}, {ev!r}, {h})")
        else:
            self.line(f"# event {ev!r} is not available on Kivy")

    def emit_tab_order(self) -> None:
        ids = [i for i in self.project.tab_order if i in self.project.nodes
               and self.project.nodes[i].type in _FOCUSABLE]
        if len(ids) > 1:
            self.h("taborder")
            self.line()
            self.line("_tab_order([" + ", ".join(self.names[i] for i in ids) + "])")

    # -------------------------------------------------------------------- plugins / unsupported
    def build_plugin(self, node: Node, var: str, body: Body, fn) -> None:
        ctx = EmitContext(self.project, node, var, body.var, "kivy")
        res = fn(ctx)
        self.extra_imports.update(res.imports)
        self.extra_reqs.update(res.requirements)
        for text in res.lines:
            self.line(text)
        self.line(f"if {var}.parent is not None:")
        self.line(f"    {var}.parent.remove_widget({var})")
        if body.mode == "absolute":
            self.line(f"{var}.size_hint = (None, None)")

    def b_placeholder(self, node: Node, st: dict, label: str) -> Built:
        self.h("fit")
        self.h("paint")
        self.note("Widgets that Kivy has no equivalent for are generated as a red placeholder "
                  "Label.")
        text = f"{node.name}\n({label} is not supported on Kivy)"
        red = (0.8, 0.2, 0.2, 1)
        return Built(self.k("Label"), [
            ("text", q(text)), ("color", rgba_src(red)), ("halign", q("center")),
            ("valign", q("middle")), ("font_size", dp(12))],
            post=["_fit({v})", f"_paint({{v}}, (1, 0.93, 0.93, 1), 4, 1, {rgba_src(red)})"])

    # ==================================================================== widget builders
    # each returns Built; "{v}" in post lines is the variable name
    def b_window(self, node: Node, st: dict) -> Built:  # nested windows are not allowed
        return self.b_placeholder(node, st, "Window")

    def b_toplevel(self, node: Node, st: dict) -> Built:
        return self.b_placeholder(node, st, "Dialog Window")

    # ---- containers
    def b_frame(self, node: Node, st: dict) -> Built:
        layout = node.layout or ContainerLayout()
        mode = self.eff_mode(node)
        built = self.container_built(layout, mode)
        body_ref: dict[str, Body] = {}
        built.post.append(self.paint_post(st))
        built.inner = lambda: self.emit_children(node, body_ref["b"])
        body_ref["b"] = Body(var=self.names[node.id], mode=mode, layout=layout,
                             w=node.box.w, h=node.box.h)
        return built

    def b_label_frame(self, node: Node, st: dict) -> Built:
        layout = node.layout or ContainerLayout()
        var = self.names[node.id]
        body_var = self.fresh(f"{var}_body")
        title_var = self.fresh(f"{var}_title")
        p = node.props
        built = Built(self.k("BoxLayout"), [("orientation", q("vertical"))])
        built.post.append(self.paint_post(st))
        halign = p.get("title_align", "left")
        self.h("fit")

        def inner() -> None:
            self.call_lines(f"{title_var} = ", self.k("Label"), [
                ("text", q(p.get("title", ""))), ("size_hint_y", "None"),
                ("height", dp(GROUP_TITLE)), ("color", self.csrc(st["foreground"])),
                ("bold", "True"), ("halign", q(halign)), ("valign", q("middle")),
                *self.font_kw(st, text_style=False)])
            self.line(f"_fit({title_var})")
            self.line(f"{title_var}.padding_x = {dp(8)}")
            mode = self.eff_mode(node)
            inner_b = self.container_built(layout, mode)
            self.call_lines(f"{body_var} = ", inner_b.cls, inner_b.kwargs)
            self.line(f"{var}.add_widget({title_var})")
            self.line(f"{var}.add_widget({body_var})")
            body = Body(var=body_var, mode=mode, layout=layout, w=node.box.w,
                        h=node.box.h - GROUP_TITLE)
            self.emit_children(node, body)

        built.inner = inner
        return built

    def b_scroll_frame(self, node: Node, st: dict) -> Built:
        layout = node.layout or ContainerLayout()
        var = self.names[node.id]
        content = self.fresh(f"{var}_content")
        p = node.props
        orient = p.get("orientation", "vertical")
        sx, sy = orient in ("horizontal", "both"), orient in ("vertical", "both")
        cw = float(p.get("content_width") or 0) or node.box.w
        ch = float(p.get("content_height") or 0) or node.box.h
        built = Built(self.k("ScrollView"), [
            ("do_scroll_x", str(sx)), ("do_scroll_y", str(sy)), ("bar_width", dp(8)),
            ("scroll_type", "['bars', 'content']")])
        built.post.append(self.paint_post(st))

        def inner() -> None:
            mode = self.eff_mode(node)
            ib = self.container_built(layout, mode)
            kw = list(ib.kwargs)
            grows: list[str] = []
            if mode == "flex":
                if sy and not p.get("content_height"):
                    kw += [("size_hint_y", "None")]
                    grows.append("height")
                elif sy or sx:
                    kw += [("size_hint_y", "None"), ("height", dp(ch))] if sy else []
                if sx and not p.get("content_width"):
                    kw += [("size_hint_x", "None")]
                    grows.append("width")
                elif sx:
                    kw += [("size_hint_x", "None"), ("width", dp(cw))]
            else:
                kw += [("size_hint", "(None, None)"), ("size", f"({dp(cw)}, {dp(ch)})")]
            self.call_lines(f"{content} = ", ib.cls, kw)
            for dim in grows:
                self.line(f"{content}.bind(minimum_{dim}={content}.setter({dim!r}))")
            self.line(f"{var}.add_widget({content})")
            body = Body(var=content, mode=mode, layout=layout, w=cw, h=ch)
            self.emit_children(node, body)

        built.inner = inner
        return built

    def b_tabview(self, node: Node, st: dict) -> Built:
        layout = node.layout or ContainerLayout()
        var = self.names[node.id]
        p = node.props
        tabs = [str(t) for t in (p.get("tabs") or ["Tab 1"])] or ["Tab 1"]
        built = Built(self.k("TabbedPanel"), [
            ("do_default_tab", "False"), ("tab_pos", q("top_left")), ("tab_height", dp(32)),
            ("tab_width", dp(110)), ("background_color", "(0, 0, 0, 0)"),
            ("background_image", q(""))])
        built.post.append(self.paint_post(st))

        def inner() -> None:
            heads = []
            for i, title in enumerate(tabs):
                head = self.fresh(f"{var}_tab{i}")
                page = self.fresh(f"{var}_page{i}")
                heads.append(head)
                mode = self.eff_mode(node)
                pb = self.container_built(layout, mode)
                self.line(f"{head} = {self.k('TabbedPanelItem')}(text={q(title)})")
                self.call_lines(f"{page} = ", pb.cls, pb.kwargs)
                self.line(f"{head}.content = {page}")
                self.line(f"{var}.add_widget({head})")
                body = Body(var=page, mode=mode, layout=layout, w=node.box.w,
                            h=node.box.h - TAB_STRIP)
                kids = [k for k in self.doc.children(node.id)
                        if min(k.page, len(tabs) - 1) == i]
                self.emit_children(node, body, kids)
            self.line(f"{var}_tabs = [{', '.join(heads)}]")
            cur = int(p.get("current") or 0)
            if 0 < cur < len(tabs):
                self.line(f"{var}.switch_to({heads[cur]})")

        built.inner = inner
        return built

    def b_paned_window(self, node: Node, st: dict) -> Built:
        layout = node.layout or ContainerLayout()
        vertical = node.props.get("orientation") == "vertical"
        var = self.names[node.id]
        built = Built(self.k("BoxLayout"), [
            ("orientation", q("vertical" if vertical else "horizontal"))])
        self.note("Splitter panes: the last pane takes the remaining space; handles are Kivy "
                  "Splitters.")

        def inner() -> None:
            body = Body(var=var, mode="paned", layout=layout, w=node.box.w, h=node.box.h,
                        vertical=vertical)
            self.emit_children(node, body)

        built.inner = inner
        return built

    # ---- display
    def b_label(self, node: Node, st: dict) -> Built:
        p = node.props
        anchor = {"w": "left", "center": "center", "e": "right"}.get(p.get("anchor", "w"), "left")
        kw = [("text", q(p.get("text", ""))), ("color", self.csrc(st["foreground"])),
              *self.font_kw(st), ("valign", q("middle"))]
        post: list[str] = []
        wrap = int(p.get("wrap_length") or 0)
        if wrap > 0:
            kw += [("halign", q(p.get("justify", "left"))), ("text_size", f"({dp(wrap)}, None)")]
        else:
            kw.append(("halign", q(anchor)))
            self.h("fit")
            post.append("_fit({v})")
        if node.style.get("background"):
            post.append(self.paint_post(st))
        if p.get("image"):
            self.h("icon")
            post.append(f"_icon({{v}}, {p['image']!r})")
        return Built(self.k("Label"), kw, post)

    def b_image(self, node: Node, st: dict) -> Built:
        p = node.props
        source = str(p.get("source") or "")
        if not source:
            self.h("fit")
            return Built(self.k("Label"), [
                ("text", q(p.get("alt_text") or "Image")), ("color", self.csrc(self.theme.muted_text)),
                ("halign", q("center")), ("valign", q("middle"))], ["_fit({v})"])
        fit = {"contain": "contain", "stretch": "fill", "none": "scale-down"}.get(
            p.get("fit", "contain"), "contain")
        self.h("asset")
        remote = source.startswith(("http://", "https://"))
        cls = self.k("AsyncImage" if remote else "Image")
        return Built(cls, [("source", f"asset({source!r})"), ("fit_mode", q(fit))])

    def b_separator(self, node: Node, st: dict) -> Built:
        color = node.style.get("background") or self.theme.border
        self.h("paint")
        return Built(self.k("Widget"), post=[f"_paint({{v}}, {self.csrc(color)})"])

    def b_progressbar(self, node: Node, st: dict) -> Built:
        p = node.props
        self.h("Progress")
        track = node.style.get("background") or self.theme.border
        fill = node.style.get("foreground") or self.theme.primary
        return Built("Progress", [
            ("value", num(p.get("value", 0))), ("maximum", num(p.get("maximum", 100) or 100)),
            ("vertical", str(p.get("orientation") == "vertical")),
            ("fill", self.csrc(fill)), ("track", self.csrc(track)),
            ("color", self.csrc(self.theme.text)),
            ("show_text", str(bool(p.get("show_text")))),
            ("indeterminate", str(p.get("mode") == "indeterminate")),
            ("radius", num(st["corner_radius"]))])

    def b_canvas(self, node: Node, st: dict) -> Built:
        if node.props.get("scrollable"):
            self.h("PaintScroll")
            self.note("Scrollable canvas: draw on `.surface` and make it larger than the view "
                      "(`surface.size = ...`) to scroll.")
            return Built("PaintScroll", post=[self.paint_post(st)])
        self.h("Paint")
        return Built("Paint", post=[self.paint_post(st)])

    def b_dial(self, node: Node, st: dict) -> Built:
        p = node.props
        self.h("Dial")
        track = node.style.get("background") or self.theme.border
        return Built("Dial", [
            ("minimum", num(p.get("minimum", 0))), ("maximum", num(p.get("maximum", 100))),
            ("value", num(p.get("value", 0))), ("track", self.csrc(track)),
            ("fill", self.csrc(self.theme.primary)),
            ("knob", self.csrc(node.style.get("foreground") or self.theme.text))])

    # ---- buttons
    def button_kwargs(self, node: Node, st: dict) -> list[tuple[str, str]]:
        return [("text", q(node.props.get("text", ""))), ("color", self.csrc(st["foreground"])),
                *self.font_kw(st), ("background_normal", q("")), ("background_down", q("")),
                ("background_color", "(0, 0, 0, 0)")]

    def b_button(self, node: Node, st: dict) -> Built:
        p = node.props
        post = [self.paint_post(st, hover=True, border=int(node.style.get("border_width", -1)
                                                           or 0) > 0)]
        if p.get("image"):
            self.h("icon")
            post.append(f"_icon({{v}}, {p['image']!r}, {p.get('compound', 'left')!r})")
        return Built(self.k("Button"), self.button_kwargs(node, st), post)

    def b_tool_button(self, node: Node, st: dict) -> Built:
        p = node.props
        cls = "ToggleButton" if p.get("checkable") else "Button"
        post = [self.paint_post(st, hover=True, border=False)]
        if p.get("checkable"):
            hv = self.csrc(st["hover_color"])
            self.h("paint")
            post = [f"_paint({{v}}, {self.csrc(st['background'])}, {num(st['corner_radius'])}, "
                    f"down={hv})"]
        if p.get("image"):
            self.h("icon")
            post.append(f"_icon({{v}}, {p['image']!r})")
        return Built(self.k(cls), self.button_kwargs(node, st), post)

    # ---- text inputs
    def input_kwargs(self, st: dict) -> list[tuple[str, str]]:
        fg = self.color(st["foreground"], (0, 0, 0, 1))
        hint = mix(fg, self.color(st["background"], (1, 1, 1, 1)), 0.55)
        return [("foreground_color", rgba_src(fg)), ("cursor_color", rgba_src(fg)),
                ("hint_text_color", rgba_src(hint)), *self.font_kw(st, text_style=False),
                ("background_normal", q("")), ("background_active", q("")),
                ("background_disabled_normal", q("")), ("background_color", "(0, 0, 0, 0)")]

    def b_entry(self, node: Node, st: dict) -> Built:
        p = node.props
        kw = [("text", q(p.get("text", ""))), ("hint_text", q(p.get("placeholder", ""))),
              ("multiline", "False"), ("write_tab", "False"),
              ("halign", q(p.get("justify", "left"))), *self.input_kwargs(st)]
        if p.get("show"):
            kw.append(("password", "True"))
        if p.get("readonly"):
            kw.append(("readonly", "True"))
        self.h("vcenter")
        post = [self.paint_post(st), "_vcenter({v})"]
        if int(p.get("max_length") or 0) > 0:
            self.h("limit")
            post.append(f"_limit({{v}}, {int(p['max_length'])})")
        return Built(self.k("TextInput"), kw, post)

    def b_text(self, node: Node, st: dict) -> Built:
        p = node.props
        kw = [("text", q(p.get("text", ""))), ("hint_text", q(p.get("placeholder", ""))),
              ("multiline", "True"), ("do_wrap", str(p.get("wrap", "word") != "none")),
              ("padding", f"[{dp(8)}, {dp(8)}, {dp(8)}, {dp(8)}]"), *self.input_kwargs(st)]
        if p.get("readonly"):
            kw.append(("readonly", "True"))
        post = [self.paint_post(st)]
        if p.get("scrollbar", True):
            self.h("scrollbar")
            muted = self.color(self.theme.muted_text, (0.5, 0.5, 0.5, 1))
            post.append(f"_scrollbar({{v}}, {rgba_src((*muted[:3], 0.7))})")
        return Built(self.k("TextInput"), kw, post)

    @staticmethod
    def date_format(node: Node) -> str:
        """strftime format for the node's display pattern (yyyy-mm-dd, dd/mm/yyyy, ...)."""
        pattern = str(node.props.get("pattern") or "yyyy-mm-dd")
        out = re.sub(r"(?i)yyyy", "%Y", pattern)
        out = re.sub(r"(?i)yy", "%y", out)
        out = re.sub(r"(?i)mm", "%m", out)
        return re.sub(r"(?i)dd", "%d", out)

    def b_date_entry(self, node: Node, st: dict) -> Built:
        import datetime

        p = node.props
        self.h("vcenter")
        fmt = self.date_format(node)
        text = str(p.get("date", ""))
        with contextlib.suppress(ValueError):
            text = datetime.date.fromisoformat(text).strftime(fmt)
        kw = [("text", q(text)), ("hint_text", q(p.get("pattern", "yyyy-mm-dd"))),
              ("multiline", "False"), ("write_tab", "False"), *self.input_kwargs(st)]
        return Built(self.k("TextInput"), kw, [self.paint_post(st), "_vcenter({v})"])

    def b_time_entry(self, node: Node, st: dict) -> Built:
        p = node.props
        self.h("vcenter")
        default = "HH:MM:SS" if p.get("show_seconds", True) else "HH:MM"
        kw = [("text", q(p.get("time", ""))), ("hint_text", q(default)), ("multiline", "False"),
              ("write_tab", "False"), *self.input_kwargs(st)]
        return Built(self.k("TextInput"), kw, [self.paint_post(st), "_vcenter({v})"])

    # ---- toggles
    def option(self, node: Node, st: dict, kind: str) -> Built:
        p = node.props
        self.h("Option")
        kw = [("text", q(p.get("text", ""))), ("kind", q(kind)),
              ("active", str(bool(p.get("checked")))), ("color", self.csrc(st["foreground"])),
              ("font_size", dp(float(st["font_size"])))]
        post: list[str] = []
        if kind == "radio":
            kw.append(("group", q(p.get("group", "group1"))))
            post.append(f"{{v}}.value = {str(p.get('value') or p.get('text', ''))!r}")
        if node.style.get("background"):
            post.append(self.paint_post(st))
        return Built("Option", kw, post)

    def b_checkbox(self, node: Node, st: dict) -> Built:
        return self.option(node, st, "check")

    def b_radio(self, node: Node, st: dict) -> Built:
        return self.option(node, st, "radio")

    def b_switch(self, node: Node, st: dict) -> Built:
        return self.option(node, st, "switch")

    # ---- value inputs
    def b_slider(self, node: Node, st: dict) -> Built:
        p = node.props
        step = float(p.get("step") or 0)
        opts = [("min", num(p.get("minimum", 0))), ("max", num(p.get("maximum", 100))),
                ("value", num(p.get("value", 0))),
                ("orientation", q(p.get("orientation", "horizontal"))),
                ("value_track", "True"), ("value_track_color", self.csrc(self.theme.primary))]
        if step > 0:
            opts.append(("step", num(step)))
        if p.get("show_value"):
            self.h("SliderRow")
            decimals = 0 if step == int(step) and float(p.get("minimum", 0)) == int(
                float(p.get("minimum", 0))) else 2
            sl = "{" + ", ".join(f"{k!r}: {v}" for k, v in opts) + "}"
            return Built("SliderRow", [
                ("slider", sl), ("color", self.csrc(st["foreground"])),
                ("font_size", dp(float(st["font_size"]))), ("decimals", str(decimals))])
        return Built(self.k("Slider"), opts)

    def b_spinbox(self, node: Node, st: dict) -> Built:
        p = node.props
        self.h("SpinBox")
        bg = node.style.get("background") or self.theme.surface
        return Built("SpinBox", [
            ("minimum", num(p.get("minimum", 0))), ("maximum", num(p.get("maximum", 100))),
            ("value", num(p.get("value", 0))), ("step", num(p.get("step", 1))),
            ("decimals", str(int(p.get("decimals", 0)))), ("wrap", str(bool(p.get("wrap")))),
            ("color", self.csrc(st["foreground"] if node.style.get("foreground")
                                else self.theme.text)),
            ("field", self.csrc(bg)), ("accent", self.csrc(self.theme.primary)),
            ("accent_hover", self.csrc(st["hover_color"])),
            ("button_text", self.csrc(self.theme.button_text)),
            ("border", self.csrc(st["border_color"])),
            ("font_size", dp(float(st["font_size"])))])

    def b_combobox(self, node: Node, st: dict) -> Built:
        p = node.props
        items = [str(i) for i in (p.get("items") or [])]
        cur = int(p.get("current", 0))
        text = items[cur] if 0 <= cur < len(items) else ""
        if p.get("editable"):
            self.h("ComboEdit")
            return Built("ComboEdit", [
                ("text", q(text)), ("values", repr(items)), ("color", self.csrc(st["foreground"])),
                ("font_size", dp(float(st["font_size"])))], [self.paint_post(st)])
        kw = [("text", q(text)), ("values", repr(items)), ("color", self.csrc(st["foreground"])),
              *self.font_kw(st, text_style=False), ("background_normal", q("")),
              ("background_down", q("")), ("background_color", "(0, 0, 0, 0)")]
        return Built(self.k("Spinner"), kw, [self.paint_post(st)])

    def b_listbox(self, node: Node, st: dict) -> Built:
        p = node.props
        self.h("ListBox")
        multi = p.get("selection_mode", "single") != "single"
        return Built("ListBox", [
            ("items", repr([str(i) for i in (p.get("items") or [])])), ("multiple", str(multi)),
            ("color", self.csrc(st["foreground"])), ("selected", self.csrc(self.theme.primary)),
            ("selected_text", self.csrc(self.theme.button_text)),
            ("font_size", dp(float(st["font_size"])))], [self.paint_post(st)])

    def b_segmented_button(self, node: Node, st: dict) -> Built:
        p = node.props
        self.h("Segmented")
        normal = node.style.get("background") or self.theme.surface
        return Built("Segmented", [
            ("items", repr([str(i) for i in (p.get("items") or [])])),
            ("current", str(int(p.get("current", 0)))),
            ("color", self.csrc(node.style.get("foreground") or self.theme.text)),
            ("normal", self.csrc(normal)), ("selected", self.csrc(self.theme.primary)),
            ("selected_text", self.csrc(self.theme.button_text)),
            ("border", self.csrc(st["border_color"])),
            ("font_size", dp(float(st["font_size"])))])

    # ---- data
    def b_table(self, node: Node, st: dict) -> Built:
        p = node.props
        self.h("Table")
        rows = p.get("rows") or []
        rows = [list(r) if isinstance(r, (list, tuple)) else [r] for r in rows]
        header_bg = mix(self.color(st["background"], (1, 1, 1, 1)),
                        self.color(self.theme.border, (0.8, 0.8, 0.8, 1)), 0.6)
        return Built("Table", [
            ("columns", repr([str(c) for c in (p.get("columns") or [])])),
            ("rows", repr([[str(c) for c in r] for r in rows])),
            ("header", str(bool(p.get("show_header", True)))),
            ("editable", str(bool(p.get("editable")))),
            ("selection", q(p.get("selection_mode", "single"))),
            ("color", self.csrc(st["foreground"])), ("header_bg", rgba_src(header_bg)),
            ("selected", rgba_src(mix(self.color(self.theme.primary, (0.4, 0.4, 0.9, 1)),
                                      self.color(st["background"], (1, 1, 1, 1)), 0.7))),
            ("font_size", dp(float(st["font_size"])))], [self.paint_post(st)])

    def b_tree_view(self, node: Node, st: dict) -> Built:
        p = node.props
        self.h("tree")
        return Built("_tree", [
            ("items", repr(p.get("items") or [])), ("header", q(p.get("header", "Items"))),
            ("show_header", str(bool(p.get("show_header")))),
            ("color", self.csrc(st["foreground"])),
            ("font_size", dp(float(st["font_size"])))], [self.paint_post(st)])

    def b_calendar(self, node: Node, st: dict) -> Built:
        p = node.props
        self.h("Calendar")
        return Built("Calendar", [
            ("date", q(p.get("date", ""))),
            ("monday_first", str(p.get("first_weekday", "monday") == "monday")),
            ("week_numbers", str(bool(p.get("show_week_numbers")))),
            ("color", self.csrc(st["foreground"])), ("accent", self.csrc(self.theme.primary)),
            ("accent_text", self.csrc(self.theme.button_text)),
            ("font_size", dp(float(st["font_size"])))], [self.paint_post(st)])


# ------------------------------------------------------------------------------ rendering
def _closure(names: set[str]) -> list[str]:
    seen: set[str] = set()

    def visit(n: str) -> None:
        if n in seen:
            return
        seen.add(n)
        for d in HELPERS[n].needs:
            visit(d)

    for n in sorted(names):
        visit(n)
    return [n for n in ORDER if n in seen]


def _imports(gen: _Gen, helper_names: list[str]) -> tuple[list[str], list[str]]:
    kivy = set(gen.kivy) | {"dp"}
    std = set(gen.std)
    for n in helper_names:
        kivy.update(HELPERS[n].kivy)
        std.update(HELPERS[n].std)
    by_module: dict[str, list[str]] = {}
    for name in sorted(kivy):
        by_module.setdefault(KIVY_MODULES[name], []).append(name)
    lines = [f"from {m} import {', '.join(sorted(ns))}" for m, ns in sorted(by_module.items())]
    # Config must be configured before the window module is imported
    lines.sort(key=lambda s: (not s.startswith("from kivy.config"), s))
    std_lines = [f"import {m}" for m in sorted(std)]
    return std_lines, lines


class KivyAdapter(Adapter):
    framework = "kivy"
    label = "Kivy"

    def base_requirements(self) -> list[str]:
        return ["kivy>=2.3"]

    # ---------------------------------------------------------------- entry
    def generate(self, project: Project, options: GenOptions) -> list[GeneratedFile]:
        gen = _Gen(project, options)
        gen.generate_ui_lines()
        helper_names = _closure(gen.helpers)
        if gen.uses_mouse_buttons:
            gen.config.append("Config.set('input', 'mouse', 'mouse,disable_multitouch')")
            gen.kivy.add("Config")
        ui_body = self._ui_source(gen, project, helper_names)
        files: list[GeneratedFile] = []
        if options.layout == "single":
            files.append(GeneratedFile("main.py", self._single_source(gen, project, options,
                                                                      ui_body)))
        else:
            files.append(GeneratedFile("main.py", self._main_source(gen, project)))
            files.append(GeneratedFile("ui.py", ui_body["ui"]))
            files.append(handlers_file(project, options))
            files.append(GeneratedFile("custom.py", _CUSTOM, overwrite=False))
        reqs = sorted(set(self.requirements(project)) | gen.extra_reqs, key=str.lower)
        files.append(GeneratedFile("requirements.txt", "\n".join(reqs) + "\n"))
        if options.readme:
            files.append(GeneratedFile("README.md", self._readme(gen, project, options)))
        return files

    # ---------------------------------------------------------------- sources
    def _ui_source(self, gen: _Gen, project: Project, helper_names: list[str]) -> dict[str, str]:
        std_lines, kivy_lines = _imports(gen, helper_names)
        std_all = sorted(set(std_lines))
        config = ["", *gen.config] if gen.config else []
        body = "\n".join(gen.lines).rstrip() + "\n"
        helpers = "\n\n".join(HELPERS[n].source for n in helper_names)
        func_defs = []
        for var, name in gen.popups:
            func_defs.append(
                f'def open_{var}():\n    """Open the "{name}" dialog window."""\n'
                f"    WINDOWS[{var!r}].open()\n")
        # the config lines have to run before kivy.core.window is imported
        config_lines = [ln for ln in config if ln]
        head_kivy = [ln for ln in kivy_lines if ln.startswith("from kivy.config")]
        tail_kivy = [ln for ln in kivy_lines if not ln.startswith("from kivy.config")]
        parts = [
            HEADER,
            f'"""User interface of {project.meta.name} (generated).\n\n'
            "``build_ui()`` creates the widgets and returns the root widget. Widgets are\n"
            "available by name in ``WIDGETS``; windows (and dialogs) in ``WINDOWS``.\n"
            '"""\n',
        ]
        imports_block = list(std_all)
        if gen.single is False:
            imports_block.append("import handlers  # noqa: F401  (event handlers)")
        pre: list[str] = []
        if head_kivy:
            pre += head_kivy + config_lines + [""]
        imports_text = "\n".join([*imports_block, *tail_kivy, *sorted(gen.extra_imports)])
        ui = "\n".join(parts) + "\n" + "\n".join(pre) + imports_text + "\n\n\n"
        if helpers:
            ui += "# ---- runtime helpers " + "-" * 56 + "\n" + helpers + "\n\n"
        ui += "WIDGETS = {}\nWINDOWS = {}\n\n\n"
        ui += "def build_ui():\n" + body + "\n\n" + "\n\n".join(func_defs)
        return {
            "ui": ui.rstrip() + "\n",
            "helpers": helpers,
            "imports": imports_text,
            "config_block": "\n".join(head_kivy + config_lines),
            "funcs": "\n\n".join(func_defs),
            "build": "def build_ui():\n" + body,
        }

    def _app_class(self, gen: _Gen, project: Project, *, ui_ref: str, custom: bool) -> str:
        icon = f"asset({gen.main_icon!r})" if gen.main_icon else None
        if icon and not gen.single:
            icon = f"ui.asset({gen.main_icon!r})"
        lines = ["class MainApp(App):", f"    title = {gen.main_title!r}"]
        if icon:
            lines.append(f"    icon = {icon}")
        lines += ["", "    def build(self):", f"        return {ui_ref}build_ui()"]
        if custom:
            lines += ["", "    def on_start(self):",
                      '        hook = getattr(custom, "on_start", None)',
                      "        if hook is not None:", "            hook(self)"]
        return "\n".join(lines) + "\n"

    def _main_source(self, gen: _Gen, project: Project) -> str:
        return (
            f'{HEADER}\n"""Entry point of {project.meta.name}: ``python main.py``."""\n\n'
            "import ui  # first: configures Kivy before the window exists\n"
            "from kivy.app import App\n\nimport custom\n\n\n"
            + self._app_class(gen, project, ui_ref="ui.", custom=True)
            + '\n\nif __name__ == "__main__":\n    MainApp().run()\n'
        )

    def _single_source(self, gen: _Gen, project: Project, options: GenOptions,
                       parts: dict[str, str]) -> str:
        existing = options.existing.get("main.py") if options.preserve_user_code else None
        handlers_src = render_handlers_module(project, existing)
        handlers_src = handlers_src.split("\n", 2)[2] if handlers_src.startswith('"""') \
            else handlers_src
        names = sorted(project.handlers)
        ns = ", ".join(f"{n}={n}" for n in names)
        gen.kivy.add("Window")
        out = [
            HEADER,
            f'"""{project.meta.name} (generated, single file). Run: ``python main.py``."""\n',
        ]
        if parts["config_block"]:
            out.append(parts["config_block"] + "\n")
        out.append(parts["imports"])
        out.append("from kivy.app import App\nfrom types import SimpleNamespace\n")
        out.append("\n# ---- event handlers (edit between the py_vui markers) " + "-" * 24)
        out.append(handlers_src.rstrip() + "\n")
        out.append(f"handlers = SimpleNamespace({ns})\n")
        if parts["helpers"]:
            out.append("\n# ---- runtime helpers " + "-" * 56)
            out.append(parts["helpers"])
        out.append("\nWIDGETS = {}\nWINDOWS = {}\n\n")
        out.append(parts["build"])
        if parts["funcs"]:
            out.append("\n" + parts["funcs"])
        out.append("\n" + self._app_class(gen, project, ui_ref="", custom=False))
        out.append('\nif __name__ == "__main__":\n    MainApp().run()\n')
        text = "\n".join(out)
        return re.sub(r"\n{4,}", "\n\n\n", text).rstrip() + "\n"

    def _readme(self, gen: _Gen, project: Project, options: GenOptions) -> str:
        single = options.layout == "single"
        layout = (
            "* `main.py` - the whole app (handlers, helpers, UI)\n" if single else
            "* `main.py` - `App` subclass, run this\n"
            "* `ui.py` - `build_ui()`, plus `WIDGETS` / `WINDOWS` registries\n"
            "* `handlers.py` - your event handlers (code between the `py_vui` markers is kept)\n"
            "* `custom.py` - your own code, never overwritten (`on_start(app)` hook)\n"
        )
        limits = [
            "Hover/pressed colours and rounded corners are drawn with canvas instructions.",
            "Kivy has no menu bar: window menus are rendered as an `ActionBar` above the content.",
            "Fonts: `.ttf` / `.otf` files are used as given; system font names are mapped to "
            "Kivy's bundled fonts (monospace -> Roboto Mono, DejaVu -> DejaVu Sans, anything else "
            "-> Roboto) because Kivy cannot load fonts by family name.",
            "Grid containers and flex containers that wrap or use `grow` are re-laid out "
            "whenever their container is resized.",
            "Dialog windows are `Popup`s and always block the window beneath them.",
            "Grid containers are positioned by the `_grid()` helper (spans, sticky and weights "
            "match the editor); `GridLayout` cannot span cells.",
            "Dropdowns, dials, progress bars and spin boxes are small custom widgets built from "
            "Kivy primitives.",
            *gen.notes,
        ]
        seen: list[str] = []
        for item in limits:
            if item not in seen:
                seen.append(item)
        return (
            f"# {project.meta.name}\n\n{project.meta.description}\n\n"
            "Generated by [py_vui](https://github.com/dfunani/py_vui) for **Kivy**.\n\n"
            "## Run\n\n```bash\npip install -r requirements.txt\npython main.py\n```\n\n"
            f"## Files\n\n{layout}* `requirements.txt`\n\n"
            "## Handlers\n\nEvent handlers receive a `UiEvent` with `.widget` plus details "
            "(`value`, `pos`, `key`, ...). Look widgets up with `ui.WIDGETS['name']` "
            "(or `WIDGETS` in single-file mode).\n\n"
            "## Kivy notes and limitations\n\n" + "\n".join(f"* {x}" for x in seen) + "\n"
        )


_CUSTOM = textwrap.dedent('''\
    """Your own code. py_vui never overwrites this file."""


    def on_start(app):
        """Called once after the window is shown. ``app`` is the running ``MainApp``."""
''')

register_adapter(KivyAdapter())
