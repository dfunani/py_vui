# py_vui architecture (schema v2)

py_vui is a desktop visual builder for Python GUIs. One document model, many code generators.

```
core/        registry-driven document model (no Qt, no I/O)       <- single source of truth
commands/    reversible edits + History (coalescing undo/redo)
codegen/     one Adapter per framework: tkinter, customtkinter, pyside6/pyqt6, kivy
plugins/     user widget plugins (specs + per-framework emitters)
app/         PySide6 editor (canvas, palette, inspector, code editor, preview…)
```

## Document model (`py_vui.core`)

* `Project` (`schemaVersion: "2"`): `meta`, `framework` (`tkinter|customtkinter|pyside6|pyqt6|kivy`),
  `rootId`, `nodes: {id: Node}`, `theme`, `handlers: {name: HandlerDef}`, `tabOrder`,
  `customCode`, `extraRequirements`, `assets`, `editor`.
* `Node`: `id, type, name, parentId, zIndex, box{x,y,w,h}, anchors, props{}, style{}, events{event_id: handler_name},
  layout (containers only), cell (grid placement), flex (flex item), page (tab index), enabled, visible, locked, tooltip, tabIndex`.
* Widget types are **data**: `core/registry.py` (`WidgetSpec`, `PropSpec`) + `core/catalog.py` (built-ins).
  Props are free-form dicts validated against the spec. `style` keys are `catalog.STYLE_PROPS`.
* Layout (`ContainerLayout.mode`): `absolute` (x/y/w/h, `place`), `flex` (row/column, gap, justify, align, wrap,
  per-child `flex.grow`/`alignSelf`/margin), `grid` (row/column weights, per-child `cell` row/col/span/sticky).
  `core/layout_engine.py` resolves flex/grid to boxes for the editor canvas.
* The root is a `window`; secondary windows are `toplevel` nodes that are direct children of the root.
  `tabview` is a *paged* container: children carry `page` = tab index.
* Handlers are always `def name(event=None):`. Bind events through `node.events`.
* Window menus: `window.props["menus"]` = list of `{title, items:[{label, handler?, shortcut?, separator?, checkable?, items?}]}`.

## Code generation (`py_vui.codegen`)

`generate(project, GenOptions) -> list[GeneratedFile]`. Project layout output:
`main.py`, `ui.py` (`build_ui()` returns the root; module-level `WIDGETS`, `WINDOWS` registries),
`handlers.py` (shared, merge-safe user code), `custom.py` (never overwritten), `requirements.txt`, `README.md`.
Single-file layout: one self-contained `main.py` (handlers inlined). Assets are referenced as `assets/<file>`
relative to the generated app (copied by `ProjectService`).
Plugin widgets register emitters with `register_plugin_emitter(type, framework, fn)`.

## Editor (`py_vui.app`)

Three-panel IDE-style layout like pyuibuilder: toolbox (left), design canvas (centre), properties/events/code (right),
widget tree, top toolbar (undo/redo, zoom, device size, preview, export), status bar, dark/light editor theme.

## Rules

* Every document mutation goes through a `Command` pushed to `History`.
* Never `exec` project content on load. Preview/Run executes generated files in a subprocess only on request.
* All features are free. No accounts, no network calls from the editor.
