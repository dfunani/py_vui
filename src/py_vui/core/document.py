"""Editing façade over :class:`Project`: tree queries, validation, node factory."""

from __future__ import annotations

import re
from collections import deque
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from py_vui.core import catalog  # noqa: F401  (registers built-in widgets)
from py_vui.core.model import (
    SCHEMA_VERSION,
    Box,
    ContainerLayout,
    Node,
    Project,
    ProjectMeta,
)
from py_vui.core.registry import get_spec, has_spec


def new_id() -> str:
    return str(uuid4())


def slug(text: str, fallback: str = "widget") -> str:
    s = re.sub(r"[^0-9a-zA-Z]+", "_", text.strip()).strip("_").lower()
    if not s:
        return fallback
    return f"_{s}" if s[0].isdigit() else s


def make_node(
    type_id: str,
    *,
    parent_id: str | None,
    x: float = 0,
    y: float = 0,
    w: float | None = None,
    h: float | None = None,
    name: str | None = None,
    z_index: int = 0,
    node_id: str | None = None,
    **props: Any,
) -> Node:
    """Create a node with registry defaults."""
    spec = get_spec(type_id)
    dw, dh = spec.default_size
    p = spec.default_props()
    p.update(props)
    layout = ContainerLayout() if spec.container else None
    return Node(
        id=node_id or new_id(),
        type=type_id,
        name=name or spec.label,
        parent_id=parent_id,
        z_index=z_index,
        box=Box(x=x, y=y, w=w if w is not None else dw, h=h if h is not None else dh),
        props=p,
        layout=layout,
    )


def new_project(name: str = "Untitled", framework: str = "tkinter") -> Project:
    root = make_node("window", parent_id=None, name="Main Window", title=name)
    root.box = Box(x=0, y=0, w=root.props["width"], h=root.props["height"])
    return Project(
        schemaVersion=SCHEMA_VERSION,  # type: ignore[arg-type]
        meta=ProjectMeta(name=name),
        framework=framework,  # type: ignore[arg-type]
        rootId=root.id,
        nodes={root.id: root},
    )


@dataclass
class Diagnostic:
    level: str  # "error" | "warning"
    node_id: str | None
    message: str


def validate_project(project: Project) -> None:
    """Raise ValueError when tree invariants are violated (cheap; run after every command)."""
    if project.root_id not in project.nodes:
        msg = f"rootId {project.root_id!r} missing from nodes"
        raise ValueError(msg)
    roots = [nid for nid, n in project.nodes.items() if n.parent_id is None]
    if roots != [project.root_id]:
        msg = f"expected exactly one root equal to rootId, got {roots!r}"
        raise ValueError(msg)
    if project.nodes[project.root_id].type != "window":
        msg = "root node must be type 'window'"
        raise ValueError(msg)
    children: dict[str, list[str]] = {}
    for nid, n in project.nodes.items():
        if n.parent_id is not None:
            if n.parent_id not in project.nodes:
                msg = f"node {nid!r} references missing parent {n.parent_id!r}"
                raise ValueError(msg)
            children.setdefault(n.parent_id, []).append(nid)
    seen: set[str] = set()
    q: deque[str] = deque([project.root_id])
    while q:
        cur = q.popleft()
        if cur in seen:
            msg = f"cycle detected at {cur!r}"
            raise ValueError(msg)
        seen.add(cur)
        q.extend(children.get(cur, ()))
    if seen != set(project.nodes):
        msg = f"orphan nodes: {sorted(set(project.nodes) - seen)!r}"
        raise ValueError(msg)
    for nid, n in project.nodes.items():
        if not has_spec(n.type):
            msg = f"node {nid!r} has unknown type {n.type!r}"
            raise ValueError(msg)
        parent = project.nodes.get(n.parent_id) if n.parent_id else None
        if parent is not None and not get_spec(parent.type).container:
            msg = f"node {nid!r} is inside non-container {parent.type!r}"
            raise ValueError(msg)
        if n.type == "toplevel" and n.parent_id != project.root_id:
            msg = "dialog windows must be direct children of the main window"
            raise ValueError(msg)


@dataclass
class ProjectDocument:
    project: Project

    # ---- queries
    def validate(self) -> None:
        validate_project(self.project)

    def get_node(self, node_id: str) -> Node:
        return self.project.nodes[node_id]

    def children(self, parent_id: str) -> list[Node]:
        kids = [n for n in self.project.nodes.values() if n.parent_id == parent_id]
        return sorted(kids, key=lambda n: (n.z_index, n.id))

    def walk(self, start: str | None = None) -> Iterator[Node]:
        """Depth-first, parents before children, siblings by (z_index, id)."""
        stack = [start or self.project.root_id]
        while stack:
            node = self.project.nodes[stack.pop()]
            yield node
            stack.extend(reversed([c.id for c in self.children(node.id)]))

    def subtree_ids(self, root_id: str) -> list[str]:
        return [n.id for n in self.walk(root_id)]

    def ancestors(self, node_id: str) -> list[Node]:
        out: list[Node] = []
        cur = self.project.nodes[node_id].parent_id
        while cur is not None:
            out.append(self.project.nodes[cur])
            cur = self.project.nodes[cur].parent_id
        return out

    def window_of(self, node_id: str) -> Node:
        """The window / toplevel that owns this node."""
        node = self.project.nodes[node_id]
        while node.type not in ("window", "toplevel") and node.parent_id:
            node = self.project.nodes[node.parent_id]
        return node

    def windows(self) -> list[Node]:
        root = self.project.nodes[self.project.root_id]
        return [root, *[c for c in self.children(root.id) if c.type == "toplevel"]]

    def unique_name(self, base: str, *, exclude: str | None = None) -> str:
        names = {n.name for n in self.project.nodes.values() if n.id != exclude}
        if base not in names:
            return base
        i = 2
        while f"{base} {i}" in names:
            i += 1
        return f"{base} {i}"

    def variable_name(self, node: Node) -> str:
        """Stable, human-readable Python identifier for a node (unique in the project)."""
        used: dict[str, str] = {}
        for n in self.walk():
            base = slug(n.name)
            cand, i = base, 2
            while cand in used:
                cand = f"{base}_{i}"
                i += 1
            used[cand] = n.id
            if n.id == node.id:
                return cand
        return slug(node.name)

    def variable_names(self) -> dict[str, str]:
        """node id -> unique python identifier, in tree order."""
        used: set[str] = set()
        out: dict[str, str] = {}
        reserved = {"main", "root", "app", "self", "tk", "ctk", "os", "sys", "handlers", "ui"}
        for n in self.walk():
            base = slug(n.name)
            if base in reserved or base.startswith("__"):
                base = f"{base}_w"
            cand, i = base, 2
            while cand in used:
                cand = f"{base}_{i}"
                i += 1
            used.add(cand)
            out[n.id] = cand
        return out

    def diagnostics(self) -> list[Diagnostic]:
        """Non-fatal problems: unsupported widgets, missing handlers, bad props."""
        out: list[Diagnostic] = []
        fw = self.project.framework
        for n in self.project.nodes.values():
            spec = get_spec(n.type)
            if not spec.supports(fw):
                out.append(Diagnostic(
                    "warning", n.id,
                    f"{spec.label} is not supported by {fw}; a placeholder will be generated."))
            for ev, h in n.events.items():
                if h not in self.project.handlers:
                    out.append(Diagnostic("warning", n.id, f"handler {h!r} for {ev} is missing"))
                if ev not in spec.events:
                    out.append(Diagnostic("warning", n.id, f"{spec.label} has no event {ev!r}"))
            for key in n.props:
                if spec.prop(key) is None:
                    out.append(Diagnostic("warning", n.id, f"unknown property {key!r}"))
        return out
