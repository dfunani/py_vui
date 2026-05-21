# py_vui — Full implementation (copy-paste)

**Version:** 0.2 (Phase 1 + Phase 2)  
**Python:** 3.12+  
**Runtime deps:** `pydantic>=2.6`  
**Optional:** `PySide6>=6.6` (Phase 1 UI), `pygame>=2.5` (Phase 2 game), `pytest`, `ruff`

This document is the **only** artifact you need to scaffold the project: create each path below and paste the matching block.

- **Phase 1 (§1–§8):** UI builder — `adapter: "pyside6"`, `schemaVersion: "1"`, PySide6 codegen.  
- **Phase 2 (§9–§15):** pygame studio — `adapter: "pygame"`, `schemaVersion: "2"`, scene/sprite/camera nodes, game loop codegen.

**Related (product intent):** [DESIGN_SPEC.md](./DESIGN_SPEC.md), [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md).

---

## Table of contents

**Phase 1 — UI builder**

1. [Repository tree](#1-repository-tree)
2. [Wire format (`py_vui.json`) — Phase 1](#2-wire-format-py_vuijson)
3. [JSON Schema — Phase 1](#3-json-schema)
4. [Config & packaging](#4-config--packaging)
5. [Package `src/py_vui` — Phase 1](#5-package-srcpy_vui)
6. [Tests — Phase 1](#6-tests)
7. [Fixture — Phase 1](#7-fixture)
8. [Verify — Phase 1](#8-verify)

**Phase 2 — pygame studio**

9. [Phase 2 overview](#9-phase-2-overview)
10. [Wire format — Phase 2](#10-wire-format--phase-2)
11. [JSON Schema — Phase 2 extensions](#11-json-schema--phase-2-extensions)
12. [Repository additions](#12-repository-additions)
13. [Package files — Phase 2](#13-package-files--phase-2)
14. [Fixtures & tests — Phase 2](#14-fixtures--tests--phase-2)
15. [Verify — Phase 2](#15-verify--phase-2)

---

## 1. Repository tree

Create these paths (empty dirs implied):

```
py_vui/
  pyproject.toml
  src/py_vui/
    __init__.py
    __main__.py
    py.typed                    # empty file
    model/
      __init__.py
      schema.py
      geometry.py
      nodes.py
      project.py
      document.py
      serde.py
    commands/
      __init__.py
      base.py
      history.py
      builtins.py
    codegen/
      __init__.py
      types.py
      pyside_emit.py
    preview/
      __init__.py
      runner.py
    app/
      __init__.py
      qt_main.py
  tests/
    test_serde_roundtrip.py
    test_project_validate.py
    test_commands.py
    test_codegen_smoke.py
  examples/fixtures/
    minimal.json
```

---

## 2. Wire format (`py_vui.json`)

### Top-level

| Field | Type | Required |
|-------|------|----------|
| `schemaVersion` | `"1"` | yes |
| `meta` | object | yes |
| `adapter` | `"pyside6"` | yes |
| `rootId` | string (UUID) | yes |
| `nodes` | object (id → node) | yes |

### `meta`

| Field | Required |
|-------|----------|
| `name` | yes |
| `createdAt`, `updatedAt` | no |

### Tree invariants

1. `nodes[k].id == k` for every key.
2. Exactly one node has `parentId: null`; it must equal `rootId` and have `type: "window"`.
3. BFS from `rootId` reaches all nodes (no orphans, no cycles).
4. `zIndex` is integer ≥ 0; siblings sorted by `(zIndex, id)` for codegen order.

### Node `type` → `props`

| `type` | `props` |
|--------|---------|
| `window` | `title`, `width`, `height` |
| `frame` | `{}` |
| `label` | `text` |
| `button` | `text` |
| `line_edit` | `text`, `placeholder` |
| `checkbox` | `text`, `checked` |

### `layout`

```json
{
  "box": { "x": 0, "y": 0, "w": 400, "h": 300 },
  "anchors": { "left": true, "top": true, "right": false, "bottom": false },
  "margins": { "top": 0, "right": 0, "bottom": 0, "left": 0 }
}
```

Phase 1 codegen uses **`layout.box` only** (`setGeometry`).

### Python ↔ JSON field names

| JSON | Python |
|------|--------|
| `schemaVersion` | `schema_version` |
| `rootId` | `root_id` |
| `parentId` | `parent_id` |
| `zIndex` | `z_index` |
| `createdAt` | `created_at` |
| `updatedAt` | `updated_at` |

---

## 3. JSON Schema

Save optionally as `docs/schema/py_vui-project-1.json` for non-Python validators.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://py_vui.dev/schema/py_vui-project-1.json",
  "title": "py_vuiProject",
  "type": "object",
  "additionalProperties": false,
  "required": ["schemaVersion", "meta", "adapter", "rootId", "nodes"],
  "properties": {
    "schemaVersion": { "type": "string", "const": "1" },
    "adapter": { "type": "string", "enum": ["pyside6"] },
    "rootId": { "type": "string", "minLength": 1 },
    "meta": {
      "type": "object",
      "additionalProperties": false,
      "required": ["name"],
      "properties": {
        "name": { "type": "string" },
        "createdAt": { "type": "string" },
        "updatedAt": { "type": "string" }
      }
    },
    "nodes": {
      "type": "object",
      "additionalProperties": { "$ref": "#/$defs/node" }
    }
  },
  "$defs": {
    "layout": {
      "type": "object",
      "additionalProperties": false,
      "required": ["box", "anchors", "margins"],
      "properties": {
        "box": {
          "type": "object",
          "additionalProperties": false,
          "required": ["x", "y", "w", "h"],
          "properties": {
            "x": { "type": "number" },
            "y": { "type": "number" },
            "w": { "type": "number", "minimum": 0 },
            "h": { "type": "number", "minimum": 0 }
          }
        },
        "anchors": {
          "type": "object",
          "additionalProperties": false,
          "required": ["left", "top", "right", "bottom"],
          "properties": {
            "left": { "type": "boolean" },
            "top": { "type": "boolean" },
            "right": { "type": "boolean" },
            "bottom": { "type": "boolean" }
          }
        },
        "margins": {
          "type": "object",
          "additionalProperties": false,
          "required": ["top", "right", "bottom", "left"],
          "properties": {
            "top": { "type": "number" },
            "right": { "type": "number" },
            "bottom": { "type": "number" },
            "left": { "type": "number" }
          }
        }
      }
    },
    "nodeBase": {
      "type": "object",
      "additionalProperties": false,
      "required": ["id", "type", "name", "parentId", "zIndex", "layout", "props"],
      "properties": {
        "id": { "type": "string", "minLength": 1 },
        "type": { "type": "string" },
        "name": { "type": "string" },
        "parentId": { "type": ["string", "null"] },
        "zIndex": { "type": "integer", "minimum": 0 },
        "layout": { "$ref": "#/$defs/layout" },
        "props": { "type": "object" }
      }
    },
    "node": {
      "oneOf": [
        {
          "allOf": [
            { "$ref": "#/$defs/nodeBase" },
            {
              "properties": {
                "type": { "const": "window" },
                "props": {
                  "type": "object",
                  "additionalProperties": false,
                  "required": ["title", "width", "height"],
                  "properties": {
                    "title": { "type": "string" },
                    "width": { "type": "number", "minimum": 1 },
                    "height": { "type": "number", "minimum": 1 }
                  }
                }
              }
            }
          ]
        },
        {
          "allOf": [
            { "$ref": "#/$defs/nodeBase" },
            {
              "properties": {
                "type": { "const": "frame" },
                "props": { "type": "object", "additionalProperties": false }
              }
            }
          ]
        },
        {
          "allOf": [
            { "$ref": "#/$defs/nodeBase" },
            {
              "properties": {
                "type": { "const": "label" },
                "props": {
                  "type": "object",
                  "additionalProperties": false,
                  "required": ["text"],
                  "properties": { "text": { "type": "string" } }
                }
              }
            }
          ]
        },
        {
          "allOf": [
            { "$ref": "#/$defs/nodeBase" },
            {
              "properties": {
                "type": { "const": "button" },
                "props": {
                  "type": "object",
                  "additionalProperties": false,
                  "required": ["text"],
                  "properties": { "text": { "type": "string" } }
                }
              }
            }
          ]
        },
        {
          "allOf": [
            { "$ref": "#/$defs/nodeBase" },
            {
              "properties": {
                "type": { "const": "line_edit" },
                "props": {
                  "type": "object",
                  "additionalProperties": false,
                  "required": ["text", "placeholder"],
                  "properties": {
                    "text": { "type": "string" },
                    "placeholder": { "type": "string" }
                  }
                }
              }
            }
          ]
        },
        {
          "allOf": [
            { "$ref": "#/$defs/nodeBase" },
            {
              "properties": {
                "type": { "const": "checkbox" },
                "props": {
                  "type": "object",
                  "additionalProperties": false,
                  "required": ["text", "checked"],
                  "properties": {
                    "text": { "type": "string" },
                    "checked": { "type": "boolean" }
                  }
                }
              }
            }
          ]
        }
      ]
    }
  }
}
```

### Codegen outputs (on save)

| Path | Role |
|------|------|
| `generated/ui_generated.py` | `def build_ui()` → root `QWidget` |
| `generated/main.py` | `QApplication` entry |

### Preview runner rules

- `cwd = project_root` (resolved absolute).
- `subprocess.run([sys.executable, entry], timeout=30)`.
- **Never** execute code from JSON on open; only on explicit Preview.

---

## 4. Config & packaging

### `pyproject.toml`

```toml
[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"

[project]
name = "py_vui"
version = "0.1.0"
description = "Visual authoring for Python UIs — editor, document model, and codegen"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "pydantic>=2.6",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "ruff>=0.4",
]
gui = [
    "PySide6>=6.6",
]
codegen = [
    "PySide6>=6.6",
]

[project.scripts]
py_vui = "py_vui.app.qt_main:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]

[tool.ruff]
line-length = 100
src = ["src", "tests"]

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]
```

---

## 5. Package `src/py_vui`

### `src/py_vui/__init__.py`

```python
"""py_vui — visual authoring core (document model, commands, codegen, preview)."""

__all__ = ["__version__"]

__version__ = "0.1.0"
```

### `src/py_vui/__main__.py`

```python
from py_vui.app.qt_main import main

if __name__ == "__main__":
    main()
```

### `src/py_vui/py.typed`

Create an **empty** file (PEP 561 marker).

---

### `src/py_vui/model/schema.py`

```python
SCHEMA_VERSION = "1"
```

### `src/py_vui/model/geometry.py`

```python
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Rect(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float = 0.0
    y: float = 0.0
    w: float = 100.0
    h: float = 32.0


class Anchors(BaseModel):
    model_config = ConfigDict(extra="forbid")

    left: bool = True
    top: bool = True
    right: bool = False
    bottom: bool = False


class Margins(BaseModel):
    model_config = ConfigDict(extra="forbid")

    top: float = 0.0
    right: float = 0.0
    bottom: float = 0.0
    left: float = 0.0


class LayoutSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    box: Rect = Field(default_factory=Rect)
    anchors: Anchors = Field(default_factory=Anchors)
    margins: Margins = Field(default_factory=Margins)
```

### `src/py_vui/model/nodes.py`

```python
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from py_vui.model.geometry import LayoutSpec


class NodeCommon(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str = Field(..., min_length=1)
    name: str
    parent_id: str | None = Field(default=None, alias="parentId")
    z_index: int = Field(default=0, ge=0, alias="zIndex")
    layout: LayoutSpec = Field(default_factory=LayoutSpec)


class WindowProps(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = "Window"
    width: float = Field(640.0, ge=1.0)
    height: float = Field(480.0, ge=1.0)


class WindowNode(NodeCommon):
    type: Literal["window"] = "window"
    props: WindowProps = Field(default_factory=WindowProps)


class FrameProps(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FrameNode(NodeCommon):
    type: Literal["frame"] = "frame"
    props: FrameProps = Field(default_factory=FrameProps)


class LabelProps(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = ""


class LabelNode(NodeCommon):
    type: Literal["label"] = "label"
    props: LabelProps = Field(default_factory=LabelProps)


class ButtonProps(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = ""


class ButtonNode(NodeCommon):
    type: Literal["button"] = "button"
    props: ButtonProps = Field(default_factory=ButtonProps)


class LineEditProps(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = ""
    placeholder: str = ""


class LineEditNode(NodeCommon):
    type: Literal["line_edit"] = "line_edit"
    props: LineEditProps = Field(default_factory=LineEditProps)


class CheckboxProps(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = ""
    checked: bool = False


class CheckboxNode(NodeCommon):
    type: Literal["checkbox"] = "checkbox"
    props: CheckboxProps = Field(default_factory=CheckboxProps)


Node = Annotated[
    WindowNode | FrameNode | LabelNode | ButtonNode | LineEditNode | CheckboxNode,
    Field(discriminator="type"),
]
```

### `src/py_vui/model/project.py`

```python
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
    """Raise ValueError if invariants are violated."""

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
```

### `src/py_vui/model/document.py`

```python
from __future__ import annotations

from dataclasses import dataclass

from py_vui.model.nodes import Node
from py_vui.model.project import py_vuiProject, validate_project


@dataclass
class ProjectDocument:
    """Mutable editing façade over `py_vuiProject` (commands mutate this)."""

    project: py_vuiProject

    def validate(self) -> None:
        validate_project(self.project)

    def get_node(self, node_id: str) -> Node:
        return self.project.nodes[node_id]

    def children(self, parent_id: str) -> list[Node]:
        kids = [n for n in self.project.nodes.values() if n.parent_id == parent_id]
        return sorted(kids, key=lambda n: (n.z_index, n.id))

    def replace_project(self, project: py_vuiProject) -> None:
        self.project = project
```

### `src/py_vui/model/serde.py`

```python
from __future__ import annotations

import json
from typing import Any

from pydantic import TypeAdapter

from py_vui.model.project import py_vuiProject

_project_adapter = TypeAdapter(py_vuiProject)


def load_json(data: str | bytes) -> py_vuiProject:
    raw: Any = json.loads(data)
    return _project_adapter.validate_python(raw)


def load_json_bytes(data: bytes) -> py_vuiProject:
    return load_json(data.decode("utf-8"))


def dump_json(project: py_vuiProject, *, indent: int | None = 2) -> str:
    data = project.model_dump(mode="json", by_alias=True)
    return json.dumps(data, indent=indent, sort_keys=True)


def dump_json_bytes(project: py_vuiProject, *, indent: int | None = 2) -> bytes:
    return dump_json(project, indent=indent).encode("utf-8")
```

### `src/py_vui/model/__init__.py`

```python
from __future__ import annotations

from py_vui.model.geometry import Anchors, LayoutSpec, Margins, Rect
from py_vui.model.nodes import (
    ButtonNode,
    ButtonProps,
    CheckboxNode,
    CheckboxProps,
    FrameNode,
    FrameProps,
    LabelNode,
    LabelProps,
    LineEditNode,
    LineEditProps,
    Node,
    WindowNode,
    WindowProps,
)
from py_vui.model.project import ProjectMeta, py_vuiProject, validate_project
from py_vui.model.schema import SCHEMA_VERSION
from py_vui.model.serde import dump_json, dump_json_bytes, load_json, load_json_bytes

__all__ = [
    "SCHEMA_VERSION",
    "Anchors",
    "ButtonNode",
    "ButtonProps",
    "CheckboxNode",
    "CheckboxProps",
    "FrameNode",
    "FrameProps",
    "LabelNode",
    "LabelProps",
    "LayoutSpec",
    "LineEditNode",
    "LineEditProps",
    "Margins",
    "Node",
    "ProjectMeta",
    "py_vuiProject",
    "Rect",
    "WindowNode",
    "WindowProps",
    "dump_json",
    "dump_json_bytes",
    "load_json",
    "load_json_bytes",
    "validate_project",
]
```

---

### `src/py_vui/commands/base.py`

```python
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
```

### `src/py_vui/commands/history.py`

```python
from __future__ import annotations

from dataclasses import dataclass, field

from py_vui.commands.base import Command
from py_vui.model.document import ProjectDocument


@dataclass
class History:
    """Undo/redo stack. Undo calls `revert`; redo reapplies the same command."""

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
```

### `src/py_vui/commands/builtins.py`

```python
from __future__ import annotations

from dataclasses import dataclass

from py_vui.commands.base import Command
from py_vui.model.document import ProjectDocument
from py_vui.model.geometry import Rect
from py_vui.model.nodes import Node
from py_vui.model.project import py_vuiProject


def _collect_subtree_ids(doc: ProjectDocument, root_id: str) -> list[str]:
    out: list[str] = []
    stack = [root_id]
    while stack:
        cur = stack.pop()
        out.append(cur)
        for child in doc.children(cur):
            stack.append(child.id)
    return out


def _remove_ids(project: py_vuiProject, ids: set[str]) -> None:
    for i in ids:
        del project.nodes[i]


@dataclass
class AddNode(Command):
    node: Node

    def apply(self, doc: ProjectDocument) -> None:
        if self.node.id in doc.project.nodes:
            msg = f"duplicate node id {self.node.id!r}"
            raise ValueError(msg)
        if self.node.parent_id is not None and self.node.parent_id not in doc.project.nodes:
            msg = f"missing parent {self.node.parent_id!r}"
            raise ValueError(msg)
        doc.project.nodes[self.node.id] = self.node

    def revert(self, doc: ProjectDocument) -> None:
        del doc.project.nodes[self.node.id]


@dataclass
class RemoveSubtree(Command):
    root_id: str
    _removed: dict[str, Node] | None = None

    def apply(self, doc: ProjectDocument) -> None:
        if self.root_id == doc.project.root_id:
            msg = "cannot remove project root subtree"
            raise ValueError(msg)
        if self.root_id not in doc.project.nodes:
            msg = f"missing node {self.root_id!r}"
            raise ValueError(msg)
        ids = _collect_subtree_ids(doc, self.root_id)
        self._removed = {i: doc.project.nodes[i] for i in ids}
        _remove_ids(doc.project, set(ids))

    def revert(self, doc: ProjectDocument) -> None:
        if not self._removed:
            msg = "RemoveSubtree not applied"
            raise RuntimeError(msg)
        doc.project.nodes.update(self._removed)
        self._removed = None


@dataclass
class ReparentNode(Command):
    node_id: str
    new_parent_id: str
    new_z_index: int | None = None
    _old_parent_id: str | None = None
    _old_z_index: int = 0
    _applied: bool = False

    def apply(self, doc: ProjectDocument) -> None:
        node = doc.project.nodes[self.node_id]
        if self.node_id == doc.project.root_id:
            msg = "cannot reparent root"
            raise ValueError(msg)
        if self.new_parent_id not in doc.project.nodes:
            msg = f"missing parent {self.new_parent_id!r}"
            raise ValueError(msg)

        if _is_descendant(doc, self.node_id, self.new_parent_id):
            msg = "cannot reparent a node into its own subtree"
            raise ValueError(msg)

        self._old_parent_id = node.parent_id
        self._old_z_index = node.z_index

        node.parent_id = self.new_parent_id
        if self.new_z_index is not None:
            node.z_index = self.new_z_index
        self._applied = True

    def revert(self, doc: ProjectDocument) -> None:
        if not self._applied:
            msg = "ReparentNode not applied"
            raise RuntimeError(msg)
        node = doc.project.nodes[self.node_id]
        if self._old_parent_id is None:
            msg = "invalid ReparentNode state (missing old parent)"
            raise RuntimeError(msg)
        node.parent_id = self._old_parent_id
        node.z_index = self._old_z_index
        self._applied = False


def _is_descendant(doc: ProjectDocument, ancestor_id: str, target_id: str) -> bool:
    """True if `target_id` is `ancestor_id` or contained in its subtree."""

    if ancestor_id == target_id:
        return True
    for child in doc.children(ancestor_id):
        if _is_descendant(doc, child.id, target_id):
            return True
    return False


@dataclass
class SetLayoutBox(Command):
    node_id: str
    new_box: Rect
    _old_box: Rect | None = None

    def apply(self, doc: ProjectDocument) -> None:
        node = doc.project.nodes[self.node_id]
        self._old_box = node.layout.box.model_copy(deep=True)
        node.layout.box = self.new_box.model_copy(deep=True)

    def revert(self, doc: ProjectDocument) -> None:
        node = doc.project.nodes[self.node_id]
        if self._old_box is None:
            msg = "SetLayoutBox not applied"
            raise RuntimeError(msg)
        node.layout.box = self._old_box


@dataclass
class ReplaceNode(Command):
    """Replace a node with another having the same `id` (e.g. props edits)."""

    before: Node
    after: Node

    def apply(self, doc: ProjectDocument) -> None:
        if self.before.id != self.after.id:
            msg = "ReplaceNode requires matching ids"
            raise ValueError(msg)
        current = doc.project.nodes.get(self.before.id)
        if current is None:
            msg = f"missing node {self.before.id!r}"
            raise ValueError(msg)
        if current.model_dump(mode="json") != self.before.model_dump(mode="json"):
            msg = "document node does not match `before` snapshot"
            raise ValueError(msg)
        doc.project.nodes[self.after.id] = self.after

    def revert(self, doc: ProjectDocument) -> None:
        doc.project.nodes[self.before.id] = self.before
```

### `src/py_vui/commands/__init__.py`

```python
from py_vui.commands.base import Command
from py_vui.commands.builtins import (
    AddNode,
    RemoveSubtree,
    ReparentNode,
    ReplaceNode,
    SetLayoutBox,
)
from py_vui.commands.history import History

__all__ = [
    "AddNode",
    "Command",
    "History",
    "RemoveSubtree",
    "ReparentNode",
    "ReplaceNode",
    "SetLayoutBox",
]
```

### `src/py_vui/codegen/types.py`

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WrittenFile:
    path: str
    """POSIX-style relative path, e.g. `generated/main.py`."""

    content: str
```

### `src/py_vui/codegen/pyside_emit.py`

```python
from __future__ import annotations

import re
import textwrap

from py_vui.codegen.types import WrittenFile
from py_vui.model.document import ProjectDocument
from py_vui.model.nodes import (
    ButtonNode,
    CheckboxNode,
    FrameNode,
    LabelNode,
    LineEditNode,
    Node,
    WindowNode,
)
from py_vui.model.project import py_vuiProject


def _py_ident(node_id: str) -> str:
    return "w_" + re.sub(r"[^0-9a-zA-Z]+", "_", node_id)


def _emit_widget_ctor(node: Node) -> tuple[str, str]:
    if isinstance(node, WindowNode):
        return ("QWidget", "QWidget()")
    if isinstance(node, FrameNode):
        return ("QFrame", "QFrame()")
    if isinstance(node, LabelNode):
        return ("QLabel", "QLabel()")
    if isinstance(node, ButtonNode):
        return ("QPushButton", "QPushButton()")
    if isinstance(node, LineEditNode):
        return ("QLineEdit", "QLineEdit()")
    if isinstance(node, CheckboxNode):
        return ("QCheckBox", "QCheckBox()")
    msg = f"unsupported node type for Phase 1 PySide6 emit: {node.type!r}"
    raise ValueError(msg)


def _emit_props_lines(node: Node, var: str) -> list[str]:
    lines: list[str] = []
    b = node.layout.box
    lines.append(f"{var}.setGeometry(int({b.x}), int({b.y}), int({b.w}), int({b.h}))")
    if isinstance(node, WindowNode):
        p = node.props
        lines.append(f"{var}.setWindowTitle({p.title!r})")
        lines.append(f"{var}.resize(int({p.width}), int({p.height}))")
    elif isinstance(node, LabelNode):
        lines.append(f"{var}.setText({node.props.text!r})")
    elif isinstance(node, ButtonNode):
        lines.append(f"{var}.setText({node.props.text!r})")
    elif isinstance(node, LineEditNode):
        lines.append(f"{var}.setText({node.props.text!r})")
        lines.append(f"{var}.setPlaceholderText({node.props.placeholder!r})")
    elif isinstance(node, CheckboxNode):
        lines.append(f"{var}.setText({node.props.text!r})")
        lines.append(f"{var}.setChecked({str(node.props.checked)})")
    return lines


def emit_pyside_phase1(project: py_vuiProject) -> list[WrittenFile]:
    if project.adapter != "pyside6":
        msg = f"unsupported adapter {project.adapter!r}"
        raise ValueError(msg)

    doc = ProjectDocument(project)

    order: list[str] = []

    def dfs(nid: str) -> None:
        order.append(nid)
        for ch in doc.children(nid):
            dfs(ch.id)

    dfs(project.root_id)

    imports: set[str] = set()
    body: list[str] = []
    for nid in order:
        node = project.nodes[nid]
        imp, ctor = _emit_widget_ctor(node)
        imports.add(imp)
        var = _py_ident(nid)
        body.append(f"{var} = {ctor}")

    for nid in order:
        node = project.nodes[nid]
        var = _py_ident(nid)
        if nid != project.root_id and node.parent_id is not None:
            parent = project.nodes[node.parent_id]
            pvar = _py_ident(parent.id)
            body.append(f"{var}.setParent({pvar})")
        body.extend(_emit_props_lines(node, var))

    root_var = _py_ident(project.root_id)
    body.append(f"return {root_var}")

    import_names = sorted(imports)
    ui_lines: list[str] = [
        '"""Generated by py_vui — do not hand-edit unless you know the merge rules."""',
        "",
        "def build_ui():",
        "    from PySide6.QtWidgets import (",
    ]
    for name in import_names:
        ui_lines.append(f"        {name},")
    ui_lines.append("    )")
    ui_lines.append("")
    for ln in body:
        ui_lines.append(f"    {ln}")
    ui_text = "\n".join(ui_lines) + "\n"

    main_text = textwrap.dedent(
        """\
        import sys

        from PySide6.QtWidgets import QApplication

        from ui_generated import build_ui


        def main() -> int:
            app = QApplication(sys.argv)
            root = build_ui()
            root.show()
            return int(app.exec())


        if __name__ == "__main__":
            raise SystemExit(main())
        """
    )

    return [
        WrittenFile("generated/ui_generated.py", ui_text),
        WrittenFile("generated/main.py", main_text),
    ]
```

### `src/py_vui/codegen/__init__.py`

```python
from py_vui.codegen.pyside_emit import emit_pyside_phase1
from py_vui.codegen.types import WrittenFile

__all__ = ["WrittenFile", "emit_pyside_phase1"]
```

### `src/py_vui/preview/runner.py`

```python
from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class PreviewResult:
    returncode: int
    stdout: str
    stderr: str


def run_preview(project_root: Path, entry: Path, *, timeout_s: float = 30.0) -> PreviewResult:
    """Run `python entry` with cwd=`project_root` (resolved to absolute)."""

    root = project_root.resolve()
    if not root.is_dir():
        msg = f"project_root is not a directory: {root}"
        raise ValueError(msg)
    script = entry if entry.is_absolute() else (root / entry)
    if not script.is_file():
        msg = f"entry script missing: {script}"
        raise ValueError(msg)

    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=timeout_s,
        check=False,
    )
    return PreviewResult(proc.returncode, proc.stdout, proc.stderr)
```

### `src/py_vui/preview/__init__.py`

```python
from py_vui.preview.runner import PreviewResult, run_preview

__all__ = ["PreviewResult", "run_preview"]
```

### `src/py_vui/app/__init__.py`

```python
"""Qt entrypoint package (optional `PySide6`)."""
```

### `src/py_vui/app/qt_main.py`

```python
from __future__ import annotations


def main() -> None:
    try:
        from PySide6.QtWidgets import QApplication, QLabel, QWidget
    except ModuleNotFoundError:
        print("py_vui editor shell requires optional dependency: pip install py_vui[gui]")
        raise SystemExit(1) from None

    app = QApplication([])
    window = QWidget()
    window.setWindowTitle("py_vui (stub)")
    label = QLabel("Editor shell not implemented yet.", parent=window)
    label.move(12, 12)
    window.resize(420, 120)
    window.show()
    app.exec()


if __name__ == "__main__":
    main()
```

---

## 6. Tests

### `tests/test_serde_roundtrip.py`

```python
from __future__ import annotations

from pathlib import Path

from py_vui.model.project import validate_project
from py_vui.model.serde import dump_json, load_json


def test_minimal_fixture_roundtrip() -> None:
    raw = Path("examples/fixtures/minimal.json").read_bytes()
    project = load_json(raw)
    validate_project(project)
    out = dump_json(project)
    project2 = load_json(out)
    validate_project(project2)
    assert project2.model_dump(mode="json") == project.model_dump(mode="json")
```

### `tests/test_project_validate.py`

```python
from __future__ import annotations

import copy

import pytest

from py_vui.model.project import py_vuiProject, validate_project
from py_vui.model.serde import load_json


def _minimal() -> py_vuiProject:
    from pathlib import Path

    return load_json(Path("examples/fixtures/minimal.json").read_bytes())


def test_validate_ok() -> None:
    validate_project(_minimal())


def test_validate_bad_root() -> None:
    p = _minimal()
    data = p.model_dump(mode="json", by_alias=True)
    data["rootId"] = "ffffffff-ffff-4fff-8fff-ffffffffffff"
    bad = py_vuiProject.model_validate(data)
    with pytest.raises(ValueError, match="missing from nodes"):
        validate_project(bad)


def test_validate_orphan() -> None:
    p = _minimal()
    data = p.model_dump(mode="json", by_alias=True)
    nodes = copy.deepcopy(data["nodes"])
    nodes["33333333-3333-4333-8333-333333333333"]["parentId"] = (
        "ffffffff-ffff-4fff-8fff-ffffffffffff"
    )
    data["nodes"] = nodes
    bad = py_vuiProject.model_validate(data)
    with pytest.raises(ValueError, match="missing parent"):
        validate_project(bad)
```

### `tests/test_commands.py`

```python
from __future__ import annotations

from pathlib import Path

import pytest

from py_vui.commands import AddNode, History, RemoveSubtree, ReparentNode
from py_vui.model.document import ProjectDocument
from py_vui.model.nodes import ButtonNode, ButtonProps, FrameNode, FrameProps
from py_vui.model.project import validate_project
from py_vui.model.serde import load_json


def test_add_remove_undo() -> None:
    p = load_json(Path("examples/fixtures/minimal.json").read_bytes())
    doc = ProjectDocument(p)
    hist = History()

    btn = ButtonNode(
        id="44444444-4444-4444-8444-444444444444",
        name="Ok",
        parent_id=p.root_id,
        z_index=1,
        props=ButtonProps(text="OK"),
    )
    hist.push(doc, AddNode(btn))
    assert btn.id in doc.project.nodes

    hist.undo(doc)
    assert btn.id not in doc.project.nodes

    hist.redo(doc)
    assert btn.id in doc.project.nodes


def test_reparent_rejects_cycle() -> None:
    p = load_json(Path("examples/fixtures/minimal.json").read_bytes())
    doc = ProjectDocument(p)
    hist = History()

    inner = FrameNode(
        id="55555555-5555-4555-8555-555555555555",
        name="Inner",
        parent_id="22222222-2222-4222-8222-222222222222",
        z_index=1,
        props=FrameProps(),
    )
    hist.push(doc, AddNode(inner))
    validate_project(doc.project)

    with pytest.raises(ValueError, match="subtree"):
        hist.push(
            doc,
            ReparentNode(
                node_id="22222222-2222-4222-8222-222222222222",
                new_parent_id="55555555-5555-4555-8555-555555555555",
            ),
        )


def test_remove_subtree() -> None:
    p = load_json(Path("examples/fixtures/minimal.json").read_bytes())
    doc = ProjectDocument(p)
    hist = History()
    hist.push(doc, RemoveSubtree("22222222-2222-4222-8222-222222222222"))
    assert "22222222-2222-4222-8222-222222222222" not in doc.project.nodes
    assert "33333333-3333-4333-8333-333333333333" not in doc.project.nodes
    validate_project(doc.project)
```

### `tests/test_codegen_smoke.py`

```python
from __future__ import annotations

from pathlib import Path

from py_vui.codegen import emit_pyside_phase1
from py_vui.model.serde import load_json


def test_emit_minimal_contains_expected_symbols() -> None:
    p = load_json(Path("examples/fixtures/minimal.json").read_bytes())
    files = {f.path: f.content for f in emit_pyside_phase1(p)}
    ui = files["generated/ui_generated.py"]
    assert "def build_ui():" in ui
    assert "QFrame" in ui
    assert "QLabel" in ui
    main = files["generated/main.py"]
    assert "QApplication" in main
    assert "from ui_generated import build_ui" in main
```

---

## 7. Fixture

### `examples/fixtures/minimal.json`

```json
{
  "adapter": "pyside6",
  "meta": {
    "name": "minimal"
  },
  "nodes": {
    "11111111-1111-4111-8111-111111111111": {
      "id": "11111111-1111-4111-8111-111111111111",
      "layout": {
        "anchors": {
          "bottom": false,
          "left": true,
          "right": false,
          "top": true
        },
        "box": {
          "h": 480,
          "w": 640,
          "x": 0,
          "y": 0
        },
        "margins": {
          "bottom": 0,
          "left": 0,
          "right": 0,
          "top": 0
        }
      },
      "name": "MainWindow",
      "parentId": null,
      "props": {
        "height": 480,
        "title": "Hello",
        "width": 640
      },
      "type": "window",
      "zIndex": 0
    },
    "22222222-2222-4222-8222-222222222222": {
      "id": "22222222-2222-4222-8222-222222222222",
      "layout": {
        "anchors": {
          "bottom": false,
          "left": true,
          "right": false,
          "top": true
        },
        "box": {
          "h": 400,
          "w": 600,
          "x": 12,
          "y": 12
        },
        "margins": {
          "bottom": 0,
          "left": 0,
          "right": 0,
          "top": 0
        }
      },
      "name": "Content",
      "parentId": "11111111-1111-4111-8111-111111111111",
      "props": {},
      "type": "frame",
      "zIndex": 0
    },
    "33333333-3333-4333-8333-333333333333": {
      "id": "33333333-3333-4333-8333-333333333333",
      "layout": {
        "anchors": {
          "bottom": false,
          "left": true,
          "right": false,
          "top": true
        },
        "box": {
          "h": 24,
          "w": 200,
          "x": 8,
          "y": 8
        },
        "margins": {
          "bottom": 0,
          "left": 0,
          "right": 0,
          "top": 0
        }
      },
      "name": "Title",
      "parentId": "22222222-2222-4222-8222-222222222222",
      "props": {
        "text": "Welcome to py_vui"
      },
      "type": "label",
      "zIndex": 0
    }
  },
  "rootId": "11111111-1111-4111-8111-111111111111",
  "schemaVersion": "1"
}
```

---

## 8. Verify

After creating all files and replacing `pyproject.toml`:

```bash
cd py_vui
uv sync --extra dev
uv run pytest -q
uv run ruff check src tests
```

Smoke-load fixture:

```bash
uv run python -c "
from pathlib import Path
from py_vui.model.serde import load_json
from py_vui.model.project import validate_project
p = load_json(Path('examples/fixtures/minimal.json').read_bytes())
validate_project(p)
print('ok')
"
```

Optional editor stub (needs PySide6):

```bash
uv sync --extra gui
uv run py_vui
```

---

# Phase 2 — pygame studio

## 9. Phase 2 overview

Phase 2 adds a **second project kind** on the same document/command architecture:

| Concern | Phase 1 | Phase 2 |
|---------|---------|---------|
| `schemaVersion` | `"1"` | `"2"` |
| `adapter` | `"pyside6"` | `"pygame"` |
| Root node `type` | `window` | `scene` |
| Codegen output | `generated/main.py`, `ui_generated.py` | `generated/game.py`, `config.py`, `scenes.py` |
| Preview entry | `generated/main.py` | `generated/game.py --py_vui-design` |
| Assets | N/A | Relative paths under `assets/` (validated, no `..`) |

**Design-mode preview:** subprocess runs `python generated/game.py --py_vui-design` so the same runtime draws editor gizmos and skips gameplay hooks where flagged.

**Non-goals (Phase 2 v1):** ECS, physics engine, networked multiplayer, texture atlas tooling.

---

## 10. Wire format — Phase 2

### Top-level (additions / differences)

| Field | Type | Required | Notes |
|-------|------|----------|--------|
| `schemaVersion` | `"2"` | yes | Game projects only. |
| `adapter` | `"pygame"` | yes | |
| `rootId` | UUID | yes | Must reference a `scene` node. |
| `runtime` | object | yes | Screen / loop settings (§10.1). |
| `inputMap` | array | no | Default `[]`. |
| `systems` | array | no | Update pipeline order (§10.2). |
| `assetsRoot` | string | no | Default `"assets"`. |

Phase 1 fields (`meta`, `nodes`) unchanged in shape; **node `type` union is extended** (§10.3).

### 10.1 `runtime`

```json
{
  "width": 800,
  "height": 600,
  "fps": 60,
  "fullscreen": false
}
```

### 10.2 `systems` entry

```json
{ "id": "default_update", "scriptHook": "on_update", "enabled": true, "order": 0 }
```

- `order` — lower runs first in generated `update(dt)`.
- `scriptHook` — name of optional user function in `custom/game_hooks.py` (stub only in v1).

### 10.3 Game node types

All game nodes include Phase 1 common fields (`id`, `name`, `parentId`, `zIndex`, `layout`) **plus**:

```json
"transform": {
  "x": 100,
  "y": 200,
  "rotation": 0,
  "scaleX": 1,
  "scaleY": 1
}
```

| `type` | `props` | Role |
|--------|---------|------|
| `scene` | `backgroundColor` (hex `#RRGGBB`), `backgroundImage` (string \| null), `worldWidth`, `worldHeight` | Root world |
| `sprite` | `spritePath`, `scriptHook` (string, may be `""`) | Drawable entity |
| `camera_2d` | `followTargetId` (string \| null), `zoom` (number, default 1) | View (one per scene typical) |

**`spritePath`:** relative to project root, must live under `assetsRoot` (e.g. `assets/player.png`).

**Tree rules (schema v2):**

1. Same invariants as Phase 1 (single root, acyclic tree, key/id match).
2. Root `type` must be `scene`.
3. Only `scene` may have `parentId: null`.
4. `camera_2d` and `sprite` must be descendants of a `scene` (any depth under root scene subtree).
5. Asset paths validated on save/load (see `assets.py`).

### 10.4 `inputMap` entry

```json
{ "action": "jump", "keys": ["K_SPACE", "K_w"] }
```

Exported to `generated/config.py` as a dict of action → list of pygame key constant names.

---

## 11. JSON Schema — Phase 2 extensions

Use **schema version 2** as a separate document (or merge into one schema with `schemaVersion` discriminator). Minimal v2 root:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://py_vui.dev/schema/py_vui-project-2.json",
  "title": "py_vuiGameProject",
  "type": "object",
  "additionalProperties": false,
  "required": ["schemaVersion", "meta", "adapter", "rootId", "nodes", "runtime"],
  "properties": {
    "schemaVersion": { "type": "string", "const": "2" },
    "adapter": { "type": "string", "const": "pygame" },
    "rootId": { "type": "string", "minLength": 1 },
    "assetsRoot": { "type": "string", "default": "assets" },
    "meta": {
      "type": "object",
      "additionalProperties": false,
      "required": ["name"],
      "properties": {
        "name": { "type": "string" },
        "createdAt": { "type": "string" },
        "updatedAt": { "type": "string" }
      }
    },
    "runtime": {
      "type": "object",
      "additionalProperties": false,
      "required": ["width", "height", "fps"],
      "properties": {
        "width": { "type": "integer", "minimum": 1 },
        "height": { "type": "integer", "minimum": 1 },
        "fps": { "type": "integer", "minimum": 1 },
        "fullscreen": { "type": "boolean" }
      }
    },
    "inputMap": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["action", "keys"],
        "properties": {
          "action": { "type": "string" },
          "keys": { "type": "array", "items": { "type": "string" } }
        }
      }
    },
    "systems": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["id", "order"],
        "properties": {
          "id": { "type": "string" },
          "scriptHook": { "type": "string" },
          "enabled": { "type": "boolean" },
          "order": { "type": "integer" }
        }
      }
    },
    "nodes": {
      "type": "object",
      "additionalProperties": { "$ref": "#/$defs/gameNode" }
    }
  },
  "$defs": {
    "transform": {
      "type": "object",
      "additionalProperties": false,
      "required": ["x", "y", "rotation", "scaleX", "scaleY"],
      "properties": {
        "x": { "type": "number" },
        "y": { "type": "number" },
        "rotation": { "type": "number" },
        "scaleX": { "type": "number" },
        "scaleY": { "type": "number" }
      }
    },
    "gameNodeBase": {
      "type": "object",
      "additionalProperties": false,
      "required": ["id", "type", "name", "parentId", "zIndex", "layout", "transform", "props"],
      "properties": {
        "id": { "type": "string" },
        "type": { "type": "string" },
        "name": { "type": "string" },
        "parentId": { "type": ["string", "null"] },
        "zIndex": { "type": "integer", "minimum": 0 },
        "layout": { "$ref": "https://py_vui.dev/schema/py_vui-project-1.json#/$defs/layout" },
        "transform": { "$ref": "#/$defs/transform" },
        "props": { "type": "object" }
      }
    },
    "gameNode": {
      "oneOf": [
        {
          "allOf": [
            { "$ref": "#/$defs/gameNodeBase" },
            {
              "properties": {
                "type": { "const": "scene" },
                "props": {
                  "type": "object",
                  "additionalProperties": false,
                  "required": ["backgroundColor", "worldWidth", "worldHeight"],
                  "properties": {
                    "backgroundColor": { "type": "string", "pattern": "^#[0-9A-Fa-f]{6}$" },
                    "backgroundImage": { "type": ["string", "null"] },
                    "worldWidth": { "type": "number", "minimum": 1 },
                    "worldHeight": { "type": "number", "minimum": 1 }
                  }
                }
              }
            }
          ]
        },
        {
          "allOf": [
            { "$ref": "#/$defs/gameNodeBase" },
            {
              "properties": {
                "type": { "const": "sprite" },
                "props": {
                  "type": "object",
                  "additionalProperties": false,
                  "required": ["spritePath", "scriptHook"],
                  "properties": {
                    "spritePath": { "type": "string" },
                    "scriptHook": { "type": "string" }
                  }
                }
              }
            }
          ]
        },
        {
          "allOf": [
            { "$ref": "#/$defs/gameNodeBase" },
            {
              "properties": {
                "type": { "const": "camera_2d" },
                "props": {
                  "type": "object",
                  "additionalProperties": false,
                  "required": ["followTargetId", "zoom"],
                  "properties": {
                    "followTargetId": { "type": ["string", "null"] },
                    "zoom": { "type": "number", "minimum": 0.01 }
                  }
                }
              }
            }
          ]
        }
      ]
    }
  }
}
```

### Codegen outputs (Phase 2)

| Path | Role |
|------|------|
| `generated/config.py` | `SCREEN`, `FPS`, `INPUT_MAP`, `DESIGN_MODE` |
| `generated/scenes.py` | `build_scenes(design: bool)` → scene instances |
| `generated/game.py` | `pygame` main loop, `--py_vui-design` flag |

---

## 12. Repository additions

Add to the Phase 1 tree:

```
  src/py_vui/
    model/
      transform.py
      game_nodes.py
      assets.py
    codegen/
      pygame_emit.py
  examples/fixtures/
    minimal_game.json
  tests/
    test_game_validate.py
    test_pygame_codegen.py
    test_assets.py
```

**Phase 2 edits to existing files** (full replacements in §13):

- `model/schema.py` — add `SCHEMA_VERSION_GAME = "2"`
- `model/project.py` — v2 fields + `validate_project` branches
- `model/nodes.py` — optional: keep UI-only; game types live in `game_nodes.py`
- `model/__init__.py` — export game types
- `codegen/__init__.py` — export `emit_pygame_phase2`
- `preview/runner.py` — `extra_args` for design mode
- `commands/builtins.py` — append `SetTransform`
- `pyproject.toml` — `[project.optional-dependencies] pygame = ["pygame>=2.5"]`

---

## 13. Package files — Phase 2

### `pyproject.toml` — optional deps block (merge into §4 file)

Add under `[project.optional-dependencies]`:

```toml
pygame = [
    "pygame>=2.5",
]
```

Combined extras example: `pip install -e ".[dev,pygame]"`.

---

### `src/py_vui/model/schema.py` — replace entire file

```python
SCHEMA_VERSION = "1"
SCHEMA_VERSION_GAME = "2"
```

---

### `src/py_vui/model/transform.py` — new file

```python
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Transform2D(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    x: float = 0.0
    y: float = 0.0
    rotation: float = 0.0
    scale_x: float = Field(default=1.0, alias="scaleX")
    scale_y: float = Field(default=1.0, alias="scaleY")
```

---

### `src/py_vui/model/game_nodes.py` — new file

```python
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from py_vui.model.geometry import LayoutSpec
from py_vui.model.transform import Transform2D


class GameNodeCommon(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str = Field(..., min_length=1)
    name: str
    parent_id: str | None = Field(default=None, alias="parentId")
    z_index: int = Field(default=0, ge=0, alias="zIndex")
    layout: LayoutSpec = Field(default_factory=LayoutSpec)
    transform: Transform2D = Field(default_factory=Transform2D)


class SceneProps(BaseModel):
    model_config = ConfigDict(extra="forbid")

    background_color: str = Field(default="#1e1e2e", alias="backgroundColor")
    background_image: str | None = Field(default=None, alias="backgroundImage")
    world_width: float = Field(default=800.0, ge=1.0, alias="worldWidth")
    world_height: float = Field(default=600.0, ge=1.0, alias="worldHeight")


class SceneNode(GameNodeCommon):
    type: Literal["scene"] = "scene"
    props: SceneProps = Field(default_factory=SceneProps)


class SpriteProps(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sprite_path: str = Field(..., alias="spritePath")
    script_hook: str = Field(default="", alias="scriptHook")


class SpriteNode(GameNodeCommon):
    type: Literal["sprite"] = "sprite"
    props: SpriteProps


class Camera2DProps(BaseModel):
    model_config = ConfigDict(extra="forbid")

    follow_target_id: str | None = Field(default=None, alias="followTargetId")
    zoom: float = Field(default=1.0, ge=0.01)


class Camera2DNode(GameNodeCommon):
    type: Literal["camera_2d"] = "camera_2d"
    props: Camera2DProps = Field(default_factory=Camera2DProps)


GameNode = Annotated[
    SceneNode | SpriteNode | Camera2DNode,
    Field(discriminator="type"),
]
```

---

### `src/py_vui/model/assets.py` — new file

```python
from __future__ import annotations

from pathlib import Path


class AssetPathError(ValueError):
    pass


def normalize_asset_ref(ref: str) -> str:
    return ref.replace("\\", "/").lstrip("/")


def validate_asset_path(
    project_root: Path,
    assets_root: str,
    asset_ref: str,
) -> Path:
    """Resolve `asset_ref` under `project_root / assets_root`. Reject traversal."""

    ref = normalize_asset_ref(asset_ref)
    if not ref:
        msg = "asset path is empty"
        raise AssetPathError(msg)
    if ".." in ref.split("/"):
        msg = f"asset path must not contain '..': {ref!r}"
        raise AssetPathError(msg)

    root = project_root.resolve()
    assets_dir = (root / assets_root).resolve()
    full = (root / ref).resolve()

    try:
        full.relative_to(assets_dir)
    except ValueError as exc:
        msg = f"asset {ref!r} must be under {assets_root!r}"
        raise AssetPathError(msg) from exc

    return full


def validate_project_assets(
    project_root: Path,
    assets_root: str,
    sprite_paths: list[str],
) -> None:
    for ref in sprite_paths:
        validate_asset_path(project_root, assets_root, ref)
```

---

### `src/py_vui/model/project.py` — replace entire file

```python
from __future__ import annotations

from collections import deque
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from py_vui.model.assets import AssetPathError, normalize_asset_ref, validate_project_assets
from py_vui.model.game_nodes import Camera2DNode, SceneNode, SpriteNode
from py_vui.model.nodes import Node, WindowNode
from py_vui.model.schema import SCHEMA_VERSION, SCHEMA_VERSION_GAME

SchemaVersion = Literal["1", "2"]
AdapterId = Literal["pyside6", "pygame"]


class ProjectMeta(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: str
    created_at: str | None = Field(default=None, alias="createdAt")
    updated_at: str | None = Field(default=None, alias="updatedAt")


class RuntimeSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    width: int = Field(default=800, ge=1)
    height: int = Field(default=600, ge=1)
    fps: int = Field(default=60, ge=1)
    fullscreen: bool = False


class InputBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str
    keys: list[str]


class SystemEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str
    script_hook: str = Field(default="", alias="scriptHook")
    enabled: bool = True
    order: int = 0


class py_vuiProject(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: SchemaVersion = Field(default="1", alias="schemaVersion")
    meta: ProjectMeta
    adapter: AdapterId
    root_id: str = Field(..., alias="rootId")
    nodes: dict[str, Node | SceneNode | SpriteNode | Camera2DNode]

    runtime: RuntimeSettings | None = None
    input_map: list[InputBinding] = Field(default_factory=list, alias="inputMap")
    systems: list[SystemEntry] = Field(default_factory=list)
    assets_root: str = Field(default="assets", alias="assetsRoot")

    @model_validator(mode="after")
    def keys_match_ids(self) -> py_vuiProject:
        for key, node in self.nodes.items():
            if key != node.id:
                msg = f"nodes map key {key!r} must equal node.id {node.id!r}"
                raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def adapter_matches_schema(self) -> py_vuiProject:
        if self.schema_version == SCHEMA_VERSION and self.adapter != "pyside6":
            msg = 'schemaVersion "1" requires adapter "pyside6"'
            raise ValueError(msg)
        if self.schema_version == SCHEMA_VERSION_GAME and self.adapter != "pygame":
            msg = 'schemaVersion "2" requires adapter "pygame"'
            raise ValueError(msg)
        if self.schema_version == SCHEMA_VERSION_GAME and self.runtime is None:
            msg = "schemaVersion 2 requires runtime settings"
            raise ValueError(msg)
        if self.schema_version == SCHEMA_VERSION and self.runtime is not None:
            msg = "schemaVersion 1 must not include runtime"
            raise ValueError(msg)
        return self


def validate_project(project: py_vuiProject, *, project_root: Path | None = None) -> None:
    """Raise ValueError (or AssetPathError) if invariants are violated."""

    if project.schema_version == SCHEMA_VERSION:
        _validate_ui_project(project)
    elif project.schema_version == SCHEMA_VERSION_GAME:
        _validate_game_project(project, project_root=project_root)
    else:
        msg = f"unsupported schemaVersion: {project.schema_version!r}"
        raise ValueError(msg)


def _validate_ui_project(project: py_vuiProject) -> None:
    _validate_tree(project)
    root = project.nodes[project.root_id]
    if not isinstance(root, WindowNode):
        msg = f"root node must be type 'window', got {root.type!r}"
        raise ValueError(msg)


def _validate_game_project(project: py_vuiProject, *, project_root: Path | None) -> None:
    _validate_tree(project)
    root = project.nodes[project.root_id]
    if not isinstance(root, SceneNode):
        msg = f"root node must be type 'scene', got {root.type!r}"
        raise ValueError(msg)

    sprite_paths: list[str] = []
    for node in project.nodes.values():
        if isinstance(node, SpriteNode):
            sprite_paths.append(normalize_asset_ref(node.props.sprite_path))
        if isinstance(node, SceneNode) and node.props.background_image:
            sprite_paths.append(normalize_asset_ref(node.props.background_image))
        if isinstance(node, Camera2DNode) and node.props.follow_target_id:
            tid = node.props.follow_target_id
            if tid not in project.nodes:
                msg = f"camera followTargetId {tid!r} not found"
                raise ValueError(msg)

    if project_root is not None:
        try:
            validate_project_assets(project_root, project.assets_root, sprite_paths)
        except AssetPathError as exc:
            raise ValueError(str(exc)) from exc


def _validate_tree(project: py_vuiProject) -> None:
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
```

---

### `src/py_vui/model/__init__.py` — add to `__all__` and imports

Append exports (keep Phase 1 exports; add):

```python
from py_vui.model.assets import AssetPathError, normalize_asset_ref, validate_asset_path, validate_project_assets
from py_vui.model.game_nodes import Camera2DNode, Camera2DProps, GameNode, SceneNode, SceneProps, SpriteNode, SpriteProps
from py_vui.model.transform import Transform2D
from py_vui.model.project import InputBinding, RuntimeSettings, SystemEntry
from py_vui.model.schema import SCHEMA_VERSION_GAME
```

And extend `__all__` with:
`SCHEMA_VERSION_GAME`, `Transform2D`, `SceneNode`, `SceneProps`, `SpriteNode`, `SpriteProps`, `Camera2DNode`, `Camera2DProps`, `GameNode`, `RuntimeSettings`, `InputBinding`, `SystemEntry`, `AssetPathError`, `normalize_asset_ref`, `validate_asset_path`, `validate_project_assets`.

---

### `src/py_vui/commands/builtins.py` — append after `ReplaceNode`

```python
@dataclass
class SetTransform(Command):
    node_id: str
    new_transform: Transform2D
    _old_transform: Transform2D | None = None

    def apply(self, doc: ProjectDocument) -> None:
        from py_vui.model.game_nodes import GameNodeCommon

        node = doc.project.nodes[self.node_id]
        if not isinstance(node, GameNodeCommon):
            msg = f"node {self.node_id!r} has no transform"
            raise ValueError(msg)
        self._old_transform = node.transform.model_copy(deep=True)
        node.transform = self.new_transform.model_copy(deep=True)

    def revert(self, doc: ProjectDocument) -> None:
        from py_vui.model.game_nodes import GameNodeCommon

        node = doc.project.nodes[self.node_id]
        if not isinstance(node, GameNodeCommon) or self._old_transform is None:
            msg = "SetTransform not applied"
            raise RuntimeError(msg)
        node.transform = self._old_transform
```

Add top-level import: `from py_vui.model.transform import Transform2D`.

Update `commands/__init__.py` `__all__` to include `SetTransform`.

---

### `src/py_vui/codegen/pygame_emit.py` — new file

```python
from __future__ import annotations

import re
import textwrap

from py_vui.codegen.types import WrittenFile
from py_vui.model.document import ProjectDocument
from py_vui.model.game_nodes import Camera2DNode, SceneNode, SpriteNode
from py_vui.model.project import py_vuiProject
from py_vui.model.schema import SCHEMA_VERSION_GAME


def _py_ident(node_id: str) -> str:
    return "n_" + re.sub(r"[^0-9a-zA-Z]+", "_", node_id)


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def emit_pygame_phase2(project: py_vuiProject) -> list[WrittenFile]:
    if project.schema_version != SCHEMA_VERSION_GAME or project.adapter != "pygame":
        msg = "emit_pygame_phase2 requires schemaVersion 2 and adapter pygame"
        raise ValueError(msg)
    if project.runtime is None:
        msg = "missing runtime settings"
        raise ValueError(msg)

    doc = ProjectDocument(project)
    rt = project.runtime

    config_lines = [
        "SCREEN_WIDTH = %d" % rt.width,
        "SCREEN_HEIGHT = %d" % rt.height,
        "FPS = %d" % rt.fps,
        "FULLSCREEN = %s" % repr(rt.fullscreen),
        "INPUT_MAP = %r" % {b.action: b.keys for b in project.input_map},
        "DESIGN_MODE = False",
    ]
    config_text = "\n".join(config_lines) + "\n"

    scene_builders: list[str] = []
    for nid, node in project.nodes.items():
        if not isinstance(node, SceneNode):
            continue
        r, g, b = _hex_to_rgb(node.props.background_color)
        scene_builders.append(f'    scenes["{nid}"] = Scene({node.name!r}, bg=({r}, {g}, {b}))')
        for child in doc.children(nid):
            _emit_entity(scene_builders, project, child, nid)

    builder_body = "\n".join(scene_builders)
    scenes_text = (
        textwrap.dedent(
            '''\
            from __future__ import annotations

            from dataclasses import dataclass, field


            @dataclass
            class Entity:
                node_id: str
                name: str
                x: float
                y: float
                rotation: float
                scale_x: float
                scale_y: float
                sprite_path: str | None = None
                script_hook: str = ""


            @dataclass
            class Scene:
                name: str
                bg: tuple[int, int, int]
                entities: list[Entity] = field(default_factory=list)
                cameras: list[Entity] = field(default_factory=list)


            def build_scenes(design: bool = False) -> dict[str, Scene]:
                scenes: dict[str, Scene] = {}
            '''
        )
        + builder_body
        + textwrap.dedent(
            '''
                if design:
                    for sc in scenes.values():
                        sc.entities.append(
                            Entity("gizmo", "editor_gizmo", 0, 0, 0, 1, 1, None, "")
                        )
                return scenes
            '''
        )
    )

    game_text = textwrap.dedent(
        '''\
        from __future__ import annotations

        import argparse
        import sys

        import pygame

        import config
        from scenes import build_scenes


        def handle_events() -> bool:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return False
            return True


        def update(dt: float, scenes: dict) -> None:
            _ = dt, scenes


        def draw(screen: pygame.Surface, scenes: dict, active_scene_id: str) -> None:
            scene = scenes.get(active_scene_id)
            if scene is None:
                screen.fill((0, 0, 0))
                return
            screen.fill(scene.bg)
            for ent in scene.entities:
                if ent.sprite_path:
                    try:
                        image = pygame.image.load(ent.sprite_path).convert_alpha()
                        image = pygame.transform.rotozoom(
                            image, -ent.rotation, max(ent.scale_x, ent.scale_y)
                        )
                        screen.blit(image, (int(ent.x), int(ent.y)))
                    except pygame.error:
                        pygame.draw.rect(
                            screen, (255, 80, 80), (int(ent.x), int(ent.y), 32, 32), 1
                        )
                elif config.DESIGN_MODE:
                    pygame.draw.circle(screen, (80, 200, 255), (int(ent.x), int(ent.y)), 6)


        def main() -> int:
            parser = argparse.ArgumentParser()
            parser.add_argument("--py_vui-design", action="store_true")
            args = parser.parse_args()
            config.DESIGN_MODE = args.py_vui_design

            pygame.init()
            flags = pygame.FULLSCREEN if config.FULLSCREEN else 0
            screen = pygame.display.set_mode((config.SCREEN_WIDTH, config.SCREEN_HEIGHT), flags)
            pygame.display.set_caption("py_vui game")
            clock = pygame.time.Clock()

            scenes = build_scenes(design=config.DESIGN_MODE)
            active = next(iter(scenes.keys()), "")

            running = True
            while running:
                dt = clock.tick(config.FPS) / 1000.0
                running = handle_events()
                update(dt, scenes)
                draw(screen, scenes, active)
                pygame.display.flip()

            pygame.quit()
            return 0


        if __name__ == "__main__":
            raise SystemExit(main())
        '''
    )

    return [
        WrittenFile("generated/config.py", config_text),
        WrittenFile("generated/scenes.py", scenes_text),
        WrittenFile("generated/game.py", game_text),
    ]


def _emit_entity(lines: list[str], project: py_vuiProject, node, scene_id: str) -> None:
    if isinstance(node, SpriteNode):
        t = node.transform
        p = node.props
        lines.append(
            f'    scenes["{scene_id}"].entities.append(Entity('
            f'"{node.id}", {node.name!r}, {t.x}, {t.y}, {t.rotation}, '
            f"{t.scale_x}, {t.scale_y}, {p.sprite_path!r}, {p.script_hook!r}))"
        )
    elif isinstance(node, Camera2DNode):
        t = node.transform
        lines.append(
            f'    scenes["{scene_id}"].cameras.append(Entity('
            f'"{node.id}", {node.name!r}, {t.x}, {t.y}, 0, 1, 1, None, ""))'
        )
```

> **Note:** `_emit_entity` only attaches direct children of each `scene` node. For deeper hierarchies, extend the DFS in `emit_pygame_phase2` to walk the full subtree (same pattern as Phase 1 `pyside_emit`).

---

### `src/py_vui/codegen/__init__.py` — replace

```python
from py_vui.codegen.pyside_emit import emit_pyside_phase1
from py_vui.codegen.pygame_emit import emit_pygame_phase2
from py_vui.codegen.types import WrittenFile

__all__ = ["WrittenFile", "emit_pyside_phase1", "emit_pygame_phase2"]
```

---

### `src/py_vui/preview/runner.py` — replace

```python
from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class PreviewResult:
    returncode: int
    stdout: str
    stderr: str


def run_preview(
    project_root: Path,
    entry: Path,
    *,
    timeout_s: float = 30.0,
    extra_args: list[str] | None = None,
) -> PreviewResult:
    """Run `python entry [extra_args...]` with cwd=`project_root`."""

    root = project_root.resolve()
    if not root.is_dir():
        msg = f"project_root is not a directory: {root}"
        raise ValueError(msg)
    script = entry if entry.is_absolute() else (root / entry)
    if not script.is_file():
        msg = f"entry script missing: {script}"
        raise ValueError(msg)

    cmd = [sys.executable, str(script)]
    if extra_args:
        cmd.extend(extra_args)

    proc = subprocess.run(
        cmd,
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=timeout_s,
        check=False,
    )
    return PreviewResult(proc.returncode, proc.stdout, proc.stderr)


def run_game_preview_design(project_root: Path) -> PreviewResult:
    """Phase 2: preview with editor gizmos."""

    return run_preview(
        project_root,
        Path("generated/game.py"),
        extra_args=["--py_vui-design"],
        timeout_s=60.0,
    )
```

Update `preview/__init__.py`:

```python
from py_vui.preview.runner import PreviewResult, run_game_preview_design, run_preview

__all__ = ["PreviewResult", "run_preview", "run_game_preview_design"]
```

---

## 14. Fixtures & tests — Phase 2

### `examples/fixtures/minimal_game.json`

```json
{
  "adapter": "pygame",
  "assetsRoot": "assets",
  "meta": { "name": "minimal_game" },
  "nodes": {
    "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa": {
      "id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      "layout": {
        "anchors": { "bottom": false, "left": true, "right": false, "top": true },
        "box": { "h": 600, "w": 800, "x": 0, "y": 0 },
        "margins": { "bottom": 0, "left": 0, "right": 0, "top": 0 }
      },
      "name": "Level1",
      "parentId": null,
      "props": {
        "backgroundColor": "#2b2b3c",
        "backgroundImage": null,
        "worldHeight": 600,
        "worldWidth": 800
      },
      "transform": { "rotation": 0, "scaleX": 1, "scaleY": 1, "x": 0, "y": 0 },
      "type": "scene",
      "zIndex": 0
    },
    "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb": {
      "id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
      "layout": {
        "anchors": { "bottom": false, "left": true, "right": false, "top": true },
        "box": { "h": 64, "w": 64, "x": 100, "y": 120 },
        "margins": { "bottom": 0, "left": 0, "right": 0, "top": 0 }
      },
      "name": "Player",
      "parentId": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      "props": { "scriptHook": "player", "spritePath": "assets/player.png" },
      "transform": { "rotation": 0, "scaleX": 1, "scaleY": 1, "x": 100, "y": 120 },
      "type": "sprite",
      "zIndex": 0
    },
    "cccccccc-cccc-4ccc-8ccc-cccccccccccc": {
      "id": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
      "layout": {
        "anchors": { "bottom": false, "left": true, "right": false, "top": true },
        "box": { "h": 32, "w": 32, "x": 0, "y": 0 },
        "margins": { "bottom": 0, "left": 0, "right": 0, "top": 0 }
      },
      "name": "MainCamera",
      "parentId": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      "props": { "followTargetId": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", "zoom": 1 },
      "transform": { "rotation": 0, "scaleX": 1, "scaleY": 1, "x": 0, "y": 0 },
      "type": "camera_2d",
      "zIndex": 1
    }
  },
  "rootId": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  "runtime": { "fps": 60, "fullscreen": false, "height": 600, "width": 800 },
  "schemaVersion": "2",
  "inputMap": [{ "action": "jump", "keys": ["K_SPACE"] }],
  "systems": [{ "enabled": true, "id": "default", "order": 0, "scriptHook": "on_update" }]
}
```

Create placeholder asset for local preview tests: `examples/fixtures/assets/player.png` (any 1×1 PNG).

### `tests/test_assets.py`

```python
from __future__ import annotations

from pathlib import Path

import pytest

from py_vui.model.assets import AssetPathError, validate_asset_path


def test_rejects_dotdot(tmp_path: Path) -> None:
    with pytest.raises(AssetPathError):
        validate_asset_path(tmp_path, "assets", "../etc/passwd")


def test_resolve_under_assets(tmp_path: Path) -> None:
    assets = tmp_path / "assets"
    assets.mkdir()
    sprite = assets / "player.png"
    sprite.write_bytes(b"\x89PNG\r\n")
    resolved = validate_asset_path(tmp_path, "assets", "assets/player.png")
    assert resolved == sprite.resolve()
```

### `tests/test_game_validate.py`

```python
from __future__ import annotations

from pathlib import Path

from py_vui.model.project import validate_project
from py_vui.model.serde import load_json


def test_minimal_game_fixture() -> None:
    fixture_dir = Path("examples/fixtures")
    p = load_json((fixture_dir / "minimal_game.json").read_bytes())
    assets = fixture_dir / "assets"
    assets.mkdir(exist_ok=True)
    (assets / "player.png").write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    validate_project(p, project_root=fixture_dir)
```

### `tests/test_pygame_codegen.py`

```python
from __future__ import annotations

from pathlib import Path

from py_vui.codegen import emit_pygame_phase2
from py_vui.model.serde import load_json


def test_emit_game_files() -> None:
    p = load_json(Path("examples/fixtures/minimal_game.json").read_bytes())
    files = {f.path: f.content for f in emit_pygame_phase2(p)}
    assert "generated/game.py" in files
    assert "--py_vui-design" in files["generated/game.py"]
    assert "INPUT_MAP" in files["generated/config.py"]
    assert "build_scenes" in files["generated/scenes.py"]
```

---

## 15. Verify — Phase 2

After Phase 1 scaffold + Phase 2 files:

```bash
cd py_vui
uv sync --extra dev --extra pygame
uv run pytest -q
```

Emit and dry-run game project (from repo root):

```bash
uv run python -c "
from pathlib import Path
from py_vui.model.serde import load_json, dump_json
from py_vui.model.project import validate_project
from py_vui.codegen import emit_pygame_phase2

root = Path('examples/fixtures')
p = load_json((root / 'minimal_game.json').read_bytes())
validate_project(p, project_root=root)
for wf in emit_pygame_phase2(p):
    out = root / 'generated_preview' / wf.path
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(wf.content)
print('emitted to examples/fixtures/generated_preview/')
"
```

Preview subprocess (requires display / pygame):

```bash
cd examples/fixtures/generated_preview
uv run python generated/game.py --py_vui-design
```

Or from Python API:

```python
from pathlib import Path
from py_vui.preview import run_game_preview_design
result = run_game_preview_design(Path("examples/fixtures/generated_preview"))
print(result.returncode, result.stderr)
```

---

*End of implementation document (Phase 1 + Phase 2).*
