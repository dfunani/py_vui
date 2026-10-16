"""Console dock: stdout / stderr of the preview process with clickable handler tracebacks."""

from __future__ import annotations

import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontDatabase, QMouseEvent, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from py_vui.app.editor.editor_theme import current_palette

_TRACE = re.compile(r'File "(?P<file>[^"]*handlers\.py)", line (?P<line>\d+), in (?P<func>\w+)')
MAX_BLOCKS = 5000


def parse_handler_ref(line: str) -> tuple[str, int] | None:
    """Return (handler name, line number) when ``line`` is a traceback frame in handlers.py."""
    m = _TRACE.search(line)
    if not m or m.group("func") == "<module>":
        return None
    return m.group("func"), int(m.group("line"))


class _Output(QPlainTextEdit):
    lineClicked = Signal(str)

    def mouseReleaseEvent(self, ev: QMouseEvent) -> None:
        super().mouseReleaseEvent(ev)
        if ev.button() == Qt.MouseButton.LeftButton and not self.textCursor().hasSelection():
            cursor = self.cursorForPosition(ev.position().toPoint())
            self.lineClicked.emit(cursor.block().text())

    def mouseMoveEvent(self, ev: QMouseEvent) -> None:
        super().mouseMoveEvent(ev)
        text = self.cursorForPosition(ev.position().toPoint()).block().text()
        self.viewport().setCursor(
            Qt.CursorShape.PointingHandCursor
            if parse_handler_ref(text)
            else Qt.CursorShape.IBeamCursor
        )


class ConsolePanel(QWidget):
    #: a traceback line pointing into handlers.py was clicked
    handlerRequested = Signal(str, int)
    stopRequested = Signal()
    restartRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.out = _Output()
        self.out.setReadOnly(True)
        self.out.setMaximumBlockCount(MAX_BLOCKS)
        self.out.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.out.setMouseTracking(True)
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        font.setPointSize(11)
        self.out.setFont(font)
        self.out.lineClicked.connect(self._on_line)

        self.status = QLabel("Idle")
        self.status.setObjectName("sectionTitle")
        self.stop_btn = self._btn("■", "Stop the preview", self.stopRequested.emit)
        self.restart_btn = self._btn("⟳", "Restart the preview", self.restartRequested.emit)
        self.clear_btn = self._btn("Clear", "Clear the console", self.clear)
        self.copy_btn = self._btn("Copy", "Copy output to the clipboard", self.copy_all)
        self.wrap_btn = self._btn("Wrap", "Toggle word wrap", self._toggle_wrap)
        self.wrap_btn.setCheckable(True)
        self.stop_btn.setEnabled(False)

        bar = QHBoxLayout()
        bar.setContentsMargins(6, 4, 6, 0)
        bar.addWidget(self.status)
        bar.addStretch(1)
        for b in (self.stop_btn, self.restart_btn, self.clear_btn, self.copy_btn, self.wrap_btn):
            bar.addWidget(b)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        lay.addLayout(bar)
        lay.addWidget(self.out, 1)

    @staticmethod
    def _btn(text: str, tip: str, slot) -> QToolButton:
        b = QToolButton()
        b.setText(text)
        b.setToolTip(tip)
        b.clicked.connect(lambda _=False: slot())
        return b

    # -- api
    def append(self, text: str, kind: str = "out") -> None:
        """kind: out | err | info"""
        pal = current_palette()
        fmt = QTextCharFormat()
        color = {"err": "#f87171" if pal.name == "dark" else "#b91c1c", "info": pal.muted}.get(
            kind, pal.text
        )
        fmt.setForeground(QColor(color))
        if kind == "info":
            fmt.setFontItalic(True)
        cursor = self.out.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        for line in text.splitlines(keepends=True) or [text]:
            f = QTextCharFormat(fmt)
            if parse_handler_ref(line):
                f.setFontUnderline(True)
                f.setForeground(QColor(pal.accent))
            cursor.insertText(line, f)
        if not text.endswith("\n"):
            cursor.insertText("\n", fmt)
        self.out.moveCursor(QTextCursor.MoveOperation.End)

    def clear(self) -> None:
        self.out.clear()

    def text(self) -> str:
        return self.out.toPlainText()

    def copy_all(self) -> None:
        cur = self.out.textCursor()
        QApplication.clipboard().setText(cur.selectedText() if cur.hasSelection() else self.text())

    def set_running(self, running: bool, label: str | None = None) -> None:
        self.stop_btn.setEnabled(running)
        self.status.setText(label or ("Running…" if running else "Idle"))

    def _toggle_wrap(self) -> None:
        self.out.setLineWrapMode(
            QPlainTextEdit.LineWrapMode.WidgetWidth
            if self.wrap_btn.isChecked()
            else QPlainTextEdit.LineWrapMode.NoWrap
        )

    def _on_line(self, line: str) -> None:
        ref = parse_handler_ref(line)
        if ref:
            self.handlerRequested.emit(*ref)

    def set_font_size(self, pt: int) -> None:
        f = QFont(self.out.font())
        f.setPointSize(pt)
        self.out.setFont(f)
