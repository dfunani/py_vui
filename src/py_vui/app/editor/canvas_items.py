"""Design-canvas scene graph: one :class:`NodeItem` per node, synced incrementally."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QGraphicsItem, QGraphicsScene, QStyleOptionGraphicsItem, QWidget

from py_vui.app.editor.canvas_geometry import content_origin, current_page, is_paged
from py_vui.app.editor.canvas_overlays import draw_dot_grid
from py_vui.app.editor.canvas_paint import (
    paint_locked_badge,
    paint_widget,
    paint_window_chrome,
    window_chrome_height,
)
from py_vui.app.editor.editor_theme import current_palette
from py_vui.app.editor.paint_common import PaintCtx
from py_vui.core.document import ProjectDocument
from py_vui.core.layout_engine import inner_size, resolve_children
from py_vui.core.model import Box, Node
from py_vui.core.registry import get_spec

SCENE_MARGIN = 600.0


class NodeItem(QGraphicsItem):
    """A widget (or window) drawn by :func:`paint_widget`. Children are real child items."""

    def __init__(
        self, node_id: str, scene: DesignScene, parent: QGraphicsItem | None = None
    ) -> None:
        super().__init__(parent)
        self.node_id = node_id
        self._scene = scene
        self._w = 10.0
        self._h = 10.0
        self.is_window = False

    # -- geometry
    def set_geometry(self, x: float, y: float, w: float, h: float) -> None:
        if (w, h) != (self._w, self._h):
            self.prepareGeometryChange()
            self._w, self._h = w, h
        if (x, y) != (self.pos().x(), self.pos().y()):
            self.setPos(x, y)

    @property
    def size(self) -> tuple[float, float]:
        return self._w, self._h

    def boundingRect(self) -> QRectF:
        if self.is_window:
            node = self._scene.node(self.node_id)
            top = window_chrome_height(node) if node else 0.0
            return QRectF(-1, -top - 1, self._w + 2, self._h + top + 2)
        return QRectF(0, 0, self._w, self._h)

    def shape(self):
        from PySide6.QtGui import QPainterPath

        path = QPainterPath()
        path.addRect(QRectF(0, 0, self._w, self._h))
        return path

    def paint(
        self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None
    ) -> None:
        node = self._scene.node(self.node_id)
        if node is None or self._scene.ctx is None:
            return
        ctx = self._scene.ctx
        paint_widget(painter, node, ctx, self._w, self._h)
        if self.is_window:
            if self._scene.show_grid:
                scale = painter.worldTransform().m11() or 1.0
                draw_dot_grid(
                    painter,
                    QRectF(0, 0, self._w, self._h),
                    self._scene.grid_size,
                    scale,
                    current_palette(),
                )
            paint_window_chrome(painter, node, ctx, self._w)
        if node.locked:
            paint_locked_badge(painter, self._w)


def parent_is_alive(parent: QGraphicsItem, items: dict[str, NodeItem]) -> bool:
    """True when ``parent`` is still tracked (i.e. not itself scheduled for deletion)."""
    return any(parent is it for it in items.values())


class DesignScene(QGraphicsScene):
    """Holds the item tree of one window and keeps it in step with the document."""

    def __init__(self) -> None:
        super().__init__()
        self.doc: ProjectDocument | None = None
        self.window_id: str | None = None
        self.items_by_id: dict[str, NodeItem] = {}
        self.ctx: PaintCtx | None = None
        self.base_dir: Path | None = None
        self._ctx_key: object = None
        self._sigs: dict[str, tuple] = {}
        self.root_item: NodeItem | None = None
        self.show_grid = True
        self.grid_size = 8

    # -- access
    def node(self, node_id: str):
        return self.doc.project.nodes.get(node_id) if self.doc else None

    def set_document(self, doc: ProjectDocument | None) -> None:
        self.doc = doc
        self.clear_items()

    def set_window(self, window_id: str | None) -> None:
        if window_id != self.window_id:
            self.window_id = window_id
            self.clear_items()

    def clear_items(self) -> None:
        for item in list(self.items_by_id.values()):
            if item.scene() is self:
                self.removeItem(item)
        self.items_by_id.clear()
        self._sigs.clear()
        self.root_item = None

    # -- sync
    def sync(self) -> bool:
        """Bring items in line with the document. Returns True when anything changed."""
        doc = self.doc
        if doc is None or self.window_id is None or self.window_id not in doc.project.nodes:
            self.clear_items()
            return False
        project = doc.project
        ctx_key = (project.framework, project.theme.model_dump_json(), str(self.base_dir))
        force = ctx_key != self._ctx_key
        if force:
            self._ctx_key = ctx_key
            self.ctx = PaintCtx(project.framework, project.theme, self.base_dir)
        changed = force

        order = self._window_nodes(doc)
        wanted = {n.id for n in order}
        stale = [i for i in self.items_by_id if i not in wanted]

        boxes = self._layout_boxes(order)
        ranks = {}
        for n in order:
            for rank, kid in enumerate(doc.children(n.id)):
                ranks[kid.id] = rank

        for node in order:
            item = self.items_by_id.get(node.id)
            parent_item = (
                self.items_by_id.get(node.parent_id) if node.id != self.window_id else None
            )
            if item is None:
                item = NodeItem(node.id, self, parent_item)
                self.items_by_id[node.id] = item
                if parent_item is None:
                    self.addItem(item)
                    item.is_window = True
                    self.root_item = item
                changed = True
            elif parent_item is not None and item.parentItem() is not parent_item:
                item.setParentItem(parent_item)
                changed = True

            if node.id == self.window_id:
                w, h = inner_size(doc, node)
                geom = (0.0, 0.0, float(w), float(h))
            else:
                parent = project.nodes[node.parent_id]  # type: ignore[index]
                ox, oy = content_origin(parent)
                b = boxes[node.id]
                geom = (b.x + ox, b.y + oy, b.w, b.h)
            vis = node.visible
            if node.parent_id and is_paged(project.nodes[node.parent_id]):
                vis = vis and node.page == current_page(project.nodes[node.parent_id])
            sig = (
                geom,
                ranks.get(node.id, 0),
                vis,
                node.enabled,
                node.locked,
                node.type,
                repr(node.props),
                repr(node.style),
                node.parent_id,
            )
            if not force and self._sigs.get(node.id) == sig:
                continue
            self._sigs[node.id] = sig
            changed = True
            item.set_geometry(*geom)
            item.setZValue(ranks.get(node.id, 0))
            item.setVisible(vis)
            item.setOpacity(1.0 if node.enabled else 0.55)
            item.setFlag(
                QGraphicsItem.GraphicsItemFlag.ItemClipsChildrenToShape,
                get_spec(node.type).container,
            )
            item.update()

        # drop vanished items last, so surviving children were already re-parented away
        for nid in stale:
            item = self.items_by_id.pop(nid)
            self._sigs.pop(nid, None)
            parent = item.parentItem()
            if parent is None:
                if item.scene() is self:
                    self.removeItem(item)
            elif parent_is_alive(parent, self.items_by_id):
                item.setParentItem(None)
                if item.scene() is self:
                    self.removeItem(item)
            changed = True

        if self.root_item is not None:
            top = window_chrome_height(project.nodes[self.window_id])
            w, h = self.root_item.size
            self.setSceneRect(
                QRectF(
                    -SCENE_MARGIN,
                    -top - SCENE_MARGIN,
                    w + 2 * SCENE_MARGIN,
                    h + top + 2 * SCENE_MARGIN,
                )
            )
        return changed

    def _window_nodes(self, doc: ProjectDocument) -> list[Node]:
        """Nodes of the active window only (dialogs are separate windows)."""
        assert self.window_id is not None
        out: list[Node] = []
        stack = [self.window_id]
        while stack:
            node = doc.project.nodes[stack.pop()]
            out.append(node)
            kids = doc.children(node.id)
            stack.extend(reversed([k.id for k in kids if k.type != "toplevel"]))
        return out

    def _layout_boxes(self, order) -> dict[str, Box]:
        """Parent-relative drawn box per node; flex/grid parents resolved once each."""
        assert self.doc is not None
        out: dict[str, Box] = {}
        for node in order:
            if not get_spec(node.type).container:
                continue
            layout = node.layout
            if layout is not None and layout.mode != "absolute" and not get_spec(node.type).paged:
                out.update(resolve_children(self.doc, node.id))
        for node in order:
            out.setdefault(node.id, node.box)
        return out
