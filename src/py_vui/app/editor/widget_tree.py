from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QMenu,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from py_vui.commands import BumpZIndex, RemoveSubtree, ReparentNode
from py_vui.model.document import ProjectDocument
from py_vui.model.nodes import FrameNode, WindowNode

if TYPE_CHECKING:
    from py_vui.commands.history import History


class WidgetTreePanel(QWidget):
    node_selected = Signal(str)
    structure_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._doc: ProjectDocument | None = None
        self._history: History | None = None
        self._block = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._tree.itemSelectionChanged.connect(self._on_select)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._context_menu)
        layout.addWidget(self._tree)

    def bind(self, doc: ProjectDocument, history: History) -> None:
        self._doc = doc
        self._history = history
        self.refresh()

    def refresh(self, *, select_id: str | None = None) -> None:
        if self._doc is None:
            return
        self._block = True
        self._tree.clear()
        root_id = self._doc.project.root_id
        root_node = self._doc.get_node(root_id)
        root_item = QTreeWidgetItem([f"{root_node.name} (window)"])
        root_item.setData(0, Qt.ItemDataRole.UserRole, root_id)
        self._tree.addTopLevelItem(root_item)

        def add_children(parent_item: QTreeWidgetItem, parent_id: str) -> None:
            for child in self._doc.children(parent_id):  # type: ignore[union-attr]
                label = f"{child.name} ({child.type})"
                item = QTreeWidgetItem([label])
                item.setData(0, Qt.ItemDataRole.UserRole, child.id)
                parent_item.addChild(item)
                add_children(item, child.id)

        add_children(root_item, root_id)
        root_item.setExpanded(True)
        if select_id:
            self._select_item_by_id(select_id)
        else:
            root_item.setSelected(True)
        self._block = False

    def _select_item_by_id(self, node_id: str) -> None:
        def walk(item: QTreeWidgetItem) -> QTreeWidgetItem | None:
            if item.data(0, Qt.ItemDataRole.UserRole) == node_id:
                return item
            for i in range(item.childCount()):
                found = walk(item.child(i))
                if found is not None:
                    return found
            return None

        for i in range(self._tree.topLevelItemCount()):
            found = walk(self._tree.topLevelItem(i))
            if found is not None:
                self._tree.setCurrentItem(found)
                return

    def _on_select(self) -> None:
        if self._block:
            return
        items = self._tree.selectedItems()
        if not items:
            return
        node_id = items[0].data(0, Qt.ItemDataRole.UserRole)
        if node_id:
            self.node_selected.emit(node_id)

    def _context_menu(self, pos) -> None:
        if self._doc is None or self._history is None:
            return
        item = self._tree.itemAt(pos)
        if item is None:
            return
        node_id = item.data(0, Qt.ItemDataRole.UserRole)
        if not node_id or node_id == self._doc.project.root_id:
            return
        menu = QMenu(self)
        reparent_menu = menu.addMenu("Move to parent")
        for candidate_id, label in self._valid_parents(node_id):
            act = reparent_menu.addAction(label)
            act.triggered.connect(
                lambda _checked=False, pid=candidate_id: self._reparent(node_id, pid)
            )
        menu.addSeparator()
        front = menu.addAction("Bring forward")
        front.triggered.connect(lambda: self._bump_z(node_id, 1))
        back = menu.addAction("Send backward")
        back.triggered.connect(lambda: self._bump_z(node_id, -1))
        menu.addSeparator()
        delete = menu.addAction("Delete")
        delete.triggered.connect(lambda: self._delete(node_id))
        menu.exec(self._tree.mapToGlobal(pos))

    def _valid_parents(self, node_id: str) -> list[tuple[str, str]]:
        assert self._doc is not None
        from py_vui.commands.builtins import collect_subtree_ids

        blocked = set(collect_subtree_ids(self._doc, node_id))
        out: list[tuple[str, str]] = []
        for nid, node in self._doc.project.nodes.items():
            if nid in blocked:
                continue
            if isinstance(node, (WindowNode, FrameNode)):
                out.append((nid, f"{node.name} ({node.type})"))
        return sorted(out, key=lambda x: x[1])

    def _reparent(self, node_id: str, new_parent_id: str) -> None:
        if self._doc is None or self._history is None:
            return
        self._history.push(
            self._doc,
            ReparentNode(node_id=node_id, new_parent_id=new_parent_id),
        )
        self.refresh(select_id=node_id)
        self.structure_changed.emit()

    def _bump_z(self, node_id: str, delta: int) -> None:
        if self._doc is None or self._history is None:
            return
        self._history.push(self._doc, BumpZIndex(node_id=node_id, delta=delta))
        self.refresh(select_id=node_id)
        self.structure_changed.emit()

    def _delete(self, node_id: str) -> None:
        if self._doc is None or self._history is None:
            return
        self._history.push(self._doc, RemoveSubtree(root_id=node_id))
        self.refresh(select_id=self._doc.project.root_id)
        self.structure_changed.emit()
