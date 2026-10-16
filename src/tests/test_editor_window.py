"""MainWindow: construction, palette insertion, themes, persistence, run wiring."""

from __future__ import annotations

import pytest
from editor_support import (
    FakeProcess,
    dispose,
    home,  # noqa: F401
    make_window,
    qapp,  # noqa: F401
)
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from py_vui.core.registry import FRAMEWORKS, all_specs, get_spec, specs_for

pytestmark = pytest.mark.gui


@pytest.fixture
def win(qapp, home, tmp_path):  # noqa: F811
    w = make_window(tmp_path)
    yield w
    dispose(w)


@pytest.mark.parametrize("framework", FRAMEWORKS)
def test_main_window_constructs_for_each_framework(qapp, home, tmp_path, framework):  # noqa: F811
    w = make_window(tmp_path, framework)
    try:
        assert framework in w.windowTitle()
        assert w.fw_combo.currentText() == framework
        supported = {s.type for s in specs_for(framework)}
        for spec in all_specs():
            item = w.toolbox.item_for(spec.type)
            assert item is not None, spec.type
            draggable = bool(item.flags() & Qt.ItemFlag.ItemIsDragEnabled)
            if spec.type == "window":
                assert not draggable
            elif spec.type in supported:
                assert draggable, spec.type
            else:
                assert not draggable, spec.type
                assert "not supported" in item.toolTip()
        assert w.canvas.window_id == w.doc.project.root_id
        assert w.host.tabs.count() == 2  # main window + "+"
    finally:
        dispose(w)


def test_every_palette_widget_can_be_added_through_the_drop_path(win):
    canvas = win.canvas
    added = 0
    for spec in all_specs():
        if spec.type == "window":
            assert canvas.add_widget("window") is None
            continue
        before = len(win.doc.project.nodes)
        win.switch_window(win.doc.project.root_id)
        nid = canvas.add_widget(spec.type)
        assert nid is not None, spec.type
        node = win.doc.get_node(nid)
        assert node.type == spec.type
        assert len(win.doc.project.nodes) == before + 1
        if spec.type == "toplevel":
            assert node.parent_id == win.doc.project.root_id
            assert canvas.window_id == nid  # the new dialog becomes the active window
        else:
            assert node.parent_id == canvas.window_id or node.parent_id == win.doc.project.root_id
        added += 1
    assert added == len(all_specs()) - 1
    win.doc.validate()
    # one undo step per add
    n = len(win.history.undo_stack)
    win.do_undo()
    assert len(win.history.undo_stack) == n - 1


def test_palette_search_and_double_click(win):
    win.toolbox.search.setText("slid")
    assert win.toolbox.visible_types() == ["slider"]
    win.toolbox.search.setText("")
    item = win.toolbox.item_for("button")
    win.toolbox.widgetActivated.emit("button")
    assert any(n.type == "button" for n in win.doc.project.nodes.values())
    assert item is not None


def test_palette_plugin_category_present(win):
    assert "Plugins" in win.toolbox._lists
    assert win.toolbox.item_for("chart") is not None


def test_unsupported_widgets_get_a_diagnostic_and_status_count(qapp, home, tmp_path):  # noqa: F811
    w = make_window(tmp_path, "kivy")
    try:
        assert get_spec("chart").supports("kivy") is False
        w.canvas.add_widget("chart")
        assert "1" in w.status.diag_btn.text()
        assert any("not supported" in d.message for d in w.doc.diagnostics())
    finally:
        dispose(w)


def test_dark_and_light_editor_themes(win):
    from py_vui.app.editor.editor_theme import current_palette

    win.set_editor_theme("light", persist=False)
    assert current_palette().name == "light"
    assert "#f3f4f8" in QApplication.instance().styleSheet()
    assert win.act["theme_light"].isChecked()
    win.set_editor_theme("dark", persist=False)
    assert current_palette().name == "dark"
    assert win.act["theme_dark"].isChecked()
    win.set_editor_theme("system", persist=False)
    assert current_palette().name in ("dark", "light")
    win.set_editor_theme("dark", persist=False)


def test_title_dirty_marker_and_undo_labels(win):
    assert not win.isWindowModified()
    win.canvas.add_widget("button")
    assert win.isWindowModified()
    assert win.act["undo"].isEnabled()
    assert "Add Button" in win.act["undo"].text()
    win.do_undo()
    assert "Add Button" in win.act["redo"].text()
    assert not win.act["undo"].isEnabled()
    win.do_redo()
    assert win.isWindowModified()
    assert win.act["undo"].isEnabled()


def test_save_and_open_round_trip(qapp, home, tmp_path, monkeypatch):  # noqa: F811
    w = make_window(tmp_path)
    try:
        w.canvas.add_widget("label")
        w.canvas.add_widget("button")
        dest = tmp_path / "projects"
        dest.mkdir()
        monkeypatch.setattr(w.prompts, "choose_dir", lambda *a, **k: dest)
        monkeypatch.setattr(w.prompts, "prompt_text", lambda *a, **k: "round trip")
        assert w.do_save()
        assert not w.isWindowModified()
        project_dir = w.service.project_dir
        assert project_dir is not None and project_dir.exists()
        assert w.recent.list()[0] == project_dir.resolve()
        names = sorted(n.name for n in w.doc.project.nodes.values())

        w.canvas.add_widget("entry")
        assert w.service.dirty
        monkeypatch.setattr(w.prompts, "ask_unsaved", lambda name: "discard")
        assert w.open_path(project_dir)
        assert sorted(n.name for n in w.doc.project.nodes.values()) == names
        assert not w.service.dirty
        assert w.canvas.doc is w.doc
        assert w.tree.item_for(next(iter(w.doc.project.nodes))) is not None
    finally:
        dispose(w)


def test_unsaved_prompt_cancels_new_project(qapp, home, tmp_path, monkeypatch):  # noqa: F811
    w = make_window(tmp_path)
    try:
        w.canvas.add_widget("label")
        monkeypatch.setattr(w.prompts, "ask_unsaved", lambda name: "cancel")
        assert w.maybe_save() is False
        monkeypatch.setattr(w.prompts, "ask_unsaved", lambda name: "discard")
        assert w.maybe_save() is True
    finally:
        dispose(w)


def test_autosave_and_recovery(qapp, home, tmp_path, monkeypatch):  # noqa: F811
    w = make_window(tmp_path, check_recovery=True)
    try:
        dest = tmp_path / "p"
        dest.mkdir()
        monkeypatch.setattr(w.prompts, "choose_dir", lambda *a, **k: dest)
        monkeypatch.setattr(w.prompts, "prompt_text", lambda *a, **k: "autosaved")
        assert w.do_save()
        w.canvas.add_widget("label")
        w.autosave_tick()
        assert w.service.recovery_path() is not None
        monkeypatch.setattr(w.prompts, "confirm", lambda *a, **k: True)
        assert w.offer_recovery() is True
        assert any(n.type == "label" for n in w.doc.project.nodes.values())
    finally:
        dispose(w)


def test_generate_and_run_spec_wiring_with_fake_process(qapp, home, tmp_path):  # noqa: F811
    FakeProcess.instances.clear()
    w = make_window(tmp_path, process_factory=FakeProcess)
    try:
        w.canvas.add_widget("button")
        w.controller._confirm = lambda missing: False  # never create a venv in tests
        w.do_run()
        assert len(FakeProcess.instances) == 1
        p = FakeProcess.instances[0]
        assert p.program and p.args == ["main.py"]
        assert p.cwd.endswith("app")
        assert w.controller.running
        assert w.act["stop"].isEnabled()
        p.emit_out("hello from the app\n")
        p.emit_err(
            'Traceback (most recent call last):\n  File "/x/app/handlers.py", '
            "line 7, in on_click\n    boom()\n"
        )
        text = w.console.text()
        assert "hello from the app" in text
        assert "handlers.py" in text
        p.finish(1)
        assert not w.controller.running
        assert "exited with code 1" in w.console.text()
        # restart launches a second process
        w.do_restart()
        assert len(FakeProcess.instances) == 2
        w.do_stop()
        assert not w.controller.running
    finally:
        dispose(w)


def test_console_error_line_opens_handler(win):
    seen = []
    win.code_panel.open_handler = seen.append  # type: ignore[method-assign]
    win.console.append('  File "/p/app/handlers.py", line 3, in on_go\n', "err")
    win.console._on_line('  File "/p/app/handlers.py", line 3, in on_go')
    assert seen == ["on_go"]


def test_live_preview_debounce(qapp, home, tmp_path):  # noqa: F811
    FakeProcess.instances.clear()
    w = make_window(tmp_path, process_factory=FakeProcess)
    try:
        w.controller._confirm = lambda m: False
        w.controller._timer.setInterval(10)
        w.act["live_preview"].setChecked(True)
        assert w.controller.live
        for _ in range(3):
            w.canvas.add_widget("label")
        import time

        deadline = time.time() + 2
        while time.time() < deadline and not FakeProcess.instances:
            QApplication.processEvents()
            time.sleep(0.01)
        assert len(FakeProcess.instances) >= 1
        n = len(FakeProcess.instances)
        # three quick edits produced one restart, not three
        assert n <= 2
    finally:
        w.act["live_preview"].setChecked(False)
        dispose(w)


def test_diagnostics_dialog_lists_issues(qapp, home, tmp_path):  # noqa: F811
    from py_vui.app.editor.statusbar import DiagnosticsDialog

    w = make_window(tmp_path, "kivy")
    try:
        nid = w.canvas.add_widget("map_view")
        dlg = DiagnosticsDialog(w.doc.diagnostics(), {nid: "Map"}, w)
        assert dlg.list.count() >= 1
        picked = []
        dlg.nodeActivated.connect(picked.append)
        dlg._activate(dlg.list.item(0))
        assert picked == [nid]
    finally:
        dispose(w)


def test_device_presets_resize_window(win):
    win.device_combo.setCurrentIndex(1)
    win.on_device_combo(1)
    root = win.doc.get_node(win.doc.project.root_id)
    assert (root.props["width"], root.props["height"]) == (390, 844)
    assert (root.box.w, root.box.h) == (390, 844)
    win.do_undo()
    assert root.props["width"] == 640


def test_framework_selector_preselects_choice_in_dialog(win, monkeypatch):
    from py_vui.app.editor import dialogs
    from py_vui.commands import SetProjectAttr

    class FakeDialog:
        def __init__(self, doc, history, parent=None):
            self.doc, self.history = doc, history
            self.framework = doc.project.framework

        def select(self, fw):
            self.framework = fw

        def exec(self):
            self.history.push(self.doc, SetProjectAttr("framework", self.framework))
            return 1

    monkeypatch.setattr(dialogs, "FrameworkDialog", FakeDialog)
    win.fw_combo.setCurrentText("kivy")
    win.on_framework_combo(0)
    assert win.doc.project.framework == "kivy"
    assert win.fw_combo.currentText() == "kivy"
    assert "kivy" in win.windowTitle()


def test_inspector_gets_asset_importer_and_project_dir(win, tmp_path):
    from PySide6.QtGui import QImage

    assert win.inspector.project_dir == win.service.work_dir
    src = tmp_path / "pic.png"
    QImage(8, 8, QImage.Format.Format_RGB32).save(str(src))
    rel = win.inspector.asset_importer(src)
    assert rel.startswith("assets/")


def test_text_undo_in_code_editor_is_not_stolen_by_app_shortcut(win):
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent, QKeySequence

    from py_vui.app.editor.code_editor import CodeEditor

    ed = CodeEditor()
    ed.show()
    ed.setPlainText("x = 1")
    ev = QKeyEvent(QEvent.Type.ShortcutOverride, Qt.Key.Key_Z,
                   Qt.KeyboardModifier.ControlModifier)
    ev.ignore()
    QApplication.sendEvent(ed, ev)
    assert ev.isAccepted()  # the editor keeps Ctrl+Z, so QAction undo does not fire
    assert QKeySequence("Ctrl+Z") in win.act["undo"].shortcuts()
    ed.deleteLater()


def test_missing_requirements_create_runtime_in_worker_then_run(qapp, home, tmp_path):  # noqa: F811
    from PySide6.QtCore import QObject, Signal

    class FakeWorker(QObject):
        progress = Signal(str)
        ready = Signal(str)
        failed = Signal(str)
        created: list = []

        def __init__(self, project_dir, requirements, parent=None):
            super().__init__(parent)
            self.requirements = requirements
            FakeWorker.created.append(self)

        def start(self):
            self.progress.emit("pip install ...")
            self.ready.emit("/fake/venv/bin/python")

        def wait(self, _ms=0):
            return True

    FakeProcess.instances.clear()
    FakeWorker.created.clear()
    w = make_window(tmp_path, process_factory=FakeProcess)
    try:
        w.canvas.add_widget("calendar")  # needs tkcalendar on tkinter
        asked = []
        w.controller._worker_factory = FakeWorker
        w.controller._confirm = lambda missing: asked.append(missing) or True
        w.do_run()
        spec = w.controller.last_spec
        if not spec.missing_requirements:  # tkcalendar happens to be installed here
            pytest.skip("requirement is installed in this environment")
        assert asked and FakeWorker.created
        assert "pip install" in w.console.text()
        assert FakeProcess.instances[-1].program == "/fake/venv/bin/python"
        assert w.controller.python == "/fake/venv/bin/python"
    finally:
        dispose(w)


def test_declined_runtime_runs_with_current_interpreter(qapp, home, tmp_path):  # noqa: F811
    FakeProcess.instances.clear()
    w = make_window(tmp_path, process_factory=FakeProcess)
    try:
        w.canvas.add_widget("calendar")
        w.controller._confirm = lambda missing: False
        w.do_run()
        assert len(FakeProcess.instances) == 1
    finally:
        dispose(w)


def test_build_executable_runs_pyinstaller_in_console(qapp, home, tmp_path, monkeypatch):  # noqa: F811
    FakeProcess.instances.clear()
    w = make_window(tmp_path, process_factory=FakeProcess)
    try:
        w.canvas.add_widget("button")
        monkeypatch.setattr(w.prompts, "choose", lambda *a, **k: "One file")
        w.do_build_exe()
        p = FakeProcess.instances[-1]
        assert "PyInstaller" in " ".join(p.args) and "--onefile" in p.args
        p.emit_out("building...\n")
        p.finish(0)
        assert "building..." in w.console.text()
        assert "Build finished" in w.console.text()
        assert w.console_dock.isVisible()
    finally:
        dispose(w)


def test_generation_failure_is_reported_in_console(qapp, home, tmp_path, monkeypatch):  # noqa: F811
    FakeProcess.instances.clear()
    w = make_window(tmp_path, process_factory=FakeProcess)
    try:
        monkeypatch.setattr(
            w.service, "generate", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("kaboom"))
        )
        w.do_run()
        assert "kaboom" in w.console.text()
        assert not FakeProcess.instances
    finally:
        dispose(w)


def test_geometry_and_theme_are_persisted(qapp, home, tmp_path):  # noqa: F811
    from PySide6.QtCore import QSettings

    w = make_window(tmp_path)
    try:
        w.set_editor_theme("light")
        w.settings.sync()
    finally:
        dispose(w)
    settings = QSettings(str(tmp_path / "editor.ini"), QSettings.Format.IniFormat)
    assert settings.value("geometry") is not None
    assert settings.value("windowState") is not None
    from py_vui.services import settings as svc_settings

    assert svc_settings.get("editor_theme") == "light"
    w2 = make_window(tmp_path, theme=None, restore_state=True)
    try:
        assert w2.current_theme_choice == "light"
        w2.set_editor_theme("dark", persist=False)
    finally:
        dispose(w2)


def test_preferences_apply_snap_and_grid(win):
    from py_vui.app.editor.dialogs.common import set_setting

    set_setting("grid_size", 16)
    set_setting("snap_enabled", False)
    win.load_preferences()
    assert win.canvas.grid_size == 16
    assert win.canvas.snap_to_grid is False
    assert not win.act["toggle_snap"].isChecked()


def test_view_toggles_drive_canvas_options_and_rulers(win):
    win.act["toggle_grid"].setChecked(False)
    assert win.canvas.show_grid is False
    win.act["toggle_guides"].setChecked(False)
    assert not win.canvas.smart_guides and not win.canvas.show_guides
    win.act["toggle_rulers"].setChecked(False)
    assert not win.host.top_ruler.isVisible()
    win.act["toggle_rulers"].setChecked(True)
    assert win.host.left_ruler.isVisible()


def test_shortcuts_are_unique_across_actions(win):
    seen: dict[str, str] = {}
    for key, act in win.act.items():
        for seq in act.shortcuts():
            text = seq.toString()
            assert text not in seen, f"{text} used by {key} and {seen[text]}"
            seen[text] = key
    assert "Ctrl+S" in seen and "Ctrl+Z" in seen and "F5" in seen


def test_json_drop_on_window_opens_project(win, tmp_path):
    from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl
    from PySide6.QtGui import QDropEvent

    from py_vui.services import ProjectService

    other = ProjectService()
    other.new_project("Dropped", "kivy", None)
    other.save_as(
        tmp_path / "elsewhere_parent"
        if (tmp_path / "elsewhere_parent").mkdir() is None
        else tmp_path,
        "Dropped",
    )
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(other.path))])
    ev = QDropEvent(
        QPointF(5, 5),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    win.dropEvent(ev)
    assert win.doc.project.meta.name == "Dropped"
    assert win.doc.project.framework == "kivy"
    assert win.fw_combo.currentText() == "kivy"


def test_project_dialogs_are_wired_to_the_document(win, monkeypatch):
    from py_vui.app.editor import dialogs

    opened: list[tuple] = []

    def fake(name):
        class Fake:
            def __init__(self, *args, **kw):
                opened.append((name, args))

            def exec(self):
                return 1

        return Fake

    for name in (
        "ThemeEditorDialog",
        "AssetManagerDialog",
        "MenuDesignerDialog",
        "PluginManagerDialog",
        "ExportDialog",
        "RequirementsDialog",
        "PreferencesDialog",
        "ShortcutsDialog",
        "AboutDialog",
    ):
        monkeypatch.setattr(dialogs, name, fake(name))
    for key in (
        "theme",
        "assets",
        "menus",
        "plugins",
        "export",
        "requirements",
        "preferences",
        "shortcuts",
        "about",
    ):
        win.act[key].trigger()
    names = [n for n, _ in opened]
    assert names == [
        "ThemeEditorDialog",
        "AssetManagerDialog",
        "MenuDesignerDialog",
        "PluginManagerDialog",
        "ExportDialog",
        "RequirementsDialog",
        "PreferencesDialog",
        "ShortcutsDialog",
        "AboutDialog",
    ]
    by_name = dict(opened)
    assert by_name["ThemeEditorDialog"][0] is win.doc
    assert by_name["ThemeEditorDialog"][1] is win.history
    assert by_name["AssetManagerDialog"][0] is win.service
    assert by_name["MenuDesignerDialog"][2] == win.doc.project.root_id


def test_new_project_dialog_creates_project(win, monkeypatch):
    from py_vui.app.editor import dialogs

    class FakeNew:
        name = "Fresh"
        framework = "pyside6"
        template_id = None

        def __init__(self, parent=None):
            pass

        def exec(self):
            return 1

        def set_template(self, _t):
            return True

    monkeypatch.setattr(dialogs, "NewProjectDialog", FakeNew)
    win.canvas.add_widget("label")
    monkeypatch.setattr(win.prompts, "ask_unsaved", lambda name: "discard")
    win.act["new"].trigger()
    assert win.doc.project.meta.name == "Fresh"
    assert win.doc.project.framework == "pyside6"
    assert len(win.doc.project.nodes) == 1
    assert not win.history.undo_stack
    assert win.canvas.doc is win.doc and win.tree.doc is win.doc
    assert "Fresh" in win.windowTitle()


def test_template_gallery_flow(win, monkeypatch):
    from py_vui.app.editor import dialogs
    from py_vui.services import list_templates, load_template

    rich = sorted(
        t.id for t in list_templates() if len(load_template(t.id, "tkinter").nodes) > 1
    )
    if not rich:
        pytest.skip("no non-blank templates installed")
    tid = rich[0]
    expected = len(load_template(tid, "tkinter").nodes)

    class FakeGallery:
        template_id = tid

        def __init__(self, parent=None):
            pass

        def exec(self):
            return 1

    class FakeNew:
        name = "From template"
        framework = "tkinter"
        template_id = tid

        def __init__(self, parent=None):
            pass

        def set_template(self, t):
            assert t == tid
            return True

        def exec(self):
            return 1

    monkeypatch.setattr(dialogs, "TemplateGalleryDialog", FakeGallery)
    monkeypatch.setattr(dialogs, "NewProjectDialog", FakeNew)
    win.act["new_template"].trigger()
    assert win.doc.project.meta.name == "From template"
    assert len(win.doc.project.nodes) == expected
    win.doc.validate()
    assert len(win.canvas.scene_.items_by_id) >= 1


def test_qt_main_starts_and_runs_event_loop(qapp, home, tmp_path, monkeypatch):  # noqa: F811
    from py_vui.app import qt_main
    from py_vui.app.editor import main_window

    shown = []
    real = main_window.MainWindow

    class Probe(real):
        def show(self):
            shown.append(self)
            super().show()

    monkeypatch.setattr(main_window, "MainWindow", Probe)
    monkeypatch.setattr(QApplication, "exec", lambda self=None: 0)
    assert qt_main.main(["py_vui"]) == 0
    assert len(shown) == 1
    dispose(shown[0])
