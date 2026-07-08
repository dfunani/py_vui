from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from py_vui.model.geometry import LayoutSpec
from py_vui.model.menus import MenuDef
from py_vui.model.theme import WidgetStyle


class NodeCommon(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str = Field(..., min_length=1)
    name: str
    parent_id: str | None = Field(default=None, alias="parentId")
    z_index: int = Field(default=0, ge=0, alias="zIndex")
    tab_index: int | None = Field(default=None, ge=0, alias="tabIndex")
    enabled: bool = True
    tooltip: str = ""
    style: WidgetStyle | None = None
    layout: LayoutSpec = Field(default_factory=LayoutSpec)


class WindowProps(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = "Window"
    width: float = Field(640.0, ge=1.0)
    height: float = Field(480.0, ge=1.0)
    menus: list[MenuDef] = Field(default_factory=list)


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
    on_click: str | None = Field(default=None, alias="onClick")


class ButtonNode(NodeCommon):
    type: Literal["button"] = "button"
    props: ButtonProps = Field(default_factory=ButtonProps)


class LineEditProps(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = ""
    placeholder: str = ""
    on_return: str | None = Field(default=None, alias="onReturn")


class LineEditNode(NodeCommon):
    type: Literal["line_edit"] = "line_edit"
    props: LineEditProps = Field(default_factory=LineEditProps)


class CheckboxProps(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = ""
    checked: bool = False
    on_toggle: str | None = Field(default=None, alias="onToggle")


class CheckboxNode(NodeCommon):
    type: Literal["checkbox"] = "checkbox"
    props: CheckboxProps = Field(default_factory=CheckboxProps)


class ComboBoxProps(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[str] = Field(default_factory=lambda: ["Option 1", "Option 2"])
    current_index: int = Field(default=0, ge=0, alias="currentIndex")
    on_change: str | None = Field(default=None, alias="onChange")


class ComboBoxNode(NodeCommon):
    type: Literal["combo_box"] = "combo_box"
    props: ComboBoxProps = Field(default_factory=ComboBoxProps)


class TextEditProps(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = ""
    placeholder: str = ""
    on_change: str | None = Field(default=None, alias="onChange")


class TextEditNode(NodeCommon):
    type: Literal["text_edit"] = "text_edit"
    props: TextEditProps = Field(default_factory=TextEditProps)


class RadioButtonProps(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = ""
    checked: bool = False
    on_toggle: str | None = Field(default=None, alias="onToggle")


class RadioButtonNode(NodeCommon):
    type: Literal["radio_button"] = "radio_button"
    props: RadioButtonProps = Field(default_factory=RadioButtonProps)


class SpinBoxProps(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min: int = 0
    max: int = 100
    value: int = 0
    on_change: str | None = Field(default=None, alias="onChange")


class SpinBoxNode(NodeCommon):
    type: Literal["spin_box"] = "spin_box"
    props: SpinBoxProps = Field(default_factory=SpinBoxProps)


class SliderProps(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min: int = 0
    max: int = 100
    value: int = 50
    on_change: str | None = Field(default=None, alias="onChange")


class SliderNode(NodeCommon):
    type: Literal["slider"] = "slider"
    props: SliderProps = Field(default_factory=SliderProps)


class ListWidgetProps(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[str] = Field(default_factory=lambda: ["Item 1", "Item 2"])
    on_select: str | None = Field(default=None, alias="onSelect")


class ListWidgetNode(NodeCommon):
    type: Literal["list_widget"] = "list_widget"
    props: ListWidgetProps = Field(default_factory=ListWidgetProps)


class GroupBoxProps(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = "Group"


class GroupBoxNode(NodeCommon):
    type: Literal["group_box"] = "group_box"
    props: GroupBoxProps = Field(default_factory=GroupBoxProps)


class TabSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = "Tab"


class TabWidgetProps(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tabs: list[TabSpec] = Field(default_factory=lambda: [TabSpec(title="Tab 1"), TabSpec(title="Tab 2")])
    current_index: int = Field(default=0, ge=0, alias="currentIndex")


class TabWidgetNode(NodeCommon):
    type: Literal["tab_widget"] = "tab_widget"
    props: TabWidgetProps = Field(default_factory=TabWidgetProps)


class ProgressBarProps(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: int = Field(default=0, ge=0)
    max: int = Field(default=100, ge=1)


class ProgressBarNode(NodeCommon):
    type: Literal["progress_bar"] = "progress_bar"
    props: ProgressBarProps = Field(default_factory=ProgressBarProps)


class ScrollAreaProps(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ScrollAreaNode(NodeCommon):
    type: Literal["scroll_area"] = "scroll_area"
    props: ScrollAreaProps = Field(default_factory=ScrollAreaProps)


Node = Annotated[
    WindowNode
    | FrameNode
    | LabelNode
    | ButtonNode
    | LineEditNode
    | CheckboxNode
    | ComboBoxNode
    | TextEditNode
    | RadioButtonNode
    | SpinBoxNode
    | SliderNode
    | ListWidgetNode
    | GroupBoxNode
    | TabWidgetNode
    | ProgressBarNode
    | ScrollAreaNode,
    Field(discriminator="type"),
]
