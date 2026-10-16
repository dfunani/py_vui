from __future__ import annotations

import json

import pytest

from py_vui.commands import (
    AddNode,
    Batch,
    History,
    RemoveSubtree,
    ReparentNode,
    SetBox,
    SetField,
    align_nodes,
    build_paste,
    copy_nodes,
)
from py_vui.core import Box, ProjectDocument, make_node, new_project
from py_vui.core.layout_engine import resolve_children
from py_vui.core.model import GridCell
from py_vui.core.registry import all_specs, get_spec
from py_vui.core.serde import dump_json, load_json


def test_registry_complete():
    types = {s.type for s in all_specs()}
    assert {"window", "toplevel", "button", "entry", "tabview", "calendar", "map_view"} <= types
    for s in all_specs():
        for ev in s.events:
            from py_vui.core.events import EVENTS

            assert ev in EVENTS, (s.type, ev)


def test_roundtrip(sample_project):
    again = load_json(dump_json(sample_project))
    assert again == sample_project


def test_v1_migration():
    p = load_json(open("examples/fixtures/minimal.json").read())
    assert p.schema_version == "2"
    ProjectDocument(p).validate()


def test_undo_redo_and_coalesce():
    p = new_project("t")
    doc, h = ProjectDocument(p), History()
    n = make_node("button", parent_id=p.root_id)
    h.push(doc, AddNode(n))
    for i in range(5):
        h.push(doc, SetField(n.id, "props", "text", f"v{i}"))
    assert len(h.undo_stack) == 2  # add + one coalesced edit
    assert p.nodes[n.id].props["text"] == "v4"
    h.undo(doc)
    assert p.nodes[n.id].props["text"] == "Button"
    h.undo(doc)
    assert n.id not in p.nodes
    h.redo(doc)
    h.redo(doc)
    assert p.nodes[n.id].props["text"] == "v4"


def test_invalid_command_rolled_back():
    p = new_project("t")
    doc, h = ProjectDocument(p), History()
    btn = make_node("button", parent_id=p.root_id)
    h.push(doc, AddNode(btn))
    bad = make_node("label", parent_id=btn.id)  # button is not a container
    with pytest.raises(ValueError):
        h.push(doc, AddNode(bad))
    assert bad.id not in p.nodes


def test_reparent_cycle_rejected():
    p = new_project("t")
    doc = ProjectDocument(p)
    a = make_node("frame", parent_id=p.root_id)
    b = make_node("frame", parent_id=a.id)
    p.nodes.update({a.id: a, b.id: b})
    with pytest.raises(ValueError):
        ReparentNode(a.id, b.id).apply(doc)


def test_remove_subtree_and_revert():
    p = new_project("t")
    doc = ProjectDocument(p)
    a = make_node("frame", parent_id=p.root_id)
    b = make_node("label", parent_id=a.id)
    p.nodes.update({a.id: a, b.id: b})
    cmd = RemoveSubtree(a.id)
    cmd.apply(doc)
    assert a.id not in p.nodes and b.id not in p.nodes
    cmd.revert(doc)
    assert b.id in p.nodes


def test_copy_paste(sample_project):
    doc = ProjectDocument(sample_project)
    ids = [n.id for n in sample_project.nodes.values() if n.type == "button"]
    payload = copy_nodes(doc, ids)
    cmd, new_ids = build_paste(doc, payload, sample_project.root_id)
    cmd.apply(doc)
    doc.validate()
    assert len(new_ids) == 1
    assert sample_project.nodes[new_ids[0]].name != "Go"


def test_align_and_batch(sample_project):
    doc = ProjectDocument(sample_project)
    ids = [n.id for n in sample_project.nodes.values() if n.type in {"label", "button"}]
    align_nodes(doc, ids, "left").apply(doc)
    assert len({sample_project.nodes[i].box.x for i in ids}) == 1
    b = Batch([SetBox(ids[0], Box(x=1, y=1, w=5, h=5))])
    b.apply(doc)
    b.revert(doc)


def test_flex_and_grid_layout():
    p = new_project("t")
    doc = ProjectDocument(p)
    root = p.nodes[p.root_id]
    root.layout.mode = "flex"
    root.layout.direction = "row"
    root.layout.align = "start"
    a = make_node("button", parent_id=root.id, w=100, h=30, z_index=0)
    b = make_node("button", parent_id=root.id, w=100, h=30, z_index=1)
    b.flex.grow = 1
    p.nodes.update({a.id: a, b.id: b})
    boxes = resolve_children(doc, root.id)
    assert boxes[a.id].x == 8 and boxes[b.id].x == 116
    assert boxes[b.id].w > 100  # grew

    root.layout.mode = "grid"
    a.cell = GridCell(row=0, column=0)
    b.cell = GridCell(row=1, column=1)
    boxes = resolve_children(doc, root.id)
    assert boxes[b.id].y > boxes[a.id].y and boxes[b.id].x > boxes[a.id].x


def test_diagnostics_unsupported_widget():
    p = new_project("t", "kivy")
    n = make_node("map_view", parent_id=p.root_id)
    p.nodes[n.id] = n
    msgs = [d.message for d in ProjectDocument(p).diagnostics()]
    assert any("not supported" in m for m in msgs)


def test_variable_names_unique(sample_project):
    doc = ProjectDocument(sample_project)
    n = make_node("button", parent_id=sample_project.root_id, name="Go")
    sample_project.nodes[n.id] = n
    names = doc.variable_names()
    assert len(set(names.values())) == len(names)
    assert json.dumps(names)
    assert get_spec("window").container


def test_nested_flex_uses_resolved_parent_size():
    from py_vui.core.layout_engine import resolved_box

    p = new_project("t")
    doc = ProjectDocument(p)
    root = p.nodes[p.root_id]
    root.layout.mode = "flex"
    root.layout.align = "stretch"
    outer = make_node("frame", parent_id=root.id, w=50, h=50)
    outer.flex.grow = 1
    outer.layout.mode = "flex"
    inner = make_node("button", parent_id=outer.id, w=10, h=10)
    p.nodes.update({outer.id: outer, inner.id: inner})
    ob = resolved_box(doc, outer)
    assert ob.w > 600 and ob.h > 400  # filled the window, not the stored 50x50
    ib = resolved_box(doc, inner)
    assert ib.w == ob.w - 16  # stretched to the container's resolved width minus padding
