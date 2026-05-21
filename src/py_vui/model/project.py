from __future__ import annotations

from collections import deque
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from py_vui.model.nodes import Node
from py_vui.model.schema import SCHEMA_VERSION

SchemaVersion = Literal["1"]
AdapterId = Literal["pyside6"]


class ProjectMeta(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: str
    created_at: str | None = Field(default=None, alias="createdAt")
    updated_at: str | None = Field(default=None, alias="updatedAt")


class py_vuiProject(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: SchemaVersion = Field(default="1", alias="schemaVersion")
    meta: ProjectMeta
    adapter: AdapterId
    root_id: str = Field(..., alias="rootId")
    nodes: dict[str, Node]

    @model_validator(mode="after")
    def keys_match_ids(self) -> py_vuiProject:
        for key, node in self.nodes.items():
            if key != node.id:
                msg = f"nodes map key {key!r} must equal node.id {node.id!r}"
                raise ValueError(msg)
        return self


def validate_project(project: py_vuiProject) -> None:
    if project.schema_version != SCHEMA_VERSION:
        msg = f"unsupported schemaVersion: {project.schema_version!r}"
        raise ValueError(msg)

    if project.root_id not in project.nodes:
        msg = f"rootId {project.root_id!r} missing from nodes"
        raise ValueError(msg)

    roots = [nid for nid, n in project.nodes.items() if n.parent_id is None]
    if len(roots) != 1:
        msg = f"expected exactly one root (parentId null), got {len(roots)}: {roots!r}"
        raise ValueError(msg)
    if roots[0] != project.root_id:
        msg = f"rootId {project.root_id!r} must be the only node with parentId null"
        raise ValueError(msg)

    root = project.nodes[project.root_id]
    if root.type != "window":
        msg = f"root node must be type 'window', got {root.type!r}"
        raise ValueError(msg)

    for nid, node in project.nodes.items():
        if node.parent_id is None:
            continue
        if node.parent_id not in project.nodes:
            msg = f"node {nid!r} references missing parent {node.parent_id!r}"
            raise ValueError(msg)

    seen: set[str] = set()
    q: deque[str] = deque([project.root_id])
    while q:
        cur = q.popleft()
        if cur in seen:
            msg = f"cycle detected at {cur!r}"
            raise ValueError(msg)
        seen.add(cur)
        for nid, node in project.nodes.items():
            if node.parent_id == cur:
                q.append(nid)

    if seen != set(project.nodes.keys()):
        orphans = set(project.nodes.keys()) - seen
        msg = f"orphan nodes not reachable from root: {sorted(orphans)!r}"
        raise ValueError(msg)
