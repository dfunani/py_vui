# py_vui — Tutorial: rebuild from scratch

**Audience:** You are building py_vui (or a similar tool) from zero. No prior knowledge of this repo is assumed.

**Companion doc:** [design.md](./design.md) explains *why* and *what*; this guide explains *how*, step by step.

**Outcome:** A installable visual UI editor that saves JSON projects, generates PySide6 apps, and publishes to PyPI for other users.

---

## Before you start

### What you will build

1. A **document model** (JSON on disk) describing a window and widgets.
2. An **undo/redo** command layer.
3. A **code generator** that writes runnable PySide6 projects.
4. A **Qt editor** (palette, canvas, inspector).
5. **Polish** (themes, handlers, clipboard, preview).
6. A **published package** anyone can `pip install`.

### Prerequisites

Install on your machine:

| Tool | Minimum version | Purpose |
|------|-----------------|--------|
| Python | 3.12 | Language runtime |
| Git | any recent | Version control |
| uv *or* pip/venv | — | Dependencies (this repo uses [uv](https://github.com/astral-sh/uv)) |

Verify:

```bash
python3 --version   # should print 3.12.x or newer
git --version
```

Optional but recommended: a GitHub account (for Phase 8).

### How to use this tutorial

- Work **one phase at a time**. Do not skip to the editor until Phases 1–3 pass tests.
- After each phase, run `pytest` (or the verify commands given).
- Compare your tree to [github.com/dfunani/py_vui](https://github.com/dfunani/py_vui) if you get stuck — but try the phase goal first.
- When this doc says **“create a file”**, create it at the exact path shown. Paths are relative to the **repository root** (the folder that contains `pyproject.toml`).

---

## Two different “apps” (do not mix them up)

You are building **two** programs:

| Program | Who runs it | Where `QApplication` lives | Purpose |
|---------|-------------|------------------------------|---------|
| **py_vui editor** | You, while developing py_vui | `src/py_vui/app/qt_main.py` | Visual tool to edit JSON and generate code |
| **Generated desktop app** | End users of a design you saved | `<your-project>/app/main.py` (emitted by codegen) | The UI you designed (buttons, labels, …) |

There is **no** `App` struct (this is Python + Qt, not Rust). The global Qt object is `QApplication`. You create **one** `QApplication` per process, show one or more windows, then call `app.exec()` so Qt can process mouse/keyboard events until the user closes the window.

---

## Qt event loop — three steps (implemented literally)

Every PySide6 program — editor or generated — follows the same pattern:

1. **Create** `QApplication` (once).
2. **Build** your window widget(s) and call `.show()`.
3. **Run** `app.exec()` so Qt enters its event loop (this call **blocks** until the last window closes).

Minimal runnable example you can save as `scratch_qt.py` at the repo root and run with `uv run --extra gui python scratch_qt.py`:

```python
import sys
from PySide6.QtWidgets import QApplication, QLabel, QWidget


def main() -> None:
    # Step 1 — application object (handles events, fonts, clipboard, …)
    app = QApplication(sys.argv)

    # Step 2 — your UI
    window = QWidget()
    window.setWindowTitle("Hello Qt")
    label = QLabel("If you see this, the loop works.", parent=window)
    label.move(12, 12)
    window.resize(360, 120)
    window.show()

    # Step 3 — hand control to Qt (blocks until window closes)
    raise SystemExit(app.exec())


if __name__ == "__main__":
    main()
```

**Editor entry** (`src/py_vui/app/qt_main.py`) is the same three steps, but step 2 uses `MainWindow()` instead of a bare `QWidget`:

```python
import sys

def main() -> None:
    from PySide6.QtWidgets import QApplication
    from py_vui.app.editor.main_window import MainWindow

    app = QApplication(sys.argv)      # step 1
    app.setApplicationName("py_vui")
    window = MainWindow()             # step 2 (your editor UI)
    window.show()
    raise SystemExit(app.exec())      # step 3
```

**Generated app entry** (`app/main.py` inside a saved project) again uses the same three steps; codegen fills in theme, `build_ui()`, and optional handler wiring.

---

## Repository layout (package you are building)

After all phases, your **source tree** looks like this (only create folders/files for the phase you are on):

```text
py_vui/                          ← repo root (git root)
├── pyproject.toml
├── README.md
├── docs/
│   ├── design.md
│   └── tutorial.md              ← this file
├── examples/
│   ├── fixtures/
│   │   └── minimal.json         ← sample py_vui.json for tests
│   └── templates/               ← Phase 7: New from template
├── src/
│   ├── tests/                   ← pytest (pythonpath = src)
│   │   ├── conftest.py
│   │   ├── test_serde_roundtrip.py
│   │   ├── test_commands.py
│   │   └── test_codegen_smoke.py
│   └── py_vui/                  ← importable package
│       ├── __init__.py          ← __version__
│       ├── __main__.py          ← python -m py_vui
│       ├── app/
│       │   ├── qt_main.py       ← CLI entry: QApplication + MainWindow
│       │   └── editor/          ← Phase 4+ (Qt designer UI)
│       │       ├── main_window.py
│       │       ├── project_service.py
│       │       ├── factory.py
│       │       ├── canvas.py
│       │       ├── palette.py
│       │       ├── inspector.py
│       │       └── …
│       ├── model/               ← Phase 1 (JSON document)
│       │   ├── geometry.py
│       │   ├── nodes.py
│       │   ├── project.py
│       │   ├── document.py      ← Phase 2
│       │   └── serde.py
│       ├── commands/            ← Phase 2 (undo/redo)
│       │   ├── base.py
│       │   ├── history.py
│       │   └── builtins.py
│       └── codegen/             ← Phase 3+
│           ├── types.py
│           ├── pyside_emit.py
│           └── node_emit.py
```

**User project folder** (created when someone uses **File → Save** in the editor — not inside the py_vui git repo unless you choose to save there):

```text
~/Documents/my-login-form/       ← one “session” / project
├── py_vui.json                  ← design document (nodes, layout, handlers)
├── session.meta.json            ← editor metadata (paths, timestamps)
├── .py_vui.autosave.json        ← optional recovery copy (Phase 7)
└── app/                         ← **Build → Generate** writes here
    ├── main.py                  ← QApplication + main()  ← run this
    ├── ui_generated.py          ← def build_ui(): …
    ├── theme.py
    ├── handlers.py
    ├── interactions.py
    ├── chrome.py
    ├── custom.py                ← your code; never overwritten
    └── requirements.txt
```

To run a generated app:

```bash
cd ~/Documents/my-login-form/app
pip install -r requirements.txt
python main.py
```

---

## Phase 0 — Environment & empty repository

**Goal:** A Python package that installs and runs a placeholder CLI.

### 0.1 Create the repo

```bash
mkdir py_vui && cd py_vui
git init
mkdir -p src/py_vui src/tests examples/fixtures docs
```

### 0.2 Add `pyproject.toml`

Create a minimal package (name on PyPI will later be `py-vui`):

```toml
[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"

[project]
name = "py_vui"
version = "0.1.0"
description = "Visual authoring for Python UIs"
readme = "README.md"
requires-python = ">=3.12"
dependencies = ["pydantic>=2.6"]

[project.optional-dependencies]
dev = ["pytest>=8.0", "ruff>=0.4"]
gui = ["PySide6>=6.6"]

[project.scripts]
py_vui = "py_vui.app.qt_main:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["src/tests"]
pythonpath = ["src"]
```

### 0.3 Stub entrypoint

`src/py_vui/__init__.py`:

```python
__version__ = "0.1.0"
```

`src/py_vui/app/qt_main.py`:

```python
def main() -> None:
    print("py_vui: editor not built yet")
```

`src/py_vui/__main__.py`:

```python
from py_vui.app.qt_main import main
if __name__ == "__main__":
    main()
```

### 0.4 Install & run

```bash
uv sync --extra dev
uv run py_vui
# prints: py_vui: editor not built yet
```

**Phase 0 done when:** `uv run py_vui` exits 0 and `uv run pytest` runs (zero tests is OK).

---

## Phase 1 — Document model & JSON

**Goal:** Load and save `py_vui.json` with validation. No GUI yet.

**Folders to create now:**

```bash
mkdir -p src/py_vui/model examples/fixtures src/tests
touch src/py_vui/model/__init__.py
```

### 1.1 Define geometry

**File:** `src/py_vui/model/geometry.py`

Copy this file verbatim to start (you can add anchors/margins usage in later phases):

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

`extra="forbid"` means unknown JSON keys raise a validation error instead of being silently ignored.

### 1.2 Define nodes

**File:** `src/py_vui/model/schema.py` (tiny constant):

```python
SCHEMA_VERSION = "1"
```

**File:** `src/py_vui/model/nodes.py`

Pattern for every widget type:

1. A `*Props` model (widget-specific fields).
2. A `*Node` extending `NodeCommon` with `type: Literal["button"]` (etc.).
3. A discriminated union `Node = Annotated[WindowNode | FrameNode | …, Field(discriminator="type")]`.

Minimal Phase-1 subset (add more types in Phase 5):

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


# … ButtonNode, LineEditNode, CheckboxNode same pattern …

Node = Annotated[
    WindowNode | FrameNode | LabelNode,  # extend union as you add types
    Field(discriminator="type"),
]
```

Python field `parent_id` ↔ JSON key `"parentId"` because of `alias="parentId"` and `populate_by_name=True`.

### 1.3 Define project

**File:** `src/py_vui/model/project.py`

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
                raise ValueError(f"nodes map key {key!r} must equal node.id {node.id!r}")
        return self


def validate_project(project: py_vuiProject) -> None:
    if project.schema_version != SCHEMA_VERSION:
        raise ValueError(f"unsupported schemaVersion: {project.schema_version!r}")
    # … one root window, no orphans, no cycles — see repo for full function …
```

Implement `validate_project` fully (copy from the reference repo if needed). It is the safety net every edit and save goes through.

### 1.4 Serde

**File:** `src/py_vui/model/serde.py`

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


def dump_json(project: py_vuiProject, *, indent: int | None = 2) -> str:
    data = project.model_dump(mode="json", by_alias=True)
    return json.dumps(data, indent=indent, sort_keys=True)
```

Quick manual check from a Python REPL:

```bash
uv run python
```

```python
from pathlib import Path
from py_vui.model.serde import load_json
from py_vui.model.project import validate_project

p = load_json(Path("examples/fixtures/minimal.json").read_bytes())
validate_project(p)
print(p.meta.name, len(p.nodes))
```

### 1.5 Fixture & test

**File:** `examples/fixtures/minimal.json` — copy from this repo (window → frame → label). The on-disk shape is what the editor saves; note camelCase keys:

```json
{
  "schemaVersion": "1",
  "adapter": "pyside6",
  "meta": { "name": "minimal" },
  "rootId": "11111111-1111-4111-8111-111111111111",
  "nodes": { … }
}
```

**File:** `src/tests/test_serde_roundtrip.py`

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
    assert load_json(out).model_dump() == project.model_dump()
```

```bash
uv run pytest -q
```

**Phase 1 done when:** round-trip and validation tests pass.

---

## Phase 2 — Command system (undo / redo)

**Goal:** Every edit is reversible. The editor never mutates `doc.project` directly for user actions — it always goes through `History.push`.

**Folders:**

```bash
mkdir -p src/py_vui/commands
touch src/py_vui/commands/__init__.py
```

### 2.1 Command interface

**File:** `src/py_vui/commands/base.py`

```python
from __future__ import annotations

from abc import ABC, abstractmethod

from py_vui.model.document import ProjectDocument


class Command(ABC):
    @abstractmethod
    def apply(self, doc: ProjectDocument) -> None: ...

    @abstractmethod
    def revert(self, doc: ProjectDocument) -> None: ...
```

**File:** `src/py_vui/model/document.py` — wraps `py_vuiProject` with helpers the commands and canvas use:

```python
from __future__ import annotations

from dataclasses import dataclass

from py_vui.model.nodes import Node
from py_vui.model.project import py_vuiProject, validate_project


@dataclass
class ProjectDocument:
    project: py_vuiProject

    def validate(self) -> None:
        validate_project(self.project)

    def get_node(self, node_id: str) -> Node:
        return self.project.nodes[node_id]

    def children(self, parent_id: str) -> list[Node]:
        kids = [n for n in self.project.nodes.values() if n.parent_id == parent_id]
        return sorted(kids, key=lambda n: (n.z_index, n.id))
```

### 2.2 History

**File:** `src/py_vui/commands/history.py`

```python
@dataclass
class History:
    undo_stack: list[Command] = field(default_factory=list)
    redo_stack: list[Command] = field(default_factory=list)

    def push(self, doc: ProjectDocument, cmd: Command) -> None:
        cmd.apply(doc)           # mutate document
        doc.validate()           # must still be a valid tree
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
        …
```

**How the editor will call this (Phase 4):** when the user drags a widget, the canvas builds `SetLayoutBox(node_id, new_rect)` and calls `self._history.push(self._doc, cmd)`, then refreshes the scene.

### 2.3 Built-in commands

**File:** `src/py_vui/commands/builtins.py` (all commands can live here initially)

Example — adding a node:

```python
@dataclass
class AddNode(Command):
    node: Node

    def apply(self, doc: ProjectDocument) -> None:
        if self.node.id in doc.project.nodes:
            raise ValueError(f"duplicate node id {self.node.id!r}")
        doc.project.nodes[self.node.id] = self.node

    def revert(self, doc: ProjectDocument) -> None:
        del doc.project.nodes[self.node.id]
```

Example — moving on the canvas:

```python
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
        node.layout.box = self._old_box  # type: ignore[assignment]
```

| Command | Behavior |
|---------|----------|
| `AddNode` | Insert node |
| `RemoveSubtree` | Delete node + children (not root) |
| `ReparentNode` | Change parent; reject cycles |
| `SetLayoutBox` | Update `layout.box` |
| `ReplaceNode` | Swap node for props edits |

### 2.4 Tests

**File:** `src/tests/test_commands.py` — build a `ProjectDocument` from `factory.new_project()`, push `AddNode`, assert undo removes it, assert reparent-into-descendant raises.

```bash
uv run pytest -q
```

**Phase 2 done when:** command tests pass and `validate_project` still holds after random undo/redo.

---

## Phase 3 — Code generation

**Goal:** From a saved JSON project, emit a **folder of Python files** that runs with `python main.py`. You are not running Qt inside the generator — you only **print** source text.

**Folders:**

```bash
mkdir -p src/py_vui/codegen
touch src/py_vui/codegen/__init__.py
```

### 3.1 Emitter types

**File:** `src/py_vui/codegen/types.py`

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WrittenFile:
    path: str      # relative path inside app/ bundle, e.g. "main.py"
    content: str   # full file text
```

**File:** `src/py_vui/codegen/__init__.py` — export a single function the editor will call later:

```python
from py_vui.codegen.pyside_emit import emit_pyside_phase1

__all__ = ["emit_pyside_phase1"]
```

### 3.2 PySide6 emitter

**File:** `src/py_vui/codegen/pyside_emit.py`

Algorithm:

1. Build a `ProjectDocument` and walk depth-first from `root_id` (children sorted by `z_index`, then `id`).
2. For each node, emit a variable `w_<id> = QLabel(...)` (see `node_emit.widget_ctor`).
3. Emit `w_child.setParent(w_parent)` and `setGeometry(x, y, w, h)` from `layout.box`.
4. Wrap in `def build_ui():` that **returns** the root widget.

Emit **`ui_generated.py`** (layout only) and **`main.py`** (the three-step Qt loop).

**`ui_generated.py`** (simplified shape):

```python
"""UI layout generated by py_vui."""

def build_ui():
    from PySide6.QtWidgets import QFrame, QLabel, QWidget

    w_root = QWidget()
    w_root.setWindowTitle("Hello")
    w_root.resize(640, 480)

    w_frame = QFrame(w_root)
    w_frame.setGeometry(12, 12, 600, 400)

    w_label = QLabel(w_frame)
    w_label.setGeometry(8, 8, 200, 24)
    w_label.setText("Welcome to py_vui")

    return w_root
```

**`main.py`** — this is where the generated app’s `QApplication` lives (not in the editor package):

```python
#!/usr/bin/env python3
import sys


def main() -> int:
    from PySide6.QtWidgets import QApplication
    from ui_generated import build_ui

    app = QApplication(sys.argv)   # step 1
    root = build_ui()              # step 2a — build widget tree
    root.show()                    # step 2b — make visible
    return int(app.exec())         # step 3


if __name__ == "__main__":
    raise SystemExit(main())
```

Your emitter returns a **list** of `WrittenFile` objects, for example:

```python
def emit_pyside_phase1(project: py_vuiProject, *, handlers_path: Path | None = None) -> list[WrittenFile]:
    return [
        WrittenFile("ui_generated.py", _emit_ui_module(project)),
        WrittenFile("main.py", _emit_main_module(project, has_handlers=False)),
        WrittenFile("requirements.txt", "PySide6>=6.6\n"),
        # Phase 6 adds theme.py, handlers.py, interactions.py, chrome.py, custom.py
    ]
```

Write files to disk in tests or a scratch script:

```python
from pathlib import Path
from py_vui.codegen import emit_pyside_phase1
from py_vui.model.serde import load_json

project = load_json(Path("examples/fixtures/minimal.json").read_bytes())
out_dir = Path("/tmp/py_vui_gen")
out_dir.mkdir(exist_ok=True)
for wf in emit_pyside_phase1(project):
    (out_dir / wf.path).write_text(wf.content, encoding="utf-8")
print("Wrote", list(out_dir.iterdir()))
```

### 3.3 Smoke test

**File:** `src/tests/test_codegen_smoke.py`

```python
from pathlib import Path

from py_vui.codegen import emit_pyside_phase1
from py_vui.model.serde import load_json


def test_emit_minimal_contains_expected_symbols() -> None:
    p = load_json(Path("examples/fixtures/minimal.json").read_bytes())
    files = {f.path: f.content for f in emit_pyside_phase1(p)}
    assert "def build_ui():" in files["ui_generated.py"]
    assert "QApplication" in files["main.py"]
    assert "from ui_generated import build_ui" in files["main.py"]
```

### 3.4 Manual run (optional)

```bash
uv run python -c "
from pathlib import Path
from py_vui.codegen import emit_pyside_phase1
from py_vui.model.serde import load_json
p = load_json(Path('examples/fixtures/minimal.json').read_bytes())
d = Path('/tmp/my-gen'); d.mkdir(exist_ok=True)
for wf in emit_pyside_phase1(p):
    (d / wf.path).write_text(wf.content)
print('OK', d)
"
cd /tmp/my-gen && pip install -r requirements.txt && python main.py
```

A window titled from your fixture should appear.

**Phase 3 done when:** smoke test passes and a generated window opens locally.

---

## Phase 4 — Editor shell & canvas

**Goal:** A Qt app that loads a project, shows widgets on a canvas, and saves. This phase wires **your** three-step loop (`qt_main.py`) to **document + commands + codegen**.

### 4.1 Install GUI extra

```bash
uv sync --extra gui --extra dev
```

PySide6 is only required for the editor and for running generated apps — not for Phases 1–3 tests.

### 4.2 Entry point and main window

**File:** `src/py_vui/app/qt_main.py` — replace the Phase 0 stub:

```python
from __future__ import annotations

import sys


def main() -> None:
    try:
        from PySide6.QtWidgets import QApplication
    except ModuleNotFoundError:
        print("py_vui editor requires: pip install py_vui[gui]")
        raise SystemExit(1) from None

    from py_vui.app.editor.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("py_vui")
    window = MainWindow()
    window.show()
    raise SystemExit(app.exec())
```

**File:** `src/py_vui/app/editor/main_window.py` — skeleton responsibilities:

| Piece | Type | Role |
|-------|------|------|
| `_service` | `ProjectService` | load/save JSON, write `app/` |
| `_doc` | `ProjectDocument` | same as `_service.doc` |
| `_history` | `History` | undo/redo |
| `_canvas` | `DesignCanvas` | visual editing |
| Menus | `QAction` | call service methods |

Minimal `__init__` pattern:

```python
class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._service = ProjectService.new()
        self._doc = self._service.doc
        self._history = History()

        self._canvas = DesignCanvas()
        self._canvas.bind(self._doc, self._history)
        self.setCentralWidget(self._canvas)

        self._build_menus()  # File / Edit / Build
```

Menu handlers (implement bodies incrementally):

```python
def _new_project(self) -> None:
    self._service = ProjectService.new()
    self._doc = self._service.doc
    self._history = History()
    self._canvas.bind(self._doc, self._history)
    self._canvas.refresh()

def _save_project(self) -> None:
    if self._service.project_dir is None:
        folder = QFileDialog.getExistingDirectory(self, "Save project into…")
        if not folder:
            return
        self._service.save(parent_dir=Path(folder))
    else:
        self._service.save()

def _generate(self) -> None:
    if self._service.project_dir is None:
        QMessageBox.warning(self, "Generate", "Save the project first.")
        return
    paths = self._service.write_generated()
    self.statusBar().showMessage(f"Wrote {len(paths)} files to {self._service.app_dir()}")
```

### 4.3 Project service and paths

**File:** `src/py_vui/app/editor/session_paths.py`

```python
SESSION_DOCUMENT = "py_vui.json"
SESSION_META = "session.meta.json"
APP_SUBDIR = "app"
```

**File:** `src/py_vui/app/editor/factory.py` — `new_project(name)` returns a `py_vuiProject` with a single `WindowNode` root (use `uuid4()` for ids).

**File:** `src/py_vui/app/editor/project_service.py`

```python
@dataclass
class ProjectService:
    doc: ProjectDocument
    project_dir: Path | None = None
    dirty: bool = False

    @classmethod
    def new(cls, name: str = "untitled") -> ProjectService:
        from py_vui.app.editor.factory import new_project
        return cls(ProjectDocument(new_project(name)), project_dir=None, dirty=True)

    def save(self, *, parent_dir: Path | None = None) -> Path:
        # first save: allocate ~/parent/untitled/ and write py_vui.json
        …

    def write_generated(self) -> list[Path]:
        if self.project_dir is None:
            raise ValueError("save the project first")
        return self.export_code_to(self.project_dir / APP_SUBDIR)
```

`export_code_to` loops `emit_pyside_phase1(self.doc.project)` and writes each `WrittenFile` to disk.

### 4.4 Canvas

**File:** `src/py_vui/app/editor/canvas.py`

- `QGraphicsView` + `QGraphicsScene`.
- One `QGraphicsRectItem` (or custom item) per node; label text drawn or as child `QGraphicsTextItem`.
- `bind(doc, history)` stores references.
- `refresh()` rebuilds items from `doc.project.nodes`.
- On mouse release after drag: compute new `Rect`, `history.push(doc, SetLayoutBox(node_id, new_box))`, then `refresh()`.

Pseudo-code for drag end:

```python
def _on_item_moved(self, node_id: str, x: float, y: float) -> None:
    node = self._doc.get_node(node_id)
    old = node.layout.box
    new_box = Rect(x=x, y=y, w=old.w, h=old.h)
    self._history.push(self._doc, SetLayoutBox(node_id, new_box))
    self.node_moved.emit(node_id)  # inspector / tree can listen
```

### 4.5 Wire menus and run

```bash
uv run py_vui
```

Workflow to verify Phase 4:

1. **File → New** — empty window node on canvas.
2. Drag the root frame (or add nodes once palette exists in Phase 5).
3. **File → Save** — pick `~/Documents`; you should get `~/Documents/untitled/py_vui.json`.
4. **Build → Generate** — creates `~/Documents/untitled/app/main.py`.
5. `cd ~/Documents/untitled/app && python main.py` — generated UI opens.

**Phase 4 done when:** you can place/move widgets, save, reload, and generate `app/` from the menu.

---

## Phase 5 — Palette, inspector & widget tree

**Goal:** Full editing workflow without hand-editing JSON.

**Layout in `MainWindow`:** use a `QSplitter` — palette + widget tree on the left, canvas center, inspector on the right (see reference `main_window.py`).

### 5.1 Palette

**File:** `src/py_vui/app/editor/palette.py`

- `QListWidget` entries: `("button", "Button"), ("label", "Label"), …`.
- Enable drag; on drop at canvas coordinates, call `factory.create_node(type, parent_id=…, x=…, y=…)`.
- Push `AddNode(node)` on `history`, then `canvas.refresh()`.

Parent selection rule: drop on a frame/group → parent is that node; else parent is root window.

### 5.2 Inspector

**File:** `src/py_vui/app/editor/inspector.py`

- `bind(doc, history)` like the canvas.
- `show_node(node_id)` builds spin boxes for `layout.box` and line edits for `props.text`, etc.
- On value change: clone node with `model_copy(update={…})`, push `ReplaceNode(before, after)` or `SetLayoutBox`.

Expand `nodes.py` toward **16 widget types** (see [design.md](./design.md)).

### 5.3 Widget tree

**File:** `src/py_vui/app/editor/widget_tree.py`

- `QTreeWidget` built from `doc.children(root_id)` recursively.
- Item `data(Qt.UserRole)` stores `node_id`.
- Selection signal → `canvas.select_node(node_id)`.

### 5.4 Canvas polish

| File | What to implement |
|------|-------------------|
| `canvas_resize.py` | 8 handles on selection; resize → `SetLayoutBox` |
| `snap.py` | `snap_value(v, grid=8)` used while dragging |
| `canvas.py` | Arrow keys → nudge 1px; Shift+nudge 8px |

**Phase 5 done when:** you can build a small form entirely in the UI and regenerate code.

---

## Phase 6 — Themes, handlers & interactions

**Goal:** Styled apps with button callbacks — still `schemaVersion: "1"`.

> In product docs this is sometimes called “Phase 2 UI” — it is **not** the pygame studio.

### 6.1 Theme model

**File:** `src/py_vui/model/theme.py` — add to `py_vuiProject`:

```python
theme: ProjectTheme = Field(default_factory=ProjectTheme)
```

Inspector: when the root window is selected, show preset/colors; per-widget overrides via `node.style`.

Codegen writes **`app/theme.py`** with `apply_theme(app)`; **`main.py`** calls it **after** `QApplication` is created (themes attach to the app object):

```python
app = QApplication(sys.argv)
apply_theme(app)
root = build_ui()
```

### 6.2 Handlers

**File:** `src/py_vui/model/interaction.py`

```python
class HandlerDef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str
```

On the project (saved inside `py_vui.json`):

```json
"handlers": {
  "on_ok_clicked": { "source": "print('OK')" }
}
```

Button node props: `"onClick": "on_ok_clicked"` (camelCase in JSON).

### 6.3 Inspector actions

**File:** `src/py_vui/app/editor/handler_snippets.py` — strings users can paste.

Inspector **Actions** panel: combo of handler ids, **New** adds `handlers["on_action_1"] = HandlerDef(source="pass")`, text editor for `source`, **Apply** pushes `ReplaceNode` on the project wrapper or a dedicated command that updates `project.handlers`.

### 6.4 Codegen extensions

Emit into **`app/`**:

| File | Purpose |
|------|---------|
| `theme.py` | `apply_theme(app)` |
| `handlers.py` | `def on_ok_clicked(): …` bodies |
| `interactions.py` | `def wire_handlers(): btn.clicked.connect(…)` |
| `chrome.py` | menu bar from `WindowProps.menus` |
| `custom.py` | user file — **never overwrite** |

**File:** `src/py_vui/codegen/merge_regions.py` — when regenerating, read existing `handlers.py` and preserve:

```python
# py_vui: begin custom
… user edits …
# py_vui: end custom
```

Update **`main.py`** template to call `wire_handlers()` after `build_ui()` when handlers exist:

```python
root = build_ui()
from interactions import wire_handlers
wire_handlers()
root.show()
```

### 6.5 Canvas preview

Tint canvas item brushes from `project.theme` so the design surface resembles the running app.

**Phase 6 done when:** a button runs your handler in the generated app:

```bash
cd <project>/app && python main.py
```

---

## Phase 7 — Product polish

**Goal:** Features expected of a shareable UI builder.

Implement incrementally (order flexible):

| Feature | Module / notes |
|---------|----------------|
| Copy / paste / duplicate | `clipboard_io.py`, `clipboard_cmds.py` |
| Multi-select + group move | `canvas.py` |
| Align / distribute | `layout_cmds.py`, Edit menu |
| Autosave + recovery | `project_service.py`, `.py_vui.autosave.json` |
| Tab order | `tabOrder` in JSON + inspector |
| Window menus | `model/menus.py`, `chrome.py` |
| Anchors in export | `apply_anchors()` when right/bottom anchored |
| Project templates | `examples/templates/*.json`, **File → New from template** |
| Live preview dock | `preview_dock.py` — QProcess runs `app/main.py` after generate |
| More signals | combo, list, spin, slider — see [design.md](./design.md) |

```bash
uv run pytest -q
uv run ruff check src
uv run py_vui
```

**Phase 7 done when:** README feature list is true and tests/lint pass.

---

## Phase 8 — Release & publishing

**Goal:** Anyone in the world can install your editor with pip.

### 8.1 Prepare the package metadata

In `pyproject.toml` add:

- `license`, `authors`, `keywords`, `classifiers`
- `[project.urls]` — Homepage, Repository, Issues
- Optional: `readme = "README.md"` with install instructions

PyPI displays the name **`py-vui`** (hyphen) while the import remains `py_vui`.

### 8.2 README for end users

Your root `README.md` should include:

```bash
pip install "py-vui[gui]"
py_vui
```

And for contributors:

```bash
git clone https://github.com/<you>/py_vui.git
cd py_vui
uv sync --extra gui --extra dev
uv run py_vui
```

### 8.3 One-time PyPI setup

1. Register at [pypi.org](https://pypi.org) and [test.pypi.org](https://test.pypi.org).
2. Create an API token (scope: project `py-vui` or whole account).
3. Search PyPI for `py-vui` — if taken, change `name` in `pyproject.toml` before first upload.
4. **Optional automation:** GitHub repo → Settings → Secrets → `PYPI_API_TOKEN`.

### 8.4 Pre-release checklist

```bash
# From repo root — fix version in pyproject.toml first
uv run pytest -q
uv run ruff check src
python -m pip install --upgrade build twine
python -m build
```

You should see:

```
dist/py_vui-<version>.tar.gz
dist/py_vui-<version>-py3-none-any.whl
```

### 8.5 Test on TestPyPI (recommended)

```bash
twine upload --repository testpypi dist/*
```

Install in a **fresh** virtualenv:

```bash
python -m venv /tmp/py-vui-test
source /tmp/py-vui-test/bin/activate
pip install --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ \
  "py-vui[gui]==<VERSION>"
py_vui
deactivate
```

Replace `<VERSION>` with the version you uploaded (e.g. `0.1.0`).

### 8.6 Publish to production PyPI

```bash
twine upload dist/*
```

When prompted:

- **Username:** `__token__`
- **Password:** your PyPI API token (includes `pypi-` prefix)

Non-interactive:

```bash
TWINE_USERNAME=__token__ TWINE_PASSWORD=pypi-XXXX twine upload dist/*
```

Verify public install:

```bash
pip install "py-vui[gui]"
py_vui
```

### 8.7 Git tag & GitHub Release

```bash
git tag -a v0.1.0 -m "Release 0.1.0"
git push origin v0.1.0
```

On GitHub: **Releases → Draft a new release** → select tag `v0.1.0`, write notes (features, Python 3.12+ requirement).

### 8.8 Automated publish (GitHub Actions)

Add `.github/workflows/publish-pypi.yml`:

```yaml
name: Publish to PyPI
on:
  push:
    tags:
      - "v*"
jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: python -m pip install --upgrade build twine
      - run: python -m build
      - env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
        run: twine upload dist/*
```

After `PYPI_API_TOKEN` is set, pushing `v0.1.0` uploads automatically.

### 8.9 Per-release routine (maintainers)

Use this checklist every release:

- [ ] Bump `version` in `pyproject.toml` and commit
- [ ] `uv run pytest -q` and `uv run ruff check src`
- [ ] `python -m build`
- [ ] `twine upload --repository testpypi dist/*` and smoke-test install
- [ ] `twine upload dist/*`
- [ ] `git tag -a vX.Y.Z -m "Release X.Y.Z"` && `git push origin vX.Y.Z`
- [ ] GitHub Release with notes
- [ ] Announce: `pip install "py-vui[gui]"`

**Phase 8 done when:** a stranger can install from PyPI and launch `py_vui` without cloning the repo.

---

## After the UI builder — pygame studio (future)

Not part of this tutorial’s implementation path yet. When you add it:

1. Bump to `schemaVersion: "2"`, `adapter: "pygame"`.
2. Add `scene`, `sprite`, `camera_2d` nodes and `runtime` settings.
3. New emitter `pygame_emit.py` → `game.py`, `config.py`, `scenes.py`.
4. Preview: `python generated/game.py --py_vui-design`.

See [design.md §12](./design.md#12-future-pygame-studio).

---

## Quick reference

| I want to… | Command / location |
|------------|-------------------|
| Run editor from source | `uv run py_vui` → `src/py_vui/app/qt_main.py` |
| Where editor `QApplication` is | `src/py_vui/app/qt_main.py` |
| Where generated `QApplication` is | `<saved-project>/app/main.py` |
| Run tests | `uv run pytest -q` |
| Lint | `uv run ruff check src` |
| Open sample JSON | **File → Open** → `examples/fixtures/minimal.json` |
| Save a design | **File → Save** → creates `py_vui.json` under `~/…/<slug>/` |
| Generate runnable code | **Build → Generate** → writes `<project>/app/` |
| Run generated app | `cd <project>/app && pip install -r requirements.txt && python main.py` |
| Understand architecture | [design.md](./design.md) |

### End-to-end checklist (first working app)

1. `uv sync --extra gui --extra dev`
2. `uv run py_vui`
3. Build a UI (palette + inspector).
4. **File → Save** into `~/Documents/my-app/`.
5. **Build → Generate**.
6. `cd ~/Documents/my-app/app && pip install -r requirements.txt && python main.py`.

---

*This tutorial supersedes the step-by-step and publishing content from `IMPLEMENTATION.md`, `IMPLEMENTATION_PLAN.md`, `PHASE2_UI.md`, and `PUBLISHING.md`.*
