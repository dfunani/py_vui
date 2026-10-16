"""Bracket matching that ignores brackets inside strings and comments (uses ``tokenize``)."""

from __future__ import annotations

import io
import tokenize
from bisect import bisect_right

OPEN = "([{"
CLOSE = ")]}"
PAIR = dict(zip(OPEN, CLOSE, strict=True)) | dict(zip(CLOSE, OPEN, strict=True))
_FSTRING_START = getattr(tokenize, "FSTRING_START", None)
_FSTRING_END = getattr(tokenize, "FSTRING_END", None)


def ignored_ranges(text: str) -> list[tuple[int, int]]:
    """Sorted ``(start, end)`` offsets of strings (incl. f-strings) and comments.

    Tokenizing stops quietly at the first error, so half-typed code still works for
    everything before the broken spot.
    """
    starts = [0]
    for line in text.split("\n"):
        starts.append(starts[-1] + len(line) + 1)

    def off(pos: tuple[int, int]) -> int:
        row, col = pos
        return starts[min(row - 1, len(starts) - 1)] + col

    out: list[tuple[int, int]] = []
    fstack: list[int] = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type == tokenize.COMMENT or tok.type == tokenize.STRING:
                out.append((off(tok.start), off(tok.end)))
            elif _FSTRING_START is not None and tok.type == _FSTRING_START:
                fstack.append(off(tok.start))
            elif _FSTRING_END is not None and tok.type == _FSTRING_END and fstack:
                begin = fstack.pop()
                if not fstack:
                    out.append((begin, off(tok.end)))
    except (tokenize.TokenError, SyntaxError, IndentationError):
        pass
    out.sort()
    return out


def _inside(ranges: list[tuple[int, int]], idx: int) -> bool:
    i = bisect_right(ranges, (idx, float("inf"))) - 1
    return i >= 0 and ranges[i][0] <= idx < ranges[i][1]


def find_match(text: str, idx: int, ranges: list[tuple[int, int]] | None = None,
               limit: int = 20000) -> int | None:
    """Offset of the bracket matching ``text[idx]``; None if unmatched or inside a string."""
    if not 0 <= idx < len(text) or text[idx] not in PAIR:
        return None
    ranges = ignored_ranges(text) if ranges is None else ranges
    if _inside(ranges, idx):
        return None
    ch = text[idx]
    other = PAIR[ch]
    forward = ch in OPEN
    step = 1 if forward else -1
    stop = min(len(text), idx + limit) if forward else max(-1, idx - limit)
    depth = 0
    i = idx
    while i != stop:
        c = text[i]
        if c in (ch, other) and not _inside(ranges, i):
            depth += 1 if c == ch else -1
            if depth == 0:
                return i
        i += step
    return None
