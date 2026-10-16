"""Edit operations: clipboard, grouping, align / distribute, z-order, flags, tabs."""

from __future__ import annotations

import pytest
from editor_support import (
    add_nodes,
    centre,
    click,
    dispose,
    home,  # noqa: F401
    make_window,
    qapp,  # noqa: F401
)
from PySide6.QtWidgets import QApplication

from py_vui.core.model import ContainerLayout

pytestmark = pytest.mark.gui


@pytest.fixture
def win(qapp, home, tmp_path):  # noqa: F811
    w = make_window(tmp_path)
    w.canvas.snap_to_grid = False
    yield w
    dispose(w)


def pos(win, nid):
    b = win.doc.get_node(nid).box
    return (b.x, b.y)


def test_copy_paste_duplicate_cut(win):
    (a,) = add_nodes(win, ("button", dict(x=50, y=60, name="Go")))
    win.select([a])
    win.do_copy()
    assert QApplication.clipboard().mimeData().hasText()
    win.do_paste()
    names = sorted(n.name for n in win.doc.project.nodes.values() if n.type == "button")
    assert names == ["Go", "Go 2"]
    pasted = win.canvas.selection[0]
    assert pos(win, pasted) == (66, 76)  # offset by 16
    win.do_duplicate()
    assert len([n for n in win.doc.project.nodes.values() if n.type == "button"]) == 3
    win.select([a])
    win.do_cut()
    assert a not in win.doc.project.nodes
    win.do_undo()
    assert a in win.doc.project.nodes


def test_paste_into_selected_container(win):
    (frame,) = add_nodes(win, ("frame", dict(x=200, y=100, w=200, h=150)))
    (a,) = add_nodes(win, ("label", dict(x=10, y=10)))
    win.select([a])
    win.do_copy()
    win.select([frame])
    win.do_paste()
    new = win.canvas.selection[0]
    assert win.doc.get_node(new).parent_id == frame


def test_group_and_ungroup_keep_geometry(win):
    a, b = add_nodes(
        win,
        ("button", dict(x=100, y=100, w=80, h=30, name="A")),
        ("button", dict(x=220, y=160, w=80, h=30, name="B")),
    )
    before = {i: win.canvas.node_scene_rect(i) for i in (a, b)}
    win.select([a, b])
    n = len(win.history.undo_stack)
    win.do_group()
    assert len(win.history.undo_stack) == n + 1
    frame = win.canvas.selection[0]
    assert win.doc.get_node(frame).type == "frame"
    assert win.doc.get_node(a).parent_id == frame == win.doc.get_node(b).parent_id
    for i in (a, b):  # visual position unchanged
        assert win.canvas.node_scene_rect(i) == before[i]
    win.select([frame])
    win.do_ungroup()
    assert frame not in win.doc.project.nodes
    assert win.doc.get_node(a).parent_id == win.doc.project.root_id
    for i in (a, b):
        assert win.canvas.node_scene_rect(i) == before[i]


def test_wrap_in_group_box_and_tabs(win):
    (a,) = add_nodes(win, ("label", dict(x=100, y=100, w=80, h=30)))
    before = win.canvas.node_scene_rect(a)
    win.select([a])
    win.wrap_selection("label_frame")
    assert win.doc.get_node(win.canvas.selection[0]).type == "label_frame"
    assert win.canvas.node_scene_rect(a) == before
    win.do_undo()
    assert win.doc.get_node(a).parent_id == win.doc.project.root_id


def test_align_distribute_and_same_size(win):
    a, b, c = add_nodes(
        win,
        ("button", dict(x=10, y=10, w=60, h=30, name="A")),
        ("button", dict(x=100, y=80, w=80, h=40, name="B")),
        ("button", dict(x=400, y=30, w=100, h=20, name="C")),
    )
    win.select([a, b, c])
    win.do_align_left()
    assert [pos(win, i)[0] for i in (a, b, c)] == [10, 10, 10]
    win.do_align_top()
    assert [pos(win, i)[1] for i in (a, b, c)] == [10, 10, 10]
    win.do_undo()
    win.do_undo()
    win.select([a, b, c])
    win.do_distribute_h()
    xs = sorted(pos(win, i)[0] for i in (a, b, c))
    gaps = [xs[1] - (xs[0] + 60), xs[2] - (xs[1] + 80)] if pos(win, a)[0] == xs[0] else None
    assert xs[0] == 10 and xs[-1] == 400
    assert gaps is None or abs(gaps[0] - gaps[1]) < 1.5
    win.select([a, b])
    win.do_same_size()
    assert win.doc.get_node(b).box.w == 60 and win.doc.get_node(b).box.h == 30
    # a single widget aligns to its parent
    win.select([a])
    win.do_align_right()
    assert pos(win, a)[0] == 640 - 60


def test_align_refuses_non_absolute_container(win):
    (frame,) = add_nodes(win, ("frame", dict(x=10, y=10, w=300, h=200)))
    win.doc.get_node(frame).layout = ContainerLayout(mode="flex")
    k1, k2 = add_nodes(
        win,
        ("button", dict(parent_id=frame, w=50, h=20)),
        ("button", dict(parent_id=frame, w=50, h=20)),
    )
    win.select([k1, k2])
    n = len(win.history.undo_stack)
    win.do_align_left()
    assert len(win.history.undo_stack) == n


def test_z_order_actions(win):
    a, b, c = add_nodes(
        win,
        ("button", dict(x=10, y=10, name="A")),
        ("button", dict(x=20, y=20, name="B")),
        ("button", dict(x=30, y=30, name="C")),
    )
    order = lambda: [n.id for n in win.doc.children(win.doc.project.root_id)]  # noqa: E731
    win.select([a])
    win.do_z_front()
    assert order() == [b, c, a]
    win.do_z_back()
    assert order() == [a, b, c]
    win.do_z_forward()
    assert order() == [b, a, c]
    win.do_z_backward()
    assert order() == [a, b, c]
    win.select([a, b])
    win.do_z_front()
    assert order() == [c, a, b]


def test_lock_and_hide_toggles_and_locked_delete_guard(win):
    a, b = add_nodes(win, ("button", dict(x=10, y=10)), ("button", dict(x=100, y=10)))
    win.select([a, b])
    win.toggle_selection_flag("locked")
    assert win.doc.get_node(a).locked and win.doc.get_node(b).locked
    win.do_delete()
    assert a in win.doc.project.nodes  # locked nodes are not deleted
    win.toggle_selection_flag("locked")
    assert not win.doc.get_node(a).locked
    win.toggle_selection_flag("visible")
    assert not win.doc.get_node(a).visible
    assert not win.canvas.item_for(a).isVisible()
    win.do_undo()
    assert win.canvas.item_for(a).isVisible()


def test_select_all_selects_siblings(win):
    a, b = add_nodes(win, ("button", dict(x=10, y=10)), ("label", dict(x=100, y=10)))
    win.select([a])
    win.do_select_all()
    assert set(win.canvas.selection) == {a, b}


def test_tab_add_and_remove(win):
    (tabs,) = add_nodes(win, ("tabview", dict(x=10, y=10, w=300, h=200)))
    (k,) = add_nodes(win, ("button", dict(parent_id=tabs, x=10, y=10)))
    win.add_tab(tabs)
    node = win.doc.get_node(tabs)
    assert node.props["tabs"] == ["Tab 1", "Tab 2", "Tab 3"] and node.props["current"] == 2
    win.doc.get_node(k).page = 2
    win.remove_tab(tabs)
    assert node.props["tabs"] == ["Tab 1", "Tab 2"]
    assert k not in win.doc.project.nodes  # children of the removed page go with it
    win.do_undo()
    assert k in win.doc.project.nodes and len(node.props["tabs"]) == 3


def test_add_dialog_window_and_tabs_switch_canvas(win):
    win.do_add_dialog()
    wins = win.doc.windows()
    assert len(wins) == 2 and wins[1].type == "toplevel"
    assert win.canvas.window_id == wins[1].id
    assert win.host.tabs.count() == 3
    nid = win.canvas.add_widget("button")
    assert win.doc.get_node(nid).parent_id == wins[1].id
    win.host.tabs.setCurrentIndex(0)
    assert win.canvas.window_id == win.doc.project.root_id
    assert win.canvas.item_for(nid) is None  # other window's widgets are not in this scene
    # selecting a node of the dialog switches to it
    win.select([nid])
    assert win.canvas.window_id == wins[1].id
    assert win.host.tabs.currentIndex() == 1


def test_insert_widget_avoids_overlap_and_uses_selected_container(win):
    win.canvas.add_widget("button")
    win.canvas.add_widget("button")
    rects = [
        win.canvas.node_scene_rect(n.id)
        for n in win.doc.project.nodes.values()
        if n.type == "button"
    ]
    assert not rects[0].intersects(rects[1])
    (frame,) = add_nodes(win, ("frame", dict(x=300, y=100, w=250, h=200)))
    win.select([frame])
    nid = win.canvas.add_widget("label")
    assert win.doc.get_node(nid).parent_id == frame


def test_undo_redo_labels_come_from_history(win):
    win.canvas.add_widget("slider")
    assert win.act["undo"].text() == "&Undo Add Slider"
    click(win.canvas, centre(win.canvas, win.canvas.selection[0]))
    win.do_undo()
    assert win.act["redo"].text() == "&Redo Add Slider"
