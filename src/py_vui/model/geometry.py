from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Rect(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float = 0.0
    y: float = 0.0
    w: float = 100.0
    h: float = 32.0


class Anchors(BaseModel):
    model_config = ConfigDict(extra="forbid")

    left: bool = True
    top: bool = True
    right: bool = False
    bottom: bool = False


class Margins(BaseModel):
    model_config = ConfigDict(extra="forbid")

    top: float = 0.0
    right: float = 0.0
    bottom: float = 0.0
    left: float = 0.0


class LayoutSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    box: Rect = Field(default_factory=Rect)
    anchors: Anchors = Field(default_factory=Anchors)
    margins: Margins = Field(default_factory=Margins)
