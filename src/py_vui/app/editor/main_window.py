from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QDockWidget,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QSplitter,
    QStatusBar,
)

from py_vui.app.editor.canvas import DesignCanvas
from py_vui.app.editor.inspector import PropertyInspector
from py_vui.app.editor.palette import WidgetPalette
from py_vui.app.editor.project_service import ProjectService
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
        self._connect_signals()
        self._inspector.show_node(self._doc.project.root_id)
        self._update_title()

    def _build_menus(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        edit_menu = self.menuBar().addMenu("&Edit")
        build_menu = self.menuBar().addMenu("&Build")

        self._act_new = QAction("&New", self)
        self._act_new.setShortcut(QKeySequence.StandardKey.New)
        self._act_new.triggered.connect(self._new_project)
        file_menu.addAction(self._act_new)

        self._act_open = QAction("&Open…", self)
        self._act_open.setShortcut(QKeySequence.StandardKey.Open)
        self._act_open.triggered.connect(self._open_project)
        file_menu.addAction(self._act_open)

        self._act_save = QAction("&Save", self)
        self._act_save.setShortcut(QKeySequence.StandardKey.Save)
        self._act_save.triggered.connect(self._save_project)
        file_menu.addAction(self._act_save)

        self._act_save_as = QAction("Save &As…", self)
        self._act_save_as.triggered.connect(self._save_project_as)
        file_menu.addAction(self._act_save_as)

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

        self._act_generate = QAction("&Generate Code", self)
        self._act_generate.triggered.connect(self._generate)
        build_menu.addAction(self._act_generate)

        self._act_preview = QAction("&Preview", self)
        self._act_preview.setShortcut("F5")
        self._act_preview.triggered.connect(self._preview)
        build_menu.addAction(self._act_preview)

    def _connect_signals(self) -> None:
        self._canvas.selection_changed.connect(self._on_selection)
        self._canvas.layout_changed.connect(self._on_document_changed)
        self._inspector.document_changed.connect(self._on_document_changed)

    def _on_selection(self, node_id: str) -> None:
        self._inspector.show_node(node_id or None)

    def _on_document_changed(self) -> None:
        self._service.mark_dirty()
        self._canvas.rebuild()
        node_id = self._canvas.selected_node_id()
        if node_id:
            self._inspector.show_node(node_id)
        self._update_title()

    def _update_title(self) -> None:
        name = self._doc.project.meta.name
        path = self._service.path
        star = "*" if self._service.dirty else ""
        loc = path.name if path else "unsaved"
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

    def _open_project(self) -> None:
        if not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open project",
            "",
            "py_vui project (py_vui.json);;JSON (*.json)",
        )
        if not path:
            return
        try:
            self._service = ProjectService.open(Path(path))
            self._doc = self._service.doc
            self._history = History()
            self._canvas.bind(self._doc, self._history)
            self._inspector.bind(self._doc, self._history)
            self._canvas.rebuild()
            self._canvas.select_node(self._doc.project.root_id)
            self._update_title()
        except Exception as exc:
            QMessageBox.critical(self, "Open failed", str(exc))

    def _save_project(self) -> None:
        if self._service.path is None:
            self._save_project_as()
            return
        try:
            self._service.save()
            self._update_title()
            self.statusBar().showMessage(f"Saved {self._service.path}", 3000)
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", str(exc))

    def _save_project_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save project",
            "py_vui.json",
            "py_vui project (py_vui.json)",
        )
        if not path:
            return
        try:
            self._service.save(Path(path))
            self._update_title()
            self.statusBar().showMessage(f"Saved {self._service.path}", 3000)
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", str(exc))

    def _generate(self) -> None:
        try:
            if self._service.path:
                self._service.save()
            root = self._service.path.parent if self._service.path else Path.cwd()
            gen = self._service.write_generated(root)
            self._output.appendPlainText(f"Generated → {gen}")
            self.statusBar().showMessage("Code generated", 3000)
        except Exception as exc:
            QMessageBox.critical(self, "Generate failed", str(exc))

    def _preview(self) -> None:
        try:
            root = self._service.path.parent if self._service.path else Path.cwd()
            gen = self._service.write_generated(root)
            entry = gen / "main.py"
            self._output.appendPlainText(f"Preview: {entry}")
            result = run_preview(root, entry)
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
