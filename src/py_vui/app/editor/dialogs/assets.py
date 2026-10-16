"""Asset manager: thumbnails of the project's bundled files, add / remove / copy path / drop."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QMimeData, QSize, Qt
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QGuiApplication, QIcon, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QWidget,
)

from py_vui.app.editor.dialogs.common import add_buttons, make_dialog_base

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".ico", ".svg"}


def urls_to_paths(mime: QMimeData) -> list[Path]:
    return [Path(u.toLocalFile()) for u in mime.urls() if u.isLocalFile()]


class AssetManagerDialog(QDialog):
    def __init__(self, service: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self.setAcceptDrops(True)
        lay = make_dialog_base(self, "Assets", (640, 480))
        self.hint = QLabel("Drop files here or use Add. Reference assets as assets/<file>.")
        self.hint.setEnabled(False)
        lay.addWidget(self.hint)
        self.list = QListWidget()
        self.list.setViewMode(QListWidget.ViewMode.IconMode)
        self.list.setIconSize(QSize(72, 72))
        self.list.setGridSize(QSize(110, 110))
        self.list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list.setMovement(QListWidget.Movement.Static)
        self.list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.list.setWordWrap(True)
        lay.addWidget(self.list, 1)
        row = QHBoxLayout()
        self.add_btn = QPushButton("Add…")
        self.remove_btn = QPushButton("Remove")
        self.copy_btn = QPushButton("Copy path")
        for b in (self.add_btn, self.remove_btn, self.copy_btn):
            b.setAutoDefault(False)
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        add_buttons(self, lay, QDialogButtonBox.StandardButton.Close)
        self.add_btn.clicked.connect(self._choose_files)
        self.remove_btn.clicked.connect(self.remove_selected)
        self.copy_btn.clicked.connect(self.copy_selected_path)
        self.refresh()

    # ------------------------------------------------------------- data
    def assets(self) -> list[str]:
        return list(self.service.doc.project.assets)

    def _base_dir(self) -> Path | None:
        for attr in ("work_dir", "project_dir"):
            v = getattr(self.service, attr, None)
            if v:
                return Path(v)
        return None

    def refresh(self) -> None:
        self.list.clear()
        base = self._base_dir()
        for rel in self.assets():
            it = QListWidgetItem(Path(rel).name)
            it.setData(Qt.ItemDataRole.UserRole, rel)
            it.setToolTip(rel)
            icon = QIcon()
            if base is not None and Path(rel).suffix.lower() in IMAGE_EXTS:
                pm = QPixmap(str(base / rel))
                if not pm.isNull():
                    icon = QIcon(pm)
            it.setIcon(icon)
            self.list.addItem(it)

    def selected(self) -> list[str]:
        return [i.data(Qt.ItemDataRole.UserRole) for i in self.list.selectedItems()]

    # ------------------------------------------------------------- actions
    def add_files(self, paths: list[Path]) -> list[str]:
        added: list[str] = []
        errors: list[str] = []
        for p in paths:
            try:
                added.append(self.service.add_asset(Path(p)))
            except Exception as exc:
                errors.append(f"{Path(p).name}: {exc}")
        self.refresh()
        if errors:
            QMessageBox.warning(self, "Assets", "\n".join(errors))
        return added

    def remove_selected(self) -> int:
        sel = self.selected()
        for rel in sel:
            self.service.remove_asset(rel)
        self.refresh()
        return len(sel)

    def copy_selected_path(self) -> str:
        sel = self.selected()
        text = "\n".join(sel)
        if text:
            QGuiApplication.clipboard().setText(text)
        return text

    def _choose_files(self) -> None:
        names, _ = QFileDialog.getOpenFileNames(self, "Add assets", "", "All files (*)")
        if names:
            self.add_files([Path(n) for n in names])

    # ------------------------------------------------------------- drag & drop
    def dragEnterEvent(self, e: QDragEnterEvent) -> None:
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e: QDropEvent) -> None:
        paths = [p for p in urls_to_paths(e.mimeData()) if p.is_file()]
        if paths:
            self.add_files(paths)
            e.acceptProposedAction()
