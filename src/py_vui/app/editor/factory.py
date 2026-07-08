from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from py_vui.model.geometry import LayoutSpec, Rect
from py_vui.model.nodes import (
    ButtonNode,
    ButtonProps,
    CheckboxNode,
    CheckboxProps,
    ComboBoxNode,
    ComboBoxProps,
    FrameNode,
    FrameProps,
    GroupBoxNode,
    GroupBoxProps,
    LabelNode,
    LabelProps,
    LineEditNode,
    LineEditProps,
    ListWidgetNode,
    ListWidgetProps,
    Node,
    ProgressBarNode,
    ProgressBarProps,
    RadioButtonNode,
    RadioButtonProps,
    ScrollAreaNode,
    ScrollAreaProps,
    SliderNode,
    SliderProps,
    SpinBoxNode,
    SpinBoxProps,
    TabWidgetNode,
    TabWidgetProps,
    TextEditNode,
    TextEditProps,
    WindowNode,
    WindowProps,
)
from py_vui.model.project import ProjectMeta, py_vuiProject
from py_vui.model.theme import theme_for_preset


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
        theme=theme_for_preset("modern"),
    )


def create_node(
    node_type: str,
    *,
    parent_id: str,
    parent: Node | None = None,
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
                props=WindowProps(width=w, height=h),
            )
        case "frame":
            return FrameNode(
                id=nid,
                name=display,
                parent_id=parent_id,
                layout=LayoutSpec(box=Rect(x=x, y=y, w=w, h=h)),
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
        case "combo_box":
            return ComboBoxNode(
                id=nid,
                name=display,
                parent_id=parent_id,
                layout=layout,
                props=ComboBoxProps(),
            )
        case "text_edit":
            return TextEditNode(
                id=nid,
                name=display,
                parent_id=parent_id,
                layout=LayoutSpec(box=Rect(x=x, y=y, w=max(w, 160), h=max(h, 80))),
                props=TextEditProps(placeholder="Enter text…"),
            )
        case "radio_button":
            return RadioButtonNode(
                id=nid,
                name=display,
                parent_id=parent_id,
                layout=layout,
                props=RadioButtonProps(text=display),
            )
        case "spin_box":
            return SpinBoxNode(
                id=nid,
                name=display,
                parent_id=parent_id,
                layout=layout,
                props=SpinBoxProps(),
            )
        case "slider":
            return SliderNode(
                id=nid,
                name=display,
                parent_id=parent_id,
                layout=LayoutSpec(box=Rect(x=x, y=y, w=max(w, 160), h=28)),
                props=SliderProps(),
            )
        case "list_widget":
            return ListWidgetNode(
                id=nid,
                name=display,
                parent_id=parent_id,
                layout=LayoutSpec(box=Rect(x=x, y=y, w=max(w, 120), h=max(h, 100))),
                props=ListWidgetProps(),
            )
        case "group_box":
            return GroupBoxNode(
                id=nid,
                name=display,
                parent_id=parent_id,
                layout=LayoutSpec(box=Rect(x=x, y=y, w=max(w, 180), h=max(h, 120))),
                props=GroupBoxProps(title=display),
            )
        case "tab_widget":
            return TabWidgetNode(
                id=nid,
                name=display,
                parent_id=parent_id,
                layout=LayoutSpec(box=Rect(x=x, y=y, w=max(w, 280), h=max(h, 200))),
                props=TabWidgetProps(),
            )
        case "progress_bar":
            return ProgressBarNode(
                id=nid,
                name=display,
                parent_id=parent_id,
                layout=LayoutSpec(box=Rect(x=x, y=y, w=max(w, 160), h=24)),
                props=ProgressBarProps(),
            )
        case "scroll_area":
            return ScrollAreaNode(
                id=nid,
                name=display,
                parent_id=parent_id,
                layout=LayoutSpec(box=Rect(x=x, y=y, w=max(w, 160), h=max(h, 100))),
                props=ScrollAreaProps(),
            )
        case other:
            raise ValueError(f"unknown widget type: {other!r}")
