"""Paint a small schematic thumbnail of a project by drawing its nodes as boxes."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap

from py_vui.core.document import ProjectDocument
from py_vui.core.layout_engine import resolve_children
from py_vui.core.model import Box, Project
from py_vui.core.theme import resolve_style


def _rects(doc: ProjectDocument, container_id: str, ox: float, oy: float,
           out: list[tuple[str, QRectF, int]], depth: int = 0) -> None:
    container = doc.get_node(container_id)
    try:
        boxes = resolve_children(doc, container_id)
    except Exception:
        boxes = {k.id: k.box for k in doc.children(container_id)}
    for kid in doc.children(container_id):
        if not kid.visible:
            continue
        b: Box = boxes.get(kid.id, kid.box)
        out.append((kid.id, QRectF(ox + b.x, oy + b.y, b.w, b.h), depth))
        if kid.layout is not None and not (
            container.type == "tabview" and kid.page != container.props.get("current", 0)
        ):
            _rects(doc, kid.id, ox + b.x, oy + b.y, out, depth + 1)


def render_thumbnail(project: Project, width: int = 200, height: int = 140) -> QPixmap:
    doc = ProjectDocument(project)
    root = project.nodes[project.root_id]
    ww = float(root.props.get("width", root.box.w) or 640)
    wh = float(root.props.get("height", root.box.h) or 480)
    pm = QPixmap(width, height)
    theme = project.theme
    pm.fill(QColor(theme.background))
    scale = min((width - 8) / ww, (height - 8) / wh)
    rects: list[tuple[str, QRectF, int]] = []
    _rects(doc, root.id, 0, 0, rects)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.translate((width - ww * scale) / 2, (height - wh * scale) / 2)
    p.scale(scale, scale)
    p.setPen(QColor(theme.border))
    p.setBrush(QColor(theme.background))
    p.drawRect(QRectF(0, 0, ww, wh))
    font = QFont()
    font.setPixelSize(max(int(12 / max(scale, 0.01)), 8))
    p.setFont(font)
    for nid, r, _depth in rects:
        node = doc.get_node(nid)
        style = resolve_style(theme, node.type, node.style)
        p.setPen(QColor(str(style["border_color"])))
        p.setBrush(QColor(str(style["background"])))
        radius = min(float(style["corner_radius"]), 12)
        p.drawRoundedRect(r, radius, radius)
        text = node.props.get("text") or node.props.get("title") or ""
        if text and r.width() > 20:
            p.setPen(QColor(str(style["foreground"])))
            p.drawText(r.adjusted(3, 0, -3, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                       str(text)[:24])
    p.end()
    return pm
