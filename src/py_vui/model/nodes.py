from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from py_vui.model.geometry import LayoutSpec


class NodeCommon(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str = Field(..., min_length=1)
    name: str
    parent_id: str | None = Field(default=None, alias="parentId")
    z_index: int = Field(default=0, ge=0, alias="zIndex")
    layout: LayoutSpec = Field(default_factory=LayoutSpec)


class WindowProps(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = "Window"
    width: float = Field(640.0, ge=1.0)
    height: float = Field(480.0, ge=1.0)


class WindowNode(NodeCommon):
    type: Literal["window"] = "window"
    props: WindowProps = Field(default_factory=WindowProps)


class FrameProps(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FrameNode(NodeCommon):
    type: Literal["frame"] = "frame"
    props: FrameProps = Field(default_factory=FrameProps)


class LabelProps(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = ""


class LabelNode(NodeCommon):
    type: Literal["label"] = "label"
    props: LabelProps = Field(default_factory=LabelProps)


class ButtonProps(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = ""


class ButtonNode(NodeCommon):
    type: Literal["button"] = "button"
    props: ButtonProps = Field(default_factory=ButtonProps)


class LineEditProps(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = ""
    placeholder: str = ""


class LineEditNode(NodeCommon):
    type: Literal["line_edit"] = "line_edit"
    props: LineEditProps = Field(default_factory=LineEditProps)


class CheckboxProps(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = ""
    checked: bool = False


class CheckboxNode(NodeCommon):
    type: Literal["checkbox"] = "checkbox"
    props: CheckboxProps = Field(default_factory=CheckboxProps)


Node = Annotated[
    WindowNode | FrameNode | LabelNode | ButtonNode | LineEditNode | CheckboxNode,
    Field(discriminator="type"),
]
