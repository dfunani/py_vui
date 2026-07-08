# py_vui — Design & implementation

**Version:** 1.0 (consolidated)  
**Audience:** Contributors and maintainers who need the full picture — product intent, architecture, wire format, and how the shipped codebase maps to each phase.

For a hands-on rebuild from an empty folder, see **[tutorial.md](./tutorial.md)**.

---

## Table of contents

1. [Problem & principles](#1-problem--principles)
2. [Personas & scope](#2-personas--scope)
3. [Architecture overview](#3-architecture-overview)
4. [Phased delivery](#4-phased-delivery)
5. [Document model & wire format](#5-document-model--wire-format)
6. [Command system](#6-command-system)
7. [Code generation](#7-code-generation)
8. [Editor application](#8-editor-application)
9. [Preview & security](#9-preview--security)
10. [Distribution](#10-distribution)
11. [Quality attributes & risks](#11-quality-attributes--risks)
12. [Future: pygame studio](#12-future-pygame-studio)
13. [Glossary](#13-glossary)

---

## 1. Problem & principles

### Problem statement

Developers and learners need a **fast, local** way to compose Python desktop UIs without hand-writing layout boilerplate. Later, the same mental model should extend to **pygame** scenes (sprites, cameras, game loop) — but that track is separate and not yet implemented in the editor.

### Product principles

1. **Generated code is the export truth** — output must be readable Python a human can maintain; the editor augments, not replaces, normal development.
2. **Deterministic round-tripping (where feasible)** — projects created in py_vui save as JSON and regenerate cleanly; arbitrary hand-edited Python is not fully re-imported in v1.
3. **Progressive complexity** — ship a solid PySide6 UI builder first; add pygame without breaking UI projects.
4. **Local-first** — no mandatory cloud; Git-friendly project folders.

### Non-goals (initial releases)

- Parity with every commercial UI builder or Qt Designer.
- Full game-engine features beyond a reasonable pygame scope.
- AST round-trip from arbitrary edited Python.
- Cloud collaboration.

---

## 2. Personas & scope

| Persona | Needs |
|--------|--------|
| **App prototyper** | Forms, dialogs, tools; cares about codegen quality and version control. |
| **Learner** | Low ceremony, visual feedback, understandable JSON. |
| **Indie / jam dev** (future) | pygame preview, assets, scene switching. |

### Current shipped scope (UI builder)

The **pyUIBuilder-class** editor is implemented:

- 16 Qt widget types, themes, event handlers, widget tree, 8px snap grid, multi-select, align/distribute, clipboard, tab order, menu bar, anchors in export, merge-safe codegen, live preview dock, project templates.
- Save/load as a **project folder** (`py_vui.json` + `session.meta.json` + generated `app/`).
- PyPI packaging docs and GitHub Actions publish workflow.

### Explicit non-goals (unchanged)

- pygame studio in the editor (planned design only).
- Embedded preview inside the canvas (preview uses a subprocess / QProcess).
- Visual anchor editor on canvas (anchors work in JSON + export).

---

## 3. Architecture overview

### Core domains

| Domain | Package / location | Responsibility |
|--------|-------------------|----------------|
| **Document model** | `src/py_vui/model/` | Tree of nodes, theme, handlers, validation, JSON serde. |
| **Command stack** | `src/py_vui/commands/` | Undo/redo; all edits as reversible commands. |
| **Codegen** | `src/py_vui/codegen/` | Document → Python modules under `app/`. |
| **Preview** | `src/py_vui/preview/` | Subprocess runner for generated apps. |
| **Editor UI** | `src/py_vui/app/editor/` | Qt main window, canvas, palette, inspector, docks. |
| **Project I/O** | `project_service.py`, `session_paths.py` | Save, open, autosave, export, generate. |

### Technology choices (decision record)

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Language | Python 3.12+ | Single stack for tool + generated apps. |
| Editor UI | PySide6 | Native desktop, tight integration with generated Qt code. |
| Canvas | `QGraphicsView` / scene items | Zoom, selection handles, snap overlays. |
| Persistence | JSON (`py_vui.json`) | Diff-friendly, no DB for v1. |
| Validation | Pydantic v2 | Models mirror JSON; `validate_project()` for tree invariants. |
| Codegen | String templates + `node_emit` | Golden tests; merge regions for `handlers.py`. |
| Packaging | setuptools + PyPI name `py-vui` | `pip install "py-vui[gui]"` → CLI `py_vui`. |

### Repository layout

```
py_vui/
  docs/
    design.md          # this file
    tutorial.md        # rebuild guide
  examples/
    fixtures/          # minimal.json for tests
    templates/         # dialog, settings, empty JSON starters
  src/py_vui/
    model/             # schema, nodes, project, theme, serde
    commands/          # history, builtins, layout, clipboard
    codegen/           # pyside_emit, node_emit, merge_regions
    preview/           # subprocess runner
    app/
      qt_main.py       # CLI entry
      editor/          # main_window, canvas, inspector, …
  src/tests/
  pyproject.toml
  .github/workflows/publish-pypi.yml
```

---

## 4. Phased delivery

Phases describe **how the product was built and documented**, not separate schema versions. The wire format stays `schemaVersion: "1"` for the UI builder; pygame would use `"2"` when implemented.

| Phase | Name | Exit criteria | Status |
|-------|------|---------------|--------|
| **0** | Spike | JSON load/save, minimal codegen, stub editor | Done |
| **1** | Core model & commands | Pydantic models, undo/redo, unit tests | Done |
| **2** | Codegen MVP | `emit_pyside_phase1` → `ui_generated.py`, `main.py` | Done |
| **3** | Editor shell | Main window, canvas select/move, project save/open | Done |
| **4** | Full canvas UX | Resize handles, snap, nudge, widget tree, palette | Done |
| **5** | Styling & actions | Themes, per-widget style, handler editor, signals | Done |
| **6** | Product polish | Clipboard, align/distribute, templates, preview dock, menus, anchors, tab order | Done |
| **7** | Release | PyPI, twine, tags, GitHub Actions, README install path | Done |
| **8** | pygame studio | `schemaVersion: "2"`, scenes/sprites, design-mode preview | Planned |

### Milestone mapping (original plan)

| Original milestone | Maps to |
|--------------------|---------|
| M0 Spike | Phase 0 |
| M1 Phase 1 MVP | Phases 1–3 |
| M2 Phase 1 v1 | Phases 4–6 |
| M3/M4 Phase 2 pygame | Phase 8 (future) |

---

## 5. Document model & wire format

### Top-level project (`py_vui.json`)

| Field | Type | Notes |
|-------|------|--------|
| `schemaVersion` | `"1"` | UI builder only today. |
| `adapter` | `"pyside6"` | Codegen target. |
| `meta` | object | `name`, optional `createdAt` / `updatedAt`. |
| `rootId` | UUID string | Must reference the sole `window` node. |
| `nodes` | map id → node | Keys must equal `node.id`. |
| `theme` | object | Preset + token overrides (`ProjectTheme`). |
| `handlers` | map name → `{ source }` | Shared handler bodies. |
| `tabOrder` | string[] | Node ids for focus order. |

Python uses snake_case internally (`schema_version`, `root_id`, …); JSON on disk uses camelCase aliases via Pydantic.

### Tree invariants (`validate_project`)

1. Exactly one node has `parentId: null`; it equals `rootId` and has `type: "window"`.
2. BFS from `rootId` reaches every node (no orphans, no cycles).
3. `nodes[k].id == k` for all keys.

### Node common fields

All widgets share: `id`, `type`, `name`, `parentId`, `zIndex`, `layout`, optional `tabIndex`, `enabled`, `tooltip`, `style`.

### Layout

```json
{
  "box": { "x": 0, "y": 0, "w": 400, "h": 300 },
  "anchors": { "left": true, "top": true, "right": false, "bottom": false },
  "margins": { "top": 0, "right": 0, "bottom": 0, "left": 0 }
}
```

- **Editor & codegen (default):** `layout.box` → `setGeometry(...)`.
- **Export:** when `anchors.right` or `anchors.bottom` are set, generated code calls `apply_anchors()` so resizing the window reflows children.

### Widget types (16)

| Type id | Role |
|---------|------|
| `window` | Root; `props.title`, `width`, `height`, `menus` |
| `frame`, `group_box`, `scroll_area`, `tab_widget` | Containers |
| `label`, `button`, `line_edit`, `text_edit` | Text |
| `checkbox`, `radio_button` | Toggles |
| `combo_box`, `list_widget` | Selection |
| `spin_box`, `slider`, `progress_bar` | Values |

### Action hooks (props → handlers)

| Widget | Signal (Qt) | JSON prop |
|--------|-------------|-----------|
| Button | `clicked` | `onClick` |
| Line edit | `returnPressed` | `onReturn` |
| Checkbox / radio | `toggled` | `onToggle` |
| Combo box | `currentIndexChanged` | `onChange` |
| List widget | `itemSelectionChanged` | `onSelection` |
| Spin box / slider | `valueChanged` | `onChange` |

Handler **names** point into `project.handlers`; the inspector edits Python source and codegen writes `handlers.py` + `interactions.py`.

### Themes

- Presets: Light, Dark, Modern, Ocean (`model/theme.py`).
- Canvas preview and generated `theme.py` share the same tokens (background, foreground, accent, font, button radius).
- Per-widget `style` overrides inherit empty fields from the project theme.

### Project folder on disk

```
my-project/
  py_vui.json              # document (SESSION_DOCUMENT)
  session.meta.json        # editor session: version, paths
  .py_vui.autosave.json    # recovery copy (optional)
  app/                     # GENERATED — Build → Generate Code
    main.py
    ui_generated.py
    handlers.py
    interactions.py
    theme.py
    chrome.py
    custom.py              # never overwritten
    requirements.txt
    README.md
```

**Export** copies the project to a sibling folder without editor-only files; **Generate** refreshes `app/` in place.

### Editing façade

`ProjectDocument` wraps `py_vuiProject` for commands: `get_node`, `children` (sorted by `zIndex`, `id`), `validate()`.

---

## 6. Command system

### Interface

Every edit implements `Command`:

- `apply(doc)` / `revert(doc)`
- `History.push(doc, cmd)` applies, validates, clears redo stack.

### Built-in commands (representative)

| Command | Purpose |
|---------|---------|
| `AddNode` | Insert widget |
| `RemoveSubtree` | Delete node + descendants (not root) |
| `ReparentNode` | Change parent; rejects cycles |
| `SetLayoutBox` | Move/resize |
| `ReplaceNode` | Props/style/name edits |
| `SetTransform` | (reserved for pygame nodes) |
| Clipboard / layout commands | Paste, duplicate, align, distribute |

### Invariants

- Commands must leave `validate_project()` passing.
- Fuzz/property tests recommended for random apply/undo sequences.
- **Future:** coalesce drag moves within ~300 ms for cleaner undo stacks.

---

## 7. Code generation

### Pipeline

```
py_vuiProject → ProjectDocument → emit_pyside_phase1() → list[WrittenFile]
```

`ProjectService.generate()` writes files under `<project>/app/`.

### Generated bundle

| File | Role |
|------|------|
| `ui_generated.py` | `build_ui()`, widget tree, stylesheets, `WIDGETS` registry |
| `handlers.py` | User callback bodies |
| `interactions.py` | `.connect()` wiring from props → handlers |
| `theme.py` | `apply_theme(app)` |
| `chrome.py` | Menu bar from window `menus` |
| `custom.py` | User extensions; **never overwritten** |
| `main.py` | `QApplication` entry |
| `requirements.txt` | PySide6 pin |

### Merge regions

In `handlers.py`, blocks between:

```python
# py_vui: begin custom
...
# py_vui: end custom
```

are preserved across regenerations. `merge_regions.py` merges new stubs without clobbering user code.

### Codegen rules

- Stable node ids → generated variable names (`w_<uuid>`).
- Sibling order: depth-first, children sorted by `(zIndex, id)`.
- Lint-friendly output (ruff-compatible; no exotic formatting).
- **Security:** never `exec` JSON contents on open.

### Testing

- Golden/smoke tests: `test_codegen_smoke.py`, fixture `examples/fixtures/minimal.json`.
- Clipboard/snap tests in `test_clipboard_snap.py`.

---

## 8. Editor application

Entry: `py_vui` → `py_vui.app.qt_main:main` → `MainWindow`.

### Major UI modules

| Module | Role |
|--------|------|
| `main_window.py` | Menus, docks, command routing, generate/export/preview |
| `canvas.py` / `canvas_resize.py` | Scene graph, handles, selection, drag |
| `snap.py` | 8px grid |
| `palette.py` | Drag-drop new widgets |
| `widget_tree.py` | Hierarchy, reparent, z-order, delete |
| `inspector.py` | Layout, props, theme, actions, handler editor |
| `handler_snippets.py` | Templates for new handlers |
| `preview_dock.py` | QProcess running `app/main.py` after generate |
| `project_service.py` | New/open/save/autosave/generate/export |
| `project_templates.py` | dialog / settings / empty starters |
| `factory.py` | Default new project graph |
| `session_paths.py` | Path constants, export layout |
| `clipboard_io.py` | Copy/paste serialization |

### UX flows

1. **New** → empty or template → edit → **Save Project As…** creates folder + `py_vui.json`.
2. **Edit** → each gesture pushes a command → undo/redo.
3. **Generate** → writes `app/`; preview dock can restart the subprocess.
4. **Export** → portable copy for sharing without editor metadata.

### Autosave

Every 60s (when project has a path), write `.py_vui.autosave.json`. On open, if newer than `py_vui.json`, offer recovery.

### Shortcuts (representative)

| Action | Shortcut |
|--------|----------|
| Save | ⌘S / Ctrl+S |
| Copy / Paste / Duplicate | ⌘C / ⌘V / ⌘D |
| Nudge 1px / 8px | Arrows / Shift+Arrows |

---

## 9. Preview & security

- Preview runs `python app/main.py` with **cwd = project directory** (via `preview/runner.py` or QProcess in the dock).
- Subprocess timeout (e.g. 30–60s) kills runaway loops.
- **Never** execute code from JSON on load — only on explicit Preview/Generate.
- Asset paths (future pygame): reject `..`; resolve under project root.

---

## 10. Distribution

| Artifact | Mechanism |
|----------|-----------|
| PyPI package | `py-vui` on install; import `py_vui` |
| Extras | `[gui]` → PySide6; `[dev]` → pytest, ruff |
| CLI | `py_vui` console script |
| CI publish | Tag `v*.*.*` → `.github/workflows/publish-pypi.yml` → `twine upload` with `PYPI_API_TOKEN` |

Maintainer release steps (version bump, TestPyPI, production upload, GitHub Release) are spelled out in **[tutorial.md — Phase 8](./tutorial.md#phase-8--release--publishing)**.

---

## 11. Quality attributes & risks

| Attribute | Target |
|-----------|--------|
| Editor latency | Interactive feedback &lt; 16 ms for typical projects |
| Cold start | Comparable to other PySide apps |
| Reliability | Autosave + recovery file |
| Security | Preview cwd constrained; no arbitrary code on open |

| Risk | Mitigation |
|------|------------|
| Toolkit fragmentation | Ship PySide6 only; adapter field for future targets |
| pygame vs Qt event loop | Subprocess preview; no embedded pygame in Qt v1 |
| Codegen merge conflicts | Merge regions + `custom.py` |
| Scope creep | Roadmap items explicitly marked optional/future |

### Optional future enhancements

- Visual anchor editor on canvas
- Drag-reorder in widget tree
- Undo coalescing for drags
- `QTabWidget` page management UI
- Partial import of `ui_generated.py` via AST
- PyInstaller bundles on GitHub Releases

---

## 12. Future: pygame studio

**Not implemented** in the editor. Design intent (from original spec):

| Concern | UI builder (today) | pygame studio (future) |
|---------|-------------------|------------------------|
| `schemaVersion` | `"1"` | `"2"` |
| `adapter` | `pyside6` | `pygame` |
| Root node | `window` | `scene` |
| Extra fields | `theme`, `handlers` | `runtime`, `inputMap`, `systems`, `assetsRoot` |
| Codegen | `app/*.py` Qt | `game.py`, `config.py`, `scenes.py` |
| Preview | `app/main.py` | `game.py --py_vui-design` |

Node kinds: `scene`, `sprite`, `camera_2d` with `transform` and asset paths under `assets/`. See historical spike content in git history (`IMPLEMENTATION.md` Phase 2 sections) if implementing Phase 8.

---

## 13. Glossary

| Term | Meaning |
|------|---------|
| **Node** | Element in the document tree (widget today; game object later). |
| **Document** | Full `py_vuiProject` state serialized to JSON. |
| **Adapter** | Target runtime (`pyside6`, future `pygame`). |
| **Command** | Reversible edit operation on `ProjectDocument`. |
| **Generate** | Write/refesh `app/` from the document. |
| **Export** | Copy project for end users without editor session files. |

---

*This document supersedes: `DESIGN_SPEC.md`, `IMPLEMENTATION_PLAN.md`, `ROADMAP.md`, `PHASE2_UI.md`, and the architectural portions of `IMPLEMENTATION.md` and `PUBLISHING.md`.*
