"""Live syntax checks for handler bodies and module code (pure Python, no Qt)."""

from __future__ import annotations

import textwrap
from dataclasses import dataclass


@dataclass(frozen=True)
class CodeProblem:
    #: 0-based line inside the checked text
    line: int
    column: int
    message: str

    def __str__(self) -> str:
        return f"line {self.line + 1}: {self.message}"


def check_handler(body: str, name: str = "f") -> CodeProblem | None:
    """Compile ``def name(event=None):`` + body; report the first syntax error in the body."""
    text = textwrap.dedent(body).rstrip() or "pass"
    src = f"def {name}(event=None):\n" + textwrap.indent(text, "    ") + "\n"
    try:
        compile(src, "<handler>", "exec")
    except SyntaxError as exc:
        line = max((exc.lineno or 2) - 2, 0)
        col = max((exc.offset or 1) - 1 - 4, 0)
        return CodeProblem(line, col, exc.msg)
    return None


def check_module(code: str) -> CodeProblem | None:
    try:
        compile(code or "", "<module>", "exec")
    except SyntaxError as exc:
        return CodeProblem(max((exc.lineno or 1) - 1, 0), max((exc.offset or 1) - 1, 0), exc.msg)
    return None


def check_source(code: str, filename: str = "<generated>") -> CodeProblem | None:
    try:
        compile(code, filename, "exec")
    except SyntaxError as exc:
        return CodeProblem(max((exc.lineno or 1) - 1, 0), max((exc.offset or 1) - 1, 0), exc.msg)
    return None
