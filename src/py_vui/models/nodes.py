from __future__ import annotations
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from py_vui.models.geometry import LayoutSpecification
from py_vui.models.properties import (
    WindowProperties,
    FrameProperties,
    LabelProperties,
    ButtonProperties,
    LineEditProperties,
    CheckboxProperties,
)

WindowNodeType = Literal["window"]
FrameNodeType = Literal["frame"]
LabelNodeType = Literal["label"]
ButtonNodeType = Literal["button"]
LineEditNodeType = Literal["line_edit"]
CheckboxNodeType = Literal["checkbox"]

NodeType = (
    WindowNodeType
    | FrameNodeType
    | LabelNodeType
    | ButtonNodeType
    | LineEditNodeType
    | CheckboxNodeType
)
type Node = WindowNode | FrameNode | LabelNode | ButtonNode | LineEditNode | CheckboxNode
type NodeProperties = WindowProperties | FrameProperties | LabelProperties | ButtonProperties | LineEditProperties | CheckboxProperties


class BaseNode(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: UUID
    name: str
    parent_id: UUID | None = None
    z_index: int = Field(default=0, ge=0)
    layout: LayoutSpecification = Field(default_factory=LayoutSpecification)


class WindowNode(BaseNode):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    type: NodeType = "window"
    properties: WindowProperties = Field(default_factory=WindowProperties)


class FrameNode(BaseNode):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    type: NodeType = "frame"
    properties: FrameProperties = Field(default_factory=FrameProperties)


class LabelNode(BaseNode):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    type: NodeType = "label"
    properties: LabelProperties = Field(default_factory=LabelProperties)


class ButtonNode(BaseNode):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    type: NodeType = "button"
    properties: ButtonProperties = Field(default_factory=ButtonProperties)


class LineEditNode(BaseNode):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    type: NodeType = "line_edit"
    properties: LineEditProperties = Field(default_factory=LineEditProperties)


class CheckboxNode(BaseNode):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    type: NodeType = "checkbox"
    properties: CheckboxProperties = Field(default_factory=CheckboxProperties)
