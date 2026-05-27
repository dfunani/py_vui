from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, field_validator

_HANDLER_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class HandlerDef(BaseModel):
    """Python callback body (statements inside the generated function)."""

    model_config = ConfigDict(extra="forbid")

    name: str
    body: str = 'print("clicked")'

    @field_validator("name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        if not _HANDLER_NAME.match(value):
            msg = f"handler name must be a valid Python identifier, got {value!r}"
            raise ValueError(msg)
        return value


def default_handler_name(widget_name: str) -> str:
    slug = re.sub(r"[^0-9a-zA-Z]+", "_", widget_name.strip()).strip("_").lower()
    if not slug:
        slug = "handler"
    if slug[0].isdigit():
        slug = f"on_{slug}"
    if not slug.startswith("on_"):
        slug = f"on_{slug}_clicked"
    return slug
