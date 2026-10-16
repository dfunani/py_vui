"""Events tab: bind widget events to project handlers (new / pick existing / unbind / edit)."""

from __future__ import annotations

import keyword
import re

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from py_vui.app.editor.edit_context import EditContext
from py_vui.app.editor.prop_editors import SplitterLabel
from py_vui.commands import Batch, Command, SetField, SetHandler
from py_vui.core.events import EVENTS
from py_vui.core.model import HandlerDef
from py_vui.core.registry import get_spec

_IDENT = re.compile(r"[^0-9a-zA-Z_]+")
NONE_LABEL = "(none)"
_MIXED = "\0mixed"


def default_handler_name(var: str, event: str, existing: set[str]) -> str:
    """``<widget>_<event>``, made a unique valid identifier."""
    base = _IDENT.sub("_", f"{var}_{event}").strip("_") or "handler"
    if base[0].isdigit() or keyword.iskeyword(base):
        base = f"on_{base}"
    cand, i = base, 2
    while cand in existing:
        cand = f"{base}_{i}"
        i += 1
    return cand


def starter_body(widget: str, event: str) -> str:
    text = f"{widget} {event}".replace("\\", "/").replace('"', "'")
    return f'print("{text}")'


class EventsPage(QWidget):
    handler_requested = Signal(str)

    def __init__(self, ctx: EditContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self._combos: dict[str, QComboBox] = {}
        self._sig: tuple | None = None
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(8, 4, 8, 8)
        self._content: QWidget | None = None
        self._build()

    # ------------------------------------------------------------- build
    def _events_for(self) -> list[str]:
        nodes = self.ctx.nodes
        if not nodes:
            return []
        common = [e for e in get_spec(nodes[0].type).events if e in EVENTS]
        for n in nodes[1:]:
            ev = set(get_spec(n.type).events)
            common = [e for e in common if e in ev]
        return common

    def _signature(self) -> tuple:
        n = self.ctx.nodes[0] if self.ctx.nodes else None
        return (
            tuple(tuple(sorted(x.events.items())) for x in self.ctx.nodes),
            tuple(sorted(self.ctx.doc.project.handlers)),
            n.type if n else "",
            len(self.ctx.nodes),
        )

    def _build(self) -> None:
        if self._content is not None:
            self._outer.removeWidget(self._content)
            self._content.setParent(None)
            self._content.deleteLater()
        self._combos.clear()
        self._sig = self._signature()
        self._content = QWidget()
        lay = QVBoxLayout(self._content)
        lay.setContentsMargins(0, 0, 0, 0)
        self._outer.insertWidget(0, self._content)
        events = self._events_for()
        if not events:
            lay.addWidget(QLabel("This widget has no events."))
            lay.addStretch(1)
            return
        handlers = sorted(self.ctx.doc.project.handlers)
        first = self.ctx.first
        groups: dict[str, list[str]] = {}
        for e in events:
            groups.setdefault(EVENTS[e].group, []).append(e)
        for group, ids in groups.items():
            lay.addWidget(SplitterLabel(group))
            for ev in ids:
                lay.addWidget(self._row(ev, first.events.get(ev), handlers))
        lay.addStretch(1)

    def _row(self, ev: str, bound: str | None, handlers: list[str]) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 2)
        v.setSpacing(2)
        label = QLabel(EVENTS[ev].label)
        if bound:
            f = label.font()
            f.setBold(True)
            label.setFont(f)
        v.addWidget(label)
        row = QHBoxLayout()
        row.setSpacing(3)
        combo = QComboBox()
        combo.addItem(NONE_LABEL, "")
        for h in handlers:
            combo.addItem(h, h)
        if bound and bound not in handlers:
            combo.addItem(f"{bound} (missing)", bound)
        combo.setCurrentIndex(max(combo.findData(bound or ""), 0))
        values = {n.events.get(ev, "") for n in self.ctx.nodes}
        mixed = len(values) > 1
        if mixed:
            combo.insertItem(0, "— mixed —", _MIXED)
            combo.setCurrentIndex(0)
        combo.setToolTip("Pick an existing handler")
        combo.activated.connect(lambda _i, e=ev, c=combo: self._picked(e, c.currentData()))
        new_btn = QPushButton("New")
        new_btn.setToolTip("Create a new handler and bind it")
        new_btn.setAutoDefault(False)
        new_btn.clicked.connect(lambda _=False, e=ev: self.new_handler(e))
        edit_btn = QPushButton("Edit code")
        edit_btn.setAutoDefault(False)
        edit_btn.setEnabled(bool(bound))
        edit_btn.clicked.connect(lambda _=False, e=ev: self.edit_event(e))
        unbind = QToolButton()
        unbind.setText("✕")
        unbind.setToolTip("Unbind")
        unbind.setEnabled(bool(bound))
        unbind.clicked.connect(lambda _=False, e=ev: self.bind_event(e, ""))
        row.addWidget(combo, 1)
        row.addWidget(new_btn)
        row.addWidget(edit_btn)
        row.addWidget(unbind)
        v.addLayout(row)
        self._combos[ev] = combo
        return w

    # ------------------------------------------------------------- actions
    def _picked(self, event: str, handler: str | None) -> None:
        if handler != _MIXED:
            self.bind_event(event, handler)

    def bind_event(self, event: str, handler: str | None) -> None:
        cmds: list[Command] = [
            SetField(n.id, "events", event, handler or None, label=f"Bind {event}")
            for n in self.ctx.nodes
        ]
        self.ctx.push(cmds, discrete=True)
        self.refresh()

    def new_handler(self, event: str) -> str:
        doc = self.ctx.doc
        first = self.ctx.first
        if len(self.ctx.nodes) == 1:
            var = doc.variable_name(first)
        else:
            var = first.type
        name = default_handler_name(var, event, set(doc.project.handlers))
        body = starter_body(first.name if len(self.ctx.nodes) == 1 else first.type, event)
        cmds: list[Command] = [SetHandler(name, HandlerDef(name=name, body=body),
                                          label="New handler")]
        cmds += [SetField(n.id, "events", event, name) for n in self.ctx.nodes]
        for c in cmds:
            c.merge_key = None
        self.ctx.push_cmd(Batch(cmds, label=f"New handler {name}"))
        self.refresh()
        return name

    def edit_event(self, event: str) -> None:
        name = self.ctx.first.events.get(event)
        if name:
            self.handler_requested.emit(name)

    def combo(self, event: str) -> QComboBox:
        return self._combos[event]

    def refresh(self) -> None:
        if self.ctx.nodes and self._signature() != self._sig:
            self._build()
