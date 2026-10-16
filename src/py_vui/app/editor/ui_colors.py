"""Palette-derived status colours (no hard-coded hex): follow the light/dark editor theme."""

from __future__ import annotations

from PySide6.QtCore import QEvent
from PySide6.QtGui import QColor, QGuiApplication, QPalette
from PySide6.QtWidgets import QLabel, QWidget


def is_dark(palette: QPalette | None = None) -> bool:
    pal = palette or QGuiApplication.palette()
    return pal.window().color().lightness() < 128


def error_color(palette: QPalette | None = None) -> QColor:
    """Red whose lightness is chosen for contrast against the palette's window colour."""
    return QColor.fromHslF(0.0, 0.72, 0.66 if is_dark(palette) else 0.40)


def on_color(bg: QColor) -> QColor:
    """Readable foreground (black or white) for text drawn on ``bg``."""
    return QColor("black") if bg.lightness() > 140 else QColor("white")


class ErrorLabel(QLabel):
    """Label whose text uses the palette-derived error colour (re-evaluated on theme change)."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self._apply()

    def _apply(self) -> None:
        pal = self.palette()
        pal.setColor(QPalette.ColorRole.WindowText, error_color(pal))
        self.setPalette(pal)

    def changeEvent(self, e: QEvent) -> None:
        super().changeEvent(e)
        if e.type() == QEvent.Type.ApplicationPaletteChange:
            self._apply()


class ErrorBanner(QLabel):
    """Filled banner (error colour background, contrasting text)."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setWordWrap(True)
        self.setAutoFillBackground(True)
        self.setContentsMargins(6, 4, 6, 4)
        self._apply()

    def _apply(self) -> None:
        pal = self.palette()
        bg = error_color(pal)
        pal.setColor(QPalette.ColorRole.Window, bg)
        pal.setColor(QPalette.ColorRole.WindowText, on_color(bg))
        self.setPalette(pal)

    def changeEvent(self, e: QEvent) -> None:
        super().changeEvent(e)
        if e.type() == QEvent.Type.ApplicationPaletteChange:
            self._apply()
