# py_vui — Design specification

**Version:** 0.1 (planning)  
**Status:** Draft

## 1. Problem statement

Developers and learners want a **fast, local** way to compose Python UIs without hand-editing layout boilerplate, and (later) to **prototype pygame experiences** with the same mental model: components on a canvas, properties in an inspector, reproducible code output.

## 2. Product principles

1. **Generated code is the source of truth export** — the tool must emit readable Python that a human would maintain by hand if needed.
2. **Deterministic round-tripping (where feasible)** — opening generated code back in the editor should be supported for a defined subset of patterns (see §7).
3. **Progressive complexity** — Phase 1 avoids pygame entirely; Phase 2 adds optional pygame concepts without breaking Phase 1 projects.

## 3. Personas

| Persona | Needs |
|--------|--------|
| **App prototyper** | Rapid forms, dialogs, simple tools; cares about codegen quality and Git-friendly saves. |
| **Learner** | Low ceremony; visual feedback; understandable file format. |
| **Indie / jam dev** | pygame preview, asset references, scene switching, minimal “engine” glue. |

## 4. High-level architecture

### 4.1 Core domains

| Domain | Responsibility |
|--------|----------------|
| **Document model** | Tree of nodes (widgets / game objects), hierarchy, IDs, constraints. |
| **Command stack** | Undo/redo; all edits as reversible commands. |
| **Layout engine** | Measure and arrange nodes for editor overlay and (Phase 1) Tk/Qt preview as applicable. |
| **Codegen** | Serialize document → Python modules + entrypoint. |
| **Asset registry** | Paths, hashes, import rules; sandboxed resolution. |
| **Runtime adapters** | Phase 1: “host toolkit” adapter; Phase 2: pygame adapter. |

### 4.2 Suggested technology directions (decision record)

| Layer | Option A | Option B | Recommendation |
|-------|----------|----------|----------------|
| **Editor UI** | Python + Qt (PySide6) | Electron + native canvas | **PySide6** for tight Python integration and single-language core team. |
| **Canvas** | QGraphicsView | QWidget absolute | **QGraphicsView** for zoom, guides, snapping. |
| **Save format** | JSON | SQLite + JSON export | **JSON** (or JSON + sidecar assets) for v1; consider SQLite for large scenes later. |
| **Phase 1 target toolkit** | tkinter | PySide6 | Start with **one** target to ship; document second target as stretch. |

*These are defaults for planning; the implementation plan lists spike tasks to validate.*

## 5. Phase 1 — pyUIBuilder-class experience

### 5.1 Feature set (MVP → v1)

**MVP**

- New / open / save project (`py_vui.json` + `generated/`)
- Palette of core widgets (e.g. frame, label, button, entry, checkbox; exact set tied to target toolkit)
- Canvas: select, move, resize, parent/reparent, z-order
- Inspector: id, text, geometry, anchors/margins (if applicable), enabled state
- Codegen: `main.py` + `ui_generated.py` (names TBD) with clear extension points (`# py_vui: begin custom` regions optional)
- Local preview: launch generated UI in subprocess

**v1**

- Alignment guides, snapping grid, keyboard nudging
- Style tokens (font family/size, padding scale) as data, not hard-coded literals everywhere
- Simple data binding hooks (code stubs only; no full reactive framework)
- Import guardrails: warn on destructive re-import

### 5.2 UX flows

1. **Create project** → pick template (empty / dialog / form) → codegen on save.
2. **Edit** → command per interaction → undo/redo unlimited (configurable cap).
3. **Preview** → run adapter; stream stdout/stderr into dock panel.

### 5.3 Codegen contract

- **Stable node IDs** map to generated function or class attributes.
- **User merge regions** (optional): clearly delimited blocks the generator will not overwrite.
- **Lint-friendly output**: isort/black-compatible formatting rules documented.

## 6. Phase 2 — pygame “studio” extension

### 6.1 Additional document concepts

- **Scene**: root node type with background color/image, world units, default camera (2D).
- **GameObject**: transform (x, y, rotation, scale), sprite reference, optional script hook name.
- **Systems (lightweight)**: update order list (fixed pipeline), not a full ECS unless needed later.
- **Input map**: abstract actions → keys (export as dict for generated `config.py`).

### 6.2 Runtime model

- Generated `game.py` owns the main loop: `init` → `handle_events` → `update(dt)` → `draw`.
- **Editor preview** uses same runtime with a “design mode” flag (e.g. draw gizmos, ignore some gameplay).

### 6.3 Asset pipeline (v1 for Phase 2)

- Relative paths under `assets/` copied verbatim on export.
- Optional: texture atlas tool deferred; start with individual images.

## 7. Round-trip and interoperability

**Supported round-trip (initial):** projects created entirely in py_vui, saved as JSON + codegen.

**Stretch:** parse a subset of generated Python back into the document model (requires AST pass + heuristics).

**Explicit non-goal early:** arbitrary hand-edited Python full recovery.

## 8. Quality attributes

| Attribute | Target |
|-----------|--------|
| **Editor latency** | <16 ms interaction feedback for 1k nodes on a mid laptop |
| **Cold start** | Competitive with typical PySide apps (not Electron-sized) |
| **Reliability** | Autosave + crash recovery file |
| **Security** | Preview subprocess with cwd constrained to project root |

## 9. Risks and mitigations

| Risk | Mitigation |
|-------|------------|
| Toolkit fragmentation (tk vs Qt vs webview) | Ship one toolkit first; adapter interface for second. |
| pygame loop vs Qt event loop | Subprocess preview; optional embedded preview only if proven stable. |
| Codegen merge conflicts | Document merge regions; semantic diff tool later. |

## 10. Glossary

- **Node**: Element in the document tree (widget or game object).
- **Adapter**: Maps document semantics to a concrete UI/game runtime.
- **Document**: Serializable full project state excluding large binaries (assets referenced by path).
