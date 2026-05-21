from __future__ import annotations

from abc import ABC, abstractmethod

from py_vui.model.document import ProjectDocument


class Command(ABC):
    @abstractmethod
    def apply(self, doc: ProjectDocument) -> None:
        raise NotImplementedError

    @abstractmethod
    def revert(self, doc: ProjectDocument) -> None:
        raise NotImplementedError
