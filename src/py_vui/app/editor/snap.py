"""Pure (Qt-free) snapping: grid, sibling/parent smart guides and user guides."""

from __future__ import annotations

from dataclasses import dataclass, field

Rect = tuple[float, float, float, float]  # x, y, w, h


@dataclass(frozen=True)
class GuideLine:
    """A drawn alignment line. ``orient`` "v" = vertical line at x=pos spanning y in [a, b]."""

    orient: str
    pos: float
    a: float
    b: float
    kind: str = "smart"  # "smart" | "guide" | "bounds"


@dataclass
class SnapResult:
    dx: float = 0.0
    dy: float = 0.0
    lines: list[GuideLine] = field(default_factory=list)


@dataclass
class SnapSettings:
    grid: int = 8
    use_grid: bool = True
    use_smart: bool = True
    use_guides: bool = True
    #: capture distance in scene units (callers divide a pixel threshold by the zoom)
    threshold: float = 6.0


def snap_value(value: float, grid: float) -> float:
    if grid <= 0:
        return value
    return round(value / grid) * grid


def snap_size(value: float, grid: float, minimum: float = 1.0) -> float:
    return max(minimum, snap_value(value, grid))


def _targets(
    others: list[Rect], bounds: Rect | None, guides: list[float], axis: int, kind_ok: bool
) -> list[tuple[float, str, Rect | None]]:
    out: list[tuple[float, str, Rect | None]] = []
    for r in others:
        lo = r[axis]
        size = r[axis + 2]
        out.extend([(lo, "smart", r), (lo + size / 2, "smart", r), (lo + size, "smart", r)])
    if bounds is not None:
        size = bounds[axis + 2]
        out.extend(
            [(0.0, "bounds", bounds), (size / 2, "bounds", bounds), (size, "bounds", bounds)]
        )
    if kind_ok:
        out.extend((g, "guide", None) for g in guides)
    return out


def _best(
    values: list[float], targets: list[tuple[float, str, Rect | None]], thr: float
) -> tuple[float, list[tuple[float, str, Rect | None]]] | None:
    best: float | None = None
    for v in values:
        for t, _, _ in targets:
            d = t - v
            if abs(d) <= thr and (best is None or abs(d) < abs(best) - 1e-9):
                best = d
    if best is None:
        return None
    hits = [t for t in targets if any(abs(t[0] - (v + best)) < 0.5 for v in values)]
    return best, hits


def _lines(
    orient: str, hits: list[tuple[float, str, Rect | None]], moving: Rect, extent: float
) -> list[GuideLine]:
    out: list[GuideLine] = []
    cross = 1 if orient == "v" else 0
    m0, m1 = moving[cross], moving[cross] + moving[cross + 2]
    for pos, kind, rect in hits:
        if kind == "guide":
            out.append(GuideLine(orient, pos, 0.0, extent, "guide"))
            continue
        if rect is None or kind == "bounds":
            out.append(GuideLine(orient, pos, min(m0, 0.0), max(m1, extent), "bounds"))
            continue
        out.append(
            GuideLine(orient, pos, min(m0, rect[cross]), max(m1, rect[cross] + rect[cross + 2]))
        )
    # de-duplicate by (orient, pos)
    seen: set[tuple[str, float]] = set()
    uniq = []
    for ln in out:
        key = (ln.orient, round(ln.pos, 1))
        if key not in seen:
            seen.add(key)
            uniq.append(ln)
    return uniq


def snap_move(
    rect: Rect,
    others: list[Rect],
    bounds: Rect | None,
    settings: SnapSettings,
    guides_x: list[float] | None = None,
    guides_y: list[float] | None = None,
) -> SnapResult:
    """Return the correction (dx, dy) that aligns ``rect`` and the lines that explain it."""
    x, y, w, h = rect
    res = SnapResult()
    use_t = settings.use_smart
    gx = guides_x or []
    gy = guides_y or []
    tx = _targets(others if use_t else [], bounds if use_t else None, gx, 0, settings.use_guides)
    ty = _targets(others if use_t else [], bounds if use_t else None, gy, 1, settings.use_guides)
    bx = _best([x, x + w / 2, x + w], tx, settings.threshold)
    by = _best([y, y + h / 2, y + h], ty, settings.threshold)
    if bx:
        res.dx = bx[0]
    elif settings.use_grid:
        res.dx = snap_value(x, settings.grid) - x
    if by:
        res.dy = by[0]
    elif settings.use_grid:
        res.dy = snap_value(y, settings.grid) - y
    moved = (x + res.dx, y + res.dy, w, h)
    extent_v = bounds[3] if bounds else moved[1] + h
    extent_h = bounds[2] if bounds else moved[0] + w
    if bx:
        res.lines += _lines("v", bx[1], moved, extent_v)
    if by:
        res.lines += _lines("h", by[1], moved, extent_h)
    return res


def snap_resize(
    rect: Rect,
    handle: str,
    others: list[Rect],
    bounds: Rect | None,
    settings: SnapSettings,
    guides_x: list[float] | None = None,
    guides_y: list[float] | None = None,
) -> tuple[Rect, list[GuideLine]]:
    """Snap only the edges that ``handle`` (letters from "nsew") is moving."""
    x, y, w, h = rect
    use_t = settings.use_smart
    tx = _targets(
        others if use_t else [], bounds if use_t else None, guides_x or [], 0, settings.use_guides
    )
    ty = _targets(
        others if use_t else [], bounds if use_t else None, guides_y or [], 1, settings.use_guides
    )
    lines: list[GuideLine] = []
    x0, x1, y0, y1 = x, x + w, y, y + h
    if "w" in handle or "e" in handle:
        edge = x0 if "w" in handle else x1
        b = _best([edge], tx, settings.threshold)
        if b:
            edge += b[0]
        elif settings.use_grid:
            edge = snap_value(edge, settings.grid)
        if "w" in handle:
            x0 = edge
        else:
            x1 = edge
        if b:
            lines += _lines("v", b[1], (x0, y0, x1 - x0, y1 - y0), bounds[3] if bounds else y1)
    if "n" in handle or "s" in handle:
        edge = y0 if "n" in handle else y1
        b = _best([edge], ty, settings.threshold)
        if b:
            edge += b[0]
        elif settings.use_grid:
            edge = snap_value(edge, settings.grid)
        if "n" in handle:
            y0 = edge
        else:
            y1 = edge
        if b:
            lines += _lines("h", b[1], (x0, y0, x1 - x0, y1 - y0), bounds[2] if bounds else x1)
    return (x0, y0, x1 - x0, y1 - y0), lines
