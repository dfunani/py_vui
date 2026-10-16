"""Find / replace bar for CodeEditor (Ctrl+F)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent, QTextCursor, QTextDocument
from PySide6.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QToolButton,
    QWidget,
)


class FindBar(QWidget):
    def __init__(self, editor: QPlainTextEdit, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.editor = editor
        grid = QGridLayout(self)
        grid.setContentsMargins(4, 2, 4, 2)
        grid.setSpacing(4)
        self.find_edit = QLineEdit()
        self.find_edit.setPlaceholderText("Find")
        self.replace_edit = QLineEdit()
        self.replace_edit.setPlaceholderText("Replace with")
        self.case = QCheckBox("Aa")
        self.case.setToolTip("Match case")
        self.status = QLabel("")
        prev_b = QToolButton()
        prev_b.setText("↑")
        prev_b.setToolTip("Previous (Shift+Enter)")
        next_b = QToolButton()
        next_b.setText("↓")
        next_b.setToolTip("Next (Enter)")
        close_b = QToolButton()
        close_b.setText("✕")
        close_b.setToolTip("Close (Esc)")
        self.replace_btn = QPushButton("Replace")
        self.replace_all_btn = QPushButton("All")
        for b in (self.replace_btn, self.replace_all_btn):
            b.setAutoDefault(False)
        grid.addWidget(self.find_edit, 0, 0)
        grid.addWidget(prev_b, 0, 1)
        grid.addWidget(next_b, 0, 2)
        grid.addWidget(self.case, 0, 3)
        grid.addWidget(self.status, 0, 4)
        grid.addWidget(close_b, 0, 5)
        grid.addWidget(self.replace_edit, 1, 0)
        grid.addWidget(self.replace_btn, 1, 1, 1, 2)
        grid.addWidget(self.replace_all_btn, 1, 3)
        grid.setColumnStretch(0, 1)
        prev_b.clicked.connect(self.find_prev)
        next_b.clicked.connect(self.find_next)
        close_b.clicked.connect(self.close_bar)
        self.replace_btn.clicked.connect(self.replace_current)
        self.replace_all_btn.clicked.connect(self.replace_all)
        self.find_edit.textChanged.connect(self._text_changed)
        self.find_edit.returnPressed.connect(self.find_next)
        self.find_edit.installEventFilter(self)
        self.replace_edit.installEventFilter(self)
        self.setVisible(False)

    def set_replace_enabled(self, on: bool) -> None:
        for w in (self.replace_edit, self.replace_btn, self.replace_all_btn):
            w.setVisible(on)

    def open_bar(self) -> None:
        sel = self.editor.textCursor().selectedText()
        if sel and " " not in sel:
            self.find_edit.setText(sel)
        self.setVisible(True)
        self.find_edit.setFocus()
        self.find_edit.selectAll()

    def close_bar(self) -> None:
        self.setVisible(False)
        self.editor.setFocus()

    def eventFilter(self, obj, event) -> bool:
        if isinstance(event, QKeyEvent) and event.type() == QKeyEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Escape:
                self.close_bar()
                return True
            if (
                obj is self.find_edit
                and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
                and event.modifiers() & Qt.KeyboardModifier.ShiftModifier
            ):
                self.find_prev()
                return True
        return super().eventFilter(obj, event)

    # ------------------------------------------------------------- searching
    def _flags(self, backward: bool = False) -> QTextDocument.FindFlag:
        flags = QTextDocument.FindFlag(0)
        if self.case.isChecked():
            flags |= QTextDocument.FindFlag.FindCaseSensitively
        if backward:
            flags |= QTextDocument.FindFlag.FindBackward
        return flags

    def match_count(self) -> int:
        needle = self.find_edit.text()
        if not needle:
            return 0
        text = self.editor.toPlainText()
        if not self.case.isChecked():
            text, needle = text.lower(), needle.lower()
        return text.count(needle)

    def _text_changed(self) -> None:
        n = self.match_count()
        self.status.setText(f"{n} match(es)" if self.find_edit.text() else "")
        if self.find_edit.text():
            cur = self.editor.textCursor()
            cur.setPosition(min(cur.selectionStart(), cur.position()))
            self.editor.setTextCursor(cur)
            self._find(False)

    def _find(self, backward: bool) -> bool:
        needle = self.find_edit.text()
        if not needle:
            return False
        flags = self._flags(backward)
        if self.editor.find(needle, flags):
            return True
        cur = self.editor.textCursor()
        cur.movePosition(
            QTextCursor.MoveOperation.End if backward else QTextCursor.MoveOperation.Start
        )
        self.editor.setTextCursor(cur)
        return self.editor.find(needle, flags)

    def find_next(self) -> bool:
        return self._find(False)

    def find_prev(self) -> bool:
        return self._find(True)

    def replace_current(self) -> bool:
        needle = self.find_edit.text()
        cur = self.editor.textCursor()
        sel = cur.selectedText()
        same = sel == needle if self.case.isChecked() else sel.lower() == needle.lower()
        if needle and same:
            cur.insertText(self.replace_edit.text())
        return self.find_next()

    def replace_all(self) -> int:
        needle = self.find_edit.text()
        if not needle:
            return 0
        cur = self.editor.textCursor()
        cur.beginEditBlock()
        cur.movePosition(QTextCursor.MoveOperation.Start)
        self.editor.setTextCursor(cur)
        count = 0
        flags = self._flags()
        while self.editor.find(needle, flags):
            self.editor.textCursor().insertText(self.replace_edit.text())
            count += 1
        end = self.editor.textCursor()
        end.endEditBlock()
        self.status.setText(f"{count} replaced")
        return count
