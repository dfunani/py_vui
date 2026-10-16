"""Plugin manager dialog: list, enable / disable (with trust prompt), reload, open folder."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from py_vui.app.editor.dialogs.common import add_buttons, make_dialog_base
from py_vui.app.editor.ui_colors import error_color

COLS = ("Enabled", "Name", "Version", "Widgets", "Description", "Status")


def default_confirm(parent: QWidget, title: str, text: str) -> bool:
    ans = QMessageBox.warning(
        parent, title, text,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        QMessageBox.StandardButton.Cancel,
    )
    return ans == QMessageBox.StandardButton.Yes


class PluginManagerDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, project_dir: Path | None = None,
                 manager: Any = None) -> None:
        super().__init__(parent)
        if manager is None:
            from py_vui.plugins import PluginManager

            manager = PluginManager(project_dir)
        self.manager = manager
        self.project_dir = project_dir
        #: ``confirm(parent, title, text) -> bool``; replaceable in tests
        self.confirm: Callable[[QWidget, str, str], bool] = default_confirm
        self._loading = False
        lay = make_dialog_base(self, "Plugins", (760, 460))
        warn = QLabel("Enabling a plugin runs its Python code on this computer. "
                      "Only enable plugins you trust.")
        warn.setWordWrap(True)
        lay.addWidget(warn)
        self.table = QTableWidget(0, len(COLS))
        self.table.setHorizontalHeaderLabels(list(COLS))
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemChanged.connect(self._on_item_changed)
        lay.addWidget(self.table, 1)
        self.message = QLabel("")
        self.message.setWordWrap(True)
        lay.addWidget(self.message)
        reload_btn = QPushButton("Reload")
        folder_btn = QPushButton("Open plugins folder")
        for b in (reload_btn, folder_btn):
            b.setAutoDefault(False)
        reload_btn.clicked.connect(self.reload)
        folder_btn.clicked.connect(self.open_folder)
        box = add_buttons(self, lay, QDialogButtonBox.StandardButton.Close)
        box.addButton(reload_btn, QDialogButtonBox.ButtonRole.ActionRole)
        box.addButton(folder_btn, QDialogButtonBox.ButtonRole.ActionRole)
        self.reload()

    def reload(self) -> None:
        self._loading = True
        try:
            infos = self.manager.scan(self.project_dir) if self._scan_takes_dir() else (
                self.manager.scan())
        except Exception as exc:
            infos = []
            self.message.setText(f"Could not scan plugins: {exc}")
        self.table.setRowCount(len(infos))
        for r, info in enumerate(infos):
            en = QTableWidgetItem()
            en.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            en.setCheckState(Qt.CheckState.Checked if info.enabled else Qt.CheckState.Unchecked)
            en.setData(Qt.ItemDataRole.UserRole, info.id)
            self.table.setItem(r, 0, en)
            self.table.setItem(r, 1, QTableWidgetItem(info.name))
            self.table.setItem(r, 2, QTableWidgetItem(info.version))
            self.table.setItem(r, 3, QTableWidgetItem(", ".join(info.widget_types)))
            self.table.setItem(r, 4, QTableWidgetItem(info.description))
            status = info.error or ("Enabled" if info.enabled else "Disabled")
            st = QTableWidgetItem(status)
            if info.error:
                st.setForeground(error_color(self.palette()))
                st.setToolTip(info.error)
                en.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.table.setItem(r, 5, st)
        self.table.resizeColumnsToContents()
        self._loading = False

    def _scan_takes_dir(self) -> bool:
        import inspect

        try:
            return "project_dir" in inspect.signature(self.manager.scan).parameters
        except (TypeError, ValueError):
            return False

    def _row_id(self, row: int) -> str:
        return self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)

    def set_enabled(self, plugin_id: str, enabled: bool) -> bool:
        """Enable/disable (enable asks for confirmation first). Returns True when applied."""
        try:
            if enabled:
                if not self.confirm(
                    self, "Enable plugin",
                    f"Enabling '{plugin_id}' will execute its code. Do you trust this plugin?",
                ):
                    return False
                self.manager.enable(plugin_id, self.project_dir)
            else:
                self.manager.disable(plugin_id)
            self.message.setText("")
            return True
        except Exception as exc:
            self.message.setText(f"{plugin_id}: {exc}")
            return False
        finally:
            self.reload()

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if self._loading or item.column() != 0:
            return
        self.set_enabled(
            item.data(Qt.ItemDataRole.UserRole), item.checkState() == Qt.CheckState.Checked)

    def plugins_dir(self) -> Path:
        d = self.manager.user_dir() if hasattr(self.manager, "user_dir") else Path.home()
        Path(d).mkdir(parents=True, exist_ok=True)
        return Path(d)

    def open_folder(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.plugins_dir())))
