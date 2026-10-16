"""Schema v2 document model (framework-agnostic, registry driven)."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from py_vui.core.registry import FrameworkId
from py_vui.core.theme import ProjectTheme

SCHEMA_VERSION = "2"
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class Box(BaseModel):
    model_config = ConfigDict(extra="forbid")
    x: float = 0.0
    y: float = 0.0
    w: float = 100.0
    h: float = 32.0


class Anchors(BaseModel):
    """Absolute-layout resize behaviour: which parent edges the widget stays pinned to."""

    model_config = ConfigDict(extra="forbid")
    left: bool = True
    top: bool = True
    right: bool = False
    bottom: bool = False


class Padding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    top: float = 0.0
    right: float = 0.0
    bottom: float = 0.0
    left: float = 0.0


LayoutMode = Literal["absolute", "flex", "grid"]
Justify = Literal["start", "center", "end", "space_between", "space_around"]
AlignItems = Literal["start", "center", "end", "stretch"]


class ContainerLayout(BaseModel):
    """How a container arranges its children (pyuibuilder: absolute / flex / grid)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    mode: LayoutMode = "absolute"
    # flex
    direction: Literal["row", "column"] = "column"
    gap: float = 8.0
    justify: Justify = "start"
    align: AlignItems = "stretch"
    wrap: bool = False
    # grid
    column_weights: list[int] = Field(default_factory=lambda: [1, 1], alias="columnWeights")
    row_weights: list[int] = Field(default_factory=lambda: [1, 1], alias="rowWeights")
    column_gap: float = Field(default=8.0, alias="columnGap")
    row_gap: float = Field(default=8.0, alias="rowGap")
    padding: Padding = Field(default_factory=lambda: Padding(top=8, right=8, bottom=8, left=8))


class GridCell(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    row: int = Field(default=0, ge=0)
    column: int = Field(default=0, ge=0)
    row_span: int = Field(default=1, ge=1, alias="rowSpan")
    column_span: int = Field(default=1, ge=1, alias="columnSpan")
    #: any of n,s,e,w (Tk `sticky` semantics); "" = centered
    sticky: str = Field(default="nsew")


class FlexItem(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    grow: float = Field(default=0.0, ge=0)
    align_self: Literal["auto", "start", "center", "end", "stretch"] = Field(
        default="auto", alias="alignSelf"
    )
    margin: Padding = Field(default_factory=Padding)


class Node(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str = Field(..., min_length=1)
    type: str
    name: str
    parent_id: str | None = Field(default=None, alias="parentId")
    z_index: int = Field(default=0, ge=0, alias="zIndex")
    box: Box = Field(default_factory=Box)
    anchors: Anchors = Field(default_factory=Anchors)
    props: dict[str, Any] = Field(default_factory=dict)
    style: dict[str, Any] = Field(default_factory=dict)
    #: event id -> handler name (see Project.handlers)
    events: dict[str, str] = Field(default_factory=dict)
    #: only meaningful for container widgets
    layout: ContainerLayout | None = None
    #: placement inside a grid / flex parent
    cell: GridCell = Field(default_factory=GridCell)
    flex: FlexItem = Field(default_factory=FlexItem)
    #: page index when the parent is a paged container (tabview)
    page: int = Field(default=0, ge=0)
    enabled: bool = True
    visible: bool = True
    locked: bool = False
    tooltip: str = ""
    tab_index: int | None = Field(default=None, ge=0, alias="tabIndex")

    @field_validator("name")
    @classmethod
    def _name_nonempty(cls, v: str) -> str:
        if not v.strip():
            msg = "name must not be empty"
            raise ValueError(msg)
        return v


class HandlerDef(BaseModel):
    """User code for one callback. ``body`` is the statements inside ``def name(event=None):``."""

    model_config = ConfigDict(extra="forbid")
    name: str
    body: str = "pass"

    @field_validator("name")
    @classmethod
    def _valid(cls, v: str) -> str:
        if not _IDENT.match(v):
            msg = f"handler name must be a Python identifier, got {v!r}"
            raise ValueError(msg)
        return v


class ProjectMeta(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    name: str
    description: str = ""
    author: str = ""
    version: str = "0.1.0"
    created_at: str | None = Field(default=None, alias="createdAt")
    updated_at: str | None = Field(default=None, alias="updatedAt")


class Project(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: Literal["2"] = Field(default="2", alias="schemaVersion")
    meta: ProjectMeta
    framework: FrameworkId = "tkinter"
    root_id: str = Field(..., alias="rootId")
    nodes: dict[str, Node]
    theme: ProjectTheme = Field(default_factory=ProjectTheme)
    handlers: dict[str, HandlerDef] = Field(default_factory=dict)
    tab_order: list[str] = Field(default_factory=list, alias="tabOrder")
    #: module-level code emitted in handlers.py (imports, globals, helpers)
    custom_code: str = Field(default="", alias="customCode")
    #: extra pip requirements the user wants in requirements.txt
    extra_requirements: list[str] = Field(default_factory=list, alias="extraRequirements")
    #: asset paths (relative to project dir) that are bundled on export
    assets: list[str] = Field(default_factory=list)
    #: free-form per-editor state (zoom, active window, guides…) – never used by codegen
    editor: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _keys_match_ids(self) -> Project:
        for key, node in self.nodes.items():
            if key != node.id:
                msg = f"nodes map key {key!r} must equal node.id {node.id!r}"
                raise ValueError(msg)
        return self
