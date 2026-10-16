"""Menu bar designer: edits ``window.props["menus"]`` as a tree."""

from __future__ import annotations

import copy
import re
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from py_vui.app.editor.dialogs.common import add_buttons, make_dialog_base
from py_vui.commands import Batch, Command, History, SetField, SetHandler
from py_vui.core.document import ProjectDocument
from py_vui.core.model import HandlerDef

ROLE = Qt.ItemDataRole.UserRole
SEPARATOR_TEXT = "──────────"


def _slug(text: str) -> str:
    s = re.sub(r"[^0-9a-zA-Z]+", "_", text.strip()).strip("_").lower()
    return s or "item"


def _btn(text: str) -> QPushButton:
    b = QPushButton(text)
    b.setAutoDefault(False)
    return b


class MenuDesignerDialog(QDialog):
    def __init__(self, doc: ProjectDocument, history: History, node_id: str,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.doc, self.history, self.node_id = doc, history, node_id
        self._pending: dict[str, HandlerDef] = {}
        self._loading = False
        lay = make_dialog_base(self, "Menu designer", (760, 520))
        split = QSplitter(Qt.Orientation.Horizontal)
        lay.addWidget(split, 1)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["Menu / item", "Shortcut", "Handler"])
        self.tree.currentItemChanged.connect(self._on_current)
        ll.addWidget(self.tree, 1)
        row = QHBoxLayout()
        self.add_menu_btn = _btn("+ Menu")
        self.add_item_btn = _btn("+ Item")
        self.add_sep_btn = _btn("+ Separator")
        self.add_sub_btn = _btn("+ Submenu")
        for b in (self.add_menu_btn, self.add_item_btn, self.add_sep_btn, self.add_sub_btn):
            row.addWidget(b)
        ll.addLayout(row)
        row2 = QHBoxLayout()
        self.up_btn = _btn("Up")
        self.down_btn = _btn("Down")
        self.del_btn = _btn("Delete")
        for b in (self.up_btn, self.down_btn, self.del_btn):
            row2.addWidget(b)
        ll.addLayout(row2)
        split.addWidget(left)

        right = QWidget()
        form = QFormLayout(right)
        self.label_edit = QLineEdit()
        self.shortcut_edit = QLineEdit()
        self.shortcut_edit.setPlaceholderText("Ctrl+N")
        self.shortcut_note = QLabel("")
        self.checkable = QCheckBox("Checkable")
        self.handler_combo = QComboBox()
        self.new_handler_btn = _btn("New handler")
        hrow = QHBoxLayout()
        hrow.addWidget(self.handler_combo, 1)
        hrow.addWidget(self.new_handler_btn)
        form.addRow("Label", self.label_edit)
        form.addRow("Shortcut", self.shortcut_edit)
        form.addRow("", self.shortcut_note)
        form.addRow("", self.checkable)
        form.addRow("Handler", hrow)
        split.addWidget(right)
        split.setSizes([440, 300])
        self.buttons = add_buttons(self, lay)

        self.add_menu_btn.clicked.connect(lambda: self.add_menu())
        self.add_item_btn.clicked.connect(lambda: self.add_item())
        self.add_sep_btn.clicked.connect(lambda: self.add_item(separator=True))
        self.add_sub_btn.clicked.connect(lambda: self.add_item(submenu=True))
        self.del_btn.clicked.connect(self.delete_current)
        self.up_btn.clicked.connect(lambda: self.move_current(-1))
        self.down_btn.clicked.connect(lambda: self.move_current(1))
        self.label_edit.textEdited.connect(self._edit_label)
        self.shortcut_edit.textEdited.connect(self._edit_shortcut)
        self.checkable.toggled.connect(self._edit_checkable)
        self.handler_combo.activated.connect(self._edit_handler)
        self.new_handler_btn.clicked.connect(self.new_handler_for_current)

        menus = doc.project.nodes[node_id].props.get("menus") or []
        for m in menus:
            self._load_menu(m)
        self.tree.expandAll()
        if self.tree.topLevelItemCount():
            self.tree.setCurrentItem(self.tree.topLevelItem(0))
        self._on_current(self.tree.currentItem())

    # ----------------------------------------------------------- tree <-> data
    def _make_item(self, data: dict[str, Any], is_menu: bool) -> QTreeWidgetItem:
        it = QTreeWidgetItem()
        it.setData(0, ROLE, {k: v for k, v in data.items() if k != "items"})
        it.setData(1, ROLE, is_menu)
        it.setFlags(it.flags() | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
        self._paint(it)
        return it

    def _load_menu(self, m: dict[str, Any]) -> None:
        item = self._make_item({"title": m.get("title", "Menu")}, True)
        self.tree.addTopLevelItem(item)
        for sub in m.get("items", []):
            self._load_item(item, sub)

    def _load_item(self, parent: QTreeWidgetItem, d: dict[str, Any]) -> None:
        item = self._make_item(d, False)
        parent.addChild(item)
        for sub in d.get("items", []) or []:
            self._load_item(item, sub)

    def _data(self, item: QTreeWidgetItem) -> dict[str, Any]:
        return item.data(0, ROLE)

    def _is_menu(self, item: QTreeWidgetItem) -> bool:
        return bool(item.data(1, ROLE))

    def _paint(self, item: QTreeWidgetItem) -> None:
        d = self._data(item)
        if self._is_menu(item):
            item.setText(0, d.get("title", "Menu"))
            item.setText(1, "")
            item.setText(2, "")
            return
        if d.get("separator"):
            item.setText(0, SEPARATOR_TEXT)
            item.setText(1, "")
            item.setText(2, "")
            return
        label = d.get("label", "Item")
        if d.get("checkable"):
            label += "  [check]"
        item.setText(0, label)
        item.setText(1, d.get("shortcut", ""))
        item.setText(2, d.get("handler", ""))

    def _item_to_dict(self, item: QTreeWidgetItem) -> dict[str, Any]:
        d = copy.deepcopy(self._data(item))
        kids = [self._item_to_dict(item.child(i)) for i in range(item.childCount())]
        if self._is_menu(item):
            return {"title": d.get("title", "Menu"), "items": kids}
        out: dict[str, Any] = {k: v for k, v in d.items() if v not in ("", None, False)}
        if d.get("separator"):
            return {"label": "", "separator": True}
        out.setdefault("label", "Item")
        if kids or d.get("submenu"):
            out["items"] = kids
        out.pop("submenu", None)
        return out

    def menus(self) -> list[dict[str, Any]]:
        return [self._item_to_dict(self.tree.topLevelItem(i))
                for i in range(self.tree.topLevelItemCount())]

    # ----------------------------------------------------------- editing
    def _current(self) -> QTreeWidgetItem | None:
        return self.tree.currentItem()

    def add_menu(self, title: str = "Menu") -> QTreeWidgetItem:
        item = self._make_item({"title": title}, True)
        self.tree.addTopLevelItem(item)
        self.tree.setCurrentItem(item)
        return item

    def add_item(self, label: str = "Item", *, separator: bool = False, submenu: bool = False,
                 shortcut: str = "", handler: str = "", checkable: bool = False,
                 ) -> QTreeWidgetItem | None:
        cur = self._current()
        if cur is None:
            cur = self.add_menu()
        # items attach to a menu or submenu; a leaf item gets a sibling
        parent = cur if (self._is_menu(cur) or cur.data(0, ROLE).get("submenu")
                         or cur.childCount()) else (cur.parent() or cur)
        data: dict[str, Any] = {"label": label}
        if separator:
            data = {"label": "", "separator": True}
        if submenu:
            data["submenu"] = True
        if shortcut:
            data["shortcut"] = shortcut
        if handler:
            data["handler"] = handler
        if checkable:
            data["checkable"] = True
        item = self._make_item(data, False)
        parent.addChild(item)
        parent.setExpanded(True)
        self.tree.setCurrentItem(item)
        return item

    def delete_current(self) -> None:
        cur = self._current()
        if cur is None:
            return
        parent = cur.parent()
        if parent is None:
            self.tree.takeTopLevelItem(self.tree.indexOfTopLevelItem(cur))
        else:
            parent.removeChild(cur)

    def move_current(self, delta: int) -> None:
        cur = self._current()
        if cur is None:
            return
        parent = cur.parent()
        if parent is None:
            i = self.tree.indexOfTopLevelItem(cur)
            j = i + delta
            if 0 <= j < self.tree.topLevelItemCount():
                self.tree.takeTopLevelItem(i)
                self.tree.insertTopLevelItem(j, cur)
        else:
            i = parent.indexOfChild(cur)
            j = i + delta
            if 0 <= j < parent.childCount():
                parent.takeChild(i)
                parent.insertChild(j, cur)
        self.tree.setCurrentItem(cur)

    def _update(self, **changes: Any) -> None:
        cur = self._current()
        if cur is None or self._loading:
            return
        d = dict(self._data(cur))
        d.update(changes)
        cur.setData(0, ROLE, d)
        self._paint(cur)

    def _edit_label(self, text: str) -> None:
        cur = self._current()
        if cur is not None:
            self._update(**({"title": text} if self._is_menu(cur) else {"label": text}))

    def _edit_shortcut(self, text: str) -> None:
        seq = QKeySequence(text)
        ok = not text or not seq.isEmpty()
        self.shortcut_note.setText("" if ok else "Unrecognised shortcut")
        if ok:
            self._update(shortcut=text)

    def _edit_checkable(self, on: bool) -> None:
        self._update(checkable=bool(on))

    def _edit_handler(self, _index: int) -> None:
        self._update(handler=self.handler_combo.currentData() or "")

    def handler_names(self) -> list[str]:
        return sorted(set(self.doc.project.handlers) | set(self._pending))

    def new_handler_for_current(self) -> str | None:
        cur = self._current()
        if cur is None or self._is_menu(cur) or self._data(cur).get("separator"):
            return None
        base = f"menu_{_slug(self._data(cur).get('label', 'item'))}"
        name, i = base, 2
        while name in self.handler_names():
            name = f"{base}_{i}"
            i += 1
        label = self._data(cur).get("label", "item")
        self._pending[name] = HandlerDef(name=name, body=f'print("Menu: {label}")'.replace("\\", ""))
        self._fill_handlers(name)
        self._update(handler=name)
        return name

    def _fill_handlers(self, selected: str = "") -> None:
        self.handler_combo.clear()
        self.handler_combo.addItem("(none)", "")
        for h in self.handler_names():
            self.handler_combo.addItem(h, h)
        self.handler_combo.setCurrentIndex(max(self.handler_combo.findData(selected), 0))

    def _on_current(self, item: QTreeWidgetItem | None, _prev: Any = None) -> None:
        self._loading = True
        try:
            has = item is not None
            is_menu = has and self._is_menu(item)  # type: ignore[arg-type]
            d = self._data(item) if has else {}  # type: ignore[arg-type]
            sep = bool(d.get("separator"))
            self.label_edit.setText(d.get("title", "") if is_menu else d.get("label", ""))
            self.shortcut_edit.setText(d.get("shortcut", ""))
            self.checkable.setChecked(bool(d.get("checkable")))
            self._fill_handlers(d.get("handler", ""))
            editable_item = has and not is_menu and not sep
            self.label_edit.setEnabled(has and not sep)
            for w in (self.shortcut_edit, self.checkable, self.handler_combo,
                      self.new_handler_btn):
                w.setEnabled(editable_item)
            for b in (self.del_btn, self.up_btn, self.down_btn):
                b.setEnabled(has)
        finally:
            self._loading = False

    # ----------------------------------------------------------- saving
    def save(self) -> None:
        menus = self.menus()
        node = self.doc.project.nodes[self.node_id]
        used: set[str] = set()

        def collect(items: list[dict[str, Any]]) -> None:
            for it in items:
                if it.get("handler"):
                    used.add(it["handler"])
                collect(it.get("items", []))

        collect(menus)
        cmds: list[Command] = [
            SetHandler(n, h, label="New handler") for n, h in self._pending.items()
            if n in used and n not in self.doc.project.handlers
        ]
        if menus != (node.props.get("menus") or []):
            cmds.append(SetField(self.node_id, "props", "menus", menus, label="Edit menus"))
        if cmds:
            self.history.push(self.doc, Batch(cmds, label="Edit menus"))

    def accept(self) -> None:
        self.save()
        super().accept()
