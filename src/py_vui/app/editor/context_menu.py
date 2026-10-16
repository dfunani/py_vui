"""Right-click menu shared by the canvas and the widget tree."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu

from py_vui.app.editor.edit_ops import WRAP_TYPES
from py_vui.core.registry import get_spec

if TYPE_CHECKING:
    from py_vui.app.editor.main_window import MainWindow


def build_context_menu(mw: MainWindow, node_id: str | None) -> QMenu:
    a = mw.act
    menu = QMenu(mw)
    doc = mw.doc
    node = doc.project.nodes.get(node_id) if node_id else None
    is_window = node is not None and node.type in ("window", "toplevel")
    if node is not None and not is_window:
        for k in ("cut", "copy", "paste", "duplicate", "delete"):
            menu.addAction(a[k])
        menu.addAction(a["rename"])
        menu.addSeparator()
        arrange = menu.addMenu("Align")
        for k in (
            "align_left",
            "align_center",
            "align_right",
            "align_top",
            "align_middle",
            "align_bottom",
        ):
            arrange.addAction(a[k])
        arrange.addSeparator()
        for k in ("distribute_h", "distribute_v", "same_width", "same_height", "same_size"):
            arrange.addAction(a[k])
        order = menu.addMenu("Order")
        for k in ("z_front", "z_forward", "z_backward", "z_back"):
            order.addAction(a[k])
        menu.addSeparator()
        menu.addAction(a["group"])
        if get_spec(node.type).container:
            menu.addAction(a["ungroup"])
        wrap = menu.addMenu("Wrap in…")
        for t in WRAP_TYPES:
            act = QAction(get_spec(t).label, wrap)
            act.triggered.connect(lambda _=False, tt=t: mw.wrap_selection(tt))
            wrap.addAction(act)
        menu.addSeparator()
        lock = QAction("Unlock" if node.locked else "Lock", menu)
        lock.triggered.connect(lambda _=False: mw.toggle_selection_flag("locked"))
        hide = QAction("Show" if not node.visible else "Hide", menu)
        hide.triggered.connect(lambda _=False: mw.toggle_selection_flag("visible"))
        menu.addAction(lock)
        menu.addAction(hide)
        handlers = [h for h in node.events.values() if h in doc.project.handlers]
        if handlers:
            menu.addSeparator()
            for h in dict.fromkeys(handlers):
                act = QAction(f"Edit handler “{h}”", menu)
                act.triggered.connect(lambda _=False, name=h: mw.open_handler(name))
                menu.addAction(act)
        if node.type == "tabview":
            menu.addSeparator()
            add = QAction("Add tab", menu)
            add.triggered.connect(lambda _=False, nid=node.id: mw.add_tab(nid))
            menu.addAction(add)
            rm = QAction("Remove current tab", menu)
            rm.triggered.connect(lambda _=False, nid=node.id: mw.remove_tab(nid))
            menu.addAction(rm)
    else:
        menu.addAction(a["paste"])
        menu.addAction(a["select_all"])
        menu.addSeparator()
        menu.addAction(a["add_dialog"])
        if node is not None and node.type == "window":
            menu.addAction(a["menus"])
        menu.addAction(a["theme"])
    return menu
