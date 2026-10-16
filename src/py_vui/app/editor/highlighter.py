"""Python syntax highlighting (own implementation; no third-party editor widgets)."""

from __future__ import annotations

import builtins
import keyword
import re

from PySide6.QtGui import QColor, QFont, QGuiApplication, QSyntaxHighlighter, QTextCharFormat

KEYWORDS = frozenset(keyword.kwlist) | {"match", "case"}
BUILTINS = frozenset(n for n in dir(builtins) if not n.startswith("_"))

#: line-start states carried between lines (triple-quoted strings)
_NONE, _TSQ, _TDQ = 0, 1, 2

_TOKEN = re.compile(
    r"(?P<comment>#.*)"
    r"|(?P<tstr>[rRbBfFuU]{0,2}(?:'''|\"\"\"))"
    r"|(?P<str>[rRbBfFuU]{0,2}(?:'(?:\\.|[^'\\])*'?|\"(?:\\.|[^\"\\])*\"?))"
    r"|(?P<deco>^[ \t]*@[A-Za-z_][\w.]*)"
    r"|(?P<number>\b(?:0[xX][0-9a-fA-F_]+|0[bB][01_]+|0[oO][0-7_]+"
    r"|\d[\d_]*(?:\.\d[\d_]*)?(?:[eE][+-]?\d+)?j?)\b|(?<![\w.])\.\d+)"
    r"|(?P<ident>[A-Za-z_]\w*)"
)

Span = tuple[int, int, str]
_KIND_NAMES = {"deco": "decorator", "str": "string"}


def scan_line(line: str, state: int = _NONE) -> tuple[list[Span], int]:
    """Tokenize one line. Returns ``(spans, next_state)``; spans are ``(start, length, kind)``.

    Kinds: keyword, builtin, string, comment, number, decorator, defname, classname, self.
    """
    spans: list[Span] = []
    pos = 0
    if state != _NONE:
        delim = "'''" if state == _TSQ else '"""'
        end = _find_close(line, 0, delim)
        if end < 0:
            return ([(0, len(line), "string")] if line else []), state
        spans.append((0, end + 3, "string"))
        pos = end + 3
        state = _NONE
    prev = ""
    while pos <= len(line):
        m = _TOKEN.search(line, pos)
        if m is None:
            break
        kind = m.lastgroup or ""
        text = m.group()
        start = m.start()
        if kind == "comment":
            spans.append((start, len(text), "comment"))
            break
        if kind == "tstr":
            delim = text[-3:]
            end = _find_close(line, m.end(), delim)
            if end < 0:
                spans.append((start, len(line) - start, "string"))
                return spans, _TSQ if delim == "'''" else _TDQ
            spans.append((start, end + 3 - start, "string"))
            pos = end + 3
            prev = ""
            continue
        if kind == "ident":
            if text in KEYWORDS:
                spans.append((start, len(text), "keyword"))
                prev = text
                pos = m.end()
                continue
            if prev == "def":
                spans.append((start, len(text), "defname"))
            elif prev == "class":
                spans.append((start, len(text), "classname"))
            elif text in ("self", "cls"):
                spans.append((start, len(text), "self"))
            elif text in BUILTINS:
                spans.append((start, len(text), "builtin"))
            prev = ""
            pos = m.end()
            continue
        spans.append((start, len(text), _KIND_NAMES.get(kind, kind)))
        prev = ""
        pos = m.end()
        if m.end() == m.start():
            pos += 1
    return spans, state


def _find_close(line: str, start: int, delim: str) -> int:
    i = start
    while i < len(line):
        if line[i] == "\\":
            i += 2
            continue
        if line.startswith(delim, i):
            return i
        i += 1
    return -1


def tokenize(text: str) -> list[list[Span]]:
    """Tokenize a whole source text (used by tests and the Generated tab)."""
    state = _NONE
    out: list[list[Span]] = []
    for line in text.split("\n"):
        spans, state = scan_line(line, state)
        out.append(spans)
    return out


# ----------------------------------------------------------------------------- palettes
_LIGHT = {
    "keyword": ("#0033b3", True, False),
    "builtin": ("#00627a", False, False),
    "string": ("#067d17", False, False),
    "comment": ("#8c8c8c", False, True),
    "number": ("#1750eb", False, False),
    "decorator": ("#9e880d", False, False),
    "defname": ("#00627a", True, False),
    "classname": ("#7a3e9d", True, False),
    "self": ("#94558d", False, True),
}
_DARK = {
    "keyword": ("#cc7832", True, False),
    "builtin": ("#8888c6", False, False),
    "string": ("#6a8759", False, False),
    "comment": ("#808080", False, True),
    "number": ("#6897bb", False, False),
    "decorator": ("#bbb529", False, False),
    "defname": ("#ffc66d", True, False),
    "classname": ("#e6b422", True, False),
    "self": ("#94558d", False, True),
}


def is_dark_palette() -> bool:
    app = QGuiApplication.instance()
    if app is None:
        return False
    return QGuiApplication.palette().window().color().lightness() < 128


def build_formats(dark: bool) -> dict[str, QTextCharFormat]:
    out: dict[str, QTextCharFormat] = {}
    for kind, (color, bold, italic) in (_DARK if dark else _LIGHT).items():
        f = QTextCharFormat()
        f.setForeground(QColor(color))
        if bold:
            f.setFontWeight(QFont.Weight.Bold)
        f.setFontItalic(italic)
        out[kind] = f
    return out


class PythonHighlighter(QSyntaxHighlighter):
    """Syntax highlighter following the application's light/dark palette."""

    def __init__(self, document, dark: bool | None = None) -> None:
        super().__init__(document)
        self._dark = is_dark_palette() if dark is None else dark
        self._formats = build_formats(self._dark)
        app = QGuiApplication.instance()
        if dark is None and app is not None:
            # follow runtime light/dark switches of the editor theme
            app.paletteChanged.connect(self._follow_palette)

    def _follow_palette(self, *_args) -> None:
        dark = is_dark_palette()
        if dark != self._dark:
            self.set_dark(dark)

    def set_dark(self, dark: bool) -> None:
        self._dark = dark
        self._formats = build_formats(dark)
        self.rehighlight()

    @property
    def dark(self) -> bool:
        return self._dark

    def highlightBlock(self, text: str) -> None:
        state = max(self.previousBlockState(), 0)
        spans, nxt = scan_line(text, state)
        for start, length, kind in spans:
            fmt = self._formats.get(kind)
            if fmt is not None:
                self.setFormat(start, length, fmt)
        self.setCurrentBlockState(nxt)
