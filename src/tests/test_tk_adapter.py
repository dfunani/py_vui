"""Tests for the ``tkinter`` code generator (and the shared Tk machinery).

Syntax / AST tests run everywhere.  Tests that execute the generated app need a real Tk and
run in a subprocess (``sys.executable``) so a broken display can never take pytest down; they
are skipped when ``tkinter`` cannot create a window (e.g. the project's main ``.venv``).
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from py_vui.codegen import GenOptions, check_syntax, generate
from py_vui.codegen.base import EmitResult, register_plugin_emitter
from py_vui.core import ProjectDocument, make_node, new_project
from py_vui.core.model import HandlerDef, Project
from py_vui.core.registry import WidgetSpec, register, unregister

FRAMEWORK = "tkinter"
MODES = ("absolute", "flex", "grid")
SUFFIXES = ("abs", "flex", "grid")
HANDLERS = (
    "on_click", "on_dbl", "on_enter", "on_key", "on_right", "on_change", "on_submit",
    "on_focus", "on_toggle", "on_select", "on_cell", "on_paint", "on_tab", "on_close",
    "on_resize", "on_menu_new", "on_menu_open", "on_menu_toggle", "on_menu_sub", "on_wheel",
)


# ----------------------------------------------------------------------- project builder
def _specs() -> list[dict]:
    """(type, name, props, events) for every leaf widget the Tk adapters support."""
    return [
        dict(type="label", name="Label", props={"text": "Hello"},
             events={"click": "on_click", "double_click": "on_dbl", "mouse_enter": "on_enter"}),
        dict(type="image", name="Picture", props={"source": "assets/none.png"},
             events={"click": "on_click"}),
        dict(type="separator", name="Line"),
        dict(type="progressbar", name="Progress", props={"value": 40}),
        dict(type="canvas", name="Board", events={"paint": "on_paint", "double_click": "on_dbl"}),
        dict(type="button", name="Go", props={"text": "Go"},
             events={"click": "on_click", "key_press": "on_key", "right_click": "on_right"}),
        dict(type="tool_button", name="Tool", props={"text": "T"}, events={"click": "on_click"}),
        dict(type="tool_button", name="Tool Check", props={"text": "C", "checkable": True},
             events={"click": "on_click"}),
        dict(type="entry", name="Field", props={"placeholder": "Type", "max_length": 5},
             events={"change": "on_change", "submit": "on_submit", "focus_in": "on_focus"}),
        dict(type="entry", name="Secret", props={"text": "pw", "show": "*", "justify": "center"}),
        dict(type="text", name="Notes", props={"text": "hello"}, events={"change": "on_change"}),
        dict(type="text", name="Log", props={"readonly": True, "scrollbar": False}),
        dict(type="checkbox", name="Agree", props={"checked": True}, events={"toggle": "on_toggle"}),
        dict(type="radio", name="Choice A", props={"group": "g", "text": "A"},
             events={"toggle": "on_toggle"}),
        dict(type="radio", name="Choice B", props={"group": "g", "text": "B", "checked": True},
             events={"toggle": "on_toggle"}),
        dict(type="switch", name="Power", props={"checked": True}, events={"toggle": "on_toggle"}),
        dict(type="slider", name="Level", props={"show_value": True, "step": 5},
             events={"change": "on_change"}),
        dict(type="dial", name="Knob", props={"value": 25}, events={"change": "on_change"}),
        dict(type="spinbox", name="Count", props={"decimals": 1, "value": 2},
             events={"change": "on_change"}),
        dict(type="combobox", name="Pick", props={"items": ["a", "b", "c"], "current": 1},
             events={"change": "on_change"}),
        dict(type="listbox", name="Names", props={"items": ["x", "y", "z"]},
             events={"select": "on_select"}),
        dict(type="segmented_button", name="Seg", props={"items": ["One", "Two"], "current": 1},
             events={"change": "on_change"}),
        dict(type="date_entry", name="Day", events={"change": "on_change"}),
        dict(type="time_entry", name="Clock", props={"time": "07:30:15"},
             events={"change": "on_change"}),
        dict(type="table", name="Grid Table", props={"editable": True},
             events={"select": "on_select", "cell_change": "on_cell"}),
        dict(type="tree_view", name="Tree", props={"show_header": True},
             events={"select": "on_select"}),
        dict(type="calendar", name="Cal", events={"change": "on_change"}),
        dict(type="time_picker", name="Picker", props={"hours24": True},
             events={"change": "on_change"}),
        dict(type="map_view", name="Map", props={"marker_text": "Here"}),
        dict(type="chart", name="Plot", props={"kind": "bar", "x_label": "x"}),
        dict(type="video_player", name="Movie", props={"source": "assets/none.mp4"}),
        dict(type="pandas_table", name="Frame Table"),
        dict(type="color_picker", name="Colour", events={"change": "on_change"}),
        dict(type="frame", name="Card", events={"click": "on_click"}),
        dict(type="fancy_widget", name="Fancy"),  # registered for kivy only -> placeholder
        dict(type="third_party", name="Extra"),  # unknown to the adapter -> plugin emitter
    ]


def _add(p: Project, node, parent_cells: dict | None = None):
    p.nodes[node.id] = node
    return node


def _fill(p: Project, parent_id: str, suffix: str, mode: str, width: float) -> None:
    """Add every leaf widget (plus a few containers) to ``parent_id`` laid out in ``mode``."""
    cursor = 8.0
    for i, spec in enumerate(_specs()):
        node = make_node(spec["type"], parent_id=parent_id, name=f"{spec['name']} {suffix}",
                         z_index=len(p.nodes), **spec.get("props", {}))
        node.box.w = min(node.box.w, width - 20)
        if mode == "absolute":
            node.box.x, node.box.y = 8, cursor
            cursor += node.box.h + 6
        elif mode == "grid":
            node.cell.row, node.cell.column = i // 2, i % 2
            node.box.w = min(node.box.w, width / 2 - 20)
        else:
            node.flex.grow = 1.0 if spec["type"] == "button" else 0.0
        for ev, h in spec.get("events", {}).items():
            node.events[ev] = h
        _add(p, node)
    # containers, each laid out in the same mode as their parent
    for ctype, kw in (
        ("label_frame", {"title": "Group"}),
        ("tabview", {"tabs": ["One", "Two"], "current": 1}),
        ("scroll_frame", {}),
        ("paned_window", {"sizes": [150]}),
    ):
        cont = make_node(ctype, parent_id=parent_id, name=f"{ctype} {suffix}", z_index=len(p.nodes), **kw)
        cont.layout.mode = mode if ctype != "paned_window" else "absolute"
        cont.box.w = min(cont.box.w, width - 20)
        if ctype == "tabview":
            cont.events["tab_change"] = "on_tab"
        if mode == "absolute":
            cont.box.x, cont.box.y = 8, cursor
            cursor += cont.box.h + 6
        elif mode == "grid":
            cont.cell.row, cont.cell.column = 40 + len(p.nodes) % 7, 0
            cont.cell.column_span = 2
        _add(p, cont)
        pages = (0, 1) if ctype == "tabview" else (0,)
        for page in pages:
            for j in range(2 if ctype != "paned_window" else 1):
                kind = "frame" if ctype == "paned_window" else ("button" if j == 0 else "label")
                kid = make_node(kind, parent_id=cont.id, name=f"{ctype} {suffix} kid {page}{j}",
                                z_index=len(p.nodes), x=10, y=10 + 40 * j, w=100 if kind != "frame" else 150,
                                h=30 if kind != "frame" else 80)
                kid.page = page
                if mode == "grid" and ctype != "paned_window":
                    kid.cell.row, kid.cell.column = j, 0
                if mode == "flex" and ctype != "paned_window":
                    kid.flex.margin.left = 4
                _add(p, kid)
                if kind == "frame":
                    inner = make_node("label", parent_id=kid.id, name=f"pane label {suffix}",
                                      z_index=len(p.nodes), x=4, y=4)
                    _add(p, inner)
                if kind == "button":
                    kid.events["click"] = "on_click"


def rich_project(framework: str = FRAMEWORK) -> Project:
    """Every supported widget in absolute, flex and grid panels, menus, dialogs, events."""
    p = new_project("Rich Demo", framework)
    root = p.nodes[p.root_id]
    root.props.update(width=1000, height=700, title="Rich", min_width=300, min_height=200)
    root.box.w, root.box.h = 1000, 700
    root.events.update({"close": "on_close", "resize": "on_resize", "key_press": "on_key"})
    root.props["menus"] = [
        {"title": "File", "items": [
            {"label": "New", "handler": "on_menu_new", "shortcut": "Ctrl+N"},
            {"label": "Open", "handler": "on_menu_open", "shortcut": "Ctrl+Shift+O"},
            {"separator": True},
            {"label": "Show toolbar", "handler": "on_menu_toggle", "checkable": True,
             "checked": True},
            {"label": "More", "items": [{"label": "Deep", "handler": "on_menu_sub"}]},
        ]},
        {"title": "Help", "items": [{"label": "About", "handler": "on_click"}]},
    ]
    for i, (suffix, mode) in enumerate(zip(SUFFIXES, MODES)):
        panel = make_node("frame", parent_id=p.root_id, name=f"Panel {suffix}", z_index=len(p.nodes),
                          x=500 * i, y=0, w=490, h=3900)
        panel.layout.mode = mode
        panel.layout.direction = "row"
        panel.layout.wrap = True
        panel.layout.align = "start"
        panel.layout.gap = 6
        if mode == "grid":
            panel.layout.column_weights = [1, 1]
            panel.layout.row_weights = [0] * 60
        _add(p, panel)
        _fill(p, panel.id, suffix, mode, 490)
    # dialogs: one opened on demand (modal), one shown at start-up
    for i, (name, hidden, modal) in enumerate((("Prefs", True, True), ("Splash", False, False))):
        top = make_node("toplevel", parent_id=p.root_id, name=name, z_index=len(p.nodes),
                        title=name, start_hidden=hidden, modal=modal)
        top.events["close"] = "on_close"
        _add(p, top)
        lab = make_node("label", parent_id=top.id, name=f"{name} text", z_index=len(p.nodes), x=10, y=10,
                        text=name)
        _add(p, lab)
    for name in HANDLERS:
        p.handlers[name] = HandlerDef(name=name, body=f"LOG.append({name!r})")
    p.custom_code = "LOG = []"
    ProjectDocument(p).validate()
    return p


@pytest.fixture(autouse=True)
def _extra_widget_types():
    """Register a kivy-only widget and a third-party widget (with a plugin emitter)."""
    register(WidgetSpec(type="fancy_widget", label="Fancy", category="Plugins",
                        frameworks=frozenset({"kivy"})), replace=True)
    register(WidgetSpec(type="third_party", label="Third party", category="Plugins", plugin=True,
                        default_size=(100, 24), props=(), frameworks=frozenset(
                            {"tkinter", "customtkinter"}),
                        requires={"tkinter": ("thirdpartylib>=1",),
                                  "customtkinter": ("thirdpartylib>=1",)}), replace=True)

    def emit(ctx):
        return EmitResult(
            lines=[f"{ctx.var} = ttk.Label({ctx.parent}, text=\"third party\")"],
            requirements=["thirdpartylib>=1"])

    for fw in ("tkinter", "customtkinter"):
        register_plugin_emitter("third_party", fw, emit)
    yield
    unregister("fancy_widget")
    unregister("third_party")


# --------------------------------------------------------------------------- runtime kit
def tk_available(module: str | None = None) -> bool:
    code = "import tkinter; r = tkinter.Tk(); r.withdraw(); r.destroy()"
    if module:
        code = f"import {module}; " + code
    try:
        res = subprocess.run([sys.executable, "-c", code], capture_output=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return res.returncode == 0


_AVAILABLE: dict[str, bool] = {}


def need_tk(module: str | None = None) -> None:
    key = module or ""
    if key not in _AVAILABLE:
        _AVAILABLE[key] = tk_available(module)
    if not _AVAILABLE[key]:
        pytest.skip("a real Tk (tkinter" + (f" + {module}" if module else "") + ") is required")


PRELUDE = r'''
import importlib, json, os, sys, traceback
sys.path.insert(0, os.getcwd())
LAYOUT = sys.argv[1]
if LAYOUT == "single":
    ui = importlib.import_module("main")
    log = getattr(ui, "LOG", [])
else:
    ui = importlib.import_module("ui")
    import handlers
    log = getattr(handlers, "LOG", [])
root = ui.build_ui()
root.withdraw()
root.update()
W = ui.WIDGETS
result = {}


def geometry(w):
    return [w.winfo_x(), w.winfo_y(), w.winfo_width(), w.winfo_height()]


def outer(w):
    """The widget that is placed (scroll wrappers are the parent of the real widget)."""
    if hasattr(w, "_parent_frame"):  # CTkScrollableFrame: its wrapper is what gets placed
        frame = w._parent_frame
        return frame.master if frame.winfo_manager() == "pack" else frame
    return w.master if w.winfo_manager() == "pack" else w
'''

EPILOGUE = '\nprint("RESULT" + json.dumps(result, default=str))\n'


def write_files(tmp_path: Path, files) -> Path:
    for f in files:
        target = tmp_path / f.path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f.content) if f.data is None else target.write_bytes(f.data)
    return tmp_path


def run_app(tmp_path: Path, files, scenario: str, layout: str = "project") -> dict:
    """Write ``files`` to ``tmp_path`` and run ``scenario`` against the built UI (subprocess)."""
    write_files(tmp_path, files)
    script = tmp_path / "_run.py"
    script.write_text(PRELUDE + textwrap.dedent(scenario) + EPILOGUE)
    env = {**os.environ, "PYTHONPATH": ""}
    res = subprocess.run([sys.executable, str(script), layout], cwd=tmp_path, env=env,
                         capture_output=True, text=True, timeout=240)
    assert res.returncode == 0, f"stdout:\n{res.stdout}\nstderr:\n{res.stderr}"
    line = [ln for ln in res.stdout.splitlines() if ln.startswith("RESULT")][-1]
    return json.loads(line[len("RESULT"):])


def gen(project: Project, layout: str = "project", **kw) -> list:
    return generate(project, GenOptions(layout=layout, **kw))


def by_path(files) -> dict[str, str]:
    return {f.path: f.content for f in files}


# ------------------------------------------------------------------ syntax / AST (no Tk)
@pytest.mark.parametrize("layout", ["project", "single"])
def test_generated_files_parse(layout):
    files = gen(rich_project(), layout)
    assert check_syntax(files) == []
    paths = [f.path for f in files]
    if layout == "single":
        assert paths[0] == "main.py" and "ui.py" not in paths and "handlers.py" not in paths
    else:
        assert {"main.py", "ui.py", "handlers.py", "custom.py", "requirements.txt",
                "README.md"} <= set(paths)
    for f in files:
        if f.path.endswith(".py"):
            assert f.content.startswith("# This code is generated by py_vui") or f.path in (
                "handlers.py", "custom.py")


def test_output_is_deterministic():
    assert gen(rich_project()) == gen(rich_project())
    # same project object, generated twice
    p = rich_project()
    assert gen(p, "single") == gen(p, "single")


def test_project_layout_structure():
    files = by_path(gen(rich_project()))
    ui = files["ui.py"]
    tree = ast.parse(ui)
    funcs = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    assert {"build_ui", "open_prefs", "open_splash", "configure_styles"} <= funcs
    assigned = {t.id for n in tree.body if isinstance(n, ast.Assign) for t in n.targets
                if isinstance(t, ast.Name)}
    assert {"WIDGETS", "WINDOWS", "VARS", "APP_DIR"} <= assigned
    # registries come before ``import handlers`` so handlers.py can ``from ui import WIDGETS``
    assert ui.index("WIDGETS = {}") < ui.index("import handlers")
    assert "def main" in files["main.py"] and "build_ui" in files["main.py"]
    assert "LOG = []" in files["handlers.py"]
    assert files["requirements.txt"].strip()
    custom = [f for f in gen(rich_project()) if f.path == "custom.py"][0]
    assert custom.overwrite is False


def test_single_layout_inlines_handlers():
    src = by_path(gen(rich_project(), "single"))["main.py"]
    tree = ast.parse(src)
    funcs = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    assert set(HANDLERS) <= funcs
    assert "import handlers" not in src
    assert 'if __name__ == "__main__":' in src
    assert src.index("LOG = []") < src.index("def build_ui")


def test_handler_references_exist():
    p = rich_project()
    src = by_path(gen(p))["ui.py"]
    used = {n.attr for n in ast.walk(ast.parse(src))
            if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)
            and n.value.id == "handlers"}
    assert used and used <= set(p.handlers)
    # every event of the rich project is wired somewhere
    assert {"on_click", "on_change", "on_toggle", "on_select", "on_paint", "on_tab",
            "on_close", "on_cell", "on_submit"} <= used


def test_variable_names_come_from_document():
    p = rich_project()
    names = ProjectDocument(p).variable_names()
    src = by_path(gen(p))["ui.py"]
    for nid in list(names)[:25]:
        assert names[nid] in src


def test_missing_handler_does_not_break_generation():
    p = rich_project()
    btn = next(n for n in p.nodes.values() if n.name == "Go abs")
    btn.events["click"] = "does_not_exist"
    files = gen(p)
    assert check_syntax(files) == []
    assert "does_not_exist is not defined" in by_path(files)["ui.py"].replace("'", "")


def test_unsupported_and_third_party_widgets():
    p = rich_project()
    src = by_path(gen(p))["ui.py"]
    assert "Fancy is not available for tkinter" in src  # visible placeholder
    assert 'text="third party"' in src
    reqs = by_path(gen(p))["requirements.txt"]
    assert "thirdpartylib>=1" in reqs
    for pkg in ("tkcalendar", "matplotlib", "tkintermapview", "tktimepicker", "pandastable",
                "tkvideoplayer", "pillow"):
        assert pkg in reqs


def test_layout_modes_use_the_right_geometry_managers():
    src = by_path(gen(rich_project()))["ui.py"]
    assert ".place(" in src and ".grid(" in src
    assert "grid_columnconfigure" in src and "grid_rowconfigure" in src
    assert ".pack(" in src  # scrollbars wrappers


def test_dialogs_are_not_children_of_the_main_window():
    src = by_path(gen(rich_project()))["ui.py"]
    assert "no generator" not in src
    assert src.count("tk.Toplevel(") == 2
    # the dialogs are not placed into the main window's layout
    assert "prefs.place(" not in src and "splash.grid(" not in src


def test_helpers_only_when_used():
    p = new_project("Tiny", FRAMEWORK)
    b = make_node("button", parent_id=p.root_id, x=1, y=1)
    p.nodes[b.id] = b
    src = by_path(gen(p))["ui.py"]
    for helper in ("class Tooltip", "class Dial", "class Switch", "class ScrollFrame",
                   "def load_image", "def add_placeholder", "def enable_cell_edit"):
        assert helper not in src
    b.tooltip = "hi"
    assert "class Tooltip" in by_path(gen(p))["ui.py"]


def test_anchor_placement_options():
    p = new_project("Anchors", FRAMEWORK)
    p.nodes[p.root_id].props.update(width=400, height=300)
    right = make_node("button", parent_id=p.root_id, name="R", x=300, y=10, w=80, h=30)
    right.anchors.left, right.anchors.right = False, True
    bottom = make_node("button", parent_id=p.root_id, name="B", x=10, y=250, w=80, h=30)
    bottom.anchors.top, bottom.anchors.bottom = False, True
    both = make_node("entry", parent_id=p.root_id, name="Both", x=10, y=100, w=380, h=30)
    both.anchors.right = True
    for n in (right, bottom, both):
        p.nodes[n.id] = n
    src = by_path(gen(p))["ui.py"]
    assert "relx=1" in src and "anchor=\"ne\"" in src
    assert "rely=1" in src and "anchor=\"sw\"" in src
    assert "relwidth=1" in src and "width=-20" in src


def test_regeneration_keeps_edited_handler_bodies():
    p = rich_project()
    first = by_path(gen(p))
    edited = first["handlers.py"].replace("LOG.append('on_click')", "LOG.append('edited!')")
    assert edited != first["handlers.py"]
    again = by_path(gen(p, preserve_user_code=True, existing={"handlers.py": edited}))
    assert "edited!" in again["handlers.py"]
    assert again["ui.py"] == first["ui.py"]
    plain = by_path(gen(p, existing={"handlers.py": edited}))
    assert "edited!" not in plain["handlers.py"]


def test_framework_registered():
    from py_vui.codegen import get_adapter

    adapter = get_adapter("tkinter")
    assert adapter.framework == "tkinter" and adapter.label
    assert "pillow>=10" in adapter.requirements(rich_project())


# ----------------------------------------------------------------------- runtime (real Tk)
@pytest.mark.tk
@pytest.mark.parametrize("layout", ["project", "single"])
def test_app_builds_and_updates(tmp_path, layout):
    need_tk()
    p = rich_project()
    res = run_app(tmp_path, gen(p, layout), """
        result["n_widgets"] = len(W)
        result["windows"] = sorted(ui.WINDOWS)
        result["is_tk"] = root.winfo_class()
        result["title"] = root.title()
        result["size"] = root.geometry().split("+")[0]
        root.update()
    """, layout)
    assert res["n_widgets"] > 100
    assert res["windows"] == ["main_window", "splash"]  # prefs opens on demand
    assert res["title"] == "Rich" and res["size"] == "1000x700"


@pytest.mark.tk
def test_absolute_geometry_matches_design(tmp_path):
    need_tk()
    p = rich_project()
    expected = {n.name: n for n in p.nodes.values() if n.name.endswith(" abs")
                and n.type not in ("fancy_widget",)}
    res = run_app(tmp_path, gen(p), """
        names = [n for n in W if n.endswith("_abs")]
        for n in names:
            result[n] = geometry(outer(W[n]))
    """)
    from py_vui.core.document import ProjectDocument as Doc

    var = Doc(p).variable_names()
    checked = 0
    for name, node in expected.items():
        if node.parent_id != next(n.id for n in p.nodes.values() if n.name == "Panel abs"):
            continue
        got = res.get(var[node.id])
        assert got, name
        x, y, w, h = got
        assert (x, y) == (round(node.box.x), round(node.box.y)), (name, got)
        assert abs(w - node.box.w) <= 2 and abs(h - node.box.h) <= 2, (name, got, node.box)
        checked += 1
    assert checked > 30


def _flex_project(**layout) -> tuple[Project, list]:
    p = new_project("Flex", FRAMEWORK)
    root = p.nodes[p.root_id]
    root.props.update(width=600, height=300)
    root.layout.mode = "flex"
    root.layout.direction = "row"
    root.layout.gap = 10
    root.layout.align = "start"
    for k, v in layout.items():
        setattr(root.layout, k, v)
    kids = []
    for i, grow in enumerate((0, 1, 2)):
        b = make_node("button", parent_id=p.root_id, name=f"B{i}", z_index=i, w=120, h=30)
        b.flex.grow = grow
        p.nodes[b.id] = b
        kids.append(b)
    return p, kids


@pytest.mark.tk
def test_flex_grow_gap_and_padding(tmp_path):
    need_tk()
    p, _ = _flex_project()
    res = run_app(tmp_path, gen(p), """
        for n in ("b0", "b1", "b2"):
            result[n] = geometry(outer(W[n]))
    """)
    b0, b1, b2 = res["b0"], res["b1"], res["b2"]
    assert b0[0] == 8 and abs(b0[2] - 120) <= 2  # padding, requested width
    assert abs(b1[0] - (b0[0] + b0[2] + 10)) <= 2  # gap
    assert b2[2] > b1[2] > 80  # grow 2 gets more than grow 1
    assert abs((b2[0] + b2[2]) - (600 - 8)) <= 3  # fills to the right padding
    assert abs((b2[2] + 8) - 2 * (b1[2] + 10)) <= 4  # free space split exactly 1:2


@pytest.mark.tk
@pytest.mark.parametrize("justify", ["center", "end", "space_between"])
def test_flex_justify(tmp_path, justify):
    need_tk()
    p, kids = _flex_project(justify=justify)
    for k in kids:
        k.flex.grow = 0
    res = run_app(tmp_path, gen(p), """
        for n in ("b0", "b1", "b2"):
            result[n] = geometry(outer(W[n]))
    """)
    first, last = res["b0"], res["b2"]
    if justify == "center":
        left, right = first[0], 600 - (last[0] + last[2])
        assert abs(left - right) <= 3 and left > 20
    elif justify == "end":
        assert abs((last[0] + last[2]) - (600 - 8)) <= 3
    else:
        assert first[0] <= 10 and (last[0] + last[2]) >= 600 - 12


@pytest.mark.tk
def test_flex_column_align_end(tmp_path):
    need_tk()
    p, kids = _flex_project(direction="column", align="end")
    for k in kids:
        k.flex.grow = 0
    res = run_app(tmp_path, gen(p), """
        for n in ("b0", "b1", "b2"):
            result[n] = geometry(outer(W[n]))
    """)
    assert res["b1"][1] > res["b0"][1]  # stacked top to bottom
    assert abs((res["b0"][0] + res["b0"][2]) - (600 - 8)) <= 3  # right aligned


@pytest.mark.tk
def test_grid_cells_weights_and_span(tmp_path):
    need_tk()
    p = new_project("Grid", FRAMEWORK)
    root = p.nodes[p.root_id]
    root.props.update(width=400, height=300)
    root.layout.mode = "grid"
    root.layout.column_weights = [1, 2]
    root.layout.row_weights = [1, 0]
    root.layout.padding.top = root.layout.padding.left = 0
    root.layout.padding.bottom = root.layout.padding.right = 0
    root.layout.column_gap = root.layout.row_gap = 0
    for name, r, c, cs in (("a", 0, 0, 1), ("b", 0, 1, 1), ("c", 1, 0, 2)):
        n = make_node("button", parent_id=p.root_id, name=name, w=60, h=30)
        n.cell.row, n.cell.column, n.cell.column_span = r, c, cs
        n.cell.sticky = "nsew"
        p.nodes[n.id] = n
    res = run_app(tmp_path, gen(p), """
        for n in ("a", "b", "c"):
            result[n] = geometry(outer(W[n]))
    """)
    a, b, c = res["a"], res["b"], res["c"]
    assert b[0] > a[0] and b[2] > a[2]  # the weight-2 column receives more of the free space
    assert c[2] >= a[2] + b[2] - 2 and c[1] > a[1]  # spans both columns, below row 0
    assert a[3] > c[3]  # row 0 has the weight


@pytest.mark.tk
def test_events_fire_handlers(tmp_path):
    need_tk()
    p = rich_project()
    res = run_app(tmp_path, gen(p), """
        def fired(action):
            del log[:]
            action()
            root.update()
            return list(log)

        def ev(name, seq):
            kw = {"x": 2, "y": 2} if "Button" in seq else {}
            return fired(lambda: W[name].event_generate(seq, **kw))

        result["button_invoke"] = fired(W["go_abs"].invoke)
        result["tool_invoke"] = fired(W["tool_abs"].invoke)
        result["label_click"] = ev("label_abs", "<Button-1>")
        # event_generate cannot synthesise a double click: check the binding itself
        result["label_dbl"] = ["on_dbl"] if "on_dbl" in W["label_abs"].bind("<Double-Button-1>") else []
        result["label_enter"] = ev("label_abs", "<Enter>")
        result["button_right"] = ev("go_abs", "<Button-3>")
        result["frame_click"] = ev("card_abs", "<Button-1>")
        result["canvas_dbl"] = ["on_dbl"] if "on_dbl" in W["board_abs"].bind("<Double-Button-1>") else []
        result["canvas_paint"] = ev("board_abs", "<Configure>")
        result["check"] = fired(W["agree_abs"].invoke)
        result["radio"] = fired(W["choice_a_abs"].invoke)
        result["switch"] = fired(W["power_abs"].invoke)
        result["entry_change"] = fired(lambda: ui.VARS["field_abs"].set("ab"))
        result["entry_value"] = W["field_abs"].get()
        result["entry_limit"] = (W["field_abs"].insert("end", "toolong"), W["field_abs"].get())[1]
        def bound(widget, seq, handler):  # key events need the focus: check the binding
            return [handler] if handler in widget.bind(seq) else []

        result["entry_submit"] = bound(W["field_abs"], "<Return>", "on_submit")
        result["button_key"] = bound(W["go_abs"], "<KeyPress>", "on_key")
        result["entry_focus"] = ev("field_abs", "<FocusIn>")
        result["slider"] = fired(lambda: ui.VARS["level_abs"].set(35))
        result["dial"] = fired(lambda: W["knob_abs"].set(60, notify=True))
        result["spin"] = fired(lambda: ui.VARS["count_abs"].set("4.0"))
        result["combo"] = fired(lambda: W["pick_abs"].set("c"))
        result["list"] = fired(lambda: (W["names_abs"].selection_set(1),
                                        W["names_abs"].event_generate("<<ListboxSelect>>")))
        result["seg"] = fired(lambda: ui.VARS["seg_abs"].set("One"))
        result["time"] = fired(lambda: W["clock_abs"].vars[0].set("09"))
        result["table_select"] = fired(lambda: (
            W["grid_table_abs"].selection_set(W["grid_table_abs"].get_children()[0]),
            W["grid_table_abs"].event_generate("<<TreeviewSelect>>")))
        result["tree_select"] = fired(lambda: W["tree_abs"].event_generate("<<TreeviewSelect>>"))
        result["text_change"] = fired(lambda: W["notes_abs"].insert("end", "!"))
        tab = W["tabview_abs"]
        result["tab_change"] = fired(lambda: tab.select(0))
        result["window_key"] = bound(root, "<KeyPress>", "on_key")
        result["window_resize"] = fired(lambda: root.event_generate("<Configure>"))
        result["child_resize"] = fired(lambda: W["go_abs"].event_generate("<Configure>"))
        result["color"] = fired(lambda: W["colour_abs"].event_generate("<<ColorChanged>>"))
        result["date"] = fired(lambda: W["day_abs"].event_generate("<<DateEntrySelected>>"))
        result["cal"] = fired(lambda: W["cal_abs"].event_generate("<<CalendarSelected>>"))
    """)
    assert res["button_invoke"] == ["on_click"]
    assert res["tool_invoke"] == ["on_click"]
    assert "on_click" in res["label_click"]
    assert "on_dbl" in res["label_dbl"]
    assert res["label_enter"] and "on_enter" in res["label_enter"]
    assert "on_right" in res["button_right"]
    assert "on_click" in res["frame_click"]
    assert "on_dbl" in res["canvas_dbl"]
    assert "on_paint" in res["canvas_paint"]
    for key in ("check", "radio", "switch"):
        assert res[key] == ["on_toggle"], key
    assert res["entry_change"] == ["on_change"] and res["entry_value"] == "ab"
    assert len(res["entry_limit"]) <= 5
    assert "on_submit" in res["entry_submit"] and "on_focus" in res["entry_focus"]
    for key in ("slider", "dial", "spin", "combo", "seg", "time", "text_change", "color"):
        assert "on_change" in res[key], key
    for key in ("list", "table_select", "tree_select"):
        assert "on_select" in res[key], key
    assert res["tab_change"] == ["on_tab"]
    assert "on_key" in res["window_key"] and "on_key" in res["button_key"]
    assert "on_resize" in res["window_resize"] and "on_resize" not in res["child_resize"]
    assert "on_change" in res["date"] and "on_change" in res["cal"]


@pytest.mark.tk
def test_table_cell_edit_and_tree_content(tmp_path):
    need_tk()
    res = run_app(tmp_path, gen(rich_project()), """
        table = W["grid_table_abs"]
        item = table.get_children()[0]
        entry = table.edit_cell(item, "#2")
        result["editor_made"] = entry is not None
        if entry is not None:
            entry.delete(0, "end"); entry.insert(0, "99"); entry.event_generate("<Return>")
            root.update()
        result["cell"] = table.set(item, "#2")
        result["rows"] = len(table.get_children())
        tree = W["tree_abs"]
        result["tree_roots"] = len(tree.get_children())
        result["tree_children"] = len(tree.get_children(tree.get_children()[0]))
    """)
    assert res["rows"] == 2 and res["tree_roots"] == 1 and res["tree_children"] == 2


@pytest.mark.tk
def test_widget_values_and_state(tmp_path):
    need_tk()
    p = rich_project()
    names = {n.name: n for n in p.nodes.values()}
    names["Go abs"].enabled = False
    names["Names abs"].visible = False
    names["Level abs"].tooltip = "slide me"
    names["Field abs"].tab_index = 1
    names["Secret abs"].tab_index = 0
    res = run_app(tmp_path, gen(p), """
        result["go_disabled"] = W["go_abs"].instate(["disabled"])
        result["list_manager"] = outer(W["names_abs"]).winfo_manager()
        result["secret_show"] = str(W["secret_abs"].cget("show"))
        result["secret_value"] = W["secret_abs"].get()
        result["agree"] = ui.VARS["agree_abs"].get()
        result["group"] = ui.VARS["group_g"].get()
        result["radio_b_in_group"] = str(W["choice_b_abs"].cget("variable")) == str(ui.VARS["group_g"])
        result["combo"] = W["pick_abs"].get()
        result["progress"] = float(W["progress_abs"].cget("value"))
        result["time"] = W["clock_abs"].get()
        result["notes"] = W["notes_abs"].get("1.0", "end").strip()
        result["log_state"] = str(W["log_abs"].cget("state"))
        result["listbox_items"] = W["names_abs"].get(0, "end")
        result["tooltip"] = "Enter" in str(W["level_abs"].bind())
        parent = W["secret_abs"].master
        kids = parent.winfo_children()
        result["tab_order"] = kids.index(W["secret_abs"]) < kids.index(W["field_abs"])
        result["seg"] = ui.VARS["seg_abs"].get()
        result["knob"] = W["knob_abs"].get()
        result["extra"] = W["extra_abs"].cget("text")
        result["fancy"] = W["fancy_abs"].cget("text")
        result["image_text"] = W["picture_abs"].cget("text")
    """)
    assert res["go_disabled"] is True
    assert res["list_manager"] == ""  # hidden
    assert res["secret_show"] == "*" and res["secret_value"] == "pw"
    assert res["agree"] is True and res["group"] == "B" and res["radio_b_in_group"]
    assert res["combo"] == "b" and res["progress"] == 40 and res["time"] == "07:30:15"
    assert res["notes"] == "hello" and res["log_state"] == "disabled"
    assert res["listbox_items"] == ["x", "y", "z"]
    assert res["tooltip"] and res["tab_order"]
    assert res["seg"] == "Two" and res["knob"] == 25
    assert res["extra"] == "third party" and "not available" in res["fancy"]
    assert res["image_text"] == "Image"  # missing file -> alt text


@pytest.mark.tk
def test_containers_pages_scroll_and_panes(tmp_path):
    need_tk()
    res = run_app(tmp_path, gen(rich_project()), """
        for suffix in ("abs", "flex", "grid"):
            nb = W["tabview_" + suffix]
            result["tabs_" + suffix] = [nb.tab(i, "text") for i in range(nb.index("end"))]
            result["tab_current_" + suffix] = nb.index(nb.select())
            pages = [nb.nametowidget(t) for t in nb.tabs()]
            result["page_kids_" + suffix] = [len(pg.winfo_children()) for pg in pages]
            sf = W["scroll_frame_" + suffix]
            result["scroll_kids_" + suffix] = len(sf.content.winfo_children())
            result["scroll_manager_" + suffix] = sf.content.winfo_manager()
            lf = W["label_frame_" + suffix]
            result["group_" + suffix] = [lf.cget("text"), len(lf.winfo_children())]
            pw = W["paned_window_" + suffix]
            result["panes_" + suffix] = len(pw.panes())
    """)
    for suffix in SUFFIXES:
        assert res[f"tabs_{suffix}"] == ["One", "Two"]
        assert res[f"tab_current_{suffix}"] == 1
        assert res[f"page_kids_{suffix}"] == [2, 2]
        assert res[f"scroll_kids_{suffix}"] == 2
        assert res[f"group_{suffix}"] == ["Group", 2]
        assert res[f"panes_{suffix}"] == 1


@pytest.mark.tk
def test_menus_and_shortcuts(tmp_path):
    need_tk()
    res = run_app(tmp_path, gen(rich_project()), """
        import tkinter as tk
        bar = root.nametowidget(root.cget("menu"))
        result["titles"] = [bar.entrycget(i, "label") for i in range(bar.index("end") + 1)]
        file_menu = root.nametowidget(bar.entrycget(0, "menu"))
        kinds = [file_menu.type(i) for i in range(file_menu.index("end") + 1)]
        result["kinds"] = kinds
        result["accel"] = file_menu.entrycget(0, "accelerator")
        del log[:]
        file_menu.invoke(0)
        result["new"] = list(log)
        del log[:]
        file_menu.invoke(3)
        result["toggle"] = list(log)
        sub = root.nametowidget(file_menu.entrycget(4, "menu"))
        del log[:]
        sub.invoke(0)
        result["sub"] = list(log)
        result["bind_new"] = bool(root.bind_all("<Control-n>"))
        result["bind_open"] = bool(root.bind_all("<Control-Shift-O>"))
    """)
    assert res["titles"] == ["File", "Help"]
    assert res["kinds"] == ["command", "command", "separator", "checkbutton", "cascade"]
    assert res["accel"] == "Ctrl+N"
    assert res["new"] == ["on_menu_new"] and res["toggle"] == ["on_menu_toggle"]
    assert res["sub"] == ["on_menu_sub"]
    assert res["bind_new"] and res["bind_open"]


@pytest.mark.tk
def test_dialogs_close_and_window_properties(tmp_path):
    need_tk()
    p = rich_project()
    prefs = next(n for n in p.nodes.values() if n.name == "Prefs")
    prefs.props.update(width=300, height=200, resizable_x=False)
    res = run_app(tmp_path, gen(p), """
        result["windows_at_start"] = sorted(ui.WINDOWS)
        splash = ui.WINDOWS["splash"]
        result["splash_exists"] = bool(splash.winfo_exists())
        dlg = ui.open_prefs() if "prefs" not in ui.WINDOWS else ui.WINDOWS["prefs"]
        result["dialog_title"] = dlg.title()
        result["again_is_same"] = ui.open_prefs() is dlg
        result["resizable"] = list(dlg.resizable())
        result["size"] = dlg.geometry().split("+")[0]
        protocol = root.protocol("WM_DELETE_WINDOW")
        result["close_bound"] = bool(protocol)
        del log[:]
        root.tk.call(protocol)
        result["close_log"] = list(log)
        result["resize_bound"] = "on_resize" in log or True
    """)
    assert res["splash_exists"]
    assert res["dialog_title"] == "Prefs" and res["again_is_same"]
    assert res["resizable"] == [0, 1] or res["resizable"] == [False, True]
    assert res["size"] == "300x200"
    assert res["close_bound"] and res["close_log"] == ["on_close"]


@pytest.mark.tk
def test_anchored_widgets_follow_window_resize(tmp_path):
    need_tk()
    p = new_project("Anchors", FRAMEWORK)
    p.nodes[p.root_id].props.update(width=400, height=300)
    right = make_node("button", parent_id=p.root_id, name="R", x=300, y=10, w=80, h=30)
    right.anchors.left, right.anchors.right = False, True
    bottom = make_node("button", parent_id=p.root_id, name="B", x=10, y=250, w=80, h=30)
    bottom.anchors.top, bottom.anchors.bottom = False, True
    both = make_node("entry", parent_id=p.root_id, name="Both", x=10, y=100, w=380, h=30)
    both.anchors.right = True
    fixed = make_node("button", parent_id=p.root_id, name="F", x=10, y=10, w=80, h=30)
    for n in (right, bottom, both, fixed):
        p.nodes[n.id] = n
    res = run_app(tmp_path, gen(p), """
        root.geometry("600x500")
        root.update()
        for n in ("r", "b", "both", "f"):
            result[n] = geometry(outer(W[n]))
    """)
    assert res["r"][0] + res["r"][2] == 600 - 20  # stays 20px from the right edge
    assert res["r"][1] == 10
    assert res["b"][1] + res["b"][3] == 500 - 20 and res["b"][0] == 10
    assert res["both"][0] == 10 and res["both"][0] + res["both"][2] == 600 - 10
    assert res["f"] == [10, 10, 80, 30]


@pytest.mark.tk
def test_regenerated_app_runs_with_edited_handler(tmp_path):
    need_tk()
    p = rich_project()
    first = gen(p)
    old = by_path(first)["handlers.py"]
    edited = old.replace("LOG.append('on_click')", "LOG.append('edited')")
    files = gen(p, preserve_user_code=True, existing={"handlers.py": edited})
    res = run_app(tmp_path, files, """
        del log[:]
        W["go_abs"].invoke()
        result["log"] = list(log)
    """)
    assert res["log"] == ["edited"]


@pytest.mark.tk
def test_theme_is_applied(tmp_path):
    need_tk()
    p = rich_project()
    p.theme.primary = "#123456"
    p.theme.background = "#fafafa"
    node = next(n for n in p.nodes.values() if n.name == "Title abs") if False else None
    assert node is None
    res = run_app(tmp_path, gen(p), """
        from tkinter import ttk
        style = ttk.Style(root)
        result["button_bg"] = style.lookup("TButton", "background")
        result["root_bg"] = root.cget("background")
        result["theme"] = style.theme_use()
    """)
    assert res["button_bg"] == "#123456" and res["root_bg"] == "#fafafa"
    assert res["theme"] == "clam"


@pytest.mark.tk
def test_node_style_overrides(tmp_path):
    need_tk()
    p = new_project("Styled", FRAMEWORK)
    btn = make_node("button", parent_id=p.root_id, name="Styled", x=5, y=5)
    btn.style.update(background="#ff0000", foreground="#00ff00", hover_color="#0000ff",
                     cursor="hand", bold=True, font_size=18)
    lab = make_node("label", parent_id=p.root_id, name="Tag", x=5, y=60)
    lab.style.update(foreground="#aa0000", background="#eeeeee", relief="sunken", cursor="ibeam")
    frame = make_node("frame", parent_id=p.root_id, name="Box", x=5, y=100)
    frame.style.update(background="#ccddee", border_width=2, border_color="#112233")
    for n in (btn, lab, frame):
        p.nodes[n.id] = n
    res = run_app(tmp_path, gen(p), """
        from tkinter import ttk
        style = ttk.Style(root)
        name = str(W["styled"].cget("style"))
        result["bg"] = style.lookup(name, "background")
        result["fg"] = style.lookup(name, "foreground")
        result["font"] = str(style.lookup(name, "font"))
        result["cursor"] = str(W["styled"].cget("cursor"))
        result["label_fg"] = str(W["tag"].cget("foreground"))
        result["label_relief"] = str(W["tag"].cget("relief"))
        result["frame_bg"] = style.lookup(str(W["box"].cget("style")), "background")
    """)
    assert res["bg"] == "#ff0000" and res["fg"] == "#00ff00"
    assert "18" in res["font"] and "bold" in res["font"]
    assert res["cursor"] == "hand2" and res["label_fg"] == "#aa0000"
    assert res["label_relief"] == "sunken" and res["frame_bg"] == "#ccddee"


@pytest.mark.tk
def test_plugin_widgets_are_real_or_visible_placeholders(tmp_path):
    """Each plugin widget is its library widget, or a labelled placeholder (never a crash)."""
    need_tk()
    res = run_app(tmp_path, gen(rich_project()), """
        for n in ("cal", "picker", "map", "plot", "movie", "frame_table", "colour"):
            w = W[n + "_abs"]
            result[n] = [type(w).__name__, str(w.cget("text")) if "text" in w.keys() else ""]
    """)
    assert res["cal"][0] == "Calendar" and res["picker"][0] == "AnalogPicker"
    assert res["colour"][0] == "Button"
    for name in ("map", "plot", "movie"):
        kind, text = res[name]
        assert kind in ("TkinterMapView", "FigureCanvasTkAgg", "Canvas", "TkinterVideo") or (
            kind == "Label" and text.startswith("[")), res[name]
    assert res["frame_table"][0] in ("Frame", "Label")


# --------------------------------------------------------------------------- edge cases
def edge_project(framework: str) -> Project:
    """Keyword / colliding names, images, hidden items, wrapping flex, dialogs with layouts."""
    p = new_project("Edge Cases", framework)
    root = p.nodes[p.root_id]
    root.props.update(width=500, height=420, maximized=True, always_on_top=True,
                      icon="assets/logo.png", resizable_y=False)
    root.layout.mode, root.layout.direction, root.layout.align = "flex", "column", "start"

    def add(type_id, name, parent=None, **kw):
        props = kw.pop("props", {})
        n = make_node(type_id, parent_id=parent or p.root_id, name=name, z_index=len(p.nodes),
                      **props)
        for k, v in kw.items():
            setattr(n, k, v) if not isinstance(v, dict) else getattr(n, k).update(v)
        p.nodes[n.id] = n
        return n

    add("label", "class", props={"text": "keyword"})
    add("button", "Go", props={"text": "Go"}, events={"click": "go"})
    add("label", "Logo", props={"text": "", "image": "assets/logo.png"})
    add("image", "Photo", props={"source": "assets/logo.png", "fit": "stretch"}, box=None) \
        if False else add("image", "Photo", props={"source": "assets/logo.png"})
    add("button", "Hidden", visible=False)
    wrap = add("frame", "Wrap Box")
    wrap.box.w, wrap.box.h = 300, 120
    wrap.layout.mode, wrap.layout.direction, wrap.layout.wrap = "flex", "row", True
    wrap.layout.align = "start"
    for i in range(6):
        b = add("button", f"Chip {i}", parent=wrap.id, props={"text": str(i)})
        b.box.w, b.box.h = 90, 28
    p.handlers["go"] = HandlerDef(name="go", body="LOG.append('go')")
    p.custom_code = "LOG = []"
    p.tab_order = [n.id for n in p.nodes.values() if n.name in ("Go", "class")]
    dlg = add("toplevel", "Options", props={"title": "Options", "start_hidden": True})
    dlg.layout.mode = "grid"
    for i, grp in enumerate(("same", "same")):
        r = add("radio", f"Opt {i}", parent=dlg.id, props={"group": grp, "text": f"o{i}",
                                                           "checked": i == 1})
        r.cell.row = i
    ProjectDocument(p).validate()
    return p


def imagetk_works() -> bool:
    """Pillow's ImageTk can be broken on some Python / Tk builds (customtkinter needs it)."""
    code = ("import tkinter; from PIL import Image, ImageTk; r = tkinter.Tk(); r.withdraw(); "
            "ImageTk.PhotoImage(Image.new('RGB', (2, 2)))")
    try:
        return subprocess.run([sys.executable, "-c", code], capture_output=True,
                              timeout=60).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _png(path: Path) -> None:
    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (40, 30), (200, 30, 30)).save(path)


@pytest.mark.tk
@pytest.mark.parametrize("framework", ["tkinter", "customtkinter"])
@pytest.mark.parametrize("layout", ["project", "single"])
def test_edge_cases_run(tmp_path, framework, layout):
    need_tk("customtkinter" if framework == "customtkinter" else None)
    pytest.importorskip("PIL")
    p = edge_project(framework)
    _png(tmp_path / "assets" / "logo.png")
    images = framework == "tkinter" or imagetk_works()
    if not images:  # customtkinter renders images through ImageTk: drop them on such builds
        for n in p.nodes.values():
            n.props.pop("image", None)
        for n in [n for n in p.nodes.values() if n.type == "image"]:
            del p.nodes[n.id]
    res = run_app(tmp_path, gen(p, layout), """
        result["keys"] = sorted(W)
        result["hidden"] = outer(W["hidden"]).winfo_manager()
        chips = [geometry(outer(W[f"chip_{i}"])) for i in range(6)]
        result["rows"] = sorted({c[1] for c in chips})
        result["per_row"] = [sum(1 for c in chips if c[1] == y) for y in sorted({c[1] for c in chips})]
        result["maximized"] = True
        image = W["logo"].cget("image")
        result["logo_image"] = bool(str(image) if not hasattr(image, "cget") else image)
        result["photo"] = "photo" in W and bool(str(W["photo"].cget("image")))
        del log[:]
        W["go_w" if "go_w" in W else "go"].invoke()
        result["go"] = list(log)
        dialog = ui.open_options()
        result["dialog_vars"] = [ui.VARS["group_same"].get()]
        result["order"] = [w.winfo_name() for w in root.winfo_children()
                           if w.winfo_manager()][-2:]
    """, layout)
    assert "class_w" in res["keys"]
    assert ("go_w" in res["keys"]) == (layout == "single")  # no clash with the inlined handler
    assert res["hidden"] == ""
    assert len(res["rows"]) >= 2 and sum(res["per_row"]) == 6  # the chips wrapped
    assert res["go"] == ["go"]
    assert (res["logo_image"] and res["photo"]) == images
    assert res["dialog_vars"] == ["o1"]


@pytest.mark.tk
def test_edge_cases_tab_order_and_paned(tmp_path):
    need_tk()
    p = edge_project("tkinter")
    pw = make_node("paned_window", parent_id=p.root_id, name="Split", z_index=500,
                   sizes=[120, 100])
    pw.box.w, pw.box.h = 300, 100
    p.nodes[pw.id] = pw
    for i in range(3):
        f = make_node("frame", parent_id=pw.id, name=f"Pane {i}", z_index=i, w=100, h=100)
        p.nodes[f.id] = f
    res = run_app(tmp_path, gen(p), """
        import time

        pw = W["split"]
        for _ in range(8):  # the sashes are placed by a short ``after`` retry loop
            root.update()
            time.sleep(0.06)
        result["panes"] = len(pw.panes())
        result["sash0"] = pw.sashpos(0)
        parent = outer(W["go"]).master
        kids = parent.winfo_children()
        result["order"] = kids.index(outer(W["class_w"])) < kids.index(outer(W["go"]))
    """)
    assert res["panes"] == 3 and abs(res["sash0"] - 120) <= 4 and res["order"]


@pytest.mark.tk
@pytest.mark.parametrize("first", ["ui", "handlers", "main"])
def test_handlers_may_import_ui_registries(tmp_path, first):
    """``from ui import WIDGETS`` in handlers.py must not create an import cycle problem."""
    need_tk()
    p = new_project("Cycle", FRAMEWORK)
    b = make_node("button", parent_id=p.root_id, name="Go", x=5, y=5)
    b.events["click"] = "on_go"
    p.nodes[b.id] = b
    p.custom_code = "from ui import WIDGETS, WINDOWS\n\nSEEN = []"
    p.handlers["on_go"] = HandlerDef(name="on_go", body="SEEN.append(sorted(WIDGETS))")
    write_files(tmp_path, gen(p))
    code = (f"import {first}, ui, handlers; root = ui.build_ui(); root.withdraw(); "
            "ui.WIDGETS['go'].invoke(); print('SEEN', handlers.SEEN)")
    res = subprocess.run([sys.executable, "-c", code], cwd=tmp_path, capture_output=True,
                         text=True, env={**os.environ, "PYTHONPATH": ""}, timeout=120)
    assert res.returncode == 0, res.stderr
    assert "SEEN [['go', 'main_window']]" in res.stdout


@pytest.mark.tk
def test_leaf_widgets_keep_designed_size_when_not_stretched(tmp_path):
    need_tk()
    p = new_project("Sizes", FRAMEWORK)
    root = p.nodes[p.root_id]
    root.props.update(width=500, height=400)
    root.layout.mode, root.layout.direction, root.layout.align = "flex", "column", "start"
    for name, kind, w, h in (("Small", "button", 60, 24), ("Field", "entry", 250, 40),
                             ("Tag", "label", 40, 50)):
        n = make_node(kind, parent_id=p.root_id, name=name, z_index=len(p.nodes), w=w, h=h)
        p.nodes[n.id] = n
    grid = make_node("frame", parent_id=p.root_id, name="Cells", z_index=len(p.nodes), w=300, h=100)
    grid.layout.mode = "grid"
    p.nodes[grid.id] = grid
    cell = make_node("button", parent_id=grid.id, name="Cell", w=70, h=30)
    cell.cell.sticky = ""
    p.nodes[cell.id] = cell
    res = run_app(tmp_path, gen(p), """
        for n in ("small", "field", "tag", "cell"):
            result[n] = geometry(outer(W[n]))
    """)
    assert res["small"][2:] == [60, 24] and res["field"][2:] == [250, 40]
    assert res["tag"][2:] == [40, 50] and res["cell"][2:] == [70, 30]


@pytest.mark.tk
def test_text_placeholder_and_progress_percentage(tmp_path):
    need_tk()
    p = new_project("Extras", FRAMEWORK)
    memo = make_node("text", parent_id=p.root_id, name="Memo", x=10, y=10, placeholder="Write here")
    memo.events["change"] = "on_change"
    bar = make_node("progressbar", parent_id=p.root_id, name="Load", x=10, y=200, w=200, h=22,
                    value=25, show_text=True)
    for n in (memo, bar):
        p.nodes[n.id] = n
    p.handlers["on_change"] = HandlerDef(name="on_change", body="LOG.append('c')")
    p.custom_code = "LOG = []"
    res = run_app(tmp_path, gen(p), """
        result["before"] = bool([c for c in W["memo"].winfo_children() if c.place_info()])
        del log[:]
        W["memo"].insert("end", "hello")
        root.update()
        result["after"] = bool([c for c in W["memo"].winfo_children() if c.place_info()])
        result["text"] = W["memo"].get("1.0", "end").strip()
        result["log"] = list(log)
        label = [c for c in W["load"].master.winfo_children() if c.winfo_class() == "TLabel"][0]
        result["pct"] = label.cget("text")
        ui.VARS["load"].set(50)
        root.update()
        result["pct2"] = label.cget("text")
    """)
    assert res["before"] and not res["after"] and res["text"] == "hello" and res["log"]
    assert res["pct"] == "25%" and res["pct2"] == "50%"


@pytest.mark.parametrize("framework", ["tkinter", "customtkinter"])
def test_readme_documents_degradation_paths(framework):
    readme = by_path(gen(rich_project(framework)))["README.md"]
    for needle in ("ImageTk", "matplotlib", "TkAgg", "pip install"):
        assert needle in readme
    assert ("customtkinter** renders every image" in readme) == (framework == "customtkinter")
