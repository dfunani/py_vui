from __future__ import annotations

from abc import ABC, abstractmethod

from py_vui.core.document import ProjectDocument


class Command(ABC):
    #: shown in Edit ▸ Undo <label>
    label: str = "Edit"
    #: consecutive commands with an equal non-None merge_key are coalesced into one undo step
    merge_key: str | None = None

    @abstractmethod
    def apply(self, doc: ProjectDocument) -> None: ...

    @abstractmethod
    def revert(self, doc: ProjectDocument) -> None: ...

    def merge(self, newer: Command) -> bool:
        """Absorb ``newer`` (already applied) into self. Return True when merged."""
        return False
