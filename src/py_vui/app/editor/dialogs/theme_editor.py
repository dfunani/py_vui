"""Project theme editor: presets + every design token, with a live mini preview."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPaintEvent
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

from py_vui.app.editor.dialogs.common import make_dialog_base
from py_vui.app.editor.prop_editors import (
    ChoiceEdit,
    ColorEdit,
    FontEdit,
    NumberEdit,
    ValueEditor,
)
from py_vui.commands import Batch, History, SetProjectAttr
from py_vui.core.document import ProjectDocument
from py_vui.core.theme import PRESETS, ProjectTheme, theme_for_preset

COLOR_TOKENS = (
    ("primary", "Primary"),
    ("primary_hover", "Primary hover"),
    ("background", "Window background"),
    ("surface", "Surface / cards"),
    ("text", "Text"),
    ("muted_text", "Muted text"),
    ("button_text", "Button text"),
    ("border", "Border"),
)


class ThemePreview(QWidget):
    """Paints a card with a label, entry and button using the theme tokens."""

    def __init__(self, theme: ProjectTheme, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.theme = theme
        self.setMinimumSize(260, 190)

    def set_theme(self, theme: ProjectTheme) -> None:
        self.theme = theme
        self.update()

    def paintEvent(self, _e: QPaintEvent) -> None:
        t = self.theme
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(t.background))
        font = QFont(t.font_family)
        font.setPixelSize(max(t.font_size, 6))
        p.setFont(font)
        w, h = self.width(), self.height()
        card = QRectF(12, 12, w - 24, h - 24)
        p.setPen(QColor(t.border))
        p.setBrush(QColor(t.surface))
        p.drawRoundedRect(card, 8, 8)
        p.setPen(QColor(t.text))
        p.drawText(QRectF(26, 20, w - 52, 24), Qt.AlignmentFlag.AlignVCenter, "Card title")
        p.setPen(QColor(t.muted_text))
        p.drawText(QRectF(26, 44, w - 52, 22), Qt.AlignmentFlag.AlignVCenter, "Muted helper text")
        entry = QRectF(26, 76, w - 52, 28)
        p.setPen(QColor(t.border))
        p.setBrush(QColor(t.surface))
        p.drawRoundedRect(entry, min(t.button_radius, 14), min(t.button_radius, 14))
        p.setPen(QColor(t.muted_text))
        p.drawText(entry.adjusted(8, 0, 0, 0), Qt.AlignmentFlag.AlignVCenter, "Entry placeholder")
        btn = QRectF(26, 116, 96, 32)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(t.primary))
        p.drawRoundedRect(btn, t.button_radius, t.button_radius)
        p.setPen(QColor(t.button_text))
        p.drawText(btn, Qt.AlignmentFlag.AlignCenter, "Button")
        hov = QRectF(134, 116, 96, 32)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(t.primary_hover))
        p.drawRoundedRect(hov, t.button_radius, t.button_radius)
        p.setPen(QColor(t.button_text))
        p.drawText(hov, Qt.AlignmentFlag.AlignCenter, "Hover")
        p.end()


class ThemeEditorDialog(QDialog):
    def __init__(self, doc: ProjectDocument, history: History, parent: QWidget | None = None,
                 ) -> None:
        super().__init__(parent)
        self.doc, self.history = doc, history
        self.theme: ProjectTheme = doc.project.theme.model_copy(deep=True)
        lay = make_dialog_base(self, "Theme editor", (700, 520))
        body = QHBoxLayout()
        lay.addLayout(body, 1)
        form = QFormLayout()
        self.preset = ChoiceEdit(PRESETS, editable=False)
        form.addRow("Preset", self.preset)
        self.editors: dict[str, ValueEditor] = {}
        for token, label in COLOR_TOKENS:
            ed = ColorEdit()
            self.editors[token] = ed
            form.addRow(label, ed)
        self.editors["font_family"] = FontEdit()
        self.editors["font_size"] = NumberEdit(minimum=6, maximum=48)
        self.editors["button_radius"] = NumberEdit(minimum=0, maximum=64)
        self.editors["border_width"] = NumberEdit(minimum=0, maximum=16)
        self.editors["appearance"] = ChoiceEdit(("system", "light", "dark"))
        form.addRow("Font family", self.editors["font_family"])
        form.addRow("Font size", self.editors["font_size"])
        form.addRow("Button radius", self.editors["button_radius"])
        form.addRow("Border width", self.editors["border_width"])
        form.addRow("Appearance", self.editors["appearance"])
        body.addLayout(form, 1)
        pv = QVBoxLayout()
        self.preview = ThemePreview(self.theme)
        pv.addWidget(self.preview)
        pv.addStretch(1)
        body.addLayout(pv, 1)
        box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Apply)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        box.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self.apply)
        lay.addWidget(box)
        self._load()
        self.preset.valueChanged.connect(self._preset_changed)
        for token, ed in self.editors.items():
            ed.valueChanged.connect(lambda v, t=token: self._token_changed(t, v))

    def _load(self) -> None:
        self.preset.set_value(self.theme.preset)
        for token, ed in self.editors.items():
            ed.set_value(getattr(self.theme, token))
        self.preview.set_theme(self.theme)

    def _preset_changed(self, preset: str) -> None:
        keep: dict[str, Any] = {"font_family": self.theme.font_family,
                                "font_size": self.theme.font_size}
        new = theme_for_preset(preset)
        self.theme = new.model_copy(update=keep)
        self._load()

    def _token_changed(self, token: str, value: Any) -> None:
        if token in {c for c, _ in COLOR_TOKENS} and not value:
            return
        if token == "font_family" and not value:
            return
        try:
            data = self.theme.model_dump()
            data[token] = value
            self.theme = ProjectTheme.model_validate(data)
        except ValueError:
            return
        self.preview.set_theme(self.theme)

    def set_token(self, token: str, value: Any) -> None:
        """Programmatic edit (as if typed in the editor)."""
        self.editors[token].set_value(value)
        self._token_changed(token, value)

    def apply(self) -> None:
        if self.theme == self.doc.project.theme:
            return
        cmd = Batch([SetProjectAttr("theme", self.theme.model_copy(deep=True),
                                    label="Edit theme")], label="Edit theme")
        self.history.push(self.doc, cmd)

    def accept(self) -> None:
        self.apply()
        super().accept()
