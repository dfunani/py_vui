from __future__ import annotations

from dataclasses import dataclass, field

from py_vui.commands.base import Command
from py_vui.core.document import ProjectDocument


@dataclass
class History:
    undo_stack: list[Command] = field(default_factory=list)
    redo_stack: list[Command] = field(default_factory=list)
    limit: int = 500
    #: bumped on every push/undo/redo; the editor compares it to its saved marker
    revision: int = 0

    def push(self, doc: ProjectDocument, cmd: Command) -> None:
        cmd.apply(doc)
        try:
            doc.validate()
        except ValueError:
            cmd.revert(doc)
            raise
        self.revision += 1
        self.redo_stack.clear()
        if (
            self.undo_stack
            and cmd.merge_key is not None
            and self.undo_stack[-1].merge_key == cmd.merge_key
            and self.undo_stack[-1].merge(cmd)
        ):
            return
        self.undo_stack.append(cmd)
        if len(self.undo_stack) > self.limit:
            del self.undo_stack[0]

    def undo(self, doc: ProjectDocument) -> bool:
        if not self.undo_stack:
            return False
        cmd = self.undo_stack.pop()
        cmd.revert(doc)
        doc.validate()
        self.redo_stack.append(cmd)
        self.revision += 1
        return True

    def redo(self, doc: ProjectDocument) -> bool:
        if not self.redo_stack:
            return False
        cmd = self.redo_stack.pop()
        cmd.apply(doc)
        doc.validate()
        self.undo_stack.append(cmd)
        self.revision += 1
        return True

    def clear(self) -> None:
        self.undo_stack.clear()
        self.redo_stack.clear()

    @property
    def undo_label(self) -> str | None:
        return self.undo_stack[-1].label if self.undo_stack else None

    @property
    def redo_label(self) -> str | None:
        return self.redo_stack[-1].label if self.redo_stack else None
