"""Resolve flex / grid container layouts into absolute boxes.

Used by the editor canvas (design-time preview) and by adapters that have no native
equivalent (Kivy fallbacks). Pure functions: no Qt, no I/O.
"""

from __future__ import annotations

from py_vui.core.document import ProjectDocument
from py_vui.core.model import Box, ContainerLayout, Node
from py_vui.core.registry import get_spec


def inner_size(doc: ProjectDocument, container: Node) -> tuple[float, float]:
    if container.type in ("window", "toplevel"):
        return float(container.props.get("width", container.box.w)), float(
            container.props.get("height", container.box.h)
        )
    box = resolved_box(doc, container)
    return box.w, box.h


def resolve_children(doc: ProjectDocument, container_id: str) -> dict[str, Box]:
    """Child id -> box for a flex/grid container (absolute containers return stored boxes)."""
    container = doc.get_node(container_id)
    layout = container.layout or ContainerLayout()
    kids = [k for k in doc.children(container_id) if k.visible]
    w, h = inner_size(doc, container)
    if layout.mode == "flex":
        return _flex(layout, kids, w, h)
    if layout.mode == "grid":
        return _grid(layout, kids, w, h)
    return {k.id: k.box for k in kids}


def _flex(layout: ContainerLayout, kids: list[Node], w: float, h: float) -> dict[str, Box]:
    pad = layout.padding
    iw, ih = max(0.0, w - pad.left - pad.right), max(0.0, h - pad.top - pad.bottom)
    row = layout.direction == "row"
    main_size, cross_size = (iw, ih) if row else (ih, iw)

    def msize(k: Node) -> float:
        m = k.flex.margin
        return (k.box.w if row else k.box.h) + ((m.left + m.right) if row else (m.top + m.bottom))

    # break into lines
    lines: list[list[Node]] = [[]]
    used = 0.0
    for k in kids:
        s = msize(k)
        if layout.wrap and lines[-1] and used + s + layout.gap > main_size:
            lines.append([])
            used = 0.0
        used += s + (layout.gap if lines[-1] else 0)
        lines[-1].append(k)

    out: dict[str, Box] = {}
    line_cross = cross_size / len(lines) if layout.wrap and len(lines) > 1 else cross_size
    cross_pos = 0.0
    for line in lines:
        if not line:
            continue
        gaps = layout.gap * (len(line) - 1)
        base = sum(msize(k) for k in line)
        free = main_size - base - gaps
        grow_total = sum(k.flex.grow for k in line)
        sizes = {}
        for k in line:
            extra = free * k.flex.grow / grow_total if grow_total > 0 and free > 0 else 0.0
            sizes[k.id] = msize(k) + extra
        pos = 0.0
        gap = layout.gap
        if grow_total == 0 or free <= 0:
            if layout.justify == "center":
                pos = max(0.0, free) / 2
            elif layout.justify == "end":
                pos = max(0.0, free)
            elif layout.justify == "space_between" and len(line) > 1 and free > 0:
                gap = layout.gap + free / (len(line) - 1)
            elif layout.justify == "space_around" and free > 0:
                gap = layout.gap + free / len(line)
                pos = gap / 2 - layout.gap / 2
        for k in line:
            m = k.flex.margin
            main_len = sizes[k.id] - ((m.left + m.right) if row else (m.top + m.bottom))
            align = layout.align if k.flex.align_self == "auto" else k.flex.align_self
            kc = (k.box.h if row else k.box.w)
            avail = line_cross - ((m.top + m.bottom) if row else (m.left + m.right))
            if align == "stretch":
                cross_len, cross_off = avail, 0.0
            else:
                cross_len = min(kc, avail)
                cross_off = {"start": 0.0, "center": (avail - cross_len) / 2,
                             "end": avail - cross_len}[align]
            main_off = pos + (m.left if row else m.top)
            cross_abs = cross_pos + cross_off + (m.top if row else m.left)
            if row:
                out[k.id] = Box(x=pad.left + main_off, y=pad.top + cross_abs,
                                w=max(1.0, main_len), h=max(1.0, cross_len))
            else:
                out[k.id] = Box(x=pad.left + cross_abs, y=pad.top + main_off,
                                w=max(1.0, cross_len), h=max(1.0, main_len))
            pos += sizes[k.id] + gap
        cross_pos += line_cross + layout.gap
    return out


def _tracks(count: int, weights: list[int], total: float, gap: float, mins: list[float]) -> list[float]:
    sizes = list(mins)
    w = [weights[i] if i < len(weights) else 0 for i in range(count)]
    free = total - sum(sizes) - gap * max(0, count - 1)
    wsum = sum(w)
    if wsum > 0 and free > 0:
        for i in range(count):
            sizes[i] += free * w[i] / wsum
    return sizes


def _grid(layout: ContainerLayout, kids: list[Node], w: float, h: float) -> dict[str, Box]:
    pad = layout.padding
    iw, ih = max(0.0, w - pad.left - pad.right), max(0.0, h - pad.top - pad.bottom)
    ncols = max([len(layout.column_weights), *[k.cell.column + k.cell.column_span for k in kids]])
    nrows = max([len(layout.row_weights), *[k.cell.row + k.cell.row_span for k in kids]])
    min_w = [0.0] * ncols
    min_h = [0.0] * nrows
    for k in kids:
        if k.cell.column_span == 1:
            min_w[k.cell.column] = max(min_w[k.cell.column], k.box.w)
        if k.cell.row_span == 1:
            min_h[k.cell.row] = max(min_h[k.cell.row], k.box.h)
    cw = _tracks(ncols, layout.column_weights, iw, layout.column_gap, min_w)
    rh = _tracks(nrows, layout.row_weights, ih, layout.row_gap, min_h)
    xs, ys = [0.0], [0.0]
    for c in cw:
        xs.append(xs[-1] + c + layout.column_gap)
    for r in rh:
        ys.append(ys[-1] + r + layout.row_gap)
    out: dict[str, Box] = {}
    for k in kids:
        c0, r0 = k.cell.column, k.cell.row
        c1, r1 = c0 + k.cell.column_span, r0 + k.cell.row_span
        cx, cy = xs[c0], ys[r0]
        cell_w = xs[c1] - layout.column_gap - cx
        cell_h = ys[r1] - layout.row_gap - cy
        s = k.cell.sticky.lower()
        bw, bh = k.box.w, k.box.h
        if "e" in s and "w" in s:
            bw, x = cell_w, cx
        elif "e" in s:
            x = cx + cell_w - bw
        elif "w" in s:
            x = cx
        else:
            x = cx + (cell_w - bw) / 2
        if "n" in s and "s" in s:
            bh, y = cell_h, cy
        elif "s" in s:
            y = cy + cell_h - bh
        elif "n" in s:
            y = cy
        else:
            y = cy + (cell_h - bh) / 2
        out[k.id] = Box(x=pad.left + x, y=pad.top + y, w=max(1.0, bw), h=max(1.0, bh))
    return out


def resolved_box(doc: ProjectDocument, node: Node) -> Box:
    """The box the editor should draw for ``node`` (honouring its parent's layout mode)."""
    if node.parent_id is None:
        return node.box
    parent = doc.get_node(node.parent_id)
    if parent.layout is None or parent.layout.mode == "absolute" or get_spec(parent.type).paged:
        return node.box
    return resolve_children(doc, parent.id).get(node.id, node.box)
