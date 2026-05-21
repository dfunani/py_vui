from __future__ import annotations

from pathlib import Path

import pytest

from py_vui.commands import AddNode, History, RemoveSubtree, ReparentNode
from py_vui.model.document import ProjectDocument
from py_vui.model.nodes import ButtonNode, ButtonProps, FrameNode, FrameProps
from py_vui.model.project import validate_project
from py_vui.model.serde import load_json


def test_add_remove_undo() -> None:
    p = load_json(Path("examples/fixtures/minimal.json").read_bytes())
    doc = ProjectDocument(p)
    hist = History()

    btn = ButtonNode(
        id="44444444-4444-4444-8444-444444444444",
        name="Ok",
        parent_id=p.root_id,
        z_index=1,
        props=ButtonProps(text="OK"),
    )
    hist.push(doc, AddNode(btn))
    assert btn.id in doc.project.nodes

    hist.undo(doc)
    assert btn.id not in doc.project.nodes

    hist.redo(doc)
    assert btn.id in doc.project.nodes


def test_reparent_rejects_cycle() -> None:
    p = load_json(Path("examples/fixtures/minimal.json").read_bytes())
    doc = ProjectDocument(p)
    hist = History()

    inner = FrameNode(
        id="55555555-5555-4555-8555-555555555555",
        name="Inner",
        parent_id="22222222-2222-4222-8222-222222222222",
        z_index=1,
        props=FrameProps(),
    )
    hist.push(doc, AddNode(inner))
    validate_project(doc.project)

    with pytest.raises(ValueError, match="subtree"):
        hist.push(
            doc,
            ReparentNode(
                node_id="22222222-2222-4222-8222-222222222222",
                new_parent_id="55555555-5555-4555-8555-555555555555",
            ),
        )


def test_remove_subtree() -> None:
    p = load_json(Path("examples/fixtures/minimal.json").read_bytes())
    doc = ProjectDocument(p)
    hist = History()
    hist.push(doc, RemoveSubtree("22222222-2222-4222-8222-222222222222"))
    assert "22222222-2222-4222-8222-222222222222" not in doc.project.nodes
    assert "33333333-3333-4333-8333-333333333333" not in doc.project.nodes
    validate_project(doc.project)
