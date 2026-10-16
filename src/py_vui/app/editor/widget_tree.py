"""Widget hierarchy: rename, show/hide, lock, drag to reorder / reparent, multi-select, filter."""

from __future__ import annotations

import json

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLineEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from py_vui.app.editor.canvas_geometry import current_page, is_paged
from py_vui.app.editor.editor_theme import current_palette
from py_vui.app.editor.icons import glyph_icon
from py_vui.app.editor.mime import MIME_NODES, MIME_WIDGET
from py_vui.commands import (
    Batch,
    Command,
    History,
    ReorderChildren,
    ReparentNode,
    SetAttr,
)
from py_vui.core.document import ProjectDocument
from py_vui.core.model import Box, Node
from py_vui.core.registry import get_spec

ROLE_ID = Qt.ItemDataRole.UserRole
COL_NAME, COL_VIS, COL_LOCK = 0, 1, 2


class _Tree(QTreeWidget):
    dropRequested = Signal(object, object, int)  # target item | None, ids, indicator position
    widgetDropped = Signal(str, object, int)  # palette widget type, target item | None, indicator

    def mimeTypes(self) -> list[str]:
        return [*super().mimeTypes(), MIME_WIDGET]

    def mimeData(self, items):
        mime = super().mimeData(items)
        mime.setData(MIME_NODES, json.dumps([i.data(COL_NAME, ROLE_ID) for i in items]).encode())
        return mime

    def dropEvent(self, ev) -> None:
        target = self.itemAt(ev.position().toPoint())
        pos = self.dropIndicatorPosition()
        if ev.mimeData().hasFormat(MIME_WIDGET):
            type_id = bytes(ev.mimeData().data(MIME_WIDGET)).decode()
            ev.setDropAction(Qt.DropAction.CopyAction)
            ev.accept()
            self.widgetDropped.emit(type_id, target, int(pos.value))
            return
        ids = [i.data(COL_NAME, ROLE_ID) for i in self.selectedItems()]
        ev.setDropAction(Qt.DropAction.IgnoreAction)  # we apply the change through History
        ev.accept()
        self.dropRequested.emit(target, ids, int(pos.value))
        self.viewport().update()


class WidgetTree(QWidget):
    selectionChanged = Signal(list)
    #: a palette widget was dropped: (type id, container id, index among siblings | None)
    widgetDropRequested = Signal(str, str, object)
    contextMenuRequested = Signal(object, QPoint)
    windowActivated = Signal(str)
    documentEdited = Signal()
    message = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.doc: ProjectDocument | None = None
        self.history: History | None = None
        self._sig: tuple | None = None
        self._populating = False
        self._items: dict[str, QTreeWidgetItem] = {}
        self._expanded: set[str] = set()
        self._known: set[str] = set()

        self.filter = QLineEdit()
        self.filter.setPlaceholderText("Filter widgets…")
        self.filter.setClearButtonEnabled(True)
        self.filter.textChanged.connect(self._apply_filter)

        self.tree = _Tree()
        t = self.tree
        t.setColumnCount(3)
        t.setHeaderHidden(True)
        t.header().setStretchLastSection(False)
        t.header().setSectionResizeMode(COL_NAME, QHeaderView.ResizeMode.Stretch)
        t.header().setSectionResizeMode(COL_VIS, QHeaderView.ResizeMode.Fixed)
        t.header().setSectionResizeMode(COL_LOCK, QHeaderView.ResizeMode.Fixed)
        t.setColumnWidth(COL_VIS, 26)
        t.setColumnWidth(COL_LOCK, 26)
        t.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        t.setDragEnabled(True)
        t.setAcceptDrops(True)
        t.setDropIndicatorShown(True)
        t.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        t.setDefaultDropAction(Qt.DropAction.MoveAction)
        t.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        t.setEditTriggers(QAbstractItemView.EditTrigger.EditKeyPressed)
        t.setIndentation(14)
        t.setUniformRowHeights(True)
        t.itemSelectionChanged.connect(self._on_selection)
        t.itemClicked.connect(self._on_clicked)
        t.itemDoubleClicked.connect(self._on_double)
        t.itemChanged.connect(self._on_changed)
        t.customContextMenuRequested.connect(self._on_context)
        t.dropRequested.connect(self._on_drop)
        t.widgetDropped.connect(self._on_widget_drop)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(4)
        lay.addWidget(self.filter)
        lay.addWidget(self.tree, 1)

    # ------------------------------------------------------------------------- binding
    def bind(self, doc: ProjectDocument, history: History) -> None:
        self.doc, self.history = doc, history
        self._sig = None
        self._expanded.clear()
        self._known.clear()
        self.refresh()

    def _signature(self) -> tuple:
        assert self.doc is not None
        return (
            self.doc.project.framework,
            tuple(
                (n.id, n.parent_id, n.z_index, n.type, n.name, n.visible, n.locked, n.page)
                for n in self.doc.project.nodes.values()
            ),
        )

    def refresh(self) -> None:
        if self.doc is None:
            return
        sig = self._signature()
        if sig == self._sig:
            return
        self._sig = sig
        selected = self.selected_ids()
        self._remember_expanded()
        self._populating = True
        self.tree.blockSignals(True)
        try:
            self.tree.clear()
            self._items.clear()
            self._build(self.doc.get_node(self.doc.project.root_id), None)
            self.tree.blockSignals(False)
            self._restore_expanded()
            self._select(selected)
        finally:
            self.tree.blockSignals(False)
            self._populating = False
        self._apply_filter()

    def _remember_expanded(self) -> None:
        for nid, it in self._items.items():
            if it.isExpanded():
                self._expanded.add(nid)
            else:
                self._expanded.discard(nid)

    def _restore_expanded(self) -> None:
        """Re-expand what the user had open; nodes never seen before start expanded."""
        for nid, it in self._items.items():
            if nid in self._expanded or nid not in self._known:
                it.setExpanded(True)
        self._known = set(self._items)

    def _build(self, node: Node, parent_item: QTreeWidgetItem | None) -> None:
        assert self.doc is not None
        spec = get_spec(node.type)
        item = QTreeWidgetItem([node.name, "", ""])
        item.setData(COL_NAME, ROLE_ID, node.id)
        pal = current_palette()
        item.setIcon(COL_NAME, glyph_icon(spec.icon, size=16))
        item.setIcon(
            COL_VIS,
            glyph_icon(
                "◉" if node.visible else "○", size=14, color=pal.text if node.visible else pal.muted
            ),
        )
        item.setIcon(
            COL_LOCK,
            glyph_icon(
                "🔒" if node.locked else "·", size=13, color=pal.text if node.locked else pal.muted
            ),
        )
        item.setToolTip(COL_VIS, "Visible" if node.visible else "Hidden")
        item.setToolTip(COL_LOCK, "Locked" if node.locked else "Unlocked")
        label = spec.label
        if not spec.supports(self.doc.project.framework):
            label += f" — not supported by {self.doc.project.framework}"
        item.setToolTip(COL_NAME, label)
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if node.type != "window":
            flags |= Qt.ItemFlag.ItemIsEditable | Qt.ItemFlag.ItemIsDragEnabled
        if spec.container:
            flags |= Qt.ItemFlag.ItemIsDropEnabled
        item.setFlags(flags)
        if not node.visible:
            f = QFont(item.font(COL_NAME))
            f.setItalic(True)
            item.setFont(COL_NAME, f)
            item.setForeground(COL_NAME, QBrush(QColor(pal.muted)))
        if not spec.supports(self.doc.project.framework):
            item.setForeground(COL_NAME, QBrush(QColor("#d97706")))
        if parent_item is None:
            self.tree.addTopLevelItem(item)
        else:
            parent_item.addChild(item)
        self._items[node.id] = item
        for kid in self.doc.children(node.id):
            self._build(kid, item)

    # ----------------------------------------------------------------------- selection
    def selected_ids(self) -> list[str]:
        return [i.data(COL_NAME, ROLE_ID) for i in self.tree.selectedItems()]

    def _select(self, ids: list[str]) -> None:
        for i in self.tree.selectedItems():
            i.setSelected(False)
        last = None
        for nid in ids:
            it = self._items.get(nid)
            if it is not None:
                it.setSelected(True)
                last = it
        if last is not None:
            self.tree.setCurrentItem(
                last, COL_NAME, self.tree.selectionModel().SelectionFlag.NoUpdate
            )
            p = last.parent()
            while p is not None:
                p.setExpanded(True)
                p = p.parent()
            self.tree.scrollToItem(last)

    def set_selection(self, ids: list[str]) -> None:
        """Programmatic selection sync (does not emit ``selectionChanged``)."""
        self.refresh()
        self.tree.blockSignals(True)
        try:
            self._select(ids)
        finally:
            self.tree.blockSignals(False)

    def _on_selection(self) -> None:
        if not self._populating:
            self.selectionChanged.emit(self.selected_ids())

    # ----------------------------------------------------------------------- clicks
    def _on_clicked(self, item: QTreeWidgetItem, col: int) -> None:
        if self.doc is None or self.history is None or col == COL_NAME:
            return
        nid = item.data(COL_NAME, ROLE_ID)
        node = self.doc.get_node(nid)
        if col == COL_VIS and node.type != "window":
            self._push(
                SetAttr(
                    nid,
                    "visible",
                    not node.visible,
                    label="Show widget" if not node.visible else "Hide widget",
                )
            )
        elif col == COL_LOCK and node.type != "window":
            self._push(
                SetAttr(
                    nid,
                    "locked",
                    not node.locked,
                    label="Lock widget" if not node.locked else "Unlock widget",
                )
            )

    def _on_double(self, item: QTreeWidgetItem, col: int) -> None:
        if self.doc is None or col != COL_NAME:
            return
        nid = item.data(COL_NAME, ROLE_ID)
        node = self.doc.get_node(nid)
        if node.type in ("window", "toplevel"):
            self.windowActivated.emit(nid)
        else:
            self.tree.editItem(item, COL_NAME)

    def start_rename(self, node_id: str) -> None:
        it = self._items.get(node_id)
        if it is not None and self.doc is not None and self.doc.get_node(node_id).type != "window":
            self.tree.editItem(it, COL_NAME)

    def _on_changed(self, item: QTreeWidgetItem, col: int) -> None:
        if self._populating or col != COL_NAME or self.doc is None:
            return
        nid = item.data(COL_NAME, ROLE_ID)
        node = self.doc.project.nodes.get(nid)
        text = item.text(COL_NAME).strip()
        if node is None or not text or text == node.name:
            self._sig = None
            self.refresh()
            return
        name = self.doc.unique_name(text, exclude=nid)
        self._push(SetAttr(nid, "name", name, label="Rename"))
        if name != text:
            self.message.emit(f"Name already in use; renamed to “{name}”.")

    def _on_context(self, pos: QPoint) -> None:
        item = self.tree.itemAt(pos)
        nid = item.data(COL_NAME, ROLE_ID) if item is not None else None
        if nid is not None and nid not in self.selected_ids():
            self.tree.clearSelection()
            item.setSelected(True)  # type: ignore[union-attr]
        self.contextMenuRequested.emit(nid, self.tree.viewport().mapToGlobal(pos))

    # ------------------------------------------------------------------------- drops
    def _on_drop(self, target: QTreeWidgetItem | None, ids: list[str], indicator: int) -> None:
        if self.doc is None or self.history is None:
            return
        doc = self.doc
        moving = [i for i in ids if doc.get_node(i).type not in ("window", "toplevel")]
        # drop ancestors-of-selected duplicates
        moving = [i for i in moving if not any(a.id in moving for a in doc.ancestors(i))]
        if not moving:
            return
        root = doc.project.root_id
        if target is None:
            parent_id, index = self._window_of_selection(moving), None
        else:
            tid = target.data(COL_NAME, ROLE_ID)
            tnode = doc.get_node(tid)
            on_item = indicator == QAbstractItemView.DropIndicatorPosition.OnItem.value
            if on_item or tnode.type == "window":
                parent_id, index = (
                    (tid, None)
                    if get_spec(tnode.type).container
                    else (tnode.parent_id or root, None)
                )
            else:
                parent_id = tnode.parent_id or root
                sibs = [k.id for k in doc.children(parent_id) if k.id not in moving]
                at = sibs.index(tid) if tid in sibs else len(sibs)
                above = indicator == QAbstractItemView.DropIndicatorPosition.AboveItem.value
                index = at if above else at + 1
        if any(parent_id in doc.subtree_ids(i) for i in moving):
            self.message.emit("A widget cannot be moved into itself.")
            return
        if parent_id == root and any(doc.get_node(i).type == "toplevel" for i in moving):
            return
        cmd = self._move_command(moving, parent_id, index)
        if cmd is not None:
            self._push(cmd)

    def _on_widget_drop(self, type_id: str, target: QTreeWidgetItem | None, indicator: int) -> None:
        if self.doc is None:
            return
        doc = self.doc
        root = doc.project.root_id
        if target is None:
            self.widgetDropRequested.emit(type_id, root, None)
            return
        tid = target.data(COL_NAME, ROLE_ID)
        tnode = doc.get_node(tid)
        on_item = indicator == QAbstractItemView.DropIndicatorPosition.OnItem.value
        if (on_item or tnode.type == "window") and get_spec(tnode.type).container:
            self.widgetDropRequested.emit(type_id, tid, None)
            return
        parent_id = tnode.parent_id or root
        sibs = [k.id for k in doc.children(parent_id)]
        at = sibs.index(tid) if tid in sibs else len(sibs)
        above = indicator == QAbstractItemView.DropIndicatorPosition.AboveItem.value
        self.widgetDropRequested.emit(type_id, parent_id, at if above else at + 1)

    def _window_of_selection(self, ids: list[str]) -> str:
        assert self.doc is not None
        return self.doc.window_of(ids[0]).id

    def _move_command(self, ids: list[str], parent_id: str, index: int | None) -> Command | None:
        assert self.doc is not None
        doc = self.doc
        parent = doc.get_node(parent_id)
        if not get_spec(parent.type).container:
            return None
        cmds: list[Command] = []
        page = current_page(parent) if is_paged(parent) else 0
        top = max((k.z_index for k in doc.children(parent_id)), default=-1) + 1
        for k, i in enumerate(ids):
            node = doc.get_node(i)
            if node.parent_id != parent_id:
                box = None
                if parent.layout is None or parent.layout.mode == "absolute":
                    box = Box(x=8.0 + 8 * k, y=8.0 + 8 * k, w=node.box.w, h=node.box.h)
                cmds.append(
                    ReparentNode(
                        i, parent_id, new_z_index=top + k, new_box=box, label="Move into container"
                    )
                )
            if node.page != page:
                cmds.append(SetAttr(i, "page", page, label="Move into container"))
        order = [k.id for k in doc.children(parent_id) if k.id not in ids]
        at = len(order) if index is None else min(index, len(order))
        order[at:at] = ids
        cmds.append(ReorderChildren(order, label="Reorder"))
        return Batch(cmds, label="Reorder / reparent")

    def _push(self, cmd: Command) -> None:
        assert self.doc is not None and self.history is not None
        try:
            self.history.push(self.doc, cmd)
        except ValueError as exc:
            self.message.emit(f"Cannot do that: {exc}")
            return
        self.documentEdited.emit()

    # -------------------------------------------------------------------------- filter
    def _apply_filter(self) -> None:
        q = self.filter.text().strip().lower()
        if self.doc is None:
            return

        def visit(item: QTreeWidgetItem) -> bool:
            nid = item.data(COL_NAME, ROLE_ID)
            node = self.doc.project.nodes.get(nid)  # type: ignore[union-attr]
            own = not q or (node is not None and (q in node.name.lower() or q in node.type.lower()))
            child_match = False
            for i in range(item.childCount()):
                child_match = visit(item.child(i)) or child_match
            show = own or child_match
            item.setHidden(not show)
            if q and child_match:
                item.setExpanded(True)
            return show

        for i in range(self.tree.topLevelItemCount()):
            visit(self.tree.topLevelItem(i))

    def visible_names(self) -> list[str]:
        out: list[str] = []

        def walk(it: QTreeWidgetItem) -> None:
            if not it.isHidden():
                out.append(it.text(COL_NAME))
            for i in range(it.childCount()):
                walk(it.child(i))

        for i in range(self.tree.topLevelItemCount()):
            walk(self.tree.topLevelItem(i))
        return out

    def item_for(self, node_id: str) -> QTreeWidgetItem | None:
        return self._items.get(node_id)
