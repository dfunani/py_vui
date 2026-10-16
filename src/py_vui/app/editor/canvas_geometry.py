"""Geometry helpers shared by the canvas painter, hit-testing and drop planning."""

from __future__ import annotations

from dataclasses import dataclass

from py_vui.core.document import ProjectDocument
from py_vui.core.layout_engine import _tracks, inner_size, resolved_box
from py_vui.core.model import Box, ContainerLayout, Node
from py_vui.core.registry import get_spec

#: height of the tab header strip drawn above the page area of a ``tabview``
TAB_HEADER_H = 30.0
#: height of the title strip of a ``label_frame`` (children are positioned below it)
GROUP_TITLE_H = 18.0
#: window chrome drawn *above* the client area (title bar, menu bar)
TITLEBAR_H = 28.0
MENUBAR_H = 24.0
TAB_MIN_W = 60.0


def content_origin(node: Node) -> tuple[float, float]:
    """Where a container's child coordinates start, relative to the container's top-left."""
    if node.type == "tabview":
        return 0.0, TAB_HEADER_H
    if node.type == "label_frame":
        return 0.0, GROUP_TITLE_H
    return 0.0, 0.0


def content_size(doc: ProjectDocument, node: Node) -> tuple[float, float]:
    ox, oy = content_origin(node)
    w, h = inner_size(doc, node)
    return max(0.0, w - ox), max(0.0, h - oy)


def node_box(doc: ProjectDocument, node: Node) -> Box:
    """The box drawn for ``node`` (parent-relative, honouring flex/grid)."""
    if node.parent_id is None:
        w, h = inner_size(doc, node)
        return Box(x=0, y=0, w=w, h=h)
    if node.type == "toplevel":
        w, h = inner_size(doc, node)
        return Box(x=0, y=0, w=w, h=h)
    return resolved_box(doc, node)


def abs_origin(doc: ProjectDocument, node: Node) -> tuple[float, float]:
    """Scene position of the node's top-left corner (window client area is the origin)."""
    x = y = 0.0
    cur: Node | None = node
    while cur is not None and cur.type not in ("window", "toplevel"):
        b = node_box(doc, cur)
        x += b.x
        y += b.y
        parent = doc.project.nodes.get(cur.parent_id) if cur.parent_id else None
        if parent is not None:
            ox, oy = content_origin(parent)
            x += ox
            y += oy
        cur = parent
    return x, y


def abs_rect(doc: ProjectDocument, node: Node) -> tuple[float, float, float, float]:
    x, y = abs_origin(doc, node)
    b = node_box(doc, node)
    return x, y, b.w, b.h


def layout_of(node: Node) -> ContainerLayout:
    return node.layout or ContainerLayout()


def is_paged(node: Node) -> bool:
    return get_spec(node.type).paged


def current_page(node: Node) -> int:
    tabs = node.props.get("tabs") or []
    cur = int(node.props.get("current", 0) or 0)
    return max(0, min(cur, max(0, len(tabs) - 1)))


def visible_children(doc: ProjectDocument, node: Node) -> list[Node]:
    """Children actually shown at design time (hidden nodes and other tab pages excluded)."""
    kids = [k for k in doc.children(node.id) if k.visible]
    if is_paged(node):
        page = current_page(node)
        kids = [k for k in kids if k.page == page]
    return kids


def tab_rects(node: Node) -> list[tuple[float, float, float, float]]:
    """Header tab rectangles (x, y, w, h) in the tabview's local coordinates."""
    from PySide6.QtGui import QFont, QFontMetricsF

    tabs = [str(t) for t in (node.props.get("tabs") or [])]
    fm = QFontMetricsF(QFont())
    out = []
    x = 0.0
    for t in tabs:
        w = max(TAB_MIN_W, fm.horizontalAdvance(t) + 28)
        out.append((x, 0.0, w, TAB_HEADER_H))
        x += w
    return out


def tab_at(node: Node, lx: float, ly: float) -> int | None:
    if ly < 0 or ly > TAB_HEADER_H:
        return None
    for i, (x, y, w, h) in enumerate(tab_rects(node)):
        if x <= lx <= x + w and y <= ly <= y + h:
            return i
    return None


@dataclass
class GridGeometry:
    xs: list[float]  # column start x (content coords incl. padding)
    ys: list[float]
    col_w: list[float]
    row_h: list[float]

    @property
    def cols(self) -> int:
        return len(self.col_w)

    @property
    def rows(self) -> int:
        return len(self.row_h)

    def cell_at(self, x: float, y: float) -> tuple[int, int]:
        col = max(0, self._index(self.xs, self.col_w, x))
        row = max(0, self._index(self.ys, self.row_h, y))
        return row, col

    @staticmethod
    def _index(starts: list[float], sizes: list[float], v: float) -> int:
        if not starts:
            return 0
        for i, (s, sz) in enumerate(zip(starts, sizes, strict=False)):
            if v < s + sz + 4:
                return i
        return len(starts) - 1

    def cell_rect(self, row: int, col: int, rspan: int = 1, cspan: int = 1) -> tuple[float, ...]:
        row = min(row, self.rows - 1)
        col = min(col, self.cols - 1)
        r1 = min(row + rspan, self.rows) - 1
        c1 = min(col + cspan, self.cols) - 1
        x0, y0 = self.xs[col], self.ys[row]
        return (x0, y0, self.xs[c1] + self.col_w[c1] - x0, self.ys[r1] + self.row_h[r1] - y0)


def grid_geometry(doc: ProjectDocument, container: Node, extra_cells: int = 0) -> GridGeometry:
    """Track geometry of a grid container (mirrors ``layout_engine._grid``)."""
    layout = layout_of(container)
    pad = layout.padding
    w, h = content_size(doc, container)
    iw, ih = max(0.0, w - pad.left - pad.right), max(0.0, h - pad.top - pad.bottom)
    kids = [k for k in doc.children(container.id) if k.visible]
    ncols = max([len(layout.column_weights), *[k.cell.column + k.cell.column_span for k in kids]])
    nrows = max([len(layout.row_weights), *[k.cell.row + k.cell.row_span for k in kids]])
    ncols += extra_cells
    nrows += extra_cells
    min_w = [0.0] * ncols
    min_h = [0.0] * nrows
    for k in kids:
        if k.cell.column_span == 1:
            min_w[k.cell.column] = max(min_w[k.cell.column], k.box.w)
        if k.cell.row_span == 1:
            min_h[k.cell.row] = max(min_h[k.cell.row], k.box.h)
    cw = _tracks(ncols, layout.column_weights, iw, layout.column_gap, min_w)
    rh = _tracks(nrows, layout.row_weights, ih, layout.row_gap, min_h)
    xs, ys = [], []
    x = pad.left
    for c in cw:
        xs.append(x)
        x += c + layout.column_gap
    y = pad.top
    for r in rh:
        ys.append(y)
        y += r + layout.row_gap
    return GridGeometry(xs, ys, cw, rh)
