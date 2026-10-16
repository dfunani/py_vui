"""PySide6 / PyQt6 adapter tests.

Generated apps are executed in a subprocess (offscreen Qt) because the two bindings must never
be loaded into the same process.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from py_vui.codegen import (
    GenOptions,
    check_syntax,
    generate,
    plugin_emitter,
    register_plugin_emitter,
)
from py_vui.codegen.base import HEADER, EmitResult
from py_vui.core import HandlerDef, ProjectDocument, make_node, new_project
from py_vui.core.document import slug
from py_vui.core.model import Anchors, GridCell, Padding
from py_vui.core.registry import all_specs
from py_vui.core.theme import theme_for_preset

BINDINGS = ["pyside6", "pyqt6"]
MODES = ["absolute", "flex", "grid"]
HAS_PYQT6 = importlib.util.find_spec("PyQt6") is not None
HAS_MPL = importlib.util.find_spec("matplotlib") is not None


def binding_param(name: str):
    marks = []
    if name == "pyqt6" and not HAS_PYQT6:
        marks.append(pytest.mark.skip(reason="PyQt6 is not installed"))
    return pytest.param(name, marks=marks, id=name)


ALL = [binding_param(b) for b in BINDINGS]

# ------------------------------------------------------------------------------ fixtures
RECORDER = '''\
CALLS = []


def _record(name, event):
    if event is None or isinstance(event, (str, int, float, bool)):
        arg = event
    elif isinstance(event, (list, tuple)):
        arg = list(event)
    else:
        arg = type(event).__name__
    CALLS.append((name, arg))
'''

#: widget type -> acceptable Qt class names (supported natively on both bindings)
EXPECTED_CLASS = {
    "label": {"QLabel"}, "image": {"_ImageLabel"}, "separator": {"QFrame"},
    "progressbar": {"QProgressBar"}, "canvas": {"_Canvas"}, "button": {"QPushButton"},
    "tool_button": {"QToolButton"}, "entry": {"QLineEdit"}, "text": {"QPlainTextEdit"},
    "checkbox": {"QCheckBox"}, "radio": {"QRadioButton"}, "switch": {"_Switch"},
    "slider": {"QSlider"}, "dial": {"QDial"}, "spinbox": {"QSpinBox", "QDoubleSpinBox"},
    "combobox": {"QComboBox"}, "listbox": {"QListWidget"}, "segmented_button": {"QWidget"},
    "date_entry": {"QDateEdit"}, "time_entry": {"QTimeEdit"}, "table": {"QTableWidget"},
    "tree_view": {"QTreeWidget"}, "calendar": {"QCalendarWidget"}, "frame": {"QFrame"},
    "label_frame": {"QGroupBox"}, "tabview": {"QTabWidget"}, "scroll_frame": {"QScrollArea"},
    "paned_window": {"QSplitter"}, "color_picker": {"_ColorButton"},
    "chart": {"QLabel", "FigureCanvasQTAgg"},
}


class Builder:
    def __init__(self, framework: str, mode: str = "absolute") -> None:
        self.p = new_project("Rich App", framework)
        self.mode = mode
        self.i = 0
        self.root = self.p.nodes[self.p.root_id]
        self.root.props["width"] = 1100
        self.root.props["height"] = 900
        self.p.custom_code = RECORDER
        self.counters: dict[str, int] = {}
        self._set_layout(self.root)
        self.cells: dict[str, int] = {}

    def _set_layout(self, node) -> None:
        if node.layout is None:
            return
        node.layout.mode = self.mode
        node.layout.direction = "column"
        node.layout.gap = 6
        node.layout.padding = Padding(top=10, right=10, bottom=10, left=10)
        node.layout.column_weights = [1, 1, 1, 1]
        node.layout.row_weights = [1] * 12

    def add(self, parent, type_, name, events=(), page=0, w=None, h=None, **props):
        pnode = self.p.nodes[parent]
        self.counters[parent] = k = self.counters.get(parent, 0)
        self.counters[parent] += 1
        n = make_node(
            type_, parent_id=parent, name=name, z_index=k, node_id=f"id_{slug(name)}",
            x=10 + (k % 4) * 240, y=10 + (k // 4) * 64, w=w, h=h, **props,
        )
        if pnode.layout is not None and pnode.layout.mode == "grid":
            n.cell = GridCell(row=k // 4, column=k % 4)
        n.page = page
        for ev in events:
            hname = f"h_{ev}_{slug(name)}"
            self.p.handlers[hname] = HandlerDef(name=hname, body=f'_record("{hname}", event)')
            n.events[ev] = hname
        self.p.nodes[n.id] = n
        if n.layout is not None:
            self._set_layout(n)
        return n

    def build(self):
        r = self.p.root_id
        add = self.add
        add(r, "label", "Title", ("click", "double_click"), text="Hello & more", w=200)
        add(r, "image", "Pic", alt_text="No image")
        add(r, "separator", "Sep", orientation="horizontal", w=200, h=4)
        add(r, "progressbar", "Prog", value=40, show_text=True)
        add(r, "canvas", "Board", ("paint", "mouse_press"), w=120, h=60)
        add(r, "button", "Go", ("click", "right_click", "mouse_enter"), text="Go & Stop")
        add(r, "tool_button", "Tool", ("click",), text="Tool", checkable=True)
        add(r, "entry", "Name Input", ("change", "submit", "key_press", "focus_in"),
            placeholder="your name", text="abc")
        add(r, "entry", "Password", show="*", max_length=8, justify="center")
        add(r, "text", "Notes", ("change",), text="line1\nline2", wrap="none")
        add(r, "checkbox", "Agree", ("toggle", "click"), text="I agree", checked=True)
        add(r, "radio", "Opt A", ("toggle",), text="A", group="g1", checked=True)
        add(r, "radio", "Opt B", ("toggle",), text="B", group="g1")
        add(r, "radio", "Opt C", text="C", group="g2", checked=True)
        add(r, "switch", "Dark Mode", ("toggle",), text="Dark", checked=True)
        add(r, "slider", "Level", ("change",), value=30, show_value=True)
        add(r, "dial", "Knob", ("change",), value=20)
        add(r, "spinbox", "Count", ("change",), value=5, maximum=10, decimals=0)
        add(r, "spinbox", "Price", ("change",), value=2.5, decimals=2, step=0.5)
        add(r, "combobox", "Choice", ("change",), items=["a", "b", "c"], current=1)
        add(r, "listbox", "Things", ("select",), items=["x", "y", "z"],
            selection_mode="multiple")
        add(r, "segmented_button", "Seg", ("change",), items=["One", "Two", "Three"], current=2)
        add(r, "date_entry", "Dob", ("change",), date="2024-02-29", pattern="dd/mm/yyyy")
        add(r, "time_entry", "At", ("change",), time="13:45:10")
        add(r, "table", "Data Table", ("select", "cell_change"), editable=True,
            columns=["A", "B"], rows=[["1", "2"], ["3", "4"], ["5", "6"]], h=140)
        add(r, "tree_view", "Tree", ("select",), h=120)
        add(r, "calendar", "Cal", ("change",), date="2025-03-15")
        add(r, "chart", "Chart", kind="bar")
        add(r, "color_picker", "Color", ("change",), color="#00ff00")
        for t in ("map_view", "time_picker", "video_player", "pandas_table"):
            add(r, t, f"Unsupported {t}", w=100, h=40)
        frame = add(r, "frame", "Panel", w=220, h=100)
        add(frame.id, "button", "Inner Btn", ("click",), text="Inner")
        add(frame.id, "label", "Inner Label", text="inside")
        grp = add(r, "label_frame", "Group", title="Group & co", w=220, h=100,
                  title_align="center")
        add(grp.id, "entry", "Group Entry", text="g")
        tabs = add(r, "tabview", "Tabs", ("tab_change",), tabs=["First", "Second"], w=240, h=140)
        add(tabs.id, "button", "Tab Btn", ("click",), page=0, text="in tab 1")
        add(tabs.id, "label", "Tab Label", page=1, text="in tab 2")
        add(tabs.id, "checkbox", "Tab Check", page=1, text="chk")
        sc = add(r, "scroll_frame", "Scroller", w=200, h=100, content_height=300)
        for i in range(4):
            add(sc.id, "label", f"Scroll Label {i}", text=f"row {i}")
        sp = add(r, "paned_window", "Split", w=240, h=100, orientation="horizontal",
                 sizes=[80, 160])
        for i in range(2):
            pane = add(sp.id, "frame", f"Pane {i}", w=100, h=80)
            add(pane.id, "label", f"Pane Label {i}", text=f"pane {i}")
        dlg = add(r, "toplevel", "Settings", ("close", "show"), title="Settings Dialog",
                  start_hidden=True, modal=True, width=300, height=200)
        add(dlg.id, "button", "Dlg Ok", ("click",), text="OK")
        self.root.props["menus"] = [
            {"title": "File", "items": [
                {"label": "Open", "handler": self._h("open"), "shortcut": "Ctrl+O"},
                {"label": "Wrap", "handler": self._h("wrap"), "checkable": True,
                 "checked": True},
                {"separator": True},
                {"label": "More", "items": [{"label": "Deep", "handler": self._h("deep")}]},
            ]},
            {"title": "Help", "items": [{"label": "About", "handler": self._h("about")}]},
        ]
        self.p.nodes[self.p.root_id].events.update({"close": self._h("close"),
                                                    "resize": self._h("resize")})
        self.p.tab_order = ["id_name_input", "id_password", "id_go"]
        ProjectDocument(self.p).validate()
        return self.p

    def _h(self, name):
        hname = f"m_{name}"
        self.p.handlers[hname] = HandlerDef(name=hname, body=f'_record("{hname}", event)')
        return hname


def rich(framework="pyside6", mode="absolute"):
    return Builder(framework, mode).build()


def write(files, out: Path) -> None:
    for f in files:
        path = out / f.path
        path.parent.mkdir(parents=True, exist_ok=True)
        if f.data is not None:
            path.write_bytes(f.data)
        else:
            path.write_text(f.content, encoding="utf-8")


DRIVER = r'''
import importlib, json, os, sys, traceback
os.environ["QT_QPA_PLATFORM"] = "offscreen"
binding, directory, mode, script = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
extra_path = sys.argv[5] if len(sys.argv) > 5 else ""
sys.path.insert(0, directory)
if extra_path:
    sys.path.insert(0, extra_path)
pkg = {"pyside6": "PySide6", "pyqt6": "PyQt6"}[binding]
QtCore = importlib.import_module(pkg + ".QtCore")
QtGui = importlib.import_module(pkg + ".QtGui")
QtWidgets = importlib.import_module(pkg + ".QtWidgets")
QtTest = importlib.import_module(pkg + ".QtTest")
Qt = QtCore.Qt
messages = []
def handler(kind, ctx, msg):
    messages.append(str(msg))
(QtCore.qInstallMessageHandler)(handler)
app = QtWidgets.QApplication([])
out = {"errors": []}
try:
    if mode == "single":
        mod = importlib.import_module("main")
        hmod = mod
    else:
        mod = importlib.import_module("ui")
        hmod = importlib.import_module("handlers")
    root = mod.build_ui()
    mod.start(root)
    app.processEvents()
    W = mod.WIDGETS
    facts = {}
    for name, w in W.items():
        text = None
        for attr in ("text", "toPlainText", "windowTitle"):
            fn = getattr(w, attr, None)
            if callable(fn):
                try:
                    text = fn()
                    break
                except Exception:
                    pass
        g = w.geometry()
        facts[name] = {
            "cls": type(w).__name__, "geom": [g.x(), g.y(), g.width(), g.height()],
            "text": text, "enabled": w.isEnabled(), "visible": w.isVisibleTo(root),
            "tip": w.toolTip(), "obj": w.objectName(),
        }
    out["facts"] = facts
    out["root"] = [k for k, v in W.items() if v is root][0]
    ns = dict(ui=mod, W=W, root=root, app=app, Qt=Qt, QtCore=QtCore, QtGui=QtGui,
              QtWidgets=QtWidgets, QTest=QtTest.QTest, OUT={}, handlers=hmod,
              process=app.processEvents, windows=mod.WINDOWS)
    exec(script, ns)
    app.processEvents()
    out["out"] = ns["OUT"]
    out["calls"] = [list(c) for c in getattr(hmod, "CALLS", [])]
except BaseException:
    out["errors"].append(traceback.format_exc())
out["messages"] = messages
print("REPORT:" + json.dumps(out, default=str))
sys.stdout.flush()
os._exit(0)
'''


def run_app(directory: Path, binding: str, mode: str = "project", script: str = "pass",
            extra_path: str = "") -> dict:
    driver = directory / "_driver.py"
    driver.write_text(DRIVER, encoding="utf-8")
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    env.pop("QT_API", None)
    proc = subprocess.run(
        [sys.executable, str(driver), binding, str(directory), mode, textwrap.dedent(script),
         extra_path],
        capture_output=True, text=True, timeout=120, env=env, cwd=str(directory),
    )
    lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("REPORT:")]
    assert lines, f"driver failed\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr[-3000:]}"
    rep = json.loads(lines[-1][len("REPORT:"):])
    assert not rep["errors"], "\n".join(rep["errors"])
    bad = [m for m in rep["messages"] if "stylesheet" in m.lower() or "parse" in m.lower()]
    assert not bad, bad
    return rep


def gen_and_write(project, tmp_path: Path, **opts) -> tuple[list, Path]:
    files = generate(project, GenOptions(**opts))
    assert check_syntax(files) == []
    write(files, tmp_path)
    return files, tmp_path


# ----------------------------------------------------------------------- generation (no Qt)
@pytest.mark.parametrize("layout", ["project", "single"])
@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("fw", BINDINGS)
def test_generates_valid_deterministic_code(fw, mode, layout):
    p = rich(fw, mode)
    files = generate(p, GenOptions(layout=layout))
    assert check_syntax(files) == []
    again = generate(p, GenOptions(layout=layout))
    assert [(f.path, f.content) for f in files] == [(f.path, f.content) for f in again]
    paths = {f.path for f in files}
    if layout == "project":
        assert {"main.py", "ui.py", "theme.py", "handlers.py", "custom.py", "requirements.txt",
                "README.md"} <= paths
        assert next(f for f in files if f.path == "custom.py").overwrite is False
    else:
        assert paths == {"main.py", "requirements.txt", "README.md"}
    for f in files:
        if f.path.endswith(".py"):
            assert f.content.startswith(HEADER)
    code = "\n".join(f.content for f in files if f.path.endswith(".py"))
    if fw == "pyside6":
        assert "PySide6" in code and "PyQt6" not in code
        assert "pyqtSignal" not in code
    else:
        assert "PyQt6" in code and "PySide6" not in code
        assert "pyqtSignal" in code  # color picker helper
    assert "app.exec()" in code
    # scoped enums only (valid on PyQt6)
    assert "Qt.AlignLeft" not in code and "Qt.Horizontal" not in code


def test_requirements_and_readme():
    for fw, pkg in (("pyside6", "PySide6"), ("pyqt6", "PyQt6")):
        files = {f.path: f for f in generate(rich(fw))}
        reqs = files["requirements.txt"].content
        assert pkg in reqs and "matplotlib" in reqs
        assert "py_vui" in files["README.md"].content or "py_vui" in HEADER


def test_names_follow_variable_names():
    p = rich("pyside6")
    doc = ProjectDocument(p)
    ui = next(f for f in generate(p) if f.path == "ui.py").content
    for var in doc.variable_names().values():
        assert f"WIDGETS['{var}']" in ui or f'WIDGETS["{var}"]' in ui


def test_keyword_names_are_safe():
    p = new_project("kw", "pyside6")
    for nm in ("class", "list", "for"):
        n = make_node("label", parent_id=p.root_id, name=nm)
        p.nodes[n.id] = n
    files = generate(p)
    assert check_syntax(files) == []


def test_every_registry_widget_is_covered():
    """Each registered widget type is either natively emitted, a plugin, or a placeholder."""
    p = new_project("cov", "pyside6")
    for i, spec in enumerate(all_specs()):
        if spec.type in ("window", "toplevel"):
            continue
        n = make_node(spec.type, parent_id=p.root_id, name=f"w{i}", z_index=i)
        p.nodes[n.id] = n
    files = generate(p)
    assert check_syntax(files) == []
    ui = next(f for f in files if f.path == "ui.py").content
    assert ui.count("WIDGETS[") >= len(p.nodes)


# -------------------------------------------------------------------------- runtime (Qt)
@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("fw", ALL)
def test_builds_every_widget(fw, mode, tmp_path):
    p = rich(fw, mode)
    _, out = gen_and_write(p, tmp_path)
    rep = run_app(out, fw)
    facts = rep["facts"]
    doc = ProjectDocument(p)
    names = doc.variable_names()
    assert set(facts) == set(names.values())
    for node in p.nodes.values():
        f = facts[names[node.id]]
        exp = EXPECTED_CLASS.get(node.type)
        if node.type in ("window", "toplevel"):
            assert f["cls"] in {"QWidget", "QMainWindow", "QDialog"}
        elif node.type in ("map_view", "time_picker", "video_player", "pandas_table"):
            assert f["cls"] == "QLabel" and "not available" in f["text"]
        else:
            assert f["cls"] in exp, (node.type, f["cls"])
        assert f["obj"] == names[node.id]
    root = facts[rep["root"]]
    assert root["cls"] == "QMainWindow"  # menus present
    assert root["text"] == "Rich App"
    assert facts["title"]["text"] == "Hello & more"
    assert facts["go"]["text"] == "Go && Stop" or facts["go"]["text"] == "Go & Stop"
    assert facts["name_input"]["text"] == "abc"
    assert facts["dob"]["cls"] == "QDateEdit"
    assert facts["price"]["cls"] == "QDoubleSpinBox" and facts["count"]["cls"] == "QSpinBox"
    assert facts["settings"]["cls"] == "QDialog"
    assert facts["settings"]["visible"] is False  # start_hidden
    assert facts["tab_label"]["visible"] is False  # second tab page is not current
    assert facts["tab_btn"]["visible"] is True
    if mode == "absolute":
        for node in p.nodes.values():
            if node.type in ("window", "toplevel", "tabview") or node.parent_id is None:
                continue
            parent = p.nodes[node.parent_id]
            if parent.type in ("paned_window", "scroll_frame") or node.type == "toplevel":
                continue
            if node.type == "slider" and node.props.get("show_value"):
                continue  # wrapped with its value label (own test)
            g = facts[names[node.id]]["geom"]
            assert g == [round(node.box.x), round(node.box.y), round(node.box.w),
                         round(node.box.h)], node.name
    assert rep["out"] == {}


@pytest.mark.parametrize("fw", ALL)
def test_props_applied(fw, tmp_path):
    p = rich(fw)
    _, out = gen_and_write(p, tmp_path)
    rep = run_app(out, fw, script='''
        OUT["pw_password_mode"] = (
            W["password"].echoMode() == type(W["password"]).EchoMode.Password)
        OUT["pw_max"] = W["password"].maxLength()
        OUT["ph"] = W["name_input"].placeholderText()
        OUT["agree"] = W["agree"].isChecked()
        OUT["sw"] = W["dark_mode"].isChecked()
        OUT["level"] = W["level"].value()
        OUT["knob"] = W["knob"].value()
        OUT["count"] = (W["count"].value(), W["count"].maximum())
        OUT["price"] = (W["price"].value(), W["price"].decimals(), W["price"].singleStep())
        OUT["choice"] = (W["choice"].currentText(), W["choice"].count())
        OUT["things"] = W["things"].count()
        OUT["seg"] = [b.text() for b in W["seg"].findChildren(QtWidgets.QPushButton)]
        OUT["seg_checked"] = [b.isChecked() for b in W["seg"].findChildren(QtWidgets.QPushButton)]
        OUT["dob"] = W["dob"].date().toString("yyyy-MM-dd")
        OUT["dob_fmt"] = W["dob"].displayFormat()
        OUT["at"] = W["at"].time().toString("HH:mm:ss")
        t = W["data_table"]
        OUT["table"] = (t.rowCount(), t.columnCount(), t.item(1, 1).text(),
                        t.horizontalHeaderItem(0).text())
        tr = W["tree"]
        OUT["tree"] = (tr.topLevelItemCount(), tr.topLevelItem(0).childCount())
        OUT["cal"] = W["cal"].selectedDate().toString("yyyy-MM-dd")
        OUT["tabs"] = (W["tabs"].count(), W["tabs"].tabText(0), W["tabs"].tabText(1))
        OUT["group_title"] = W["group"].title()
        OUT["radio"] = (W["opt_a"].isChecked(), W["opt_b"].isChecked(), W["opt_c"].isChecked())
        W["opt_b"].setChecked(True)
        OUT["radio_after"] = (W["opt_a"].isChecked(), W["opt_b"].isChecked(),
                              W["opt_c"].isChecked())
        OUT["prog"] = (W["prog"].value(), W["prog"].maximum())
        OUT["split"] = W["split"].count()
        OUT["scroll_widget"] = W["scroller"].widget().height()
        OUT["color"] = W["color"].color()
        OUT["title_tip"] = W["title"].toolTip()
    ''')
    o = rep["out"]
    assert o["pw_password_mode"] and o["pw_max"] == 8 and o["ph"] == "your name"
    assert o["agree"] and o["sw"]
    assert o["level"] == 30 and o["knob"] == 20
    assert o["count"] == [5, 10]
    assert o["price"] == [2.5, 2, 0.5]
    assert o["choice"] == ["b", 3] and o["things"] == 3
    assert o["seg"] == ["One", "Two", "Three"] and o["seg_checked"] == [False, False, True]
    assert o["dob"] == "2024-02-29" and o["dob_fmt"] == "dd/MM/yyyy"
    assert o["at"] == "13:45:10"
    assert o["table"] == [3, 2, "4", "A"]
    assert o["tree"] == [1, 2]
    assert o["cal"] == "2025-03-15"
    assert o["tabs"] == [2, "First", "Second"]
    assert o["group_title"] == "Group && co"
    assert o["radio"] == [True, False, True]
    assert o["radio_after"] == [False, True, True]  # g1 exclusive, g2 independent
    assert o["prog"] == [40, 100]
    assert o["split"] == 2
    assert o["scroll_widget"] == 300
    assert o["color"] == "#00ff00"


# --------------------------------------------------------------------------------- events
@pytest.mark.parametrize("fw", ALL)
def test_events_call_handlers(fw, tmp_path):
    p = rich(fw)
    _, out = gen_and_write(p, tmp_path)
    script = '''
        from_ = Qt.MouseButton
        QTest.mouseClick(W["go"], from_.LeftButton)
        QTest.mouseClick(W["go"], from_.RightButton)
        QTest.mouseClick(W["tool"], from_.LeftButton)
        W["name_input"].setText("zed")
        QTest.keyClick(W["name_input"], Qt.Key.Key_Return)
        QTest.keyClick(W["name_input"], Qt.Key.Key_A)
        app.sendEvent(W["name_input"], QtGui.QFocusEvent(QtCore.QEvent.Type.FocusIn))
        W["notes"].setPlainText("changed")
        W["agree"].click()
        W["opt_b"].setChecked(True)
        QTest.mouseClick(W["dark_mode"], from_.LeftButton)
        W["level"].setValue(77)
        W["knob"].setValue(33)
        W["count"].setValue(8)
        W["price"].setValue(1.5)
        W["choice"].setCurrentIndex(2)
        W["things"].item(0).setSelected(True)
        W["things"].item(2).setSelected(True)
        seg = W["seg"].findChildren(QtWidgets.QPushButton)
        QTest.mouseClick(seg[0], from_.LeftButton)
        W["dob"].setDate(QtCore.QDate(2020, 1, 2))
        W["at"].setTime(QtCore.QTime(1, 2, 3))
        t = W["data_table"]
        t.item(0, 0).setText("edited")
        t.selectRow(2)
        W["tree"].topLevelItem(0).setSelected(True)
        W["cal"].setSelectedDate(QtCore.QDate(2025, 4, 1))
        W["tabs"].setCurrentIndex(1)
        W["color"].setColor("#123456")
        W["board"].grab()
        QTest.mouseClick(W["board"], from_.LeftButton)
        QTest.mouseClick(W["title"], from_.LeftButton)
        QTest.mouseDClick(W["title"], from_.LeftButton)
        QTest.mouseClick(W["inner_btn"], from_.LeftButton)
        windows["settings"].show()
        windows["settings"].close()
        root.resize(900, 700)
        process()
        ui.ACTIONS["File/Open"].trigger()
        ui.ACTIONS["File/Wrap"].trigger()
        ui.ACTIONS["File/More/Deep"].trigger()
        ui.ACTIONS["Help/About"].trigger()
        OUT["wrap_checked"] = ui.ACTIONS["File/Wrap"].isChecked()
        OUT["open_shortcut"] = ui.ACTIONS["File/Open"].shortcut().toString()
        pt = QtCore.QPointF(2, 2)
        app.sendEvent(W["go"], QtGui.QEnterEvent(pt, pt, pt))
        W["dlg_ok"].click()
        root.close()
    '''
    rep = run_app(out, fw, script=script)
    calls = rep["calls"]
    names = [c[0] for c in calls]
    expected = {
        "h_click_go", "h_right_click_go", "h_click_tool", "h_change_name_input",
        "h_submit_name_input", "h_key_press_name_input", "h_focus_in_name_input",
        "h_change_notes", "h_toggle_agree", "h_click_agree", "h_toggle_opt_a", "h_toggle_opt_b",
        "h_toggle_dark_mode", "h_change_level", "h_change_knob", "h_change_count",
        "h_change_price", "h_change_choice", "h_select_things", "h_change_seg",
        "h_change_dob", "h_change_at", "h_cell_change_data_table", "h_select_data_table",
        "h_select_tree", "h_change_cal", "h_tab_change_tabs", "h_change_color",
        "h_paint_board", "h_mouse_press_board", "h_click_title", "h_double_click_title",
        "h_click_inner_btn", "h_show_settings", "h_close_settings", "m_resize", "m_close",
        "m_open", "m_wrap", "m_deep", "m_about", "h_mouse_enter_go", "h_click_dlg_ok",
    }
    missing = {n for n in expected if n not in names}
    assert not missing, f"handlers never called: {sorted(missing)}"
    by = {}
    for n, a in calls:
        by.setdefault(n, []).append(a)
    assert by["h_click_go"] == [None]
    assert by["h_change_level"][-1] == 77
    assert by["h_change_choice"][-1] == "c"
    assert by["h_change_name_input"][0] == "zed"
    assert by["h_submit_name_input"][0] == "zed"
    assert by["h_toggle_agree"][-1] is False
    assert by["h_select_things"][-1] == ["x", "z"]
    assert by["h_change_seg"][-1] == "One"
    assert by["h_change_dob"][-1] == "2020-01-02"
    assert by["h_change_at"][-1] == "01:02:03"
    assert by["h_cell_change_data_table"][0] == [0, 0]
    assert by["h_change_cal"][-1] == "2025-04-01"
    assert by["h_tab_change_tabs"][-1] == 1
    assert by["h_change_color"][-1] == "#123456"
    assert by["h_change_notes"][-1] == "changed"
    assert by["h_click_title"] and by["h_double_click_title"]
    assert by["h_key_press_name_input"][0] == "QKeyEvent"
    assert by["h_paint_board"][0] == "_PaintEvent"
    assert by["m_wrap"] == [False]  # checkable item reports its new state
    assert by["m_open"] == [None]
    assert rep["out"]["wrap_checked"] is False
    assert rep["out"]["open_shortcut"] in ("Ctrl+O", "Meta+O")


@pytest.mark.parametrize("fw", ALL)
def test_close_event_can_be_vetoed(fw, tmp_path):
    p = new_project("veto", fw)
    p.custom_code = RECORDER
    p.handlers["h_close"] = HandlerDef(name="h_close", body="event.ignore()\n_record('h_close', event)")
    p.nodes[p.root_id].events["close"] = "h_close"
    _, out = gen_and_write(p, tmp_path)
    rep = run_app(out, fw, script='''
        OUT["closed"] = root.close()
        OUT["visible"] = root.isVisible()
    ''')
    assert rep["out"] == {"closed": False, "visible": True}


@pytest.mark.parametrize("fw", ALL)
def test_paint_handler_draws(fw, tmp_path):
    p = new_project("paint", fw)
    p.custom_code = RECORDER
    p.handlers["on_paint"] = HandlerDef(
        name="on_paint",
        body="color = type(event.painter.pen().color())('#ff0000')\n"
             "event.painter.fillRect(event.rect, color)\n"
             "_record('on_paint', 'ok')",
    )
    n = make_node("canvas", parent_id=p.root_id, name="Pad", x=0, y=0, w=50, h=50)
    n.events["paint"] = "on_paint"
    p.nodes[n.id] = n
    _, out = gen_and_write(p, tmp_path)
    rep = run_app(out, fw, script='''
        img = W["pad"].grab().toImage()
        c = img.pixelColor(10, 10)
        OUT["rgb"] = [c.red(), c.green(), c.blue()]
    ''')
    assert rep["out"]["rgb"] == [255, 0, 0]
    assert ["on_paint", "ok"] in rep["calls"]


# ------------------------------------------------------------------------------ layouts
@pytest.mark.parametrize("fw", ALL)
def test_absolute_anchors_follow_resize(fw, tmp_path):
    p = new_project("anch", fw)
    p.nodes[p.root_id].props.update(width=400, height=300)
    right = make_node("button", parent_id=p.root_id, name="Right", x=300, y=10, w=80, h=30)
    right.anchors = Anchors(left=False, top=True, right=True, bottom=False)
    both = make_node("entry", parent_id=p.root_id, name="Both", x=10, y=50, w=200, h=30)
    both.anchors = Anchors(left=True, top=True, right=True, bottom=False)
    bottom = make_node("label", parent_id=p.root_id, name="Bottom", x=10, y=260, w=100, h=30)
    bottom.anchors = Anchors(left=True, top=False, right=False, bottom=True)
    plain = make_node("label", parent_id=p.root_id, name="Plain", x=5, y=5, w=40, h=20)
    for n in (right, both, bottom, plain):
        p.nodes[n.id] = n
    files, out = gen_and_write(p, tmp_path)
    ui = next(f for f in files if f.path == "ui.py").content
    assert "_Anchors" in ui
    assert ui.count(".add(") == 3  # the plain widget needs no anchor tracking
    rep = run_app(out, fw, script='''
        root.resize(600, 500)
        process()
        OUT["root"] = [W["main_window"].width(), W["main_window"].height()]
        for k in ("right", "both", "bottom", "plain"):
            g = W[k].geometry()
            OUT[k] = [g.x(), g.y(), g.width(), g.height()]
    ''')
    o = rep["out"]
    assert o["right"] == [500, 10, 80, 30]
    assert o["both"] == [10, 50, 400, 30]
    assert o["bottom"][1] == 260 + 200 and o["bottom"][0] == 10
    assert o["plain"] == [5, 5, 40, 20]


def _layout_project(fw, mode, **layout):
    p = new_project("lay", fw)
    root = p.nodes[p.root_id]
    root.props.update(width=500, height=400)
    root.layout.mode = mode
    for k, v in layout.items():
        setattr(root.layout, k, v)
    return p


def _geom_script(*names):
    return (
        f"for k in {names!r}:\n"
        "    g = W[k].geometry()\n"
        "    OUT[k] = [g.x(), g.y(), g.width(), g.height()]\n"
    )


@pytest.mark.parametrize("fw", ALL)
def test_flex_column_gap_padding_grow(fw, tmp_path):
    p = _layout_project(fw, "flex", direction="column", gap=10, align="stretch",
                        padding=Padding(top=20, right=15, bottom=20, left=30))
    a = make_node("button", parent_id=p.root_id, name="A", w=100, h=40, z_index=0)
    b = make_node("button", parent_id=p.root_id, name="B", w=100, h=40, z_index=1)
    b.flex.grow = 1
    c = make_node("button", parent_id=p.root_id, name="C", w=100, h=40, z_index=2)
    for n in (a, b, c):
        p.nodes[n.id] = n
    _, out = gen_and_write(p, tmp_path)
    o = run_app(out, fw, script=_geom_script("a", "b", "c"))["out"]
    assert o["a"] == [30, 20, 500 - 45, 40]  # stretch across the cross axis
    assert o["b"][1] == 70 and o["c"][1] + o["c"][3] == 400 - 20  # grow pushes C to the end
    assert o["b"][3] == 400 - 40 - 20 - 80


@pytest.mark.parametrize("fw", ALL)
def test_flex_row_justify_align_margin(fw, tmp_path):
    p = _layout_project(fw, "flex", direction="row", gap=0, align="center", justify="center",
                        padding=Padding())
    a = make_node("button", parent_id=p.root_id, name="A", w=100, h=40, z_index=0)
    b = make_node("button", parent_id=p.root_id, name="B", w=100, h=40, z_index=1)
    b.flex.align_self = "end"
    c = make_node("button", parent_id=p.root_id, name="C", w=100, h=40, z_index=2)
    c.flex.margin = Padding(top=5, bottom=5, left=10, right=10)
    for n in (a, b, c):
        p.nodes[n.id] = n
    _, out = gen_and_write(p, tmp_path)
    o = run_app(out, fw, script=_geom_script("a", "b", "c"))["out"]
    total = 100 + 100 + 120
    start = (500 - total) // 2
    assert abs(o["a"][0] - start) <= 1 and o["a"][1] == (400 - 40) // 2
    assert o["b"][1] == 400 - 40  # align_self end
    # margins: c is inside a wrapper widget offset by its margin
    assert o["c"][0] == 10 and o["c"][1] == 5


@pytest.mark.parametrize("fw", ALL)
def test_flex_space_between_and_wrap(fw, tmp_path):
    p = _layout_project(fw, "flex", direction="row", gap=0, align="start",
                        justify="space_between", padding=Padding())
    for i in range(3):
        n = make_node("button", parent_id=p.root_id, name=f"B{i}", w=100, h=30, z_index=i)
        p.nodes[n.id] = n
    _, out = gen_and_write(p, tmp_path / "sb")
    o = run_app(out, fw, script=_geom_script("b0", "b1", "b2"))["out"]
    assert o["b0"][0] == 0 and o["b2"][0] + o["b2"][2] == 500
    assert o["b1"][0] == 200

    q = _layout_project(fw, "flex", direction="row", gap=10, wrap=True, align="start",
                        padding=Padding())
    for i in range(6):
        n = make_node("button", parent_id=q.root_id, name=f"B{i}", w=150, h=30, z_index=i)
        q.nodes[n.id] = n
    files, out2 = gen_and_write(q, tmp_path / "wrap")
    assert "_FlowLayout" in next(f for f in files if f.path == "ui.py").content
    o = run_app(out2, fw, script=_geom_script(*[f"b{i}" for i in range(6)]))["out"]
    rows = {o[f"b{i}"][1] for i in range(6)}
    assert len(rows) == 2  # 3 per row inside 500px
    assert o["b3"][0] == 0 and o["b3"][1] > o["b0"][1]


@pytest.mark.parametrize("fw", ALL)
def test_grid_cells_spans_sticky_weights(fw, tmp_path):
    p = _layout_project(fw, "grid", column_gap=10, row_gap=20, padding=Padding(),
                        column_weights=[1, 3], row_weights=[0, 1])
    a = make_node("button", parent_id=p.root_id, name="A", w=60, h=30)
    a.cell = GridCell(row=0, column=0, sticky="nw")
    b = make_node("button", parent_id=p.root_id, name="B", w=60, h=30)
    b.cell = GridCell(row=1, column=1, sticky="nsew")
    c = make_node("button", parent_id=p.root_id, name="C", w=60, h=30)
    c.cell = GridCell(row=0, column=1, sticky="se")
    d = make_node("label", parent_id=p.root_id, name="D", w=60, h=20)
    d.cell = GridCell(row=1, column=0, column_span=1, sticky="")
    for n in (a, b, c, d):
        p.nodes[n.id] = n
    _, out = gen_and_write(p, tmp_path)
    o = run_app(out, fw, script=_geom_script("a", "b", "c", "d"))["out"]
    assert o["a"][:2] == [0, 0] and o["a"][2:] == [60, 30]
    assert o["b"][0] > o["a"][0] + 60 and o["b"][1] >= 30 and o["b"][0] + o["b"][2] == 500
    assert o["b"][3] > 100  # row weight 1 stretches
    assert o["c"][0] + o["c"][2] == 500  # sticky east
    assert o["c"][1] + o["c"][3] <= o["b"][1]
    assert o["d"][2] == 60


@pytest.mark.parametrize("fw", ALL)
def test_layouts_inside_tabs_scroll_and_groupbox(fw, tmp_path):
    p = new_project("nest", fw)
    p.nodes[p.root_id].props.update(width=500, height=400)
    tabs = make_node("tabview", parent_id=p.root_id, name="T", x=0, y=0, w=400, h=300)
    tabs.layout.mode = "flex"
    tabs.layout.padding = Padding(top=4, right=4, bottom=4, left=4)
    grp = make_node("label_frame", parent_id=p.root_id, name="G", x=0, y=310, w=200, h=80)
    grp.layout.mode = "grid"
    sc = make_node("scroll_frame", parent_id=p.root_id, name="S", x=210, y=310, w=200, h=80)
    sc.layout.mode = "flex"
    p.nodes.update({tabs.id: tabs, grp.id: grp, sc.id: sc})
    for i in range(2):
        n = make_node("button", parent_id=tabs.id, name=f"TB{i}", w=80, h=30, z_index=i, page=i)
        p.nodes[n.id] = n
    for i in range(2):
        n = make_node("button", parent_id=grp.id, name=f"GB{i}", w=60, h=20, z_index=i)
        n.cell = GridCell(row=0, column=i)
        p.nodes[n.id] = n
    for i in range(6):
        n = make_node("button", parent_id=sc.id, name=f"SB{i}", w=80, h=40, z_index=i)
        p.nodes[n.id] = n
    _, out = gen_and_write(p, tmp_path)
    o = run_app(out, fw, script=_geom_script("tb0", "tb1", "gb0", "gb1", "sb0", "sb5") + '''
OUT["scroll_h"] = W["s"].widget().height()
OUT["vbar"] = W["s"].verticalScrollBar().maximum() > 0
''')["out"]
    assert o["tb0"][0] == 4 and o["tb0"][1] == 4 and o["tb0"][2] > 80
    assert o["gb1"][0] > o["gb0"][0]
    assert o["sb5"][1] > o["sb0"][1]
    assert o["vbar"] is True


# ------------------------------------------------------------------- window properties
@pytest.mark.parametrize("fw", ALL)
def test_window_and_dialog_props(fw, tmp_path):
    p = new_project("Win", fw)
    root = p.nodes[p.root_id]
    root.props.update(title="T1", width=420, height=310, resizable_x=False, resizable_y=False,
                      always_on_top=True)
    root.tooltip = "tip"
    dlg = make_node("toplevel", parent_id=p.root_id, name="Dlg", title="D", width=250,
                    height=180, modal=True, start_hidden=False, min_width=100)
    p.nodes[dlg.id] = dlg
    b = make_node("button", parent_id=p.root_id, name="B", x=5, y=5)
    b.visible, b.enabled, b.tooltip = False, False, "hello"
    b.style = {"cursor": "hand"}
    p.nodes[b.id] = b
    _, out = gen_and_write(p, tmp_path)
    rep = run_app(out, fw, script='''
        OUT["fixed"] = [root.minimumWidth(), root.maximumWidth(), root.minimumHeight(),
                        root.maximumHeight()]
        OUT["top"] = bool(root.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
        d = windows["dlg"]
        OUT["dlg_visible"] = d.isVisible()
        OUT["dlg_modal"] = d.isModal()
        OUT["dlg_size"] = [d.width(), d.height()]
        OUT["root_cls"] = type(root).__name__
        OUT["cursor"] = W["b"].cursor().shape() == Qt.CursorShape.PointingHandCursor
        OUT["win_names"] = sorted(windows)
        d.setWindowTitle("x"); ui.open_dlg()
    ''')
    o = rep["out"]
    assert o["fixed"] == [420, 420, 310, 310]
    assert o["top"] is True and o["dlg_visible"] is True and o["dlg_modal"] is True
    assert o["dlg_size"] == [250, 180] and o["root_cls"] == "QWidget"
    assert o["cursor"] and o["win_names"] == ["dlg", "main_window"]
    f = rep["facts"]["b"]
    assert f["enabled"] is False and f["visible"] is False and f["tip"] == "hello"


@pytest.mark.parametrize("fw", ALL)
def test_menu_bar_and_maximized(fw, tmp_path):
    p = new_project("M", fw)
    root = p.nodes[p.root_id]
    root.props["maximized"] = True
    root.props["menus"] = [{"title": "File", "items": [{"label": "Quit"}]}]
    _, out = gen_and_write(p, tmp_path)
    rep = run_app(out, fw, script='''
        OUT["menus"] = [a.text() for a in root.menuBar().actions()]
        OUT["max"] = bool(root.windowState() & Qt.WindowState.WindowMaximized)
    ''')
    assert rep["out"]["menus"] == ["File"] and rep["out"]["max"] is True


@pytest.mark.parametrize("fw", ALL)
def test_tab_order(fw, tmp_path):
    p = rich(fw)
    files, out = gen_and_write(p, tmp_path)
    ui = next(f for f in files if f.path == "ui.py").content
    assert "QWidget.setTabOrder(name_input, password)" in ui
    assert "QWidget.setTabOrder(password, go)" in ui
    run_app(out, fw)


# --------------------------------------------------------------------------------- style
@pytest.mark.parametrize("preset", ["light", "dark", "midnight", "ocean"])
@pytest.mark.parametrize("fw", ALL)
def test_theme_presets_produce_valid_qss(fw, preset, tmp_path):
    p = rich(fw)
    p.theme = theme_for_preset(preset)
    files, out = gen_and_write(p, tmp_path)
    theme = next(f for f in files if f.path == "theme.py").content
    assert p.theme.background in theme and p.theme.primary in theme
    # Fusion + palette keep native checkbox/radio indicators (a QSS rule would flatten them)
    assert "Fusion" in theme and "QPalette.ColorRole.Highlight" in theme
    assert "QCheckBox" not in theme.split("def make_palette")[0]
    assert "QComboBox" in theme and "QScrollBar" in theme
    assert "QTabBar::tab" in theme and "QListWidget" in theme
    run_app(out, fw, script='''
        app.setStyle("Fusion")
        import theme
        theme.apply_theme(app)
        process()
        OUT["pal"] = root.palette().color(QtGui.QPalette.ColorRole.Window).name()
    ''')


@pytest.mark.parametrize("fw", ALL)
def test_node_style_applied(fw, tmp_path):
    p = new_project("Sty", fw)
    n = make_node("button", parent_id=p.root_id, name="Fancy", x=5, y=5)
    n.style = {"background": "#ff0000", "foreground": "#00ff00", "font_family": "Courier",
               "font_size": 20, "bold": True, "italic": True, "underline": True,
               "border_width": 3, "border_color": "#0000ff", "corner_radius": 12,
               "hover_color": "#111111", "relief": "raised"}
    lab = make_node("label", parent_id=p.root_id, name="Plain", x=5, y=60)
    lab.style = {"foreground": "#abcdef"}
    p.nodes.update({n.id: n, lab.id: lab})
    files, out = gen_and_write(p, tmp_path)
    ui = next(f for f in files if f.path == "ui.py").content
    for frag in ("#fancy {", "background-color: #ff0000", "color: #00ff00", 'font-family: "Courier"',
                 "font-size: 20px", "font-weight: bold", "font-style: italic",
                 "text-decoration: underline", "border-radius: 12px", "#fancy:hover",
                 "background-color: #111111", "outset", "#plain {"):
        assert frag in ui, frag
    rep = run_app(out, fw, script='''
        f = W["fancy"].font()
        OUT["font"] = [f.pixelSize(), f.bold(), f.italic(), f.underline()]
        OUT["fg"] = W["plain"].palette().color(QtGui.QPalette.ColorRole.WindowText).name()
        OUT["bg"] = root.grab().toImage().pixelColor(200, 200).name()
    ''')
    assert rep["out"]["font"][1:] == [True, True, True]
    assert rep["out"]["bg"] == "#f4f4f5"  # theme background of the window


# --------------------------------------------------------------------------- single file
@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("fw", ALL)
def test_single_file_runs(fw, mode, tmp_path):
    p = rich(fw, mode)
    files, out = gen_and_write(p, tmp_path, layout="single")
    assert {f.path for f in files} == {"main.py", "requirements.txt", "README.md"}
    main = (out / "main.py").read_text()
    assert "import handlers" not in main and "def h_click_go(event=None):" in main
    rep = run_app(out, fw, mode="single", script='''
        QTest.mouseClick(W["go"], Qt.MouseButton.LeftButton)
        W["level"].setValue(12)
    ''')
    assert ["h_click_go", None] in rep["calls"]
    assert ["h_change_level", 12] in rep["calls"]


@pytest.mark.parametrize("fw", ALL)
def test_main_module_entry_point(fw, tmp_path):
    p = new_project("Entry", fw)
    _, out = gen_and_write(p, tmp_path)
    pkg = {"pyside6": "PySide6", "pyqt6": "PyQt6"}[fw]
    main = (out / "main.py").read_text()
    assert f"from {pkg}.QtWidgets import QApplication" in main
    assert "app.exec()" in main and 'if __name__ == "__main__"' in main
    # run main.main() with exec patched so it returns immediately
    code = f"""
import os, sys
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, {str(out)!r})
import main, ui
from {pkg}.QtWidgets import QApplication
QApplication.exec = lambda *a, **k: 0
rc = main.main()
print("RC", rc, len(ui.WINDOWS))
"""
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                          timeout=120, cwd=str(out),
                          env=dict(os.environ, QT_QPA_PLATFORM="offscreen"))
    assert "RC 0 1" in proc.stdout, proc.stdout + proc.stderr[-2000:]


# --------------------------------------------------------------------- user code merging
@pytest.mark.parametrize("layout", ["project", "single"])
def test_preserve_user_code(layout):
    p = rich("pyside6")
    name = "main.py" if layout == "single" else "handlers.py"
    first = {f.path: f.content for f in generate(p, GenOptions(layout=layout))}
    edited = first[name].replace(
        '_record("h_click_go", event)\n',
        '_record("h_click_go", event)\n    print("MY CUSTOM CODE")\n', 1)
    assert edited != first[name]
    kept = {f.path: f.content for f in generate(
        p, GenOptions(layout=layout, preserve_user_code=True, existing={name: edited}))}
    assert "MY CUSTOM CODE" in kept[name]
    dropped = {f.path: f.content for f in generate(
        p, GenOptions(layout=layout, preserve_user_code=False, existing={name: edited}))}
    assert "MY CUSTOM CODE" not in dropped[name]
    assert check_syntax([f for f in generate(p, GenOptions(layout=layout))]) == []


def test_custom_py_is_not_overwritten_flag():
    files = {f.path: f for f in generate(rich("pyqt6"))}
    assert files["custom.py"].overwrite is False
    assert files["handlers.py"].overwrite is True


# --------------------------------------------------------------------------- plugins
def test_chart_and_color_picker_emitters_registered():
    for fw in BINDINGS:
        assert plugin_emitter("chart", fw) is not None
        assert plugin_emitter("color_picker", fw) is not None


@pytest.mark.parametrize("fw", ALL)
def test_chart_falls_back_without_matplotlib_and_uses_it_when_present(fw, tmp_path):
    p = new_project("Ch", fw)
    n = make_node("chart", parent_id=p.root_id, name="Plot", x=0, y=0, w=300, h=200,
                  kind="pie", title="T", x_label="x", y_label="y")
    p.nodes[n.id] = n
    files, out = gen_and_write(p, tmp_path)
    ui = next(f for f in files if f.path == "ui.py").content
    assert "backend_qtagg" in ui and "except ImportError" in ui
    # stubbed matplotlib => the canvas path runs
    stub = tmp_path / "stub" / "matplotlib"
    (stub / "backends").mkdir(parents=True)
    pkg = {"pyside6": "PySide6", "pyqt6": "PyQt6"}[fw]
    (stub / "__init__.py").write_text("")
    (stub / "figure.py").write_text(
        "class _Ax:\n    def __getattr__(self, n):\n        return lambda *a, **k: None\n"
        "class Figure:\n    def __init__(self, **k): pass\n"
        "    def add_subplot(self, *a): return _Ax()\n")
    (stub / "backends" / "__init__.py").write_text("")
    (stub / "backends" / "backend_qtagg.py").write_text(
        f"from {pkg}.QtWidgets import QWidget\n"
        "class FigureCanvasQTAgg(QWidget):\n    def __init__(self, fig): super().__init__()\n")
    rep = run_app(out, fw, extra_path=str(tmp_path / "stub"))
    assert rep["facts"]["plot"]["cls"] == "FigureCanvasQTAgg"
    rep = run_app(out, fw)  # real environment: matplotlib missing => label, present => canvas
    assert rep["facts"]["plot"]["cls"] in {"QLabel", "FigureCanvasQTAgg"}
    if not HAS_MPL:
        assert rep["facts"]["plot"]["cls"] == "QLabel"


@pytest.mark.parametrize("fw", ALL)
def test_third_party_plugin_emitter(fw, tmp_path):
    from py_vui.core.registry import PropSpec, WidgetSpec, register, unregister

    register(WidgetSpec(
        type="x_gauge", label="Gauge", category="Plugins", plugin=True,
        frameworks=frozenset({"pyside6", "pyqt6"}),
        props=(PropSpec("value", "int", 3),), events=("click", "change"),
    ), replace=True)

    def emit(ctx):
        pkg = "PySide6" if ctx.framework == "pyside6" else "PyQt6"
        return EmitResult(
            imports=[f"from {pkg}.QtWidgets import QDial"],
            lines=[f"{ctx.var} = QDial({ctx.parent})",
                   f"{ctx.var}.setValue({ctx.node.props['value']})"],
        )

    for f in BINDINGS:
        register_plugin_emitter("x_gauge", f, emit)
    try:
        p = new_project("Pl", fw)
        p.custom_code = RECORDER
        p.handlers["h"] = HandlerDef(name="h", body='_record("h", event)')
        n = make_node("x_gauge", parent_id=p.root_id, name="Gauge1", x=0, y=0, w=80, h=80)
        n.events["change"] = "h"
        p.nodes[n.id] = n
        _, out = gen_and_write(p, tmp_path)
        rep = run_app(out, fw, script='W["gauge1"].setValue(9)')
        assert rep["facts"]["gauge1"]["cls"] == "QDial"
        assert rep["facts"]["gauge1"]["geom"] == [0, 0, 80, 80]
        assert ["h", None] in rep["calls"]
    finally:
        from py_vui.codegen import base

        base._PLUGIN_EMITTERS.pop(("x_gauge", "pyside6"), None)
        base._PLUGIN_EMITTERS.pop(("x_gauge", "pyqt6"), None)
        unregister("x_gauge")


@pytest.mark.parametrize("fw", ALL)
def test_unsupported_widget_placeholder_and_disabled_widgets(fw, tmp_path):
    p = new_project("Un", fw)
    n = make_node("map_view", parent_id=p.root_id, name="Mapper", x=3, y=4, w=222, h=111)
    p.nodes[n.id] = n
    _, out = gen_and_write(p, tmp_path)
    rep = run_app(out, fw)
    f = rep["facts"]["mapper"]
    assert f["cls"] == "QLabel" and f["geom"] == [3, 4, 222, 111]
    assert "Map Viewer" in f["text"]


def test_generic_event_helper_only_when_used():
    p = new_project("noev", "pyside6")
    ui = next(f for f in generate(p) if f.path == "ui.py").content
    assert "_Events" not in ui and "_FlowLayout" not in ui and "_Anchors" not in ui
    p2 = new_project("ev", "pyside6")
    p2.handlers["h"] = HandlerDef(name="h", body="pass")
    n = make_node("label", parent_id=p2.root_id, name="L")
    n.events["mouse_move"] = "h"
    p2.nodes[n.id] = n
    ui2 = next(f for f in generate(p2) if f.path == "ui.py").content
    assert "class _Events" in ui2 and "_Events(l, {'mouse_move'" in ui2


@pytest.mark.parametrize("fw", ALL)
def test_all_generic_events_fire(fw, tmp_path):
    p = new_project("gen", fw)
    p.custom_code = RECORDER
    lab = make_node("label", parent_id=p.root_id, name="Lab", x=0, y=0, w=100, h=100)
    evs = ("double_click", "right_click", "middle_click", "mouse_press", "mouse_release",
           "mouse_move", "mouse_enter", "mouse_leave", "mouse_wheel", "key_press",
           "key_release", "focus_in", "focus_out", "resize", "click")
    for ev in evs:
        hn = f"h_{ev}"
        p.handlers[hn] = HandlerDef(name=hn, body=f'_record("{hn}", event)')
        lab.events[ev] = hn
    p.nodes[lab.id] = lab
    _, out = gen_and_write(p, tmp_path)
    rep = run_app(out, fw, script='''
        import gc
        gc.collect()  # event filters must stay alive without python references
        w = W["lab"]
        L, R, M = Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton, Qt.MouseButton.MiddleButton
        QTest.mouseClick(w, L)
        QTest.mouseDClick(w, L)
        QTest.mouseClick(w, R)
        QTest.mouseClick(w, M)
        QTest.mouseMove(w, QtCore.QPoint(20, 20))
        QTest.keyClick(w, Qt.Key.Key_A)
        app.sendEvent(w, QtGui.QFocusEvent(QtCore.QEvent.Type.FocusIn))
        app.sendEvent(w, QtGui.QFocusEvent(QtCore.QEvent.Type.FocusOut))
        app.sendEvent(w, QtGui.QEnterEvent(QtCore.QPointF(2, 2), QtCore.QPointF(2, 2), QtCore.QPointF(2, 2)))
        app.sendEvent(w, QtCore.QEvent(QtCore.QEvent.Type.Leave))
        pt = QtCore.QPointF(5, 5)
        wheel = QtGui.QWheelEvent(pt, pt, QtCore.QPoint(0, 0), QtCore.QPoint(0, 120),
                                  Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                                  Qt.ScrollPhase.NoScrollPhase, False)
        app.sendEvent(w, wheel)
        w.resize(50, 50)
        process()
    ''')
    got = {c[0] for c in rep["calls"]}
    assert got >= {f"h_{e}" for e in evs}, {f"h_{e}" for e in evs} - got


@pytest.mark.parametrize("fw", ALL)
def test_single_letter_names_do_not_clash_with_generated_lambdas(fw, tmp_path):
    p = new_project("sh", fw)
    p.custom_code = RECORDER
    for nm in ("v", "i", "b"):
        n = make_node("entry" if nm == "v" else "listbox", parent_id=p.root_id, name=nm, x=0,
                      y=0)
        p.handlers[f"h_{nm}"] = HandlerDef(name=f"h_{nm}", body=f'_record("h_{nm}", event)')
        n.events["change" if nm == "v" else "select"] = f"h_{nm}"
        p.nodes[n.id] = n
    _, out = gen_and_write(p, tmp_path)
    rep = run_app(out, fw, script='''
        W["v"].setText("q")
        W["i"].item(0).setSelected(True)
    ''')
    assert ["h_v", "q"] in rep["calls"] and ["h_i", ["Item 1"]] in rep["calls"]


def _png(path: Path) -> None:
    import struct
    import zlib

    def chunk(kind: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(kind + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)

    raw = b"".join(b"\x00" + b"\xff\x00\x00\xff" * 8 for _ in range(4))
    data = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 8, 4, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


@pytest.mark.parametrize("fw", ALL)
def test_images_icons_and_assets_resolve_relative_to_script(fw, tmp_path):
    p = new_project("img", fw)
    p.nodes[p.root_id].props["icon"] = "assets/logo.png"
    p.assets = ["assets/logo.png"]
    for i, fit in enumerate(("contain", "stretch", "none")):
        n = make_node("image", parent_id=p.root_id, name=f"Img {fit}", x=10, y=10 + i * 70,
                      w=64, h=64, source="logo.png", fit=fit)
        p.nodes[n.id] = n
    b = make_node("button", parent_id=p.root_id, name="Ib", x=200, y=10, image="assets/logo.png",
                  compound="right")
    lab = make_node("label", parent_id=p.root_id, name="Il", x=200, y=60, image="/some/abs/logo.png")
    p.nodes.update({b.id: b, lab.id: lab})
    files, out = gen_and_write(p, tmp_path)
    _png(out / "assets" / "logo.png")
    ui = next(f for f in files if f.path == "ui.py").content
    assert "_asset('assets/logo.png')" in ui
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    rep = run_app(out, fw, script='''
        import os
        os.chdir(ELSEWHERE)
        OUT["contain"] = W["img_contain"].pixmap().isNull()
        OUT["stretch"] = W["img_stretch"].hasScaledContents()
        OUT["none"] = W["img_none"].pixmap().size().width()
        OUT["icon"] = W["ib"].icon().isNull()
        OUT["wicon"] = root.windowIcon().isNull()
        OUT["rtl"] = W["ib"].layoutDirection() == Qt.LayoutDirection.RightToLeft
    '''.replace("ELSEWHERE", repr(str(elsewhere))))
    o = rep["out"]
    assert o["contain"] is False and o["stretch"] is True and o["none"] == 8
    assert o["icon"] is False and o["wicon"] is False and o["rtl"] is True


@pytest.mark.parametrize("layout", ["project", "single"])
@pytest.mark.parametrize("fw", ALL)
def test_generated_app_runs_as_a_script(fw, layout, tmp_path):
    """`python main.py` starts, shows the window and exits cleanly (quit via a timer)."""
    p = rich(fw)
    files, out = gen_and_write(p, tmp_path, layout=layout)
    pkg = {"pyside6": "PySide6", "pyqt6": "PyQt6"}[fw]
    quit_code = f"from {pkg}.QtCore import QTimer\nQTimer.singleShot(300, app.quit)\n"
    if layout == "project":
        (out / "custom.py").write_text(
            "def setup(app, root):\n    " + quit_code.replace("\n", "\n    ") + "\n")
    else:
        main = (out / "main.py").read_text()
        main = main.replace("    start(root)\n", "    start(root)\n    " + quit_code.replace(
            "\n", "\n    ").rstrip() + "\n")
        (out / "main.py").write_text(main)
    proc = subprocess.run([sys.executable, "main.py"], capture_output=True, text=True,
                          timeout=120, cwd=str(out),
                          env=dict(os.environ, QT_QPA_PLATFORM="offscreen"))
    assert proc.returncode == 0, proc.stderr[-3000:]
    assert "Traceback" not in proc.stderr


@pytest.mark.parametrize("fw", ALL)
def test_invalid_qss_would_be_detected_by_the_harness(fw, tmp_path):
    """Guard for the guard: the driver really reports stylesheet parse warnings."""
    p = new_project("q", fw)
    _, out = gen_and_write(p, tmp_path)
    with pytest.raises(AssertionError):
        run_app(out, fw, script="root.setStyleSheet('QWidget { color: ; ;; background: }}} ')")


# ------------------------------------------------------------------------------ gap fixes
@pytest.mark.parametrize("compound", ["top", "bottom"])
@pytest.mark.parametrize("fw", ALL)
def test_button_compound_top_bottom(fw, compound, tmp_path):
    p = new_project("cmp", fw)
    p.assets = ["assets/logo.png"]
    b = make_node("button", parent_id=p.root_id, name="B", x=10, y=10, w=120, h=90,
                  text="Hi", image="assets/logo.png", compound=compound)
    p.nodes[b.id] = b
    t = make_node("tool_button", parent_id=p.root_id, name="T", x=200, y=10, text="T",
                  image="assets/logo.png", compound=compound)
    p.nodes[t.id] = t
    files, out = gen_and_write(p, tmp_path)
    _png(out / "assets" / "logo.png")
    rep = run_app(out, fw, script='''
        img = W["b"].grab().toImage()
        rows = [y for y in range(img.height()) for x in range(img.width())
                if img.pixelColor(x, y).red() > 200 and img.pixelColor(x, y).green() < 60
                and img.pixelColor(x, y).blue() < 60]
        OUT["icon_y"] = sum(rows) / len(rows) if rows else -1
        OUT["h"] = img.height()
        OUT["text"] = W["b"].text()
        OUT["tool_style"] = W["t"].toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonTextUnderIcon
        W["b"].click()
    ''')
    o = rep["out"]
    assert rep["facts"]["b"]["cls"] == "_StackedButton" and o["text"] == "Hi"
    assert o["icon_y"] > 0
    assert (o["icon_y"] < o["h"] / 2) == (compound == "top")
    assert o["tool_style"]


@pytest.mark.parametrize("fw", ALL)
def test_scrollable_canvas(fw, tmp_path):
    p = new_project("sc", fw)
    c = make_node("canvas", parent_id=p.root_id, name="Pad", x=20, y=30, w=120, h=80,
                  scrollable=True)
    p.nodes[c.id] = c
    _, out = gen_and_write(p, tmp_path)
    rep = run_app(out, fw, script='''
        pad = W["pad"]
        scroll = pad.parentWidget().parentWidget()
        OUT["cls"] = type(scroll).__name__
        g = scroll.geometry()
        OUT["geom"] = [g.x(), g.y(), g.width(), g.height()]
        OUT["bar_before"] = scroll.verticalScrollBar().maximum()
        pad.resize(120, 400)
        process()
        OUT["bar_after"] = scroll.verticalScrollBar().maximum()
    ''')
    o = rep["out"]
    assert o["cls"] == "QScrollArea" and o["geom"] == [20, 30, 120, 80]
    assert o["bar_before"] == 0 and o["bar_after"] > 0


@pytest.mark.parametrize("fw", ALL)
def test_flex_column_wrap(fw, tmp_path):
    p = _layout_project(fw, "flex", direction="column", gap=10, wrap=True, align="start",
                        padding=Padding())
    p.nodes[p.root_id].props["height"] = 140
    for i in range(6):
        n = make_node("button", parent_id=p.root_id, name=f"B{i}", w=100, h=30, z_index=i)
        p.nodes[n.id] = n
    files, out = gen_and_write(p, tmp_path)
    assert "vertical" in next(f for f in files if f.path == "ui.py").content
    o = run_app(out, fw, script=_geom_script(*[f"b{i}" for i in range(6)]))["out"]
    assert [o[f"b{i}"][:2] for i in range(3)] == [[0, 0], [0, 40], [0, 80]]
    assert o["b3"][:2] == [110, 0] and o["b5"][:2] == [110, 80]


@pytest.mark.parametrize("fw", ALL)
def test_slider_value_label(fw, tmp_path):
    p = new_project("sv", fw)
    s = make_node("slider", parent_id=p.root_id, name="S", x=10, y=10, w=240, h=30,
                  value=30, show_value=True)
    p.nodes[s.id] = s
    _, out = gen_and_write(p, tmp_path)
    rep = run_app(out, fw, script='''
        sl = W["s"]
        box = sl.parentWidget()
        label = [c for c in box.findChildren(QtWidgets.QLabel)][0]
        OUT["before"] = label.text()
        sl.setValue(64)
        OUT["after"] = label.text()
        g = box.geometry()
        OUT["box"] = [g.x(), g.y(), g.width(), g.height()]
        OUT["label_right"] = label.geometry().x() > sl.geometry().x()
        OUT["cls"] = type(sl).__name__
    ''')
    o = rep["out"]
    assert o["before"] == "30" and o["after"] == "64" and o["cls"] == "QSlider"
    assert o["box"] == [10, 10, 240, 30] and o["label_right"]


@pytest.mark.parametrize("fw", ALL)
def test_calendar_nav_arrows_follow_theme(fw, tmp_path):
    p = new_project("cal", fw)
    p.theme = theme_for_preset("dark")
    c = make_node("calendar", parent_id=p.root_id, name="C", x=0, y=0, w=300, h=240)
    p.nodes[c.id] = c
    _, out = gen_and_write(p, tmp_path)
    rep = run_app(out, fw, script='''
        prev = W["c"].findChild(QtWidgets.QToolButton, "qt_calendar_prevmonth")
        nxt = W["c"].findChild(QtWidgets.QToolButton, "qt_calendar_nextmonth")
        OUT["text"] = [prev.text(), nxt.text()]
        OUT["icons"] = [prev.icon().isNull(), nxt.icon().isNull()]
        OUT["color"] = prev.palette().color(QtGui.QPalette.ColorRole.ButtonText).name()
    ''')
    o = rep["out"]
    assert o["text"] == ["\u2039", "\u203a"] and o["icons"] == [True, True]
    assert o["color"] == p.theme.text


@pytest.mark.parametrize("fw", ALL)
def test_anchors_inside_tab_pages_account_for_tab_bar(fw, tmp_path):
    p = new_project("tabs", fw)
    p.nodes[p.root_id].props.update(width=500, height=400)
    t = make_node("tabview", parent_id=p.root_id, name="T", x=0, y=0, w=400, h=300)
    p.nodes[t.id] = t
    b = make_node("button", parent_id=t.id, name="Br", x=300, y=200, w=60, h=30)
    b.anchors = Anchors(left=False, top=False, right=True, bottom=True)
    p.nodes[b.id] = b
    _, out = gen_and_write(p, tmp_path)
    rep = run_app(out, fw, script='''
        g = W["br"].geometry()
        OUT["initial"] = [g.x(), g.y()]
        W["t"].resize(500, 400)
        process()
        g = W["br"].geometry()
        OUT["resized"] = [g.x(), g.y()]
    ''')
    o = rep["out"]
    # pane borders are 1px each: the design size is only off by those, never by the tab bar
    assert abs(o["initial"][0] - 300) <= 2 and abs(o["initial"][1] - 200) <= 2
    assert abs(o["resized"][0] - 400) <= 2 and abs(o["resized"][1] - 300) <= 2


@pytest.mark.parametrize("fw", ALL)
def test_handlers_module_imports_qt_by_default(fw, tmp_path):
    p = new_project("hq", fw)
    p.handlers["h"] = HandlerDef(name="h", body="return Qt.AlignmentFlag.AlignCenter")
    pkg = {"pyside6": "PySide6", "pyqt6": "PyQt6"}[fw]
    for layout in ("project", "single"):
        files = {f.path: f.content for f in generate(p, GenOptions(layout=layout))}
        src = files["handlers.py" if layout == "project" else "main.py"]
        assert f"from {pkg}.QtCore import Qt" in src
        assert f"# from {pkg}.QtWidgets import QFileDialog, QMessageBox" in src
        assert f"from {pkg}.QtCore import Qt" in src[src.index("# py_vui: begin module"):]
    _, out = gen_and_write(p, tmp_path)
    rep = run_app(out, fw, script='OUT["v"] = handlers.h() == Qt.AlignmentFlag.AlignCenter')
    assert rep["out"]["v"] is True
    # an explicit import in the user's module code is respected (no duplicate)
    p.custom_code = f"from {pkg}.QtCore import Qt as _Q\n"
    again = {f.path: f.content for f in generate(p)}["handlers.py"]
    assert again.count(f"from {pkg}.QtCore import") == 1


@pytest.mark.skipif(not os.environ.get("PY_VUI_MPL_PYTHON"),
                    reason="set PY_VUI_MPL_PYTHON to a python with PySide6/PyQt6 + matplotlib")
@pytest.mark.parametrize("fw", ALL)
def test_real_matplotlib_chart(fw, tmp_path):
    p = new_project("ch", fw)
    for i, kind in enumerate(("line", "bar", "scatter", "pie", "hist")):
        n = make_node("chart", parent_id=p.root_id, name=f"C{i}", x=0, y=i * 10, w=200, h=150,
                      kind=kind)
        p.nodes[n.id] = n
    _, out = gen_and_write(p, tmp_path)
    saved = sys.executable
    try:
        sys.executable = os.environ["PY_VUI_MPL_PYTHON"]
        rep = run_app(out, fw)
    finally:
        sys.executable = saved
    assert {rep["facts"][f"c{i}"]["cls"] for i in range(5)} == {"FigureCanvasQTAgg"}
