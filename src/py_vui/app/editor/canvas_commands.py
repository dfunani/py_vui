"""Editor-side Command subclasses that coalesce interactive edits into one undo step."""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import count

from py_vui.commands.base import Command
from py_vui.commands.builtins import SetBoxes
from py_vui.core.document import ProjectDocument
from py_vui.core.model import Box

_drag_ids = count(1)


def new_drag_key(prefix: str = "drag") -> str:
    """A merge key unique to one gesture (so two separate drags never coalesce)."""
    return f"{prefix}:{next(_drag_ids)}"


@dataclass
class MergeableBoxes(SetBoxes):
    """``SetBoxes`` that really merges with a following command carrying the same merge key
    (``SetBoxes`` itself declares a key but has no ``merge``)."""

    def merge(self, newer: Command) -> bool:
        if isinstance(newer, SetBoxes) and newer.merge_key == self.merge_key:
            by_id = {nid: box for nid, box in self.updates}
            for nid, box in newer.updates:
                by_id[nid] = box
                if all(nid != o for o, _ in self._old):
                    # first time this node is touched: remember its pre-gesture box
                    self._old.extend((o, b) for o, b in newer._old if o == nid)
            self.updates = list(by_id.items())
            return True
        return False


@dataclass
class SetWindowSize(Command):
    """Resize a window / dialog (props width + height, and the root box)."""

    node_id: str
    width: int
    height: int
    label: str = "Resize window"
    merge_key: str | None = None
    _old: tuple[int, int, Box] | None = field(default=None, repr=False)

    def apply(self, doc: ProjectDocument) -> None:
        n = doc.get_node(self.node_id)
        if self._old is None:
            self._old = (
                int(n.props.get("width", n.box.w)),
                int(n.props.get("height", n.box.h)),
                n.box.model_copy(),
            )
        n.props["width"] = self.width
        n.props["height"] = self.height
        n.box = Box(x=n.box.x, y=n.box.y, w=float(self.width), h=float(self.height))

    def revert(self, doc: ProjectDocument) -> None:
        assert self._old is not None
        n = doc.get_node(self.node_id)
        n.props["width"], n.props["height"] = self._old[0], self._old[1]
        n.box = self._old[2].model_copy()

    def merge(self, newer: Command) -> bool:
        if (
            isinstance(newer, SetWindowSize)
            and newer.node_id == self.node_id
            and newer.merge_key == self.merge_key
            and self.merge_key is not None
        ):
            self.width, self.height = newer.width, newer.height
            return True
        return False
