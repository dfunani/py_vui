"""py_vui main window: toolbox | design canvas | inspector, code + console docks."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import QByteArray, QProcess, QSettings, Qt, QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QLabel,
    QMainWindow,
    QWidget,
)

from py_vui.app.editor import editor_theme
from py_vui.app.editor.actions import build_actions
from py_vui.app.editor.build_actions import BuildMixin
from py_vui.app.editor.canvas_host import CanvasHost
from py_vui.app.editor.console_panel import ConsolePanel
from py_vui.app.editor.context_menu import build_context_menu
from py_vui.app.editor.edit_actions import EditMixin
from py_vui.app.editor.edit_ops import top_level_ids
from py_vui.app.editor.menus import build_menus, build_toolbars, fill_docks_menu
from py_vui.app.editor.palette import Palette
from py_vui.app.editor.preview_dock import RunController
from py_vui.app.editor.project_actions import ProjectMixin
from py_vui.app.editor.prompts import Prompts
from py_vui.app.editor.statusbar import DiagnosticsDialog, EditorStatusBar
from py_vui.app.editor.view_actions import ViewMixin
from py_vui.app.editor.widget_tree import WidgetTree
from py_vui.commands import History
from py_vui.core.document import ProjectDocument
from py_vui.services import ProjectService, RecentProjects

ORG, APP = "py_vui", "editor"


class _Placeholder(QWidget):
    """Stand-in when an optional panel (inspector / code editor) is unavailable."""

    from PySide6.QtCore import Signal as _Signal

    changed = _Signal()
    handler_requested = _Signal(str)

    def __init__(self, text: str) -> None:
        super().__init__()
        from PySide6.QtWidgets import QVBoxLayout

        lay = QVBoxLayout(self)
        label = QLabel(text)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(label)

    def bind(self, *_a: Any) -> None: ...
    def set_selection(self, _ids: list[str]) -> None: ...
    def refresh(self) -> None: ...
    def open_handler(self, _name: str) -> None: ...


def _make_panel(path: str, name: str, label: str) -> QWidget:
    try:
        module = __import__(path, fromlist=[name])
        return getattr(module, name)()
    except Exception as exc:  # pragma: no cover - only when a panel module is broken
        return _Placeholder(f"{label} unavailable: {exc}")


class MainWindow(ProjectMixin, EditMixin, BuildMixin, ViewMixin, QMainWindow):
    def __init__(
        self,
        service: ProjectService | None = None,
        settings: QSettings | None = None,
        *,
        check_recovery: bool = True,
        process_factory: Callable[[], Any] = QProcess,
        restore_state: bool = True,
        theme: str | None = None,
    ) -> None:
        super().__init__()
        self.setObjectName("py_vui_main")
        self.setAcceptDrops(True)
        self.settings = settings or QSettings(ORG, APP)
        self.service = service or ProjectService()
        self.prompts = Prompts(self)
        self.recent = RecentProjects()
        self.check_recovery = check_recovery
        self.current_theme_choice = "dark"
        self._window_sig: tuple | None = None
        self._syncing = False

        # ---- central: canvas host
        self.host = CanvasHost()
        self.canvas = self.host.canvas
        self.setCentralWidget(self.host)

        # ---- panels
        self.toolbox = Palette()
        self.tree = WidgetTree()
        self.inspector = _make_panel("py_vui.app.editor.inspector", "InspectorPanel", "Inspector")
        self.code_panel = _make_panel("py_vui.app.editor.code_panel", "CodePanel", "Code editor")
        self.console = ConsolePanel()
        self.status = EditorStatusBar()
        self.setStatusBar(self.status)

        self.toolbox_dock = self._dock(
            "Toolbox", self.toolbox, Qt.DockWidgetArea.LeftDockWidgetArea
        )
        self.tree_dock = self._dock("Widgets", self.tree, Qt.DockWidgetArea.LeftDockWidgetArea)
        self.inspector_dock = self._dock(
            "Inspector", self.inspector, Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.code_dock = self._dock("Code", self.code_panel, Qt.DockWidgetArea.BottomDockWidgetArea)
        self.console_dock = self._dock(
            "Console", self.console, Qt.DockWidgetArea.BottomDockWidgetArea
        )
        self.tabifyDockWidget(self.toolbox_dock, self.tree_dock)
        self.tabifyDockWidget(self.code_dock, self.console_dock)
        self.toolbox_dock.raise_()
        self.code_dock.raise_()
        self.resizeDocks([self.toolbox_dock], [250], Qt.Orientation.Horizontal)
        self.resizeDocks([self.inspector_dock], [330], Qt.Orientation.Horizontal)
        self.resizeDocks([self.code_dock], [230], Qt.Orientation.Vertical)

        # ---- actions, menus, toolbars
        self.act = build_actions(self)
        build_menus(self)
        build_toolbars(self)
        fill_docks_menu(
            self,
            self.docks_menu,
            [
                self.toolbox_dock,
                self.tree_dock,
                self.inspector_dock,
                self.code_dock,
                self.console_dock,
            ],
        )

        # ---- run controller
        self.controller = RunController(
            lambda: self.service, self, process_factory, self._confirm_runtime
        )
        self.controller.output.connect(self.console.append)
        self.controller.message.connect(self.flash)
        self.controller.runningChanged.connect(self._on_running)

        self._connect()
        self.autosave_timer = QTimer(self)
        self.autosave_timer.timeout.connect(self.autosave_tick)

        # ---- preferences / theme
        self.load_preferences()
        if theme:  # an explicit theme (tests, --theme) wins over the stored preference
            self.set_editor_theme(theme, persist=False)
        self.bind_document()
        if restore_state:
            self._restore_geometry()
        else:
            self.resize(1440, 900)

    # ------------------------------------------------------------------ properties
    @property
    def doc(self) -> ProjectDocument:
        return self.service.doc

    @property
    def history(self) -> History:
        return self.service.history

    # ------------------------------------------------------------------- building
    def _dock(self, title: str, widget: QWidget, area: Qt.DockWidgetArea) -> QDockWidget:
        dock = QDockWidget(title, self)
        dock.setObjectName("dock_" + title.lower())
        dock.setWidget(widget)
        dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        self.addDockWidget(area, dock)
        return dock

    def _connect(self) -> None:
        c = self.canvas
        c.selectionChanged.connect(lambda ids: self.select(ids, source="canvas"))
        c.zoomChanged.connect(self.on_zoom_changed)
        c.cursorMoved.connect(self.status.set_cursor)
        c.documentEdited.connect(lambda: self.after_edit("canvas"))
        c.contextMenuRequested.connect(self.show_context_menu)
        c.filesDropped.connect(self.on_files_dropped)
        c.windowRequested.connect(self.switch_window)
        c.message.connect(self.flash)
        c.sizeChanged.connect(lambda w, h: self.flash(f"Window size {w} × {h}"))
        self.host.windowSwitched.connect(self.switch_window)
        self.host.addDialogRequested.connect(self.do_add_dialog)
        self.host.closeWindowRequested.connect(self.close_window)

        t = self.tree
        t.selectionChanged.connect(lambda ids: self.select(ids, source="tree"))
        t.contextMenuRequested.connect(self.show_context_menu)
        t.windowActivated.connect(self.switch_window)
        t.documentEdited.connect(lambda: self.after_edit("tree"))
        t.message.connect(self.flash)
        t.widgetDropRequested.connect(self.on_tree_widget_drop)

        self.toolbox.widgetActivated.connect(self.insert_widget)
        self.inspector.changed.connect(lambda: self.after_edit("inspector"))
        self.inspector.handler_requested.connect(self.open_handler)
        self.code_panel.changed.connect(lambda: self.after_edit("code"))
        self.console.handlerRequested.connect(lambda name, _line: self.open_handler(name))
        self.console.stopRequested.connect(self.do_stop)
        self.console.restartRequested.connect(self.do_restart)
        self.status.diagnosticsClicked.connect(self.show_diagnostics)

    def _confirm_runtime(self, missing: list[str]) -> bool:
        return self.prompts.confirm(
            "Missing packages",
            "The preview needs packages that are not installed:\n  "
            + "\n  ".join(missing)
            + "\n\nCreate a private runtime environment for this project and install them "
            "(uses pip / network)?",
            yes="Create environment",
        )

    # ----------------------------------------------------------------- doc binding
    def bind_document(self) -> None:
        """(Re)bind every panel after new / open / recover."""
        doc, hist = self.doc, self.history
        self.canvas.set_base_dir(self.service.work_dir)
        self.canvas.bind(doc, hist)
        self.tree.bind(doc, hist)
        self.inspector.bind(doc, hist)
        self._wire_inspector_assets()
        self.code_panel.bind(doc, hist, self.service)
        self.toolbox.set_framework(doc.project.framework)
        self._window_sig = None
        self.sync_all()
        self.select([doc.project.root_id], source="main")
        self.canvas.fit()
        self.restart_autosave()

    def _wire_inspector_assets(self) -> None:
        """Image / file pickers copy into assets/ and previews resolve against the project."""
        self.inspector.asset_importer = lambda p: self.service.add_asset(p)
        self.inspector.project_dir = self.service.work_dir

    # ----------------------------------------------------------------- selection
    def select(self, ids: list[str], source: str = "main") -> None:
        """Single entry point for selection changes; keeps all panels in step."""
        doc = self.doc
        ids = [i for i in ids if i in doc.project.nodes]
        if ids:
            win = doc.window_of(ids[-1]).id
            if win != self.canvas.window_id:
                self.switch_window(win, select=False)
        if source != "canvas":
            self.canvas.set_selection(ids, emit=False)
        if source != "tree":
            self.tree.set_selection(ids)
        self.inspector.set_selection(ids)
        self._update_selection_ui()

    def switch_window(self, window_id: str, select: bool = True) -> None:
        if window_id not in self.doc.project.nodes:
            return
        self.canvas.set_window(window_id)
        self.host.select_tab(window_id)
        self.sync_device_combo()
        if select:
            self.select([window_id], source="main")

    def close_window(self, window_id: str) -> None:
        from py_vui.commands import RemoveSubtree

        node = self.doc.project.nodes.get(window_id)
        if node is None or node.type != "toplevel":
            return
        if not self.prompts.confirm(
            "Remove dialog", f"Remove “{node.name}” and everything in it?", yes="Remove"
        ):
            return
        self.switch_window(self.doc.project.root_id)
        self.push(
            RemoveSubtree(window_id, label=f"Remove {node.name}"), select=[self.doc.project.root_id]
        )

    def insert_widget(self, type_id: str) -> None:
        """Palette double-click: insert into the current container."""
        self.canvas.add_widget(type_id)
        self.canvas.setFocus()

    def on_tree_widget_drop(self, type_id: str, container_id: str, index: int | None) -> None:
        """A palette widget was dropped on the tree."""
        win = self.doc.window_of(container_id).id
        if win != self.canvas.window_id:
            self.switch_window(win, select=False)
        self.canvas.add_widget(type_id, container_id=container_id, index=index)

    def show_context_menu(self, node_id: str | None, global_pos) -> None:
        menu = build_context_menu(self, node_id)
        menu.exec(global_pos)

    # -------------------------------------------------------------------- syncing
    def after_edit(self, source: str | None = None) -> None:
        """Call after *any* document change. ``source`` panel is not asked to refresh itself."""
        self.canvas.refresh()
        self.sync_all(source)
        self.controller.schedule()

    def sync_all(self, source: str | None = None) -> None:
        if self._syncing:
            return
        self._syncing = True
        try:
            doc = self.doc
            sig = (
                tuple((w.id, str(w.props.get("title") or w.name)) for w in doc.windows()),
                self.canvas.window_id,
            )
            if sig != self._window_sig:
                self._window_sig = sig
                self.host.rebuild_tabs(doc, self.canvas.window_id)
            self.tree.refresh()
            self.tree.set_selection(self.canvas.selection)
            if source != "inspector":
                self.inspector.refresh()
            if source != "code":
                self.code_panel.refresh()
            self.toolbox.set_framework(doc.project.framework)
            self.fw_combo.setCurrentText(doc.project.framework)
            self.status.set_framework(doc.project.framework)
            self.status.set_diagnostics(len(doc.diagnostics()))
            self.sync_device_combo()
            self._update_selection_ui()
            self.update_chrome()
        finally:
            self._syncing = False

    def update_chrome(self) -> None:
        proj = self.doc.project
        self.setWindowTitle(f"{proj.meta.name}[*] — {proj.framework} — py_vui")
        self.setWindowModified(self.service.dirty)
        h = self.history
        self.act["undo"].setText(f"&Undo {h.undo_label}" if h.undo_label else "&Undo")
        self.act["undo"].setEnabled(bool(h.undo_stack))
        self.act["redo"].setText(f"&Redo {h.redo_label}" if h.redo_label else "&Redo")
        self.act["redo"].setEnabled(bool(h.redo_stack))
        self.act["save"].setEnabled(True)

    def _update_selection_ui(self) -> None:
        doc = self.doc
        sel = [i for i in self.canvas.selection if i in doc.project.nodes]
        tops = top_level_ids(doc, sel)
        counts = {
            "sel": len(tops) >= 1,
            "one": len(sel) == 1,
            "two": len(tops) >= 2,
            "three": len(tops) >= 3,
        }
        for act in self.act.values():
            need = act.property("needs")
            if need:
                act.setEnabled(bool(counts.get(str(need), True)))
        if len(sel) == 1:
            n = doc.get_node(sel[0])
            self.status.set_selection(f"{n.name}: {n.box.w:.0f} × {n.box.h:.0f}")
        elif sel:
            self.status.set_selection(f"{len(sel)} selected")
        else:
            self.status.set_selection("")

    def show_diagnostics(self) -> None:
        doc = self.doc
        names = {n.id: n.name for n in doc.project.nodes.values()}
        dlg = DiagnosticsDialog(doc.diagnostics(), names, self)
        dlg.nodeActivated.connect(lambda nid: (self.select([nid]), dlg.close()))
        dlg.exec()

    def flash(self, text: str, ms: int = 5000) -> None:
        self.status.showMessage(text, ms)

    def _on_running(self, running: bool) -> None:
        self.console.set_running(running)
        self.act["stop"].setEnabled(running)

    # --------------------------------------------------------------- drag and drop
    def dragEnterEvent(self, ev) -> None:
        md = ev.mimeData()
        if md.hasUrls() and any(u.toLocalFile().lower().endswith(".json") for u in md.urls()):
            ev.acceptProposedAction()

    def dropEvent(self, ev) -> None:
        for u in ev.mimeData().urls():
            if u.toLocalFile().lower().endswith(".json"):
                self.open_path(Path(u.toLocalFile()))
                ev.acceptProposedAction()
                return

    # ------------------------------------------------------------- window lifecycle
    def _restore_geometry(self) -> None:
        geo = self.settings.value("geometry")
        state = self.settings.value("windowState")
        if isinstance(geo, QByteArray) and not geo.isEmpty():
            self.restoreGeometry(geo)
        else:
            self.resize(1440, 900)
        if isinstance(state, QByteArray) and not state.isEmpty():
            self.restoreState(state)

    def closeEvent(self, ev: QCloseEvent) -> None:
        if not self.maybe_save():
            ev.ignore()
            return
        self.controller.shutdown()
        self.autosave_timer.stop()
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
        self.settings.setValue("editor_theme_choice", self.current_theme_choice)
        ev.accept()


def create_main_window(argv_project: str | None = None, **kwargs: Any) -> MainWindow:
    """Factory used by ``qt_main`` and tests."""
    app = QApplication.instance()
    assert app is not None, "create a QApplication first"
    win = MainWindow(**kwargs)
    if argv_project:
        win.open_path(Path(argv_project), checked=True)
    return win


__all__ = ["MainWindow", "create_main_window", "editor_theme"]
