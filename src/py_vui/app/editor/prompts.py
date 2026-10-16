"""Modal prompts used by the main window, isolated so tests can replace them."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox, QWidget


class Prompts:
    def __init__(self, parent: QWidget) -> None:
        self.parent = parent

    def ask_unsaved(self, name: str) -> str:
        """Return "save", "discard" or "cancel"."""
        box = QMessageBox(self.parent)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Unsaved changes")
        box.setText(f"“{name}” has unsaved changes.")
        box.setInformativeText("Do you want to save them before continuing?")
        save = box.addButton("Save", QMessageBox.ButtonRole.AcceptRole)
        discard = box.addButton("Discard", QMessageBox.ButtonRole.DestructiveRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(save)
        box.exec()
        clicked = box.clickedButton()
        if clicked is save:
            return "save"
        if clicked is discard:
            return "discard"
        return "cancel"

    def confirm(self, title: str, text: str, yes: str = "Yes") -> bool:
        box = QMessageBox(self.parent)
        box.setWindowTitle(title)
        box.setText(text)
        ok = box.addButton(yes, QMessageBox.ButtonRole.AcceptRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.exec()
        return box.clickedButton() is ok

    def choose(self, title: str, text: str, options: list[str]) -> str | None:
        """Offer several buttons; returns the chosen label or None."""
        box = QMessageBox(self.parent)
        box.setWindowTitle(title)
        box.setText(text)
        buttons = {box.addButton(o, QMessageBox.ButtonRole.AcceptRole): o for o in options}
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.exec()
        return buttons.get(box.clickedButton())

    def error(self, title: str, text: str) -> None:
        QMessageBox.critical(self.parent, title, text)

    def info(self, title: str, text: str) -> None:
        QMessageBox.information(self.parent, title, text)

    def choose_dir(self, title: str, start: str = "") -> Path | None:
        d = QFileDialog.getExistingDirectory(self.parent, title, start)
        return Path(d) if d else None

    def choose_open_file(self, title: str, filt: str, start: str = "") -> Path | None:
        f, _ = QFileDialog.getOpenFileName(self.parent, title, start, filt)
        return Path(f) if f else None

    def prompt_text(self, title: str, label: str, default: str = "") -> str | None:
        text, ok = QInputDialog.getText(self.parent, title, label, text=default)
        return text.strip() if ok and text.strip() else None
