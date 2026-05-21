from __future__ import annotations

from dataclasses import dataclass, field

from py_vui.commands.base import Command
from py_vui.model.document import ProjectDocument


@dataclass
class History:
    undo_stack: list[Command] = field(default_factory=list)
    redo_stack: list[Command] = field(default_factory=list)

    def push(self, doc: ProjectDocument, cmd: Command) -> None:
        cmd.apply(doc)
        doc.validate()
        self.undo_stack.append(cmd)
        self.redo_stack.clear()

    def undo(self, doc: ProjectDocument) -> None:
        if not self.undo_stack:
            return
        cmd = self.undo_stack.pop()
        cmd.revert(doc)
        doc.validate()
        self.redo_stack.append(cmd)

    def redo(self, doc: ProjectDocument) -> None:
        if not self.redo_stack:
            return
        cmd = self.redo_stack.pop()
        cmd.apply(doc)
        doc.validate()
        self.undo_stack.append(cmd)
