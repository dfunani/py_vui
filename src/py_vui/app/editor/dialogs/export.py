"""Export dialog: project folder / single file / zip, with framework override preview."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QRadioButton,
    QWidget,
)

from py_vui.app.editor.dialogs.common import FRAMEWORK_INFO, add_buttons, make_dialog_base
from py_vui.codegen import GenOptions, generate
from py_vui.core.registry import FRAMEWORKS

FORMATS = (
    ("project", "Project folder (main.py, ui.py, handlers.py, requirements.txt…)"),
    ("single", "Single Python file"),
    ("zip", "Zip archive"),
)


class ExportDialog(QDialog):
    def __init__(self, service: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self.result_path: Path | None = None
        self.error: str = ""
        lay = make_dialog_base(self, "Export code", (620, 560))
        form = QFormLayout()
        self._formats: dict[str, QRadioButton] = {}
        for i, (fid, text) in enumerate(FORMATS):
            rb = QRadioButton(text)
            rb.setChecked(i == 0)
            rb.toggled.connect(lambda _on: self._refresh_preview())
            self._formats[fid] = rb
            form.addRow("Format" if i == 0 else "", rb)
        self.framework = QComboBox()
        proj_fw = service.doc.project.framework
        for fw in FRAMEWORKS:
            label = FRAMEWORK_INFO[fw][0] + (" (project)" if fw == proj_fw else "")
            self.framework.addItem(label, fw)
        self.framework.setCurrentIndex(self.framework.findData(proj_fw))
        self.framework.currentIndexChanged.connect(lambda _i: self._refresh_preview())
        form.addRow("Framework", self.framework)
        self.include_assets = QCheckBox("Include assets")
        self.include_assets.setChecked(True)
        self.include_requirements = QCheckBox("Include requirements.txt")
        self.include_requirements.setChecked(True)
        form.addRow("", self.include_assets)
        form.addRow("", self.include_requirements)
        row = QHBoxLayout()
        self.dest = QLineEdit(str(Path.home() / "py_vui_export"))
        browse = QPushButton("Browse…")
        browse.setAutoDefault(False)
        browse.clicked.connect(self._browse)
        row.addWidget(self.dest, 1)
        row.addWidget(browse)
        form.addRow("Destination", row)
        lay.addLayout(form)
        lay.addWidget(QLabel("Files that will be generated"))
        self.preview = QListWidget()
        lay.addWidget(self.preview, 1)
        self.result_label = QLabel("")
        self.result_label.setWordWrap(True)
        self.result_label.setOpenExternalLinks(False)
        lay.addWidget(self.result_label)
        self.buttons = add_buttons(
            self, lay, QDialogButtonBox.StandardButton.Close)
        self.export_btn = QPushButton("Export")
        self.export_btn.clicked.connect(self.export)
        self.buttons.addButton(self.export_btn, QDialogButtonBox.ButtonRole.ActionRole)
        self.include_assets.toggled.connect(lambda _on: self._refresh_preview())
        self.include_requirements.toggled.connect(lambda _on: self._refresh_preview())
        self._refresh_preview()

    # ------------------------------------------------------------- state
    def fmt(self) -> str:
        return next(f for f, rb in self._formats.items() if rb.isChecked())

    def set_format(self, fmt: str) -> None:
        self._formats[fmt].setChecked(True)

    def chosen_framework(self) -> str:
        return self.framework.currentData()

    def _layout(self) -> str:
        return "single" if self.fmt() == "single" else "project"

    def _refresh_preview(self) -> None:
        self.preview.clear()
        try:
            p = self.service.doc.project.model_copy(
                update={"framework": self.chosen_framework()})
            files = generate(p, GenOptions(layout=self._layout()))
        except Exception as exc:
            self.preview.addItem(f"Generation failed: {exc}")
            return
        for f in files:
            if f.path == "requirements.txt" and not self.include_requirements.isChecked():
                continue
            self.preview.addItem(f.path)
        if self.include_assets.isChecked() and self.service.doc.project.assets:
            self.preview.addItem(f"assets/ ({len(self.service.doc.project.assets)} file(s))")
        z = self.fmt() == "zip"
        self.include_assets.setEnabled(True)
        self.include_requirements.setEnabled(True)
        if z and self.dest.text() and not self.dest.text().endswith(".zip"):
            self.dest.setText(self.dest.text() + ".zip")
        if not z and self.dest.text().endswith(".zip"):
            self.dest.setText(self.dest.text()[:-4])

    def _browse(self) -> None:
        if self.fmt() == "zip":
            fn, _ = QFileDialog.getSaveFileName(self, "Export zip", self.dest.text(), "Zip (*.zip)")
        elif self.fmt() == "single":
            fn, _ = QFileDialog.getSaveFileName(self, "Export file", self.dest.text(), "Python (*.py)")
        else:
            fn = QFileDialog.getExistingDirectory(self, "Export folder", self.dest.text())
        if fn:
            self.dest.setText(fn)

    # ------------------------------------------------------------- export
    def export(self) -> Path | None:
        """Run ``service.export``; returns the result path (or None and sets ``error``)."""
        self.error = ""
        dest = Path(self.dest.text()).expanduser()
        try:
            result = self.service.export(
                dest,
                self.fmt(),
                include_assets=self.include_assets.isChecked(),
                include_requirements=self.include_requirements.isChecked(),
                framework=self.chosen_framework(),
            )
        except Exception as exc:
            self.error = str(exc)
            self.result_label.setText(f"Export failed: {exc}")
            return None
        self.result_path = Path(result)
        self.result_label.setText(f"Exported to {self.result_path}")
        return self.result_path
