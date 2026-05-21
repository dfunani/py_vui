from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QDialog,
    QDockWidget,
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QSplitter,
    QStatusBar,
    QToolBar,
)

from py_vui.app.editor.canvas import DesignCanvas
from py_vui.app.editor.inspector import PropertyInspector
from py_vui.app.editor.palette import WidgetPalette
from py_vui.app.editor.project_service import ProjectService
from py_vui.app.editor.recent_projects import load_recent, remember
from py_vui.app.editor.save_project_dialog import SaveProjectDialog
from py_vui.app.editor.session_paths import SESSION_DOCUMENT, sanitize_project_slug
from py_vui.commands import History
from py_vui.model.document import ProjectDocument
from py_vui.preview import run_preview


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("py_vui")
        self.resize(1280, 800)

        self._service = ProjectService.new()
        self._doc = self._service.doc
        self._history = History()

        self._canvas = DesignCanvas()
        self._palette = WidgetPalette()
        self._inspector = PropertyInspector()
        self._output = QPlainTextEdit()
        self._output.setReadOnly(True)
        self._output.setMaximumBlockCount(500)

        self._canvas.bind(self._doc, self._history)
        self._inspector.bind(self._doc, self._history)

        splitter = QSplitter()
        splitter.addWidget(self._palette)
        splitter.addWidget(self._canvas)
        splitter.addWidget(self._inspector)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        self.setCentralWidget(splitter)

        from PySide6.QtCore import Qt

        out_dock = QDockWidget("Output", self)
        out_dock.setWidget(self._output)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, out_dock)

        self.setStatusBar(QStatusBar(self))
        self._build_menus()
        self._build_toolbar()
        self._connect_signals()
        self._inspector.show_node(self._doc.project.root_id)
        self._update_title()
        self.statusBar().showMessage(
            "Save: picks a folder (e.g. Documents/untitled/) with py_vui.json + session.meta.json",
            15000,
        )

    def _build_menus(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        edit_menu = self.menuBar().addMenu("&Edit")
        build_menu = self.menuBar().addMenu("&Build")

        self._act_new = QAction("&New", self)
        self._act_new.setShortcut(QKeySequence.StandardKey.New)
        self._act_new.triggered.connect(self._new_project)
        file_menu.addAction(self._act_new)

        self._act_open = QAction("&Open Project Folder…", self)
        self._act_open.setShortcut(QKeySequence.StandardKey.Open)
        self._act_open.setStatusTip("Open a saved project folder containing py_vui.json")
        self._act_open.triggered.connect(self._open_project_folder)

        self._act_open_file = QAction("Open &py_vui.json…", self)
        self._act_open_file.triggered.connect(self._open_project_file)
        file_menu.addAction(self._act_open)
        file_menu.addAction(self._act_open_file)

        self._recent_menu = file_menu.addMenu("Open &Recent")
        self._refresh_recent_menu()

        self._act_save = QAction("&Save Project", self)
        self._act_save.setShortcut(QKeySequence.StandardKey.Save)
        self._act_save.triggered.connect(self._save_project)
        file_menu.addAction(self._act_save)

        self._act_save_as = QAction("Save Project &As…", self)
        self._act_save_as.setStatusTip(
            "Pick a new project name and folder location (creates e.g. my-app/)"
        )
        self._act_save_as.triggered.connect(self._save_project_as)
        file_menu.addAction(self._act_save_as)

        self._act_save_copy = QAction("Save As New &Name…", self)
        self._act_save_copy.setStatusTip(
            "Copy session to a new project name and folder (keeps original untouched)"
        )
        self._act_save_copy.triggered.connect(self._save_project_as_new_name)
        file_menu.addAction(self._act_save_copy)

        file_menu.addSeparator()
        quit_act = QAction("&Quit", self)
        quit_act.setShortcut(QKeySequence.StandardKey.Quit)
        quit_act.triggered.connect(self.close)
        file_menu.addAction(quit_act)

        self._act_undo = QAction("&Undo", self)
        self._act_undo.setShortcut(QKeySequence.StandardKey.Undo)
        self._act_undo.triggered.connect(self._undo)
        edit_menu.addAction(self._act_undo)

        self._act_redo = QAction("&Redo", self)
        self._act_redo.setShortcut(QKeySequence.StandardKey.Redo)
        self._act_redo.triggered.connect(self._redo)
        edit_menu.addAction(self._act_redo)

        self._act_export = QAction("&Export Code…", self)
        self._act_export.setShortcut("Ctrl+E")
        self._act_export.setStatusTip("Choose a folder and save generated Python files")
        self._act_export.triggered.connect(self._export_code)
        build_menu.addAction(self._act_export)

        self._act_generate = QAction("Generate Code (project folder)", self)
        self._act_generate.setStatusTip(
            "Write runnable app into <project>/app/ (save project first)"
        )
        self._act_generate.triggered.connect(self._generate)
        build_menu.addAction(self._act_generate)

        self._act_preview = QAction("&Preview", self)
        self._act_preview.setShortcut("F5")
        self._act_preview.triggered.connect(self._preview)
        build_menu.addAction(self._act_preview)

    def _build_toolbar(self) -> None:
        bar = QToolBar("Main", self)
        bar.setMovable(False)
        self.addToolBar(bar)
        for action in (
            self._act_new,
            self._act_open,
            self._act_save,
            self._act_export,
            self._act_preview,
        ):
            bar.addAction(action)

    def _refresh_recent_menu(self) -> None:
        self._recent_menu.clear()
        recent = load_recent()
        if not recent:
            empty = self._recent_menu.addAction("(no recent projects)")
            empty.setEnabled(False)
            return
        for path in recent:
            folder = path.parent if path.name == SESSION_DOCUMENT else path
            act = self._recent_menu.addAction(folder.name)
            act.setToolTip(str(folder))
            act.triggered.connect(
                lambda _checked=False, p=folder: self._open_project_path(p)
            )

    def _connect_signals(self) -> None:
        self._canvas.selection_changed.connect(self._on_selection)
        self._canvas.layout_changed.connect(self._on_layout_changed)
        self._canvas.document_dirty.connect(self._on_document_dirty)
        self._inspector.document_changed.connect(self._on_layout_changed)
        self._inspector.document_dirty.connect(self._on_document_dirty)

    def _on_selection(self, node_id: str) -> None:
        self._inspector.show_node(node_id or None)

    def _on_document_dirty(self) -> None:
        self._service.mark_dirty()
        self._update_title()

    def _on_layout_changed(self) -> None:
        self._service.mark_dirty()
        node_id = self._canvas.selected_node_id()
        self._canvas.rebuild()
        if node_id and node_id in self._doc.project.nodes:
            self._canvas.select_node(node_id)
            self._inspector.show_node(node_id)
        self._update_title()

    def _update_title(self) -> None:
        name = self._doc.project.meta.name
        star = "*" if self._service.dirty else ""
        if self._service.project_dir is not None:
            loc = self._service.project_dir.name
        else:
            loc = f"unsaved ({sanitize_project_slug(name)})"
        self.setWindowTitle(f"{name}{star} — {loc} — py_vui")

    def _new_project(self) -> None:
        if not self._confirm_discard():
            return
        self._service = ProjectService.new()
        self._doc = self._service.doc
        self._history = History()
        self._canvas.bind(self._doc, self._history)
        self._inspector.bind(self._doc, self._history)
        self._canvas.rebuild()
        self._inspector.show_node(self._doc.project.root_id)
        self._update_title()

    def _default_parent_dir(self) -> str:
        if self._service.project_dir is not None:
            return str(self._service.project_dir.parent)
        recent = load_recent()
        if recent:
            return str(recent[0].parent.parent if recent[0].name == SESSION_DOCUMENT else recent[0].parent)
        return str(Path.home() / "Documents")

    def _open_project_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            "Open project folder",
            self._default_parent_dir(),
        )
        if not folder:
            return
        self._open_project_path(Path(folder))

    def _open_project_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open py_vui.json",
            self._default_parent_dir(),
            "py_vui document (py_vui.json)",
        )
        if not path:
            return
        self._open_project_path(Path(path))

    def _open_project_path(self, location: Path) -> None:
        if not self._confirm_discard():
            return
        try:
            self._service = ProjectService.open(location)
            self._doc = self._service.doc
            self._history = History()
            self._canvas.bind(self._doc, self._history)
            self._inspector.bind(self._doc, self._history)
            self._canvas.rebuild()
            self._canvas.select_node(self._doc.project.root_id)
            session_file = self._service.path or location
            remember(session_file)
            self._refresh_recent_menu()
            self._update_title()
            folder = self._service.project_dir
            self.statusBar().showMessage(f"Loaded project: {folder}", 5000)
            self._output.appendPlainText(f"Opened project folder: {folder}")
        except Exception as exc:
            QMessageBox.critical(self, "Open failed", str(exc))

    def _save_project(self) -> None:
        if self._service.path is None:
            self._save_project_as()
            return
        try:
            saved = self._service.save()
            remember(saved)
            self._refresh_recent_menu()
            self._update_title()
            folder = self._service.project_dir
            self.statusBar().showMessage(f"Saved project: {folder}", 3000)
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", str(exc))

    def _prompt_save_as(self, *, title: str) -> SaveProjectDialog | None:
        dialog = SaveProjectDialog(
            self,
            default_name=self._service.project_name(),
            default_parent=self._default_parent_dir(),
        )
        dialog.setWindowTitle(title)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        if not dialog.project_name():
            QMessageBox.warning(self, "Invalid name", "Project name cannot be empty.")
            return None
        return dialog

    def _finalize_save(self, saved: Path, *, new_name: bool) -> None:
        folder = self._service.project_dir
        remember(saved)
        self._refresh_recent_menu()
        self._update_title()
        self.statusBar().showMessage(f"Saved project: {folder}", 5000)
        self._output.appendPlainText(
            f"Saved project folder: {folder}\n"
            f"  {SESSION_DOCUMENT}\n"
            f"  session.meta.json"
        )
        suffix = " (new copy)" if new_name else ""
        QMessageBox.information(
            self,
            "Project saved",
            f"Session saved{suffix} to:\n{folder}\n\n"
            f"Project name: {self._service.project_name()}\n\n"
            f"Generated app: {folder}/app/",
        )

    def _save_project_as(self) -> None:
        dialog = self._prompt_save_as(title="Save Project As")
        if dialog is None:
            return
        try:
            saved = self._service.save_to_new_folder(
                dialog.parent_dir(),
                project_name=dialog.project_name(),
            )
            self._finalize_save(saved, new_name=False)
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", str(exc))

    def _save_project_as_new_name(self) -> None:
        """Save a copy under a new name; clears project_dir so folder slug uses new name."""
        dialog = self._prompt_save_as(title="Save As New Name")
        if dialog is None:
            return
        old_dir = self._service.project_dir
        try:
            self._service.project_dir = None
            self._service.dirty = True
            saved = self._service.save_to_new_folder(
                dialog.parent_dir(),
                project_name=dialog.project_name(),
            )
            self._finalize_save(saved, new_name=True)
            if old_dir:
                self._output.appendPlainText(f"Original project unchanged: {old_dir}")
        except Exception as exc:
            self._service.project_dir = old_dir
            QMessageBox.critical(self, "Save failed", str(exc))

    def _export_code(self) -> None:
        try:
            default_parent = (
                str(self._service.project_dir.parent)
                if self._service.project_dir
                else self._default_parent_dir()
            )
            chosen = QFileDialog.getExistingDirectory(
                self,
                "Choose parent folder for export (creates <project-name>/ inside)",
                default_parent,
            )
            if not chosen:
                return
            export_path, written = self._service.export_code_to_parent(Path(chosen))
            lines = "\n".join(f"  {p}" for p in written)
            self._output.appendPlainText(f"Exported to {export_path}:\n{lines}")
            self.statusBar().showMessage(
                f"Exported to {export_path} ({len(written)} files)",
                5000,
            )
            QMessageBox.information(
                self,
                "Export complete",
                f"Wrote a runnable app to:\n{export_path}\n\n"
                f"(inside the folder you chose, named after project "
                f"\"{self._service.project_name()}\")\n\n"
                "Setup and run:\n"
                f"  cd {export_path}\n"
                "  pip install -r requirements.txt\n"
                "  python main.py",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Export failed", str(exc))

    def _generate(self) -> None:
        try:
            if self._service.project_dir is None:
                answer = QMessageBox.question(
                    self,
                    "Save project first?",
                    "Generate writes into <project>/app/. Save the project now?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if answer == QMessageBox.StandardButton.Yes:
                    self._save_project_as()
                    if self._service.project_dir is None:
                        return
                else:
                    raise ValueError("save the project before generating")
            else:
                self._service.save()
            written = self._service.write_generated()
            app_dir = self._service.app_dir()
            self._output.appendPlainText(
                f"Generated in {app_dir}:\n" + "\n".join(f"  {p}" for p in written)
            )
            self.statusBar().showMessage(f"Generated app in {app_dir}", 3000)
        except Exception as exc:
            QMessageBox.critical(self, "Generate failed", str(exc))

    def _preview(self) -> None:
        try:
            if self._service.project_dir is None:
                QMessageBox.information(
                    self,
                    "Save project first",
                    "Save your session to a project folder before preview.",
                )
                return
            self._service.save()
            written = self._service.write_generated()
            app_dir = self._service.app_dir()
            entry = app_dir / "main.py"
            if not entry.is_file() and written:
                entry = written[0].parent / "main.py"
            self._output.appendPlainText(f"Preview: {entry}")
            result = run_preview(app_dir, entry)
            self._output.appendPlainText(result.stdout)
            if result.stderr:
                self._output.appendPlainText(result.stderr)
            if result.returncode != 0:
                QMessageBox.warning(
                    self,
                    "Preview exited with errors",
                    result.stderr or f"exit code {result.returncode}",
                )
        except Exception as exc:
            QMessageBox.critical(self, "Preview failed", str(exc))

    def _undo(self) -> None:
        self._history.undo(self._doc)
        self._service.mark_dirty()
        self._canvas.rebuild()
        self._update_title()

    def _redo(self) -> None:
        self._history.redo(self._doc)
        self._service.mark_dirty()
        self._canvas.rebuild()
        self._update_title()

    def _confirm_discard(self) -> bool:
        if not self._service.dirty:
            return True
        answer = QMessageBox.question(
            self,
            "Unsaved changes",
            "Discard unsaved changes?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def closeEvent(self, event) -> None:
        if self._confirm_discard():
            event.accept()
        else:
            event.ignore()
