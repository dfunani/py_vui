from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from py_vui.core import ProjectDocument, make_node, new_project


@pytest.fixture
def sample_project():
    """A project with a representative widget mix; framework is overridden per test."""
    p = new_project("Sample", "tkinter")
    root = p.root_id
    p.handlers["on_go"] = __import__("py_vui.core.model", fromlist=["HandlerDef"]).HandlerDef(
        name="on_go", body='print("go")'
    )
    nodes = [
        make_node("label", parent_id=root, x=16, y=16, name="Title", text="Hello"),
        make_node("entry", parent_id=root, x=16, y=56, name="Name Input", placeholder="name"),
        make_node("button", parent_id=root, x=16, y=100, name="Go", text="Go"),
        make_node("checkbox", parent_id=root, x=16, y=144, name="Agree"),
        make_node("combobox", parent_id=root, x=16, y=180, name="Choices"),
        make_node("slider", parent_id=root, x=16, y=220, name="Level"),
        make_node("listbox", parent_id=root, x=200, y=16, name="Items"),
        make_node("progressbar", parent_id=root, x=200, y=150, name="Progress"),
    ]
    nodes[2].events["click"] = "on_go"
    for n in nodes:
        p.nodes[n.id] = n
    ProjectDocument(p).validate()
    return p
