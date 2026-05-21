# py_vui — Implementation plan

**Version:** 0.1 (planning)  
**Related:** [Design specification](./DESIGN_SPEC.md)

## 0. Milestone overview

| Milestone | Scope | Exit criteria |
|-----------|--------|----------------|
| **M0 — Spike** | Prove editor stack + subprocess preview | 50-node canvas, save/load JSON, codegen runs |
| **M1 — Phase 1 MVP** | pyUIBuilder-class core on one toolkit | Usable small app exported end-to-end |
| **M2 — Phase 1 v1** | UX + stability | Snap/guides, autosave, docs for codegen contract |
| **M3 — Phase 2 MVP** | pygame scene + preview | One scene, sprite, main loop export |
| **M4 — Phase 2 v1** | Studio polish | Multi-scene, asset panel, input map |

## 1. Workstreams

### 1.1 Document model & schema

**Deliverables**

- JSON Schema (or pydantic models) for `py_vuiProject`, `Node`, `Style`, `BindingStub`.
- Version field `schemaVersion` with migration hooks.

**Tasks**

1. Define immutable node identity (`uuid4`) separate from display `name`.
2. Define transform schema for Phase 2 compatibility even if Phase 1 ignores rotation/scale.
3. Unit tests: serde round-trip for golden fixtures.

### 1.2 Command system

**Deliverables**

- `Command` interface: `apply()`, `revert()`, metadata for coalescing (drag moves).
- `History` with configurable depth; macro commands for paste/delete subtree.

**Tasks**

1. Property edits coalesce within 300 ms window where safe.
2. Fuzz test: random command sequences preserve invariants (unique ids, single root).

### 1.3 Editor shell (PySide6 assumed)

**Deliverables**

- Main window: palette dock, canvas, inspector, log/output dock.
- Project service: dirty flag, save, autosave timer.

**Tasks**

1. `QGraphicsScene`/`QGraphicsView` prototype with selection handles.
2. Serialization wiring: menu actions → model updates → codegen hook on save.

### 1.4 Layout & constraints (Phase 1)

**Deliverables**

- Data model for anchors/margins OR pack-grid analog matching chosen toolkit.
- Editor overlay for constraint editing.

**Tasks**

1. Pick **one** layout paradigm for MVP to avoid half-implemented engines.
2. Golden screenshots for layout cases (manual QA checklist if no pixel CI).

### 1.5 Codegen pipeline

**Deliverables**

- `codegen/` package: `emit_project(project) -> list[WrittenFile]`.
- Template strategy: Jinja2 or ast-based generation (choose in M0 spike).

**Tasks**

1. Golden file tests: given `fixtures/minimal.json`, output matches expected `.py`.
2. Optional merge regions: tokenizer that refuses to clobber user blocks.

### 1.6 Preview runner

**Deliverables**

- `preview_runner.py`: spawn `python -m generated_app` with env + cwd set.
- Capture return code; surface tracebacks in UI.

**Tasks**

1. Windows/macOS/Linux path normalization for subprocess.
2. Timeout kill switch for runaway loops (Phase 2 especially).

### 1.7 Phase 2 — pygame bridge

**Deliverables**

- New node kinds: `Scene`, `SpriteNode`, `Camera2D` (minimal).
- Codegen template for pygame loop + scene stack.
- Asset browser: file tree rooted at `assets/`.

**Tasks**

1. Define `RuntimeContext` passed to generated code (screen size, flags).
2. Scene switch API: `push_scene`, `pop_scene` stubs.
3. Preview subprocess uses same entrypoint with `--py_vui-design` flag.

### 1.8 Packaging & distribution

**Deliverables**

- `pyproject.toml` with console script `py_vui`.
- Brief “install from source” and “build bundle” (pyinstaller brief only).

**Tasks**

1. CI: lint (ruff), typecheck (pyright/mypy), tests on 3.11+.

## 2. Suggested repository structure (when coding starts)

```
py_vui/
  docs/
  src/py_vui/
    __init__.py
    app/                 # Qt main window, docks
    model/               # document, nodes, schema
    commands/
    codegen/
    adapters/
      tk/                # optional later
      pyside/            # Phase 1 primary
      pygame_runtime/    # Phase 2
    preview/
  tests/
  examples/
```

## 3. Dependency policy

- **Pinned** dev dependencies in lockfile (uv or pip-tools — team choice).
- **Runtime** deps minimized; pygame optional extra: `pip install py_vui[pygame]`.

## 4. Testing strategy

| Layer | Strategy |
|-------|----------|
| Model | Pure unit tests, property-based optional |
| Codegen | Golden files + AST parse smoke |
| UI | pytest-qt for critical dialogs; heavy reliance on manual QA early |
| Preview | Mock subprocess in CI; real subprocess locally |

## 5. Security notes

- Never execute arbitrary code from project JSON on open; only on explicit Preview.
- Validate asset paths stay under project root (reject `..` segments).

## 6. Open decisions (resolve in M0)

1. Primary Phase 1 toolkit: **PySide6** vs **tkinter**.
2. Codegen style: **Jinja2** vs **ast/unparse**.
3. Minimum Python version support matrix.

## 7. Rough sequencing (calendar-agnostic)

1. M0 spike (1–2 weeks solo equivalent): canvas + JSON + codegen + subprocess.
2. M1 breadth: palette/inspector completeness + error UX.
3. M2 depth: autosave, guides, docs.
4. M3 pygame: scene + sprite + preview flag.
5. M4 studio: multi-scene, assets, polish.

## 8. Definition of Done (global)

- README quickstart updated for that milestone.
- No known P0 crashes on golden fixtures.
- CHANGELOG entry following Keep a Changelog (once shipping).
