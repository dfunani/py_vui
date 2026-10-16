"""Every editor dialog constructs and performs its main action (offscreen, temp dirs)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import zipfile
from pathlib import Path

import pytest
from PySide6.QtCore import QMimeData, QUrl
from PySide6.QtWidgets import QApplication

from py_vui.app.editor.dialogs import (
    AboutDialog,
    AssetManagerDialog,
    ExportDialog,
    FrameworkDialog,
    MenuDesignerDialog,
    NewProjectDialog,
    PluginManagerDialog,
    PreferencesDialog,
    RequirementsDialog,
    ShortcutsDialog,
    TemplateGalleryDialog,
    ThemeEditorDialog,
)
from py_vui.app.editor.dialogs.thumbnail import render_thumbnail
from py_vui.commands import History
from py_vui.core import ProjectDocument, make_node, new_project
from py_vui.core.model import HandlerDef
from py_vui.services import settings
from py_vui.services.project_service import ProjectService
from py_vui.services.templates import list_templates, load_template


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _home(tmp_path, monkeypatch, qapp):
    monkeypatch.setenv("PY_VUI_HOME", str(tmp_path / "home"))


@pytest.fixture
def doc_hist():
    p = new_project("D", "tkinter")
    btn = make_node("button", parent_id=p.root_id, name="Go")
    p.nodes[btn.id] = btn
    return ProjectDocument(p), History()


@pytest.fixture
def service():
    s = ProjectService()
    s.new_project("Svc", "tkinter")
    btn = make_node("button", parent_id=s.project.root_id, name="Go", x=10, y=10)
    s.project.nodes[btn.id] = btn
    return s


# ------------------------------------------------------------------ new project / gallery
def test_new_project_dialog_defaults_and_accept(qapp):
    d = NewProjectDialog()
    d.name_edit.setText("My App")
    d.set_framework("kivy")
    d.accept()
    assert (d.name, d.framework, d.template_id) == ("My App", "kivy", None)


def test_new_project_dialog_template_and_default_framework(qapp):
    settings.set("default_framework", "pyside6")
    d = NewProjectDialog()
    assert d._radios["pyside6"].isChecked()
    tid = list_templates()[1].id
    assert d.set_template(tid)
    d.accept()
    assert d.template_id == tid and d.name == "Untitled"


def test_gallery_filter_search_and_pick(qapp):
    d = TemplateGalleryDialog()
    all_ids = d.visible_ids()
    assert len(all_ids) == len(list_templates()) > 5
    d.search.setText("login")
    assert 0 < len(d.visible_ids()) < len(all_ids)
    d.search.setText("")
    cats = [d.category.itemData(i) for i in range(1, d.category.count())]
    d.category.setCurrentIndex(1)
    shown = d.visible_ids()
    assert shown and all(
        next(t for t in list_templates() if t.id == i).category == cats[0] for i in shown)
    assert d.select(shown[0])
    assert d.title.text()
    d.accept()
    assert d.template_id == shown[0]


def test_thumbnail_renders_every_template(qapp):
    for t in list_templates():
        pm = render_thumbnail(load_template(t.id), 120, 80)
        assert not pm.isNull() and pm.width() == 120


# ------------------------------------------------------------------ theme
def test_theme_editor_applies_single_undo_step(qapp, doc_hist):
    doc, h = doc_hist
    d = ThemeEditorDialog(doc, h)
    d.preset.set_value("dark")
    d.preset.valueChanged.emit("dark")
    assert d.theme.preset == "dark"
    d.set_token("primary", "#ff0000")
    d.set_token("button_radius", 20)
    d.set_token("font_size", 15)
    assert d.preview.theme.primary == "#ff0000"
    d.accept()
    t = doc.project.theme
    assert (t.preset, t.primary, t.button_radius, t.font_size) == ("dark", "#ff0000", 20, 15)
    assert len(h.undo_stack) == 1
    h.undo(doc)
    assert doc.project.theme.preset != "dark"


def test_theme_editor_cancel_changes_nothing(qapp, doc_hist):
    doc, h = doc_hist
    d = ThemeEditorDialog(doc, h)
    d.set_token("primary", "#00ff00")
    d.reject()
    assert not h.undo_stack


# ------------------------------------------------------------------ menus
def test_menu_designer_builds_and_saves(qapp, doc_hist):
    doc, h = doc_hist
    root = doc.project.root_id
    d = MenuDesignerDialog(doc, h, root)
    file_menu = d.add_menu("File")
    d._on_current(file_menu)
    d.add_item("Open")
    d.label_edit.setText("Open…")
    d.label_edit.textEdited.emit("Open…")
    d.shortcut_edit.setText("Ctrl+O")
    d.shortcut_edit.textEdited.emit("Ctrl+O")
    name = d.new_handler_for_current()
    assert name == "menu_open"
    d.add_item(separator=True)
    d.add_item("Recent", submenu=True)
    d.add_item("a.txt")
    d.tree.setCurrentItem(file_menu)
    d.add_item("Quit", checkable=True)
    d.accept()
    menus = doc.project.nodes[root].props["menus"]
    assert menus[0]["title"] == "File"
    items = menus[0]["items"]
    assert items[0] == {"label": "Open…", "shortcut": "Ctrl+O", "handler": "menu_open"}
    assert items[1]["separator"] is True
    assert items[2]["label"] == "Recent" and items[2]["items"][0]["label"] == "a.txt"
    assert items[3]["checkable"] is True
    assert "menu_open" in doc.project.handlers
    assert len(h.undo_stack) == 1
    h.undo(doc)
    assert "menu_open" not in doc.project.handlers
    assert not doc.project.nodes[root].props["menus"]


def test_menu_designer_reload_move_delete(qapp, doc_hist):
    doc, h = doc_hist
    root = doc.project.root_id
    doc.project.handlers["h"] = HandlerDef(name="h", body="pass")
    doc.project.nodes[root].props["menus"] = [
        {"title": "A", "items": [{"label": "x", "handler": "h"}, {"label": "y"}]},
        {"title": "B", "items": []},
    ]
    d = MenuDesignerDialog(doc, h, root)
    assert d.menus() == doc.project.nodes[root].props["menus"]
    d.tree.setCurrentItem(d.tree.topLevelItem(0).child(1))
    d.move_current(-1)
    assert [m["label"] for m in d.menus()[0]["items"]] == ["y", "x"]
    d.delete_current()
    d.tree.setCurrentItem(d.tree.topLevelItem(1))
    d.move_current(-1)
    assert d.menus()[0]["title"] == "B"
    d.accept()
    assert doc.project.nodes[root].props["menus"][1]["items"] == [{"label": "x", "handler": "h"}]


def test_menu_designer_via_inspector(qapp, doc_hist, monkeypatch):
    from py_vui.app.editor.inspector import InspectorPanel

    doc, h = doc_hist
    panel = InspectorPanel()
    panel.bind(doc, h)
    panel.set_selection([doc.project.root_id])
    monkeypatch.setattr(MenuDesignerDialog, "exec", lambda self: 1)
    panel.edit_menus()  # opens (stubbed exec) without error


# ------------------------------------------------------------------ assets
def test_asset_manager_add_remove_copy_drop(qapp, service, tmp_path):
    from PySide6.QtGui import QColor, QImage

    img = QImage(8, 8, QImage.Format.Format_RGB32)
    img.fill(QColor("red"))
    src = tmp_path / "pic.png"
    assert img.save(str(src))
    other = tmp_path / "note.txt"
    other.write_text("hi")
    d = AssetManagerDialog(service)
    assert d.add_files([src]) == ["assets/pic.png"]
    assert d.list.count() == 1 and not d.list.item(0).icon().isNull()
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(other))])
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtGui import QDropEvent

    ev = QDropEvent(QPoint(5, 5), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton,
                    Qt.KeyboardModifier.NoModifier)
    d.dropEvent(ev)
    assert sorted(d.assets()) == ["assets/note.txt", "assets/pic.png"]
    d.list.item(0).setSelected(True)
    assert d.copy_selected_path() == d.selected()[0]
    assert QApplication.clipboard().text() == d.selected()[0]
    assert d.remove_selected() == 1
    assert len(service.project.assets) == 1 and d.list.count() == 1


# ------------------------------------------------------------------ plugins
class FakeInfo:
    def __init__(self, id, enabled=False, error=None):
        self.id, self.name, self.version = id, id.title(), "1.0"
        self.description, self.path = "demo", Path(".")
        self.enabled, self.error, self.widget_types = enabled, error, ["gauge"]


class FakeManager:
    def __init__(self, tmp):
        self.state = {"alpha": False, "beta": False}
        self.tmp = tmp
        self.enabled_calls: list[str] = []

    def user_dir(self):
        return self.tmp / "plugins"

    def scan(self, project_dir=None):
        out = [FakeInfo(k, v) for k, v in self.state.items()]
        out.append(FakeInfo("broken", error="bad plugin.json"))
        return out

    def enable(self, pid, project_dir=None):
        self.enabled_calls.append(pid)
        if pid == "beta":
            raise RuntimeError("failed to load")
        self.state[pid] = True

    def disable(self, pid):
        self.state[pid] = False


def test_plugin_manager_enable_confirm_disable(qapp, tmp_path):
    m = FakeManager(tmp_path)
    d = PluginManagerDialog(None, manager=m)
    assert d.table.rowCount() == 3
    assert "bad plugin.json" in d.table.item(2, 5).text()
    asked: list[str] = []
    d.confirm = lambda _p, _t, text: (asked.append(text), False)[1]
    assert d.set_enabled("alpha", True) is False and not m.state["alpha"]
    assert "execute" in asked[0]
    d.confirm = lambda *_a: True
    assert d.set_enabled("alpha", True) and m.state["alpha"]
    assert d.table.item(0, 5).text() == "Enabled"
    assert d.set_enabled("beta", True) is False
    assert "failed to load" in d.message.text()
    assert d.set_enabled("alpha", False) and not m.state["alpha"]
    assert d.plugins_dir().is_dir()


def test_plugin_manager_with_real_manager(qapp, tmp_path):
    d = PluginManagerDialog(None, project_dir=tmp_path)
    assert d.table.rowCount() >= 0


# ------------------------------------------------------------------ export
def test_export_project_single_zip(qapp, service, tmp_path):
    d = ExportDialog(service)
    assert d.preview.count() >= 3
    d.dest.setText(str(tmp_path / "out"))
    assert d.export() == tmp_path / "out"
    assert (tmp_path / "out" / "main.py").is_file()
    assert "Exported to" in d.result_label.text()

    d.set_format("single")
    d.dest.setText(str(tmp_path / "one.py"))
    assert d.export() == tmp_path / "one.py"
    assert "def " in (tmp_path / "one.py").read_text() or (tmp_path / "one.py").stat().st_size > 0

    d.set_format("zip")
    assert d.dest.text().endswith(".zip")
    d.dest.setText(str(tmp_path / "pack.zip"))
    d.include_requirements.setChecked(False)
    out = d.export()
    assert out == tmp_path / "pack.zip"
    names = zipfile.ZipFile(out).namelist()
    assert any(n.endswith("main.py") for n in names)
    assert not any(n.endswith("requirements.txt") for n in names)


def test_export_framework_override_restores_project(qapp, service, tmp_path):
    d = ExportDialog(service)
    d.framework.setCurrentIndex(d.framework.findData("pyside6"))
    d.dest.setText(str(tmp_path / "qt"))
    assert d.export() is not None
    assert service.project.framework == "tkinter"
    assert "PySide6" in (tmp_path / "qt" / "ui.py").read_text()


def test_export_reports_failure(qapp, service, tmp_path):
    d = ExportDialog(service)
    d.service = type("S", (), {"doc": service.doc, "export": lambda *a, **k: 1 / 0})()
    d.dest.setText(str(tmp_path / "x"))
    assert d.export() is None and d.error and "failed" in d.result_label.text()


# ------------------------------------------------------------------ framework / requirements
def test_framework_dialog_report_and_apply(qapp, doc_hist):
    doc, h = doc_hist
    d = FrameworkDialog(doc, h)
    d.select("kivy")
    assert d.report.count() >= 1
    d.accept()
    assert doc.project.framework == "kivy"
    h.undo(doc)
    assert doc.project.framework == "tkinter"


def test_framework_dialog_unsupported_widgets_listed(qapp, doc_hist):
    from py_vui.app.editor.dialogs.framework import compatibility_report
    from py_vui.core.registry import all_specs

    doc, _h = doc_hist
    fws = ("tkinter", "customtkinter", "pyside6", "pyqt6", "kivy")
    partial = next((s for s in all_specs() if any(not s.supports(f) for f in fws)), None)
    if partial is None:
        pytest.skip("every widget supports every framework")
    n = make_node(partial.type, parent_id=doc.project.root_id, name="Odd")
    doc.project.nodes[n.id] = n
    fw = next(f for f in fws if not partial.supports(f))
    assert any("Odd" in line for line in compatibility_report(doc, fw))


def test_requirements_dialog_edits_extras(qapp, doc_hist):
    doc, h = doc_hist
    d = RequirementsDialog(doc, h)
    d.editor.extra.setPlainText("rich")
    assert doc.project.extra_requirements == ["rich"]


# ------------------------------------------------------------------ prefs / shortcuts / about
def test_preferences_roundtrip(qapp):
    d = PreferencesDialog()
    d.theme.setCurrentIndex(d.theme.findData("dark"))
    d.autosave.setValue(30)
    d.framework.setCurrentIndex(d.framework.findData("kivy"))
    d.snap.setChecked(False)
    d.grid.setValue(16)
    d.accept()
    assert settings.get("editor_theme") == "dark"
    assert settings.get("autosave_seconds") == 30
    assert settings.get("default_framework") == "kivy"
    assert settings.get("snap_enabled") is False
    assert settings.get("grid_size") == 16
    again = PreferencesDialog()
    assert again.values() == d.values()


def test_shortcuts_and_about(qapp):
    from py_vui import __version__

    d = ShortcutsDialog()
    assert d.table.rowCount() > 10
    d.filter.setText("undo")
    visible = [r for r in range(d.table.rowCount()) if not d.table.isRowHidden(r)]
    assert visible and all("undo" in d.table.item(r, 1).text().lower() for r in visible)
    a = AboutDialog()
    assert __version__ in a.version_label.text()


# ------------------------------------------------------------------ adapter-derived facts
def test_framework_facts_match_adapter_sources():
    from py_vui.app.editor.dialogs.framework_facts import _FACTS

    codegen = Path(__file__).resolve().parents[1] / "py_vui" / "codegen"
    for fw, facts in _FACTS.items():
        assert facts, fw
        for f in facts:
            assert f.phrase in (codegen / f.module).read_text(encoding="utf-8"), (fw, f.text)


def test_framework_caveats_are_project_specific(qapp):
    from py_vui.app.editor.dialogs.framework_facts import project_caveats

    p = new_project("C", "tkinter")
    doc = ProjectDocument(p)
    root = p.nodes[p.root_id]
    root.props["menus"] = [{"title": "File", "items": []}]
    root.props["resizable_x"], root.props["resizable_y"] = True, False
    frame = make_node("frame", parent_id=p.root_id, name="Row")
    frame.layout.mode, frame.layout.wrap, frame.layout.direction = "flex", True, "column"
    combo = make_node("combobox", parent_id=p.root_id, name="Pick", editable=True)
    combo.style["font_family"] = "Helvetica"
    top = make_node("toplevel", parent_id=p.root_id, name="Dlg")
    for n in (frame, combo, top):
        p.nodes[n.id] = n
    kivy = " ".join(project_caveats(doc, "kivy"))
    for needle in ("ActionBar", "snapped back", "Popups"):
        assert needle in kivy, needle
    assert "Helvetica" not in kivy and "wrap" not in kivy  # the adapter now handles both
    assert project_caveats(doc, "tkinter") == []
    assert project_caveats(doc, "pyside6") == []  # Qt wraps both directions (flow layout)


# ------------------------------------------------------------------ export options (real service)
def test_export_dialog_passes_options_to_service(qapp, service, tmp_path):
    img = tmp_path / "a.png"
    img.write_bytes(b"x")
    service.add_asset(img)
    d = ExportDialog(service)
    d.include_assets.setChecked(False)
    d.include_requirements.setChecked(False)
    d.dest.setText(str(tmp_path / "lean"))
    out = d.export()
    assert out is not None and (out / "main.py").is_file()
    assert not (out / "assets").exists() and not (out / "requirements.txt").exists()
    names = [d.preview.item(i).text() for i in range(d.preview.count())]
    assert "requirements.txt" not in names and not any(n.startswith("assets/") for n in names)
    d.include_assets.setChecked(True)
    d.include_requirements.setChecked(True)
    d.dest.setText(str(tmp_path / "full"))
    full = d.export()
    assert (full / "assets" / "a.png").is_file() and (full / "requirements.txt").is_file()
    assert any(d.preview.item(i).text().startswith("assets/") for i in range(d.preview.count()))
