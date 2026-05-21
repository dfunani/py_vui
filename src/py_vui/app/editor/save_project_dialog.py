from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from py_vui.app.editor.session_paths import sanitize_project_slug


class SaveProjectDialog(QDialog):
    """Ask for project display name and parent folder before Save As."""

    def __init__(
        self,
        parent=None,
        *,
        default_name: str = "untitled",
        default_parent: str | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Save Project As")
        self.setMinimumWidth(420)

        self._name = QLineEdit(default_name)
        self._parent = QLineEdit(default_parent or str(Path.home() / "Documents"))
        self._parent.setReadOnly(True)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse_parent)

        parent_row = QHBoxLayout()
        parent_row.addWidget(self._parent, stretch=1)
        parent_row.addWidget(browse)

        slug = sanitize_project_slug(default_name)
        self._hint = QLabel(f"Will create folder: {slug}/")
        self._hint.setStyleSheet("color: palette(mid);")
        self._name.textChanged.connect(self._update_hint)

        form = QFormLayout()
        form.addRow("Project name", self._name)
        form.addRow("Save inside", parent_row)
        form.addRow("", self._hint)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _browse_parent(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self,
            "Choose parent folder for project",
            self._parent.text(),
        )
        if chosen:
            self._parent.setText(chosen)

    def _update_hint(self) -> None:
        slug = sanitize_project_slug(self._name.text())
        self._hint.setText(f"Will create folder: {slug}/")

    def project_name(self) -> str:
        return self._name.text().strip() or "untitled"

    def parent_dir(self) -> Path:
        return Path(self._parent.text())
