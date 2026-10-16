"""Widget tree: rename, visibility / lock toggles, reparent, filter, selection sync."""

from __future__ import annotations

import pytest
from editor_support import add_nodes, dispose, home, make_window, qapp  # noqa: F401
from PySide6.QtWidgets import QAbstractItemView

from py_vui.app.editor.widget_tree import COL_LOCK, COL_NAME, COL_VIS

pytestmark = pytest.mark.gui

ON = QAbstractItemView.DropIndicatorPosition.OnItem.value
ABOVE = QAbstractItemView.DropIndicatorPosition.AboveItem.value
BELOW = QAbstractItemView.DropIndicatorPosition.BelowItem.value


@pytest.fixture
def win(qapp, home, tmp_path):  # noqa: F811
    w = make_window(tmp_path)
    yield w
    dispose(w)


def test_tree_mirrors_hierarchy(win):
    (frame,) = add_nodes(win, ("frame", dict(x=10, y=10, w=200, h=100, name="Box")))
    (k,) = add_nodes(win, ("button", dict(parent_id=frame, name="Inner")))
    root_item = win.tree.tree.topLevelItem(0)
    assert root_item.text(COL_NAME) == "Main Window"
    box_item = win.tree.item_for(frame)
    assert box_item.parent() is root_item
    assert win.tree.item_for(k).parent() is box_item


def test_tree_selection_syncs_both_ways(win):
    a, b = add_nodes(
        win, ("button", dict(x=10, y=10, name="A")), ("label", dict(x=10, y=60, name="B"))
    )
    win.tree.item_for(b).setSelected(True)
    win.tree.tree.setCurrentItem(win.tree.item_for(b))
    assert win.canvas.selection == [b]
    win.select([a])
    assert win.tree.selected_ids() == [a]
    # multi-select from the tree
    win.tree.item_for(a).setSelected(True)
    win.tree.item_for(b).setSelected(True)
    assert set(win.canvas.selection) == {a, b}


def test_rename_through_tree_is_unique_and_undoable(win):
    a, b = add_nodes(
        win, ("button", dict(x=10, y=10, name="A")), ("button", dict(x=10, y=60, name="B"))
    )
    item = win.tree.item_for(b)
    item.setText(COL_NAME, "A")  # clash
    assert win.doc.get_node(b).name == "A 2"
    item = win.tree.item_for(b)
    item.setText(COL_NAME, "Fancy")
    assert win.doc.get_node(b).name == "Fancy"
    win.do_undo()  # consecutive renames of one widget coalesce into a single undo step
    assert win.doc.get_node(b).name == "B"
    assert win.tree.item_for(b).text(COL_NAME) == "B"
    # empty names are rejected
    win.tree.item_for(b).setText(COL_NAME, "  ")
    assert win.doc.get_node(b).name == "B"
    assert a


def test_visibility_and_lock_columns(win):
    (a,) = add_nodes(win, ("button", dict(x=10, y=10, name="A")))
    win.tree._on_clicked(win.tree.item_for(a), COL_VIS)
    assert win.doc.get_node(a).visible is False
    assert not win.canvas.item_for(a).isVisible()
    win.tree._on_clicked(win.tree.item_for(a), COL_VIS)
    assert win.doc.get_node(a).visible is True
    win.tree._on_clicked(win.tree.item_for(a), COL_LOCK)
    assert win.doc.get_node(a).locked is True
    # the main window cannot be hidden or locked
    root = win.doc.project.root_id
    win.tree._on_clicked(win.tree.item_for(root), COL_VIS)
    assert win.doc.get_node(root).visible is True


def test_drop_on_container_reparents(win):
    (frame,) = add_nodes(win, ("frame", dict(x=10, y=10, w=200, h=100, name="Box")))
    (a,) = add_nodes(win, ("button", dict(x=300, y=10, name="A")))
    win.tree._on_drop(win.tree.item_for(frame), [a], ON)
    assert win.doc.get_node(a).parent_id == frame
    win.do_undo()
    assert win.doc.get_node(a).parent_id == win.doc.project.root_id


def test_drop_above_and_below_reorders_siblings(win):
    a, b, c = add_nodes(
        win,
        ("button", dict(x=10, y=10, name="A")),
        ("button", dict(x=10, y=60, name="B")),
        ("button", dict(x=10, y=110, name="C")),
    )
    order = lambda: [n.id for n in win.doc.children(win.doc.project.root_id)]  # noqa: E731
    win.tree._on_drop(win.tree.item_for(a), [c], ABOVE)
    assert order() == [c, a, b]
    win.tree._on_drop(win.tree.item_for(b), [c], BELOW)
    assert order() == [a, b, c]


def test_cannot_drop_into_own_subtree_or_move_windows(win):
    (frame,) = add_nodes(win, ("frame", dict(x=10, y=10, w=200, h=100)))
    (inner,) = add_nodes(win, ("frame", dict(parent_id=frame, x=5, y=5, w=50, h=50)))
    win.tree._on_drop(win.tree.item_for(inner), [frame], ON)
    assert win.doc.get_node(frame).parent_id == win.doc.project.root_id
    win.tree._on_drop(win.tree.item_for(frame), [win.doc.project.root_id], ON)
    assert win.doc.get_node(win.doc.project.root_id).parent_id is None


def test_drop_non_container_inserts_beside_it(win):
    (frame,) = add_nodes(win, ("frame", dict(x=10, y=10, w=200, h=100)))
    (k,) = add_nodes(win, ("button", dict(parent_id=frame, name="K")))
    (a,) = add_nodes(win, ("label", dict(x=300, y=10, name="A")))
    win.tree._on_drop(win.tree.item_for(k), [a], ON)  # a button is not a container
    assert win.doc.get_node(a).parent_id == frame


def test_filter_and_dialog_activation(win):
    add_nodes(
        win, ("button", dict(x=10, y=10, name="Alpha")), ("label", dict(x=10, y=60, name="Beta"))
    )
    win.tree.filter.setText("alp")
    names = win.tree.visible_names()
    assert "Alpha" in names and "Beta" not in names and "Main Window" in names
    win.tree.filter.setText("")
    assert "Beta" in win.tree.visible_names()
    win.do_add_dialog()
    dlg = win.doc.windows()[1].id
    win.switch_window(win.doc.project.root_id)
    win.tree._on_double(win.tree.item_for(dlg), COL_NAME)
    assert win.canvas.window_id == dlg


def test_tree_context_menu_signal(win):
    (a,) = add_nodes(win, ("button", dict(x=10, y=10)))
    got = []
    win.tree.contextMenuRequested.disconnect()  # do not open a modal menu in tests
    win.tree.contextMenuRequested.connect(lambda nid, pos: got.append(nid))
    item = win.tree.item_for(a)
    rect = win.tree.tree.visualItemRect(item)
    win.tree._on_context(rect.center())
    assert got == [a]


def test_palette_widget_dropped_on_tree(win):
    from PySide6.QtCore import QMimeData, QPointF, Qt
    from PySide6.QtGui import QDropEvent

    from py_vui.app.editor.mime import MIME_WIDGET

    (frame,) = add_nodes(win, ("frame", dict(x=10, y=10, w=200, h=100, name="Box")))
    a, b = add_nodes(
        win,
        ("button", dict(parent_id=frame, name="A")),
        ("button", dict(parent_id=frame, name="B")),
    )
    # onto the container: appended inside it
    win.tree._on_widget_drop("label", win.tree.item_for(frame), ON)
    kids = [n for n in win.doc.children(frame)]
    assert kids[-1].type == "label"
    # above button B: inserted between A and B
    win.tree._on_widget_drop("checkbox", win.tree.item_for(b), ABOVE)
    ids = [n.id for n in win.doc.children(frame)]
    check = next(n.id for n in win.doc.children(frame) if n.type == "checkbox")
    assert ids.index(check) + 1 == ids.index(b)
    # a real drop event on the viewport goes through the same path
    mime = QMimeData()
    mime.setData(MIME_WIDGET, b"slider")
    pos = QPointF(win.tree.tree.visualItemRect(win.tree.item_for(frame)).center())
    ev = QDropEvent(
        pos,
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    win.tree.tree.dropEvent(ev)
    assert any(n.type == "slider" for n in win.doc.project.nodes.values())
    assert a
