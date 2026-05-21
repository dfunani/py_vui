from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WrittenFile:
    path: str
    content: str
