"""Design-time rendering of every registry widget in every framework look."""

from __future__ import annotations

import time

import pytest
from editor_support import dispose, home, make_window, qapp  # noqa: F401
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QImage, QPainter

from py_vui.core import make_node
from py_vui.core.registry import FRAMEWORKS, all_specs

pytestmark = pytest.mark.gui


def _render(canvas, w: int, h: int) -> QImage:
    img = QImage(w, h, QImage.Format.Format_ARGB32)
    img.fill(QColor("#ff00ff"))
    p = QPainter(img)
    canvas.scene_.render(p, QRectF(0, 0, w, h), QRectF(0, 0, w, h))
    p.end()
    return img


def _distinct_colours(img: QImage) -> int:
    seen = set()
    step = 1 if img.width() * img.height() < 20000 else 3
    for y in range(0, img.height(), step):
        for x in range(0, img.width(), step):
            seen.add(img.pixel(x, y))
    return len(seen)


@pytest.mark.parametrize("framework", FRAMEWORKS)
def test_every_widget_type_paints_in_every_framework(qapp, home, tmp_path, framework):  # noqa: F811
    w = make_window(tmp_path, framework)
    try:
        root = w.doc.project.root_id
        specs = [s for s in all_specs() if s.type not in ("window", "toplevel")]
        assert len(specs) == 34
        x = y = 8
        for spec in specs:
            n = make_node(spec.type, parent_id=root, x=x, y=y, name=spec.label)
            w.doc.project.nodes[n.id] = n
            x += 330
            if x > 1500:
                x, y = 8, y + 250
        w.doc.project.nodes[root].props.update(width=1900, height=1600)
        w.canvas.refresh()
        assert len(w.canvas.scene_.items_by_id) == len(specs) + 1
        img = _render(w.canvas, 1900, 1600)
        assert _distinct_colours(img) > 12
        # each widget leaves ink inside its own rectangle
        for nid, item in w.canvas.scene_.items_by_id.items():
            if nid == root:
                continue
            r = w.canvas.node_scene_rect(nid).toRect().intersected(img.rect())
            patch = img.copy(r)
            assert _distinct_colours(patch) >= 2, w.doc.get_node(nid).type
    finally:
        dispose(w)


def test_container_children_are_clipped_and_nested(qapp, home, tmp_path):  # noqa: F811
    w = make_window(tmp_path)
    try:
        frame = make_node("frame", parent_id=w.doc.project.root_id, x=20, y=20, w=100, h=80)
        w.doc.project.nodes[frame.id] = frame
        child = make_node("button", parent_id=frame.id, x=60, y=40, w=100, h=40)
        w.doc.project.nodes[child.id] = child
        w.canvas.refresh()
        r = w.canvas.node_scene_rect(child.id)
        assert (r.x(), r.y()) == (80, 60)  # container origin + child offset
        # hit-testing respects clipping: the clipped part of the child belongs to nobody
        assert w.canvas.hit_node(r.topLeft() + type(r.topLeft())(5, 5)) == child.id
        assert w.canvas.hit_node(r.topLeft() + type(r.topLeft())(70, 5)) != child.id
    finally:
        dispose(w)


def test_hidden_disabled_locked_states(qapp, home, tmp_path):  # noqa: F811
    w = make_window(tmp_path)
    try:
        a = make_node("button", parent_id=w.doc.project.root_id, x=10, y=10)
        b = make_node("button", parent_id=w.doc.project.root_id, x=10, y=60)
        c = make_node("button", parent_id=w.doc.project.root_id, x=10, y=110)
        for n in (a, b, c):
            w.doc.project.nodes[n.id] = n
        a.visible = False
        b.enabled = False
        c.locked = True
        w.canvas.refresh()
        items = w.canvas.scene_.items_by_id
        assert not items[a.id].isVisible()
        assert items[b.id].opacity() < 1.0
        assert items[c.id].isVisible()
        assert w.canvas.hit_node(w.canvas.node_scene_rect(a.id).center()) != a.id
    finally:
        dispose(w)


def test_unsupported_widget_is_hatched(qapp, home, tmp_path):  # noqa: F811
    w = make_window(tmp_path, "kivy")
    try:
        n = make_node("chart", parent_id=w.doc.project.root_id, x=10, y=10)
        w.doc.project.nodes[n.id] = n
        w.canvas.refresh()
        img = _render(w.canvas, 400, 300)
        patch = img.copy(10 + 360 - 22, 10, 22, 22)  # the warning triangle, top-right
        amber = sum(
            1
            for yy in range(patch.height())
            for xx in range(patch.width())
            if QColor(patch.pixel(xx, yy)).red() > 200
            and QColor(patch.pixel(xx, yy)).green() > 120
            and QColor(patch.pixel(xx, yy)).blue() < 120
        )
        assert amber > 15
    finally:
        dispose(w)


def test_framework_changes_the_look(qapp, home, tmp_path):  # noqa: F811
    renders = {}
    for fw in ("tkinter", "customtkinter", "kivy"):
        w = make_window(tmp_path, fw)
        try:
            n = make_node("button", parent_id=w.doc.project.root_id, x=20, y=20, w=140, h=44)
            w.doc.project.nodes[n.id] = n
            w.canvas.refresh()
            renders[fw] = _render(w.canvas, 220, 120).copy(20, 20, 140, 44)
        finally:
            dispose(w)
    assert renders["tkinter"] != renders["customtkinter"]
    assert renders["customtkinter"] != renders["kivy"]


def test_repaint_is_fast_with_300_widgets(qapp, home, tmp_path):  # noqa: F811
    w = make_window(tmp_path)
    try:
        root = w.doc.project.root_id
        kinds = ["button", "label", "entry", "checkbox", "slider", "combobox"]
        for i in range(300):
            n = make_node(
                kinds[i % len(kinds)], parent_id=root, x=(i % 20) * 60, y=(i // 20) * 34, w=56, h=30
            )
            w.doc.project.nodes[n.id] = n
        w.doc.project.nodes[root].props.update(width=1260, height=520)
        t0 = time.perf_counter()
        w.canvas.refresh()
        build = time.perf_counter() - t0
        w.canvas.resize(900, 700)
        w.canvas.fit()
        times = []
        for _ in range(5):
            t0 = time.perf_counter()
            w.canvas.viewport().grab()
            times.append(time.perf_counter() - t0)
        # unchanged document: incremental sync must be much cheaper than the first build
        t0 = time.perf_counter()
        w.canvas.refresh()
        resync = time.perf_counter() - t0
        assert min(times) < 0.25, times
        assert resync < 0.2, resync
        assert resync <= build + 0.05
    finally:
        dispose(w)


def test_incremental_sync_only_touches_changed_nodes(qapp, home, tmp_path):  # noqa: F811
    w = make_window(tmp_path)
    try:
        root = w.doc.project.root_id
        a = make_node("button", parent_id=root, x=10, y=10)
        b = make_node("label", parent_id=root, x=10, y=60)
        w.doc.project.nodes[a.id] = a
        w.doc.project.nodes[b.id] = b
        w.canvas.refresh()
        item_a, item_b = w.canvas.item_for(a.id), w.canvas.item_for(b.id)
        sigs = dict(w.canvas.scene_._sigs)
        a.props["text"] = "changed"
        w.canvas.refresh()
        assert w.canvas.item_for(a.id) is item_a and w.canvas.item_for(b.id) is item_b
        assert w.canvas.scene_._sigs[a.id] != sigs[a.id]
        assert w.canvas.scene_._sigs[b.id] == sigs[b.id]
    finally:
        dispose(w)
