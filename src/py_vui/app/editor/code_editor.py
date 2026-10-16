"""Line-numbered Python editor (QPlainTextEdit based): indent, brackets, completion, squiggles."""

from __future__ import annotations

import re
from collections.abc import Callable

from PySide6.QtCore import QRect, QSize, QStringListModel, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QKeyEvent,
    QKeySequence,
    QPainter,
    QPaintEvent,
    QResizeEvent,
    QShortcut,
    QTextCharFormat,
    QTextCursor,
    QTextFormat,
)
from PySide6.QtWidgets import (
    QCompleter,
    QPlainTextEdit,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from py_vui.app.editor.brackets import PAIR, find_match, ignored_ranges
from py_vui.app.editor.code_check import CodeProblem
from py_vui.app.editor.completion import MemberContext, member_context
from py_vui.app.editor.find_bar import FindBar
from py_vui.app.editor.highlighter import BUILTINS, KEYWORDS, PythonHighlighter
from py_vui.app.editor.ui_colors import error_color

INDENT = "    "
_WORD = re.compile(r"[A-Za-z_]\w*$")


class _LineNumbers(QWidget):
    def __init__(self, editor: CodeEditor) -> None:
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self) -> QSize:
        return QSize(self._editor.line_number_width(), 0)

    def paintEvent(self, event: QPaintEvent) -> None:
        self._editor.paint_line_numbers(event)


class CodeEditor(QPlainTextEdit):
    """The editor used for handlers, module code and generated-code viewing."""

    def __init__(self, parent: QWidget | None = None, *, highlight: bool = True,
                 read_only: bool = False) -> None:
        super().__init__(parent)
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        font.setPointSize(max(font.pointSize(), 11))
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setTabStopDistance(4 * self.fontMetrics().horizontalAdvance(" "))
        self.setReadOnly(read_only)
        self._problem: CodeProblem | None = None
        self._ignored_cache: tuple[int, list[tuple[int, int]]] = (-1, [])
        self._member_provider: Callable[[MemberContext], list[str]] | None = None
        self._member_mode = False
        self._numbers = _LineNumbers(self)
        self.highlighter: PythonHighlighter | None = (
            PythonHighlighter(self.document()) if highlight else None
        )
        self._words: list[str] = sorted(KEYWORDS | BUILTINS)
        self._completer = QCompleter(self)
        self._model = QStringListModel(self._words, self._completer)
        self._completer.setModel(self._model)
        self._completer.setWidget(self)
        self._completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._completer.activated.connect(self._insert_completion)
        self.blockCountChanged.connect(self._update_margin)
        self.updateRequest.connect(self._scroll_numbers)
        self.cursorPositionChanged.connect(self._update_selections)
        self._update_margin()
        self._update_selections()

    # ------------------------------------------------------------------ public
    def set_completions(self, words: list[str]) -> None:
        self._words = sorted(set(words) | KEYWORDS | BUILTINS)
        self._model.setStringList(self._words)

    def completions(self) -> list[str]:
        return list(self._words)

    def set_problem(self, problem: CodeProblem | None) -> None:
        self._problem = problem
        self._update_selections()

    def problem(self) -> CodeProblem | None:
        return self._problem

    def set_code(self, text: str) -> None:
        """Replace the whole text without losing the caret when the text is unchanged."""
        if text == self.toPlainText():
            return
        cur = self.textCursor()
        pos = min(cur.position(), len(text))
        self.setPlainText(text)
        cur = self.textCursor()
        cur.setPosition(pos)
        self.setTextCursor(cur)

    # ------------------------------------------------------------ line numbers
    def line_number_width(self) -> int:
        digits = max(3, len(str(max(1, self.blockCount()))))
        return 12 + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_margin(self) -> None:
        self.setViewportMargins(self.line_number_width(), 0, 0, 0)

    def _scroll_numbers(self, rect: QRect, dy: int) -> None:
        if dy:
            self._numbers.scroll(0, dy)
        else:
            self._numbers.update(0, rect.y(), self._numbers.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_margin()

    def resizeEvent(self, e: QResizeEvent) -> None:
        super().resizeEvent(e)
        cr = self.contentsRect()
        self._numbers.setGeometry(QRect(cr.left(), cr.top(), self.line_number_width(), cr.height()))

    def paint_line_numbers(self, event: QPaintEvent) -> None:
        p = QPainter(self._numbers)
        pal = self.palette()
        p.fillRect(event.rect(), pal.alternateBase().color())
        fg = pal.placeholderText().color()
        cur_line = self.textCursor().blockNumber()
        block = self.firstVisibleBlock()
        n = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                p.setPen(pal.text().color() if n == cur_line else fg)
                p.drawText(0, top, self._numbers.width() - 6, self.fontMetrics().height(),
                           Qt.AlignmentFlag.AlignRight, str(n + 1))
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            n += 1

    # --------------------------------------------------------------- selections
    def _update_selections(self) -> None:
        sels: list[QTextEdit.ExtraSelection] = []
        if not self.isReadOnly():
            s = QTextEdit.ExtraSelection()
            s.format.setBackground(self.palette().alternateBase().color())
            s.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            s.cursor = self.textCursor()
            s.cursor.clearSelection()
            sels.append(s)
        sels.extend(self._bracket_selections())
        sels.extend(self._problem_selections())
        self.setExtraSelections(sels)

    def _problem_selections(self) -> list[QTextEdit.ExtraSelection]:
        p = self._problem
        if p is None:
            return []
        block = self.document().findBlockByNumber(min(p.line, self.blockCount() - 1))
        if not block.isValid():
            return []
        text = block.text()
        start = min(p.column, max(len(text) - 1, 0))
        s = QTextEdit.ExtraSelection()
        fmt = QTextCharFormat()
        fmt.setUnderlineStyle(QTextCharFormat.UnderlineStyle.WaveUnderline)
        fmt.setUnderlineColor(error_color(self.palette()))
        s.format = fmt
        cur = QTextCursor(block)
        cur.setPosition(block.position() + start)
        cur.setPosition(block.position() + max(len(text), start + 1), QTextCursor.MoveMode.KeepAnchor)
        if not text.strip():
            cur = QTextCursor(block)
            cur.select(QTextCursor.SelectionType.LineUnderCursor)
        s.cursor = cur
        return [s]

    def _ignored(self) -> list[tuple[int, int]]:
        rev = self.document().revision()
        if self._ignored_cache[0] != rev:
            self._ignored_cache = (rev, ignored_ranges(self.toPlainText()))
        return self._ignored_cache[1]

    def matching_bracket(self) -> tuple[int, int] | None:
        """Positions of the bracket pair adjacent to the caret (strings/comments skipped)."""
        text = self.toPlainText()
        pos = self.textCursor().position()
        for idx in (pos - 1, pos):
            if 0 <= idx < len(text) and text[idx] in PAIR:
                other = find_match(text, idx, self._ignored())
                if other is not None:
                    return idx, other
        return None

    def _bracket_selections(self) -> list[QTextEdit.ExtraSelection]:
        pair = self.matching_bracket()
        if pair is None:
            return []
        out = []
        for idx in pair:
            s = QTextEdit.ExtraSelection()
            c = QColor(self.palette().highlight().color())
            c.setAlpha(110)
            s.format.setBackground(c)
            s.format.setFontWeight(QFont.Weight.Bold)
            cur = QTextCursor(self.document())
            cur.setPosition(idx)
            cur.setPosition(idx + 1, QTextCursor.MoveMode.KeepAnchor)
            s.cursor = cur
            out.append(s)
        return out

    # ------------------------------------------------------------------- keys
    def keyPressEvent(self, e: QKeyEvent) -> None:
        if self._completer.popup().isVisible() and e.key() in (
            Qt.Key.Key_Enter, Qt.Key.Key_Return, Qt.Key.Key_Escape, Qt.Key.Key_Tab,
            Qt.Key.Key_Backtab,
        ):
            e.ignore()
            return
        if self.isReadOnly():
            super().keyPressEvent(e)
            return
        key = e.key()
        mods = e.modifiers()
        if key == Qt.Key.Key_Space and mods & Qt.KeyboardModifier.ControlModifier:
            self.show_completions(force=True)
            return
        if key == Qt.Key.Key_Tab and not mods & Qt.KeyboardModifier.ControlModifier:
            self.indent_selection()
            return
        if key == Qt.Key.Key_Backtab:
            self.dedent_selection()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not mods & (
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
        ):
            self.insert_newline_indented()
            return
        if (
            key == Qt.Key.Key_Backspace
            and not self.textCursor().hasSelection()
            and self._backspace_indent()
        ):
            return
        super().keyPressEvent(e)
        if e.text() and (e.text().isalnum() or e.text() in ("_", ".", '"', "'")):
            self.show_completions()
        elif self._completer.popup().isVisible():
            self._completer.popup().hide()

    def insert_newline_indented(self) -> None:
        cur = self.textCursor()
        line = cur.block().text()
        before = line[: cur.positionInBlock()]
        indent = re.match(r"[ \t]*", line).group()  # type: ignore[union-attr]
        stripped = before.split("#")[0].rstrip()
        if stripped.endswith(":") or stripped.endswith(("(", "[", "{")):
            indent += INDENT
        cur.insertText("\n" + indent)
        self.setTextCursor(cur)
        self.ensureCursorVisible()

    def _backspace_indent(self) -> bool:
        cur = self.textCursor()
        col = cur.positionInBlock()
        before = cur.block().text()[:col]
        if col and before.strip() == "" and col % len(INDENT) == 0 and " " in before:
            cur.setPosition(cur.position() - len(INDENT), QTextCursor.MoveMode.KeepAnchor)
            cur.removeSelectedText()
            return True
        return False

    def indent_selection(self) -> None:
        cur = self.textCursor()
        if not cur.hasSelection() or cur.document().findBlock(
            cur.selectionStart()
        ) == cur.document().findBlock(cur.selectionEnd()):
            if cur.hasSelection():
                cur.removeSelectedText()
            n = len(INDENT) - (cur.positionInBlock() % len(INDENT))
            cur.insertText(" " * n)
            return
        self._for_selected_blocks(lambda c: c.insertText(INDENT))

    def dedent_selection(self) -> None:
        def undent(c: QTextCursor) -> None:
            text = c.block().text()
            n = min(len(INDENT), len(text) - len(text.lstrip(" ")))
            if n:
                c.movePosition(QTextCursor.MoveOperation.StartOfBlock)
                c.setPosition(c.position() + n, QTextCursor.MoveMode.KeepAnchor)
                c.removeSelectedText()

        self._for_selected_blocks(undent)

    def _for_selected_blocks(self, fn) -> None:
        cur = self.textCursor()
        doc = self.document()
        first = doc.findBlock(cur.selectionStart()).blockNumber()
        last = doc.findBlock(cur.selectionEnd()).blockNumber()
        if cur.selectionEnd() == doc.findBlockByNumber(last).position() and last > first:
            last -= 1
        cur.beginEditBlock()
        for n in range(first, last + 1):
            c = QTextCursor(doc.findBlockByNumber(n))
            c.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            fn(c)
        cur.endEditBlock()

    # -------------------------------------------------------------- completion
    def _word_prefix(self) -> str:
        cur = self.textCursor()
        m = _WORD.search(cur.block().text()[: cur.positionInBlock()])
        return m.group() if m else ""

    def set_member_provider(self, fn: Callable[[MemberContext], list[str]] | None) -> None:
        """``fn(context) -> candidate names`` for ``WIDGETS["x"].`` / ``module.`` completion."""
        self._member_provider = fn

    def _text_before_caret(self) -> str:
        cur = self.textCursor()
        return cur.block().text()[: cur.positionInBlock()]

    def member_candidates(self) -> tuple[MemberContext, list[str]] | None:
        ctx = member_context(self._text_before_caret())
        if ctx is None or self._member_provider is None:
            return None
        words = self._member_provider(ctx)
        return (ctx, words) if words else None

    def _use_words(self, words: list[str], members: bool) -> None:
        if members or self._member_mode:
            self._model.setStringList(words)
            self._member_mode = members

    def show_completions(self, *, force: bool = False) -> None:
        member = self.member_candidates()
        if member is not None:
            ctx, words = member
            self._use_words(words, True)
            prefix = ctx.prefix
            if not prefix and not force and ctx.kind == "name" and not words:
                self._completer.popup().hide()
                return
        else:
            self._use_words(self._words, False)
            prefix = self._word_prefix()
            if len(prefix) < (1 if force else 2):
                self._completer.popup().hide()
                return
        self._completer.setCompletionPrefix(prefix)
        if self._completer.completionCount() == 0 or (
            self._completer.completionCount() == 1
            and self._completer.currentCompletion() == prefix
        ):
            self._completer.popup().hide()
            return
        popup = self._completer.popup()
        popup.setCurrentIndex(self._completer.completionModel().index(0, 0))
        rect = self.cursorRect()
        rect.setWidth(popup.sizeHintForColumn(0) + popup.verticalScrollBar().sizeHint().width())
        self._completer.complete(rect)

    def completion_matches(self, prefix: str) -> list[str]:
        """Names offered for ``prefix`` at the caret (members when after a dot)."""
        p = prefix.lower()
        member = self.member_candidates()
        words = member[1] if member is not None else self._words
        return [w for w in words if w.lower().startswith(p)]

    def _insert_completion(self, text: str) -> None:
        cur = self.textCursor()
        prefix = self._word_prefix()
        cur.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.KeepAnchor, len(prefix))
        cur.insertText(text)
        self.setTextCursor(cur)


class CodeEditorView(QWidget):
    """CodeEditor + find/replace bar (Ctrl+F)."""

    def __init__(self, parent: QWidget | None = None, *, highlight: bool = True,
                 read_only: bool = False) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.editor = CodeEditor(self, highlight=highlight, read_only=read_only)
        self.find_bar = FindBar(self.editor, self)
        self.find_bar.set_replace_enabled(not read_only)
        lay.addWidget(self.find_bar)
        lay.addWidget(self.editor, 1)
        sc = QShortcut(QKeySequence.StandardKey.Find, self)
        sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc.activated.connect(self.find_bar.open_bar)
