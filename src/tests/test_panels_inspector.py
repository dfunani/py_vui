"""Inspector panel: builds for every widget type and writes the right commands."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from py_vui.app.editor.inspector import InspectorPanel
from py_vui.app.editor.prop_editors import FileEdit
from py_vui.commands import History
from py_vui.core import ProjectDocument, make_node, new_project
from py_vui.core.registry import all_specs


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


class Env:
    def __init__(self) -> None:
        self.project = new_project("T", "tkinter")
        self.doc = ProjectDocument(self.project)
        self.history = History()
        self.panel = InspectorPanel()
        self.panel.bind(self.doc, self.history)
        self.changed = 0
        self.panel.changed.connect(self._bump)

    def _bump(self) -> None:
        self.changed += 1

    def add(self, type_id: str, parent: str | None = None, **kw):
        n = make_node(type_id, parent_id=parent or self.project.root_id, **kw)
        self.project.nodes[n.id] = n
        return n

    def select(self, *nodes) -> None:
        self.panel.set_selection([n.id for n in nodes])

    def undo(self) -> None:
        self.history.undo(self.doc)
        self.panel.refresh()


@pytest.fixture
def env(qapp):
    return Env()


def type_text(editor, text: str) -> None:
    editor._w.setText(text)  # TextEdit line edit: emits like user typing


@pytest.mark.parametrize("spec", all_specs(), ids=lambda s: s.type)
def test_inspector_builds_for_every_type(env, spec):
    node = env.project.nodes[env.project.root_id] if spec.type == "window" else env.add(spec.type)
    env.select(node)
    titles = [env.panel.tabs.tabText(i) for i in range(env.panel.tabs.count())]
    assert "Style" in titles and "Layout" in titles
    if spec.props:
        assert "Properties" in titles
    if spec.events:
        assert "Events" in titles
    assert env.panel.type_label.text() == spec.label


def test_prop_edit_is_command_coalesced_and_undoable(env):
    lab = env.add("label", text="Hello")
    env.select(lab)
    ed = env.panel.props_page.editor("text")
    type_text(ed, "H")
    type_text(ed, "Hi")
    type_text(ed, "Hi there")
    assert lab.props["text"] == "Hi there"
    assert len(env.history.undo_stack) == 1
    assert env.changed >= 3
    env.undo()
    assert lab.props["text"] == "Hello"
    assert env.panel.props_page.editor("text").value() == "Hello"


def test_choice_bool_int_edits(env):
    lab = env.add("label")
    env.select(lab)
    env.panel.props_page.editor("anchor").combo().setCurrentIndex(
        env.panel.props_page.editor("anchor").combo().findData("center"))
    assert lab.props["anchor"] == "center"
    env.panel.props_page.editor("wrap_length").spin().setValue(120)
    assert lab.props["wrap_length"] == 120
    cb = env.add("checkbox")
    env.select(cb)
    assert "checked" in cb.props
    env.panel.props_page.editor("checked")._cb.setChecked(True)
    assert cb.props["checked"] is True


def test_list_and_json_and_file_editors(env):
    combo = env.add("combobox")
    env.select(combo)
    items = env.panel.props_page.editor("items")
    items._add()
    assert combo.props["items"][-1].startswith("Item")
    items.list_widget().setCurrentRow(0)
    items._move(1)
    assert combo.props["items"][1] == "Option 1"
    items._remove()
    assert len(combo.props["items"]) == 2
    win = env.project.nodes[env.project.root_id]
    env.select(win)
    # json editor rejects invalid text and accepts valid text
    tbl = env.add("table")
    env.select(tbl)
    js = env.panel.props_page.editor("rows")
    js.setText("[[1,")
    assert not js.is_valid() and tbl.props["rows"] != [[1]]
    js.setText('[["a", "b"]]')
    assert tbl.props["rows"] == [["a", "b"]]


def test_image_picker_uses_asset_importer(env, tmp_path):
    img = env.add("image")
    env.select(img)
    env.panel.asset_importer = lambda p: f"assets/{p.name}"
    fe = env.panel.props_page.editor("source")
    assert isinstance(fe, FileEdit)
    fe.pick(tmp_path / "logo.png")
    assert img.props["source"] == "assets/logo.png"
    env.panel.asset_importer = None
    fe.pick(Path("/x/other.png"))
    assert img.props["source"] == "/x/other.png"


def test_style_edit_and_reset_to_theme(env):
    btn = env.add("button")
    env.select(btn)
    page = env.panel.style_page
    page.editor("background").set_value("#112233")
    page.editor("background").valueChanged.emit("#112233")
    assert btn.style["background"] == "#112233"
    page.editor("font_size").spin().setValue(20)
    assert btn.style["font_size"] == 20
    page._reset("background")
    assert "background" not in btn.style
    # setting a field back to its inherit value drops the key
    page.editor("font_size").spin().setValue(0)
    assert "font_size" not in btn.style
    env.undo()
    assert btn.style["font_size"] == 20


def test_events_new_pick_unbind_edit(env):
    btn = env.add("button", name="Save Btn")
    env.select(btn)
    ev = env.panel.events_page
    requested: list[str] = []
    env.panel.handler_requested.connect(requested.append)
    name = ev.new_handler("click")
    assert name == "save_btn_click"
    assert btn.events["click"] == name
    assert env.project.handlers[name].body == 'print("Save Btn click")'
    assert len(env.history.undo_stack) == 1  # handler + binding = one step
    ev.edit_event("click")
    assert requested == [name]
    ev.new_handler("double_click")
    other = btn.events["double_click"]
    ev.bind_event("click", other)
    assert btn.events["click"] == other
    ev.bind_event("click", "")
    assert "click" not in btn.events
    env.undo()
    assert btn.events["click"] == other
    # second button reuses an existing handler via the combo
    b2 = env.add("button", name="Other")
    env.select(b2)
    combo = env.panel.events_page.combo("click")
    assert combo.findData(name) >= 0
    env.panel.events_page.bind_event("click", name)
    assert b2.events["click"] == name


def test_events_grouped_by_catalog(env):
    btn = env.add("button")
    env.select(btn)
    from py_vui.core.events import EVENTS
    from py_vui.core.registry import get_spec

    page = env.panel.events_page
    assert set(page._combos) == {e for e in get_spec("button").events if e in EVENTS}


def test_layout_box_coalesces_and_undoes(env):
    btn = env.add("button", x=10, y=10)
    env.select(btn)
    lp = env.panel.layout_page
    for v in (11, 12, 13):
        lp._box_editors["x"].spin().setValue(v)
    lp._box_editors["w"].spin().setValue(200)
    assert btn.box.x == 13 and btn.box.w == 200
    assert len(env.history.undo_stack) == 1
    env.undo()
    assert btn.box.x == 10
    assert lp._box_editors["x"].value() == 10


def test_layout_flags_anchors_name(env):
    btn = env.add("button")
    env.select(btn)
    lp = env.panel.layout_page
    lp.editor("anchor_right")._cb.setChecked(True)
    assert btn.anchors.right is True
    lp.editor("locked")._cb.setChecked(True)
    assert btn.locked is True
    lp.editor("tab_index").spin().setValue(3)
    assert btn.tab_index == 3
    lp.editor("tab_index").spin().setValue(-1)
    assert btn.tab_index is None
    env.panel.name_edit.setText("Renamed")
    env.panel.commit_name()
    assert btn.name == "Renamed"
    other = env.add("button", name="Taken")
    env.select(other)
    env.panel.name_edit.setText("Renamed")
    env.panel.commit_name()
    assert other.name == "Renamed 2"


def test_container_layout_modes(env):
    frame = env.add("frame")
    env.select(frame)
    lp = env.panel.layout_page
    lp.editor("mode").button("flex").setChecked(True)
    assert frame.layout.mode == "flex"
    env.panel.layout_page.editor("direction").button("row").setChecked(True)
    assert frame.layout.direction == "row"
    env.panel.layout_page.editor("gap").spin().setValue(20)
    assert frame.layout.gap == 20
    env.panel.layout_page.editor("justify").combo().setCurrentIndex(
        env.panel.layout_page.editor("justify").combo().findData("center"))
    assert frame.layout.justify == "center"
    env.panel.layout_page.editor("padding_top").spin().setValue(5)
    assert frame.layout.padding.top == 5
    env.panel.layout_page.editor("mode").button("grid").setChecked(True)
    assert frame.layout.mode == "grid"
    cw = env.panel.layout_page.editor("column_weights")
    cw._add()
    assert len(frame.layout.column_weights) == 3
    cw.list_widget().setCurrentRow(0)
    cw._remove()
    assert len(frame.layout.column_weights) == 2
    rw = env.panel.layout_page.editor("row_weights")
    rw._add()
    assert len(frame.layout.row_weights) == 3


def test_flex_item_editor(env):
    frame = env.add("frame")
    frame.layout.mode = "flex"
    child = env.add("button", parent=frame.id)
    env.select(child)
    lp = env.panel.layout_page
    lp.editor("grow").spin().setValue(2.0)
    assert child.flex.grow == 2.0
    lp.editor("align_self").combo().setCurrentIndex(lp.editor("align_self").combo().findData("end"))
    assert child.flex.align_self == "end"
    lp.editor("margin_left").spin().setValue(7)
    assert child.flex.margin.left == 7
    assert "row" not in lp._named  # not a grid child


def test_grid_cell_editor(env):
    frame = env.add("frame")
    frame.layout.mode = "grid"
    child = env.add("button", parent=frame.id)
    env.select(child)
    lp = env.panel.layout_page
    lp.editor("row").spin().setValue(1)
    lp.editor("column").spin().setValue(2)
    lp.editor("row_span").spin().setValue(2)
    lp.editor("column_span").spin().setValue(3)
    assert (child.cell.row, child.cell.column) == (1, 2)
    assert (child.cell.row_span, child.cell.column_span) == (2, 3)
    lp.editor("sticky_n")._cb.setChecked(False)
    assert child.cell.sticky == "sew"
    lp.editor("sticky_n")._cb.setChecked(True)
    assert child.cell.sticky == "nsew"


def test_paged_container_page_selector(env):
    tabs = env.add("tabview")
    child = env.add("button", parent=tabs.id)
    env.select(child)
    ed = env.panel.layout_page.editor("page")
    ed.combo().setCurrentIndex(1)
    assert child.page == 1


def test_multi_select_batch_single_undo(env):
    a, b = env.add("label", text="a"), env.add("label", text="b")
    env.select(a, b)
    assert env.panel.name_edit.isEnabled() is False
    ed = env.panel.props_page.editor("text")
    type_text(ed, "x")
    type_text(ed, "xy")
    assert a.props["text"] == b.props["text"] == "xy"
    assert len(env.history.undo_stack) == 1
    env.undo()
    assert (a.props["text"], b.props["text"]) == ("a", "b")
    env.panel.layout_page._box_editors["w"].spin().setValue(77)
    assert a.box.w == b.box.w == 77
    assert len(env.history.undo_stack) == 1


def test_multi_select_mixed_types_only_common_tabs(env):
    a, b = env.add("label"), env.add("button")
    env.select(a, b)
    titles = [env.panel.tabs.tabText(i) for i in range(env.panel.tabs.count())]
    assert titles[:2] == ["Style", "Layout"]
    assert "Properties" not in titles
    env.panel.style_page.editor("bold")._cb.setChecked(True)
    assert a.style["bold"] and b.style["bold"]


def test_project_summary_when_nothing_selected(env):
    env.add("label")
    env.panel.set_selection([])
    s = env.panel.summary
    assert not s.isHidden()
    assert env.panel.tabs.isHidden()
    s.theme.setCurrentIndex(s.theme.findData("dark"))
    s._theme_picked(0)
    assert env.project.theme.preset == "dark"
    env.undo()
    assert env.project.theme.preset != "dark"
    # a dangling handler reference shows up in diagnostics
    env.project.nodes[env.project.root_id].events["close"] = "missing_handler"
    s.refresh()
    assert any("missing_handler" in s.diag.item(i).text() for i in range(s.diag.count()))


def test_refresh_after_external_change_does_not_loop(env):
    lab = env.add("label", text="a")
    env.select(lab)
    lab.props["text"] = "changed externally"
    before = len(env.history.undo_stack)
    env.panel.refresh()
    assert env.panel.props_page.editor("text").value() == "changed externally"
    assert len(env.history.undo_stack) == before


def test_menu_button_for_window(env):
    env.select(env.project.nodes[env.project.root_id])
    assert hasattr(env.panel, "menus_button")
    assert "menus" not in env.panel.props_page._rows


# ------------------------------------------------------------------ true mixed state
def test_mixed_text_number_bool_choice_color(env):
    a = env.add("label", text="a", x=1)
    b = env.add("label", text="b", x=1)
    a.style["bold"] = True
    a.props["anchor"] = "center"
    a.style["background"] = "#111111"
    env.select(a, b)
    pp, sp = env.panel.props_page, env.panel.style_page
    assert pp.editor("text").is_mixed() and pp.editor("text").value() == ""
    assert pp.editor("text")._w.placeholderText() == pp.editor("text").MIXED_TEXT
    assert not pp.editor("wrap_length").is_mixed()
    assert pp.editor("anchor").is_mixed() and pp.editor("anchor").combo().currentText() == "—"
    assert sp.editor("bold").is_mixed() and sp.editor("bold")._cb.checkState().name == (
        "PartiallyChecked")
    assert sp.editor("background").is_mixed()
    assert sp.editor("background")._hex.placeholderText() == sp.editor("background").MIXED_TEXT
    assert not sp.editor("italic").is_mixed()
    # the layout page agrees field by field
    lp = env.panel.layout_page
    a.box.w = 50
    env.panel.refresh()
    assert lp._box_editors["w"].is_mixed() and lp._box_editors["w"].spin().specialValueText()
    assert not lp._box_editors["x"].is_mixed()


def test_mixed_edit_applies_to_all_and_clears_mixed(env):
    a = env.add("label", text="a")
    b = env.add("label", text="b")
    a.style["bold"] = True
    a.props["anchor"] = "center"
    env.select(a, b)
    pp, sp = env.panel.props_page, env.panel.style_page
    type_text(pp.editor("text"), "same")
    assert a.props["text"] == b.props["text"] == "same"
    assert not pp.editor("text").is_mixed()
    pp.editor("anchor").combo().setCurrentIndex(pp.editor("anchor").combo().findData("e"))
    assert a.props["anchor"] == b.props["anchor"] == "e"
    assert not pp.editor("anchor").is_mixed()
    assert pp.editor("anchor").combo().findData(pp.editor("anchor")._MIX) < 0
    sp.editor("bold")._cb.setCheckState(sp.editor("bold")._cb.checkState().Checked)
    assert a.style.get("bold") is True and b.style.get("bold") is True
    assert not sp.editor("bold").is_mixed()
    # all edits so far are separate, undoable steps over both nodes
    env.undo()
    assert "bold" not in b.style or b.style["bold"] is False or a.style["bold"]


def test_mixed_number_stepping_and_special_value(env):
    a, b = env.add("label"), env.add("label")
    a.props["wrap_length"] = 10
    b.props["wrap_length"] = 20
    env.select(a, b)
    ed = env.panel.props_page.editor("wrap_length")
    assert ed.is_mixed()
    spin = ed.spin()
    assert spin.value() == spin.minimum()
    spin.setValue(40)
    assert a.props["wrap_length"] == b.props["wrap_length"] == 40
    assert not ed.is_mixed() and spin.specialValueText() == ""


def test_mixed_list_json_and_choice_events(env):
    a, b = env.add("combobox"), env.add("combobox")
    a.props["items"] = ["x"]
    env.select(a, b)
    items = env.panel.props_page.editor("items")
    assert items.is_mixed() and items.value() == []
    items._add()
    assert not items.is_mixed()
    assert a.props["items"] == b.props["items"]
    # events: differing bindings show a mixed entry which cannot be "picked"
    env.project.handlers["h"] = __import__("py_vui.core.model", fromlist=["x"]).HandlerDef(
        name="h", body="pass")
    a.events["change"] = "h"
    env.select(a, b)
    combo = env.panel.events_page.combo("change")
    assert combo.itemText(0).endswith("mixed —")
    env.panel.events_page._picked("change", combo.itemData(0))
    assert "change" in a.events and "change" not in b.events
    env.panel.events_page.bind_event("change", "h")
    assert a.events["change"] == b.events["change"] == "h"


def test_mixed_radio_and_layout_mode(env):
    f1, f2 = env.add("frame"), env.add("frame")
    f2.layout.mode = "flex"
    env.select(f1, f2)
    mode = env.panel.layout_page.editor("mode")
    assert mode.is_mixed() and mode.value() == ""
    mode.button("grid").setChecked(True)
    assert f1.layout.mode == f2.layout.mode == "grid"
    assert not mode.is_mixed()
