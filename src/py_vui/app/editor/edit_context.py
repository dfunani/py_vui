"""Shared plumbing for inspector pages: selection context and coalescing command helpers."""

from __future__ import annotations

import itertools
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from py_vui.commands import Batch, Command, History, SetBoxes
from py_vui.core.document import ProjectDocument
from py_vui.core.model import Box, Node

_counter = itertools.count(1)


class MergeBatch(Batch):
    """A Batch whose members coalesce pairwise (multi-selection typing = one undo step)."""

    def __init__(self, commands: list[Command], label: str = "Edit") -> None:
        super().__init__(commands, label)
        keys = [c.merge_key for c in commands]
        self.merge_key = "batch:" + "|".join(k or "" for k in keys) if all(keys) else None

    def merge(self, newer: Command) -> bool:
        if not isinstance(newer, MergeBatch) or len(newer.commands) != len(self.commands):
            return False
        if newer.merge_key != self.merge_key:
            return False
        return all(a.merge(b) for a, b in zip(self.commands, newer.commands, strict=True))


class MergeBoxes(SetBoxes):
    """SetBoxes that coalesces consecutive edits of the same nodes (typing / scrubbing)."""

    def merge(self, newer: Command) -> bool:
        if isinstance(newer, SetBoxes) and [i for i, _ in newer.updates] == [
            i for i, _ in self.updates
        ]:
            self.updates = newer.updates
            return True
        return False


def box_command(updates: list[tuple[str, Box]], *, label: str = "Move / resize") -> MergeBoxes:
    key = "box:" + ",".join(i for i, _ in updates)
    return MergeBoxes(updates, label, key)


@dataclass
class EditContext:
    """What every inspector page edits: the doc, history and the selected nodes."""

    doc: ProjectDocument
    history: History
    ids: list[str]
    on_change: Callable[[], None] = field(default=lambda: None)
    asset_importer: Callable[[Path], str] | None = None
    project_dir: Path | None = None

    @property
    def nodes(self) -> list[Node]:
        return [self.doc.project.nodes[i] for i in self.ids if i in self.doc.project.nodes]

    @property
    def first(self) -> Node:
        return self.nodes[0]

    def push(self, cmds: list[Command], *, discrete: bool = False, label: str | None = None) -> None:
        """Push one command (or one Batch) as a single undo step.

        ``discrete`` edits (toggles, choices) never coalesce with neighbours.
        """
        if not cmds:
            return
        if discrete:
            tag = next(_counter)
            for c in cmds:
                if c.merge_key is not None:
                    c.merge_key = f"{c.merge_key}#{tag}"
        cmd: Command = cmds[0] if len(cmds) == 1 else MergeBatch(cmds, label or cmds[0].label)
        self.history.push(self.doc, cmd)
        self.on_change()

    def push_cmd(self, cmd: Command) -> None:
        self.history.push(self.doc, cmd)
        self.on_change()
