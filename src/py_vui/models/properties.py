from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class WindowProperties(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = "Window"
    width: float = Field(default=640.0, ge=1.0)
    height: float = Field(default=480.0, ge=1.0)


class FrameProperties(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LabelProperties(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = ""


class ButtonProperties(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = ""


class LineEditProperties(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = ""
    placeholder: str = ""


class CheckboxProperties(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = ""
    checked: bool = False
