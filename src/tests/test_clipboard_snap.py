from __future__ import annotations

from pathlib import Path

from py_vui.app.editor.snap import snap, snap_size
from py_vui.commands import remap_subtree, subtree_root_id
from py_vui.model.serde import load_json


def test_snap_grid() -> None:
    assert snap(9) == 8
    assert snap(10) == 8
    assert snap_size(20) == 16


def test_remap_subtree_new_ids() -> None:
    p = load_json(Path("examples/fixtures/minimal.json").read_bytes())
    label_id = "33333333-3333-4333-8333-333333333333"
    nodes = {label_id: p.nodes[label_id]}
    root_id, clones = remap_subtree(nodes)
    assert root_id == clones[0].id
    assert root_id != label_id
    assert subtree_root_id(nodes) == label_id
