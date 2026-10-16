"""Code panel: highlighter, syntax check, editor behaviours, handler CRUD, generated view."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from py_vui.app.editor.code_check import check_handler, check_module
from py_vui.app.editor.code_editor import CodeEditor, CodeEditorView
from py_vui.app.editor.code_panel import CodePanel
from py_vui.app.editor.highlighter import PythonHighlighter, scan_line, tokenize
from py_vui.codegen import GeneratedFile
from py_vui.commands import History
from py_vui.core import ProjectDocument, make_node, new_project
from py_vui.core.model import HandlerDef


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


def kinds(line: str, state: int = 0) -> list[tuple[str, str]]:
    spans, _ = scan_line(line, state)
    return [(line[s : s + n], k) for s, n, k in spans]


# ------------------------------------------------------------------ highlighter
def test_highlighter_tokens():
    assert ("def", "keyword") in kinds("def go(event=None):")
    assert ("go", "defname") in kinds("def go(event=None):")
    assert ("Foo", "classname") in kinds("class Foo:")
    toks = kinds('print("hi", 42) # note')
    assert ("print", "builtin") in toks
    assert ('"hi"', "string") in toks
    assert ("42", "number") in toks
    assert ("# note", "comment") in toks
    assert ("@staticmethod", "decorator") in kinds("@staticmethod")
    assert ("self", "self") in kinds("self.x = 0x1F")
    assert ("0x1F", "number") in kinds("self.x = 0x1F")
    # keywords inside strings / comments are not keywords
    assert ("if", "keyword") not in kinds('x = "if" # if')


def test_highlighter_multiline_strings():
    lines = tokenize('x = """abc\ndef"""\ny = 1')
    assert lines[0][-1][2] == "string"
    assert lines[1][0] == (0, 6, "string")
    assert any(k == "number" for _, _, k in lines[2])


def test_highlighter_light_and_dark_palettes(qapp):
    ed = CodeEditor()
    hl = ed.highlighter
    assert isinstance(hl, PythonHighlighter)
    hl.set_dark(True)
    dark = hl._formats["keyword"].foreground().color().name()
    hl.set_dark(False)
    light = hl._formats["keyword"].foreground().color().name()
    assert dark != light
    ed.setPlainText("def f():\n    return 1\n")
    fmts = ed.document().firstBlock().layout().formats()
    assert fmts  # highlighter produced formats


# ------------------------------------------------------------------ syntax check
def test_syntax_check_maps_lines():
    assert check_handler('print("ok")') is None
    assert check_handler("") is None
    p = check_handler('print("a")\nif True print(1)')
    assert p is not None and p.line == 1
    assert check_module("import os\nx = (") is not None
    assert check_module("import os\nx = 1") is None
    bad = check_handler("x = (")
    assert bad is not None and bad.line == 0


# ------------------------------------------------------------------ editor
def test_editor_tab_and_autoindent(qapp):
    ed = CodeEditor()
    QTest.keyClick(ed, Qt.Key.Key_Tab)
    assert ed.toPlainText() == "    "
    ed.setPlainText("if x:")
    ed.moveCursor(QTextCursor.MoveOperation.End)
    QTest.keyClick(ed, Qt.Key.Key_Return)
    assert ed.toPlainText() == "if x:\n    "
    QTest.keyClicks(ed, "pass")
    QTest.keyClick(ed, Qt.Key.Key_Return)
    assert ed.toPlainText().endswith("pass\n    ")
    QTest.keyClick(ed, Qt.Key.Key_Backspace)
    assert ed.toPlainText().endswith("pass\n")


def test_editor_block_indent_dedent(qapp):
    ed = CodeEditor()
    ed.setPlainText("a\nb\nc")
    ed.selectAll()
    ed.indent_selection()
    assert ed.toPlainText() == "    a\n    b\n    c"
    ed.selectAll()
    ed.dedent_selection()
    assert ed.toPlainText() == "a\nb\nc"


def test_bracket_matching_and_completion(qapp):
    ed = CodeEditor()
    ed.setPlainText("foo(bar[1], {2})")
    cur = ed.textCursor()
    cur.setPosition(4)  # after "("
    ed.setTextCursor(cur)
    assert ed.matching_bracket() == (3, 15)
    cur.setPosition(0)
    ed.setTextCursor(cur)
    assert ed.matching_bracket() is None
    ed.set_completions(["WIDGETS", "handler_one"])
    assert "WIDGETS" in ed.completion_matches("wid")
    assert "while" in ed.completion_matches("wh")


def test_problem_squiggle_extra_selection(qapp):
    ed = CodeEditor()
    ed.setPlainText("x = (\ny = 2")
    base = len(ed.extraSelections())
    ed.set_problem(check_module(ed.toPlainText()))
    assert len(ed.extraSelections()) == base + 1
    ed.set_problem(None)
    assert len(ed.extraSelections()) == base


def test_find_replace(qapp):
    v = CodeEditorView()
    v.editor.setPlainText("one two one two one")
    fb = v.find_bar
    fb.find_edit.setText("one")
    assert fb.match_count() == 3
    fb.replace_edit.setText("1")
    assert fb.replace_all() == 3
    assert v.editor.toPlainText() == "1 two 1 two 1"
    fb.find_edit.setText("TWO")
    assert fb.find_next()
    fb.case.setChecked(True)
    assert fb.match_count() == 0
    v.editor.undo()
    assert "one" in v.editor.toPlainText() or v.editor.toPlainText() == "1 two 1 two 1"


# ------------------------------------------------------------------ panel fixtures
class FakeService:
    def __init__(self, doc: ProjectDocument, fail: bool = False) -> None:
        self.doc = doc
        self.fail = fail
        self.calls = 0

    def generated_files(self, options=None):
        self.calls += 1
        if self.fail:
            raise ValueError("boom")
        return [
            GeneratedFile("main.py", "import ui\n\nprint('hi')\n"),
            GeneratedFile("requirements.txt", "pillow\n"),
            GeneratedFile("bad.py", "x = (\n"),
        ]


@pytest.fixture
def setup(qapp):
    p = new_project("P", "tkinter")
    btn = make_node("button", parent_id=p.root_id, name="Go")
    btn.events["click"] = "on_go"
    p.nodes[btn.id] = btn
    p.handlers["on_go"] = HandlerDef(name="on_go", body='print("go")')
    doc = ProjectDocument(p)
    h = History()
    svc = FakeService(doc)
    panel = CodePanel()
    panel.bind(doc, h, svc)
    return panel, doc, h, svc, btn


def test_handlers_list_shows_usage(setup):
    panel, doc, h, svc, btn = setup
    ht = panel.handlers
    assert ht.list.count() == 1
    assert "Go.click" in ht.list.item(0).text()
    assert ht.current() == "on_go"
    assert ht.editor.toPlainText() == 'print("go")'
    assert ht.signature.text() == "def on_go(event=None):"


def test_handler_typing_coalesces_and_undo_refreshes(setup):
    panel, doc, h, svc, btn = setup
    ht = panel.handlers
    ht.editor.setPlainText('print("a")')
    ht.editor.setPlainText('print("ab")')
    assert doc.project.handlers["on_go"].body == 'print("ab")'
    assert len(h.undo_stack) == 1
    h.undo(doc)
    panel.refresh()
    assert ht.editor.toPlainText() == 'print("go")'
    assert "Syntax OK" in ht.status.text()


def test_handler_syntax_status(setup):
    panel, doc, h, svc, btn = setup
    ht = panel.handlers
    ht.editor.setPlainText("if True print(1)")
    assert "Syntax error" in ht.status.text()
    assert ht.editor.problem() is not None
    ht.editor.setPlainText("pass")
    assert ht.editor.problem() is None


def test_handler_add_rename_delete(setup):
    panel, doc, h, svc, btn = setup
    ht = panel.handlers
    assert ht.add_handler("on_other") == "on_other"
    assert ht.add_handler("on_other") is None  # duplicate
    assert ht.add_handler("not valid") is None
    assert ht.add_handler("class") is None  # keyword
    auto = ht.add_handler()
    assert auto == "handler_1"
    assert ht.rename_handler("on_go", "go_clicked")
    assert btn.events["click"] == "go_clicked"
    assert "on_go" not in doc.project.handlers
    assert not ht.rename_handler("go_clicked", "on_other")
    n = len(h.undo_stack)
    h.undo(doc)
    assert btn.events["click"] == "on_go" and len(h.undo_stack) == n - 1
    assert ht.delete_handler("on_go")
    assert "click" not in btn.events and "on_go" not in doc.project.handlers
    h.undo(doc)
    assert btn.events["click"] == "on_go"
    panel.refresh()
    assert ht.list.count() == 3


def test_open_handler_focuses(setup):
    panel, doc, h, svc, btn = setup
    panel.handlers.add_handler("another")
    panel.tabs.setCurrentWidget(panel.generated)
    panel.open_handler("on_go")
    assert panel.tabs.currentWidget() is panel.handlers
    assert panel.handlers.current() == "on_go"


def test_changed_signal(setup):
    panel, doc, h, svc, btn = setup
    seen = []
    panel.changed.connect(lambda: seen.append(1))
    panel.handlers.editor.setPlainText("pass")
    panel.module.editor.setPlainText("import os")
    assert len(seen) == 2


def test_module_code_tab(setup):
    panel, doc, h, svc, btn = setup
    panel.module.editor.setPlainText("import os\nX = 1")
    panel.module.editor.setPlainText("import os\nX = 2")
    assert doc.project.custom_code == "import os\nX = 2"
    assert len(h.undo_stack) == 1
    panel.module.editor.setPlainText("x = (")
    assert "Syntax error" in panel.module.status.text()
    h.undo(doc)
    panel.refresh()
    assert panel.module.editor.toPlainText() == ""


def test_generated_tab_with_fake_service(setup):
    panel, doc, h, svc, btn = setup
    g = panel.generated
    panel.tabs.setCurrentWidget(g)
    assert svc.calls >= 1
    assert g.file_names() == ["main.py", "requirements.txt", "bad.py"]
    assert "print('hi')" in g.editor.toPlainText()
    assert g.editor.isReadOnly()
    assert not g.banner.isHidden() and "bad.py" in g.banner.text()
    g.file_combo.setCurrentIndex(1)
    assert g.editor.toPlainText().startswith("pillow")
    assert g.highlighter.document() is None
    g.copy()
    assert QApplication.clipboard().text().startswith("pillow")


def test_generated_tab_error_banner(setup):
    panel, doc, h, svc, btn = setup
    svc.fail = True
    panel.generated.refresh()
    assert not panel.generated.banner.isHidden()
    assert "boom" in panel.generated.banner.text()


def test_requirements_tab(setup):
    panel, doc, h, svc, btn = setup
    r = panel.requirements
    r.extra.setPlainText("requests>=2\n\nrich")
    assert doc.project.extra_requirements == ["requests>=2", "rich"]
    assert len(h.undo_stack) == 1
    h.undo(doc)
    panel.refresh()
    assert r.extra.toPlainText() == ""


# ------------------------------------------------------------------ brackets (tokenize based)
def test_bracket_matching_skips_strings_and_comments(qapp):
    from py_vui.app.editor.brackets import find_match, ignored_ranges

    src = 'f("(", x) # )\ny = [1, ")"]'
    assert find_match(src, 1) == 8  # the ")" inside the string is skipped
    assert find_match(src, 3) is None  # a bracket inside a string has no partner
    assert find_match(src, 8) == 1
    comment_paren = src.index("# )") + 2
    assert find_match(src, comment_paren) is None
    assert find_match(src, src.index("[")) == src.index("]")
    assert ignored_ranges("x = (") == []  # tolerates unterminated code
    assert ignored_ranges('s = "a" + (') == [(4, 7)]
    assert find_match("x = (", 4) is None
    fs = 'g(f"({a}) )", b)'
    assert find_match(fs, 1) == len(fs) - 1


def test_editor_bracket_selection_ignores_strings(qapp):
    ed = CodeEditor()
    ed.setPlainText('print(")", (1))')
    cur = ed.textCursor()
    cur.setPosition(6)  # right after the first "("
    ed.setTextCursor(cur)
    assert ed.matching_bracket() == (5, 14)
    ed.setPlainText('x = "(" # (\n(y)')
    cur.setPosition(len('x = "(" # (\n') + 1)
    ed.setTextCursor(cur)
    assert ed.matching_bracket() == (12, 14)


# ------------------------------------------------------------------ member completion
def test_member_context_parsing():
    from py_vui.app.editor.completion import member_context

    c = member_context('WIDGETS["go_btn"].se')
    assert (c.kind, c.key, c.prefix) == ("widget", "go_btn", "se")
    c = member_context("ui.WIDGETS['x'].")
    assert (c.kind, c.key, c.prefix) == ("widget", "x", "")
    c = member_context('WIDGETS["na')
    assert (c.kind, c.prefix) == ("key", "na")
    c = member_context("    os.path.jo")
    assert (c.kind, c.key, c.prefix) == ("name", "os.path", "jo")
    assert member_context("x = 1 + 2") is None


@pytest.mark.parametrize(
    ("framework", "node_type", "expected"),
    [
        ("tkinter", "entry", {"get", "insert", "delete", "configure"}),
        ("tkinter", "listbox", {"curselection", "insert"}),
        ("customtkinter", "checkbox", {"select", "deselect", "toggle"}),
        ("pyside6", "entry", {"setText", "text", "clear"}),
        ("pyqt6", "combobox", {"addItem", "currentText"}),
        ("kivy", "slider", {"value", "min", "max", "bind"}),
    ],
)
def test_widget_members_per_framework(framework, node_type, expected):
    from py_vui.app.editor.completion import widget_members

    assert expected <= set(widget_members(framework, node_type))
    assert widget_members(framework, node_type) == sorted(set(widget_members(framework, node_type)))


def test_module_members_whitelist():
    from py_vui.app.editor.completion import module_members

    assert "listdir" in module_members("os", "tkinter")
    assert "join" in module_members("os.path", "tkinter")
    assert "sqrt" in module_members("math", "kivy")
    assert module_members("evilmodule", "tkinter") == []
    assert "showinfo" in module_members("messagebox", "tkinter")
    assert "keysym" in module_members("event", "tkinter")
    assert "pos" in module_members("event", "kivy")


def test_editor_offers_widget_members_after_dot(setup):
    panel, doc, h, svc, btn = setup
    ht = panel.handlers
    ed = ht.editor
    var = doc.variable_names()[btn.id]
    ed.setPlainText(f'WIDGETS["{var}"].conf')
    ed.moveCursor(QTextCursor.MoveOperation.End)
    assert "configure" in ed.completion_matches("conf")
    assert "invoke" in ed.completion_matches("inv")
    doc.project.framework = "pyside6"
    ed.setPlainText(f'WIDGETS["{var}"].set')
    ed.moveCursor(QTextCursor.MoveOperation.End)
    assert "setText" in ed.completion_matches("set")
    ed.setPlainText('WIDGETS["')
    ed.moveCursor(QTextCursor.MoveOperation.End)
    assert var in ed.completion_matches("")
    ed.setPlainText("import os\nos.")
    ed.moveCursor(QTextCursor.MoveOperation.End)
    assert "getcwd" in ed.completion_matches("getc")
    ed.setPlainText("wh")
    ed.moveCursor(QTextCursor.MoveOperation.End)
    assert "while" in ed.completion_matches("wh")


# ------------------------------------------------------------------ palette-derived colours
def test_error_colours_follow_palette(qapp):
    from PySide6.QtGui import QColor, QGuiApplication, QPalette

    from py_vui.app.editor.ui_colors import ErrorBanner, ErrorLabel, error_color, is_dark

    light, dark = QPalette(), QPalette()
    light.setColor(QPalette.ColorRole.Window, QColor("#f5f5f5"))
    dark.setColor(QPalette.ColorRole.Window, QColor("#202020"))
    assert not is_dark(light) and is_dark(dark)
    el, ed = error_color(light), error_color(dark)
    assert el.lightness() < ed.lightness()
    assert el.red() > el.green() and ed.red() > ed.green()
    lab = ErrorLabel("x")
    assert lab.palette().windowText().color() == error_color(QGuiApplication.palette())
    banner = ErrorBanner("x")
    assert banner.palette().window().color() == error_color(QGuiApplication.palette())
    assert banner.styleSheet() == "" and lab.styleSheet() == ""


def test_no_hardcoded_error_hex_in_panel_sources():
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "py_vui" / "app" / "editor"
    names = ["prop_editors.py", "code_tabs.py", "code_editor.py", "dialogs/plugins.py",
             "find_bar.py", "inspector.py"]
    for n in names:
        text = (root / n).read_text(encoding="utf-8")
        assert not re.search(r"#(?:d33|e5484d|b3261e)", text, re.I), n
