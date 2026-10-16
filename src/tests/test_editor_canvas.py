"""Canvas interaction through synthesized mouse / key events."""

from __future__ import annotations

import pytest
from editor_support import (
    add_nodes,
    centre,
    click,
    dispose,
    drag,
    home,  # noqa: F401
    make_window,
    move,
    press,
    qapp,  # noqa: F401
    release,
)
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtCore import QPointF as P
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from py_vui.app.editor.canvas_drop import content_origin_abs
from py_vui.app.editor.canvas_geometry import grid_geometry
from py_vui.core.model import ContainerLayout

pytestmark = pytest.mark.gui


@pytest.fixture
def win(qapp, home, tmp_path):  # noqa: F811
    w = make_window(tmp_path)
    w.canvas.snap_to_grid = False
    w.canvas.smart_guides = False
    w.resize(1400, 900)
    w.canvas.actual_size()  # 1:1 so view <-> scene conversions are exact
    yield w
    dispose(w)


def box(win, nid):
    b = win.doc.get_node(nid).box
    return (b.x, b.y, b.w, b.h)


def test_click_selects_and_syncs_tree_and_status(win):
    (a, b) = add_nodes(
        win, ("button", dict(x=100, y=100, name="A")), ("label", dict(x=300, y=200, name="B"))
    )
    click(win.canvas, centre(win.canvas, a))
    assert win.canvas.selection == [a]
    assert win.tree.selected_ids() == [a]
    assert "A: 110 × 34" in win.status.sel_label.text()
    click(win.canvas, centre(win.canvas, b))
    assert win.canvas.selection == [b]
    # clicking empty window space selects the window itself
    click(win.canvas, (600, 400))
    assert win.canvas.selection == [win.doc.project.root_id]


def test_drag_moves_widget_as_one_undo_step(win):
    (a,) = add_nodes(win, ("button", dict(x=100, y=100, name="A")))
    n_before = len(win.history.undo_stack)
    c = centre(win.canvas, a)
    drag(win.canvas, c, (c[0] + 40, c[1] + 20), steps=8)
    assert box(win, a)[:2] == (140, 120)
    assert len(win.history.undo_stack) == n_before + 1
    win.do_undo()
    assert box(win, a)[:2] == (100, 100)
    win.do_redo()
    assert box(win, a)[:2] == (140, 120)


def test_click_without_moving_does_not_edit(win):
    (a,) = add_nodes(win, ("button", dict(x=100, y=100)))
    n = len(win.history.undo_stack)
    click(win.canvas, centre(win.canvas, a))
    assert len(win.history.undo_stack) == n


def test_drag_snaps_to_grid(win):
    win.canvas.snap_to_grid = True
    win.canvas.grid_size = 8
    (a,) = add_nodes(win, ("button", dict(x=100, y=100)))
    c = centre(win.canvas, a)
    drag(win.canvas, c, (c[0] + 13, c[1] + 11))
    x, y, _, _ = box(win, a)
    assert x % 8 == 0 and y % 8 == 0


def test_smart_guides_snap_to_sibling_and_user_guide(win):
    win.canvas.smart_guides = True
    a, b = add_nodes(
        win, ("button", dict(x=100, y=100, name="A")), ("button", dict(x=300, y=250, name="B"))
    )
    c = centre(win.canvas, b)
    # left edge of B ends 3px from A's left edge -> snaps exactly
    drag(win.canvas, c, (c[0] - 200 + 3, c[1]))
    assert box(win, b)[0] == 100
    # a user guide at x=400 attracts the left edge too
    win.canvas.begin_ruler_drag("v", 0)
    win.canvas.update_ruler_drag(QPointF(400, 0))
    win.canvas.end_ruler_drag(QPointF(400, 0))
    assert win.doc.project.editor["guides"][win.canvas.window_id]["v"] == [400]
    c = centre(win.canvas, b)
    drag(win.canvas, c, (c[0] + 300 - 2, c[1]))
    assert box(win, b)[0] == 400
    win.do_undo()  # undo the move
    win.do_undo()  # undo the guide
    assert "guides" not in win.doc.project.editor or not win.doc.project.editor["guides"]


def test_resize_with_handles(win):
    (a,) = add_nodes(win, ("button", dict(x=100, y=100, w=100, h=40)))
    click(win.canvas, centre(win.canvas, a))
    rect = win.canvas.node_scene_rect(a)
    n = len(win.history.undo_stack)
    drag(win.canvas, (rect.right(), rect.bottom()), (rect.right() + 30, rect.bottom() + 20))
    assert box(win, a) == (100, 100, 130, 60)
    assert len(win.history.undo_stack) == n + 1
    rect = win.canvas.node_scene_rect(a)
    drag(win.canvas, (rect.left(), rect.top()), (rect.left() + 20, rect.top() + 10))
    assert box(win, a) == (120, 110, 110, 50)
    win.do_undo()
    win.do_undo()
    assert box(win, a) == (100, 100, 100, 40)


def test_resize_respects_minimum_size(win):
    (a,) = add_nodes(win, ("button", dict(x=100, y=100, w=100, h=40)))
    click(win.canvas, centre(win.canvas, a))
    rect = win.canvas.node_scene_rect(a)
    drag(win.canvas, (rect.right(), rect.bottom()), (rect.left() - 80, rect.top() - 80))
    _, _, w, h = box(win, a)
    assert w >= 8 and h >= 8


def test_multi_select_shift_and_rubber_band_and_group_move(win):
    a, b, c = add_nodes(
        win,
        ("button", dict(x=50, y=50, name="A")),
        ("button", dict(x=250, y=50, name="B")),
        ("button", dict(x=450, y=300, name="C")),
    )
    click(win.canvas, centre(win.canvas, a))
    click(win.canvas, centre(win.canvas, b), Qt.KeyboardModifier.ShiftModifier)
    assert set(win.canvas.selection) == {a, b}
    click(win.canvas, centre(win.canvas, b), Qt.KeyboardModifier.ShiftModifier)  # toggle off
    assert win.canvas.selection == [a]
    # rubber band from empty space around A and B
    drag(win.canvas, (20, 20), (400, 130))
    assert set(win.canvas.selection) == {a, b}
    n = len(win.history.undo_stack)
    ca = centre(win.canvas, a)
    drag(win.canvas, ca, (ca[0] + 10, ca[1] + 30))
    assert box(win, a)[:2] == (60, 80) and box(win, b)[:2] == (260, 80)
    assert len(win.history.undo_stack) == n + 1  # one step for both
    assert box(win, c)[:2] == (450, 300)


def test_nudge_with_arrow_keys_coalesces(win):
    (a,) = add_nodes(win, ("button", dict(x=100, y=100)))
    click(win.canvas, centre(win.canvas, a))
    n = len(win.history.undo_stack)
    for _ in range(3):
        QTest.keyClick(win.canvas, Qt.Key.Key_Right)
    QTest.keyClick(win.canvas, Qt.Key.Key_Down)
    assert box(win, a)[:2] == (103, 101)
    assert len(win.history.undo_stack) == n + 1
    QTest.keyClick(win.canvas, Qt.Key.Key_Left, Qt.KeyboardModifier.ShiftModifier)
    assert box(win, a)[0] == 93  # Shift = 10 px
    assert len(win.history.undo_stack) == n + 1  # a burst of nudges is a single undo step
    win.do_undo()
    assert box(win, a)[:2] == (100, 100)


def test_locked_widgets_do_not_move_or_resize_but_can_be_selected(win):
    (a,) = add_nodes(win, ("button", dict(x=100, y=100, w=100, h=40)))
    win.doc.get_node(a).locked = True
    win.canvas.refresh()
    c = centre(win.canvas, a)
    drag(win.canvas, c, (c[0] + 50, c[1] + 50))
    assert box(win, a)[:2] == (100, 100)
    assert win.canvas.selection == [a]
    QTest.keyClick(win.canvas, Qt.Key.Key_Right)
    assert box(win, a)[0] == 100


def test_delete_key_and_undo(win):
    (a,) = add_nodes(win, ("button", dict(x=100, y=100)))
    click(win.canvas, centre(win.canvas, a))
    win.act["delete"].trigger()
    assert a not in win.doc.project.nodes
    assert win.canvas.selection == [win.doc.project.root_id]
    win.do_undo()
    assert a in win.doc.project.nodes


def test_drag_into_container_reparents_in_one_step(win):
    (frame,) = add_nodes(win, ("frame", dict(x=300, y=100, w=200, h=150, name="Box")))
    (a,) = add_nodes(win, ("button", dict(x=20, y=20, w=100, h=40, name="Btn")))
    n = len(win.history.undo_stack)
    c = centre(win.canvas, a)
    target = (400, 170)
    drag(win.canvas, c, target)
    node = win.doc.get_node(a)
    assert node.parent_id == frame
    ox, oy = content_origin_abs(win.doc, win.doc.get_node(frame))
    r = win.canvas.node_scene_rect(a)
    assert (r.x(), r.y()) == (ox + node.box.x, oy + node.box.y)
    assert len(win.history.undo_stack) == n + 1
    win.do_undo()
    assert win.doc.get_node(a).parent_id == win.doc.project.root_id
    assert box(win, a)[:2] == (20, 20)


def test_drag_out_of_container_back_to_window(win):
    (frame,) = add_nodes(win, ("frame", dict(x=300, y=100, w=200, h=150)))
    (a,) = add_nodes(
        win,
        ("button", dict(x=20, y=20, w=100, h=40)),
    )
    win.canvas.add_widget("label", P(400, 150), container_id=frame)
    kid = [n for n in win.doc.project.nodes.values() if n.parent_id == frame][0]
    c = centre(win.canvas, kid.id)
    drag(win.canvas, c, (100, 400))
    assert win.doc.get_node(kid.id).parent_id == win.doc.project.root_id
    assert a  # untouched


def test_flex_container_reorders_children(win):
    (frame,) = add_nodes(win, ("frame", dict(x=50, y=50, w=500, h=100, name="Row")))
    win.doc.get_node(frame).layout = ContainerLayout(
        mode="flex", direction="row", gap=10, align="start"
    )
    kids = add_nodes(
        win, *[("button", dict(parent_id=frame, w=100, h=40, name=f"K{i}")) for i in range(3)]
    )
    order = lambda: [k.id for k in win.doc.children(frame)]  # noqa: E731
    assert order() == kids
    # resolved positions are laid out left to right by the layout engine
    xs = [win.canvas.node_scene_rect(k).x() for k in kids]
    assert xs == sorted(xs) and xs[1] - xs[0] == 110
    n = len(win.history.undo_stack)
    first = centre(win.canvas, kids[0])
    last_rect = win.canvas.node_scene_rect(kids[2])
    drag(win.canvas, first, (last_rect.right() - 5, last_rect.center().y()))
    assert order() == [kids[1], kids[2], kids[0]]
    assert len(win.history.undo_stack) == n + 1
    win.do_undo()
    assert order() == kids


def test_flex_drop_from_palette_inserts_at_cursor_position(win):
    (frame,) = add_nodes(win, ("frame", dict(x=50, y=50, w=500, h=100)))
    win.doc.get_node(frame).layout = ContainerLayout(
        mode="flex", direction="row", gap=10, align="start"
    )
    kids = add_nodes(
        win, *[("button", dict(parent_id=frame, w=100, h=40, name=f"K{i}")) for i in range(3)]
    )
    r = win.canvas.node_scene_rect(kids[1])
    nid = win.canvas.add_widget("label", P(r.left() + 2, r.center().y()))
    order = [k.id for k in win.doc.children(frame)]
    assert order == [kids[0], nid, kids[1], kids[2]]


def test_grid_container_assigns_cells_and_spans(win):
    (frame,) = add_nodes(win, ("frame", dict(x=50, y=50, w=400, h=300, name="Grid")))
    layout = ContainerLayout(
        mode="grid", column_weights=[1, 1, 1], row_weights=[1, 1, 1], column_gap=0, row_gap=0
    )
    win.doc.get_node(frame).layout = layout
    (k,) = add_nodes(win, ("button", dict(parent_id=frame, w=80, h=30, name="K")))
    win.doc.get_node(k).cell.sticky = "nsew"
    win.canvas.refresh()
    gg = grid_geometry(win.doc, win.doc.get_node(frame))
    ox, oy = content_origin_abs(win.doc, win.doc.get_node(frame))

    def cell_centre(row, col):
        x, y, w, h = gg.cell_rect(row, col)
        return ox + x + w / 2, oy + y + h / 2

    drag(win.canvas, centre(win.canvas, k), cell_centre(2, 1))
    cell = win.doc.get_node(k).cell
    assert (cell.row, cell.column) == (2, 1)
    # resize span with the east handle dragged into the next column
    click(win.canvas, centre(win.canvas, k))
    rect = win.canvas.node_scene_rect(k)
    drag(win.canvas, (rect.right(), rect.center().y()), cell_centre(2, 2))
    cell = win.doc.get_node(k).cell
    assert (cell.row, cell.column, cell.column_span) == (2, 1, 2)
    win.do_undo()
    assert win.doc.get_node(k).cell.column_span == 1


def test_grid_palette_drop_assigns_cell(win):
    (frame,) = add_nodes(win, ("frame", dict(x=50, y=50, w=400, h=300)))
    win.doc.get_node(frame).layout = ContainerLayout(
        mode="grid", column_weights=[1, 1], row_weights=[1, 1], column_gap=0, row_gap=0
    )
    gg = grid_geometry(win.doc, win.doc.get_node(frame))
    ox, oy = content_origin_abs(win.doc, win.doc.get_node(frame))
    x, y, w, h = gg.cell_rect(1, 1)
    nid = win.canvas.add_widget("entry", P(ox + x + w / 2, oy + y + h / 2))
    cell = win.doc.get_node(nid).cell
    assert (cell.row, cell.column) == (1, 1)
    assert win.doc.get_node(nid).parent_id == frame


def test_tab_header_switches_page_and_drops_land_on_that_page(win):
    (tabs,) = add_nodes(win, ("tabview", dict(x=40, y=40, w=400, h=300, name="Tabs")))
    node = win.doc.get_node(tabs)
    assert node.props["current"] == 0
    rect = win.canvas.node_scene_rect(tabs)
    # second tab header
    from py_vui.app.editor.canvas_geometry import tab_rects

    x, y, w, h = tab_rects(node)[1]
    click(win.canvas, (rect.x() + x + w / 2, rect.y() + y + h / 2))
    assert node.props["current"] == 1
    nid = win.canvas.add_widget("button", P(rect.x() + 100, rect.y() + 100))
    assert win.doc.get_node(nid).parent_id == tabs
    assert win.doc.get_node(nid).page == 1
    # the widget is only visible on its page
    assert win.canvas.item_for(nid).isVisible()
    x0, y0, w0, h0 = tab_rects(node)[0]
    click(win.canvas, (rect.x() + x0 + w0 / 2, rect.y() + y0 + h0 / 2))
    assert node.props["current"] == 0
    assert not win.canvas.item_for(nid).isVisible()
    # dropping onto another tab's header switches to it and adds to that page
    nid2 = win.canvas.add_widget("label", P(rect.x() + x + w / 2, rect.y() + y + h / 2))
    assert win.doc.get_node(nid2).page == 1
    assert node.props["current"] == 1


def test_window_resize_by_dragging_corner(win):
    root = win.doc.get_node(win.doc.project.root_id)
    n = len(win.history.undo_stack)
    drag(win.canvas, (641, 481), (741, 561), steps=6)
    assert (root.props["width"], root.props["height"]) == (740, 560)
    assert (root.box.w, root.box.h) == (740, 560)
    assert len(win.history.undo_stack) == n + 1
    win.do_undo()
    assert (root.props["width"], root.props["height"]) == (640, 480)


def test_window_edge_resize_only_one_axis(win):
    root = win.doc.get_node(win.doc.project.root_id)
    drag(win.canvas, (641, 200), (701, 260))
    assert (root.props["width"], root.props["height"]) == (700, 480)


def test_zoom_clamp_fit_and_wheel(win):
    c = win.canvas
    c.set_zoom(2.0)
    assert c.transform().m11() == pytest.approx(2.0)
    c.set_zoom(0.001)
    assert c.zoom == pytest.approx(0.1)
    c.set_zoom(99)
    assert c.zoom == pytest.approx(4.0)
    c.fit()
    assert 0.1 <= c.zoom <= 1.0
    vis = c.mapToScene(c.viewport().rect()).boundingRect()
    assert vis.contains(c.window_rect())
    c.actual_size()
    assert c.zoom == 1.0
    before = c.zoom
    ev = QWheelEvent(
        QPointF(100, 100),
        QPointF(100, 100),
        QPoint(0, 0),
        QPoint(0, 240),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.ControlModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    QApplication.sendEvent(c.viewport(), ev)
    assert c.zoom > before
    win.apply_zoom_text("50%")
    assert c.zoom == pytest.approx(0.5)
    assert win.status.zoom_label.text() == "50%"


def test_pan_with_space_drag_and_middle_button(win):
    c = win.canvas
    c.set_zoom(2.0)
    h0 = c.horizontalScrollBar().value()
    QTest.keyPress(c, Qt.Key.Key_Space)
    press(c, (300, 300))
    move(c, (250, 300))
    release(c, (250, 300))
    QTest.keyRelease(c, Qt.Key.Key_Space)
    assert c.horizontalScrollBar().value() != h0
    assert win.canvas.selection == [win.doc.project.root_id]
    h1 = c.horizontalScrollBar().value()
    press(c, (300, 300), button=Qt.MouseButton.MiddleButton)
    move(c, (350, 300), button=Qt.MouseButton.MiddleButton)
    release(c, (350, 300), button=Qt.MouseButton.MiddleButton)
    assert c.horizontalScrollBar().value() != h1


def test_double_click_inline_edit_text(win):
    (a,) = add_nodes(win, ("label", dict(x=100, y=100, w=160, h=30, name="L")))
    c = centre(win.canvas, a)
    click(win.canvas, c)
    ev_pos = win.canvas.mapFromScene(QPointF(*c))
    QTest.mouseDClick(
        win.canvas.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, ev_pos
    )
    edit = win.canvas._edit
    assert edit is not None and edit.text() == "Label"
    edit.setText("Hello world")
    edit.editingFinished.emit()
    assert win.doc.get_node(a).props["text"] == "Hello world"
    win.do_undo()
    assert win.doc.get_node(a).props["text"] == "Label"


def test_double_click_tab_title_renames_tab(win):
    (tabs,) = add_nodes(win, ("tabview", dict(x=40, y=40, w=400, h=300)))
    node = win.doc.get_node(tabs)
    from py_vui.app.editor.canvas_geometry import tab_rects

    rect = win.canvas.node_scene_rect(tabs)
    x, y, w, h = tab_rects(node)[0]
    pt = QPointF(rect.x() + x + w / 2, rect.y() + y + h / 2)
    QTest.mouseDClick(
        win.canvas.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        win.canvas.mapFromScene(pt),
    )
    assert win.canvas._edit is not None
    win.canvas._edit.setText("Settings")
    win.canvas.commit_inline_edit()
    assert node.props["tabs"][0] == "Settings"


def test_context_menu_contents(win):
    from py_vui.app.editor.context_menu import build_context_menu

    (a,) = add_nodes(win, ("button", dict(x=100, y=100)))
    titles = [x.text().replace("&", "") for x in build_context_menu(win, a).actions()]
    for expected in ("Cut", "Copy", "Paste", "Duplicate", "Delete", "Group in Frame", "Lock"):
        assert expected in titles
    root_menu = build_context_menu(win, win.doc.project.root_id)
    assert "Add Dialog Window" in [x.text().replace("&", "") for x in root_menu.actions()]


def test_escape_cancels_a_drag(win):
    (a,) = add_nodes(win, ("button", dict(x=100, y=100)))
    c = centre(win.canvas, a)
    press(win.canvas, c)
    move(win.canvas, (c[0] + 30, c[1] + 30))
    move(win.canvas, (c[0] + 60, c[1] + 60))
    QTest.keyClick(win.canvas, Qt.Key.Key_Escape)
    release(win.canvas, (c[0] + 60, c[1] + 60))
    assert box(win, a)[:2] == (100, 100)


def test_drop_events_from_palette_and_image_files(win, tmp_path):
    from PySide6.QtCore import QMimeData, QUrl
    from PySide6.QtGui import QDropEvent, QImage

    from py_vui.app.editor.mime import MIME_WIDGET

    mime = QMimeData()
    mime.setData(MIME_WIDGET, b"checkbox")
    pos = QPointF(win.canvas.mapFromScene(QPointF(200, 200)))
    ev = QDropEvent(
        pos,
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    win.canvas.dropEvent(ev)
    assert any(n.type == "checkbox" for n in win.doc.project.nodes.values())

    img = tmp_path / "pic.png"
    QImage(64, 48, QImage.Format.Format_RGB32).save(str(img))
    mime2 = QMimeData()
    mime2.setUrls([QUrl.fromLocalFile(str(img))])
    ev2 = QDropEvent(
        pos,
        Qt.DropAction.CopyAction,
        mime2,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    win.canvas.dropEvent(ev2)
    images = [n for n in win.doc.project.nodes.values() if n.type == "image"]
    assert len(images) == 1
    assert images[0].props["source"].startswith("assets/")
    assert (images[0].box.w, images[0].box.h) == (64, 48)
    assert QEvent.Type.Drop  # silence unused


def test_alt_drag_disables_snapping(win):
    win.canvas.snap_to_grid = True
    (a,) = add_nodes(win, ("button", dict(x=100, y=100)))
    c = centre(win.canvas, a)
    drag(win.canvas, c, (c[0] + 13, c[1] + 11), Qt.KeyboardModifier.AltModifier)
    assert box(win, a)[:2] == (113, 111)


def test_guide_dragged_back_outside_the_window_is_deleted(win):
    win.canvas.begin_ruler_drag("h", 0)
    win.canvas.update_ruler_drag(QPointF(0, 120))
    win.canvas.end_ruler_drag(QPointF(0, 120))
    win_id = win.canvas.window_id
    assert win.doc.project.editor["guides"][win_id]["h"] == [120]
    # grab the existing guide on the canvas and drop it above the window
    drag(win.canvas, (300, 120), (300, -40))
    assert "guides" not in win.doc.project.editor or win_id not in win.doc.project.editor["guides"]


def test_image_widget_paints_the_real_asset(win, tmp_path):
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QColor, QImage, QPainter

    src = tmp_path / "red.png"
    img = QImage(40, 40, QImage.Format.Format_RGB32)
    img.fill(QColor("#ff0000"))
    img.save(str(src))
    rel = win.service.add_asset(src)
    nid = win.canvas.add_widget("image", QPointF(100, 100), props={"source": rel, "fit": "stretch"})
    win.canvas.refresh()
    out = QImage(640, 480, QImage.Format.Format_ARGB32)
    p = QPainter(out)
    win.canvas.scene_.render(p, QRectF(0, 0, 640, 480), QRectF(0, 0, 640, 480))
    p.end()
    r = win.canvas.node_scene_rect(nid)
    px = QColor(out.pixel(int(r.center().x()), int(r.center().y())))
    assert px.red() > 200 and px.green() < 60
