from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class MenuItemDef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = ""
    separator: bool = False
    handler: str | None = None


class MenuDef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = "File"
    items: list[MenuItemDef] = Field(default_factory=list)
