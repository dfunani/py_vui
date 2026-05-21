from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from py_vui.model.geometry import LayoutSpec, Rect
from py_vui.model.nodes import (
    ButtonNode,
    ButtonProps,
    CheckboxNode,
    CheckboxProps,
    FrameNode,
    FrameProps,
    LabelNode,
    LabelProps,
    LineEditNode,
    LineEditProps,
    Node,
    WindowNode,
    WindowProps,
)
from py_vui.model.project import ProjectMeta, py_vuiProject


def new_node_id() -> str:
    return str(uuid4())


def new_project(name: str = "untitled") -> py_vuiProject:
    root_id = new_node_id()
    now = datetime.now(timezone.utc).isoformat()
    root = WindowNode(
        id=root_id,
        name="MainWindow",
        parent_id=None,
        layout=LayoutSpec(box=Rect(x=0, y=0, w=640, h=480)),
        props=WindowProps(title="Window", width=640, height=480),
    )
    return py_vuiProject(
        meta=ProjectMeta(name=name, created_at=now, updated_at=now),
        adapter="pyside6",
        root_id=root_id,
        nodes={root_id: root},
    )


def create_node(
    node_type: str,
    *,
    parent_id: str,
    name: str | None = None,
    x: float = 8,
    y: float = 8,
    w: float = 120,
    h: float = 32,
) -> Node:
    nid = new_node_id()
    layout = LayoutSpec(box=Rect(x=x, y=y, w=w, h=h))
    display = name or node_type.replace("_", " ").title()

    match node_type:
        case "window":
            return WindowNode(
                id=nid,
                name=display,
                parent_id=parent_id,
                layout=layout,
                props=WindowProps(),
            )
        case "frame":
            return FrameNode(
                id=nid,
                name=display,
                parent_id=parent_id,
                layout=LayoutSpec(box=Rect(x=x, y=y, w=200, h=150)),
                props=FrameProps(),
            )
        case "label":
            return LabelNode(
                id=nid,
                name=display,
                parent_id=parent_id,
                layout=layout,
                props=LabelProps(text=display),
            )
        case "button":
            return ButtonNode(
                id=nid,
                name=display,
                parent_id=parent_id,
                layout=layout,
                props=ButtonProps(text=display),
            )
        case "line_edit":
            return LineEditNode(
                id=nid,
                name=display,
                parent_id=parent_id,
                layout=layout,
                props=LineEditProps(placeholder="Enter text…"),
            )
        case "checkbox":
            return CheckboxNode(
                id=nid,
                name=display,
                parent_id=parent_id,
                layout=layout,
                props=CheckboxProps(text=display),
            )
        case other:
            raise ValueError(f"unknown widget type: {other!r}")
