from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Rectangle(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    x: float = 0.0
    y: float = 0.0
    width: float = 100.0
    height: float = 32.0


class Anchors(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    left: bool = True
    top: bool = True
    right: bool = False
    bottom: bool = False


class Margins(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    top: float = 0.0
    right: float = 0.0
    bottom: float = 0.0
    left: float = 0.0


class LayoutSpecification(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    box: Rectangle = Field(default_factory=Rectangle)
    anchors: Anchors = Field(default_factory=Anchors)
    margins: Margins = Field(default_factory=Margins)
