# py_vui user guide

py_vui is a visual builder: you drag widgets onto a canvas and it generates plain Python for
Tkinter, CustomTkinter, PySide6, PyQt6 or Kivy. Everything is free and local: no account, no
network calls from the editor.

## Contents

1. [Quick start](#quick-start) 2. [Window layout](#the-editor-window) 3. [Building a UI](#building-a-ui)
4. [Layouts](#layouts) 5. [Events and handlers](#events-and-handlers) 6. [Menus](#menus)
7. [Themes](#themes) 8. [Assets](#assets) 9. [Templates](#templates) 10. [Preview and run](#preview-and-run)
11. [Export](#export) 12. [Plugins](#plugins) 13. [Projects, autosave and undo](#projects-autosave-and-undo)
14. [Shortcuts](#keyboard-shortcuts)

## Quick start

```bash
pip install "py-vui[gui]"
py_vui
```

1. `File > New from Template...` (Ctrl+Shift+N), or `File > New Project...` (Ctrl+N).
2. Drag widgets from the palette onto the canvas; edit them in the inspector.
3. `Build > Run / Preview` (F5) to see the real app.
4. `File > Save As...` once, then Ctrl+S. `File > Export...` (Ctrl+E) to ship the code.

## The editor window

* **Palette** (left): widgets grouped by category (Window, Layout, Input, Display, Data,
  Plugins). Drag onto the canvas.
* **Canvas** (centre): the design surface with rulers, grid, snapping, smart guides, zoom and
  device-size presets (phone, tablet, laptop, desktop).
* **Inspector** (right): *Properties*, *Style*, *Layout* and *Events* pages for the selected
  widget, plus project-level settings when nothing is selected.
* **Widget tree**: every widget by hierarchy; drag to reparent or reorder, F2 to rename.
* **Code panel / console**: generated `ui.py`, `handlers.py`, `custom.py`, `requirements.txt`
  with syntax checking; the console shows output of the running preview.
* **Toolbar**: undo/redo, clipboard, the target **framework** selector, generate/run/stop,
  live preview, export and theme.
* `View > Panels` toggles docks; `View > Editor Theme` switches dark, light or follow-system.

## Building a UI

* **Add**: drag from the palette. Containers (Frame, Group Box, Tabs, Scroll Area, Splitter,
  windows) accept children.
* **Select**: click, Shift+click, rubber-band; Ctrl+A selects all in the container.
* **Move / resize**: drag to move, use the handles to resize; snapping and guides help alignment.
* **Edit menu**: cut/copy/paste/duplicate, delete, rename; **Align** (left/centre/right,
  top/middle/bottom), **Distribute**, **Size** (same width/height/size), **Order** (front/back);
  **Group in Frame** and **Wrap in...** (wrap the selection in a container); **Ungroup**.
* **Tab order** and tooltips, enabled/visible/locked flags are in the inspector.
* **Dialog windows**: `Project > Add Dialog Window`. Dialogs are children of the main window and
  are generated as functions that open them on demand.
* **Tabs** are a paged container: each child belongs to one tab (its `page`).
* **Properties** are validated against the widget definition; unknown or unsupported ones are
  reported as warnings, never silently dropped.

## Layouts

Each container chooses how its children are arranged (inspector > Layout):

| Mode | Use it for | Per-child settings |
|---|---|---|
| **Absolute** | free placement, pixel positions | x, y, width, height, anchors (stay pinned to edges on resize) |
| **Flex** | rows / columns that adapt | direction, gap, justify, align, wrap; child `grow`, `align self`, margins |
| **Grid** | forms and dashboards | column / row weights and gaps; child row, column, spans, sticky |

You can mix modes: a flex window containing a grid frame is normal. See
[frameworks.md](./frameworks.md) for how each mode maps to every toolkit.

## Events and handlers

Bind an event on the *Events* page (click, change, toggle, select, submit, close, key and mouse
events, focus, resize...). The available events depend on the widget.

* A **handler** is a function `def on_save(event=None): ...`. Choose an existing one or create
  a new one from the event dropdown; templates and snippets give you a starting body.
* Handler bodies are edited in the code panel and stored in the project. They are written to
  `app/handlers.py` between `# py_vui: begin custom` / `end custom` markers.
* **Regeneration is merge-safe.** Edits you make inside the markers survive, and module-level
  code (imports, globals, helpers) lives in the marked module region. `custom.py` is yours and is
  never overwritten.
* If you edit `handlers.py` in another editor, `Build > Sync Handlers from Disk` (or just
  generating again) pulls those edits back into the project.
* Use `ui.WIDGETS` (a registry of the built widgets) to read or change widgets from handlers.

## Menus

`Project > Menus...` designs the main window's menu bar: titles, items, separators, shortcuts,
checkable items, sub-menus, and the handler each item calls.

## Themes

`Project > Theme...` offers presets (light, dark, modern, ocean, forest, sunset, midnight) and
fine control over colours, font, border and button radius. The theme is translated to each
framework's native styling. Individual widgets can override colours, font, border, radius, hover
colour, cursor and relief in the *Style* page. The *editor* theme (dark, light, system) is
separate: it only styles the editor.

## Assets

`Project > Assets...` imports images and files into `<project>/assets/`. Reference them from
image properties as `assets/name.png`. Assets are copied next to the generated app on generate
and export. Removing an asset from the project keeps the file on disk so undo still works. If you
add assets before saving, they wait in a temporary folder and are moved on Save As.

## Templates

`File > New from Template...` or `py_vui templates` lists 14 starting points: Empty, Login Form,
Sign-up Form, Contact Form, Settings Dialog (tabs), Calculator, To-do List, Dashboard (flex +
grid), Data Table Viewer, File Converter (grid), Media Player, Chat Window, Landing / About and
Multi-window App. Templates are ordinary projects: every widget can be changed, and each load
gets fresh ids.

## Preview and run

* **Run / Preview** (F5) generates the app and runs it in a separate process, so your project
  and the editor are never affected by it. **Stop** (Shift+F5), **Restart** (Ctrl+F5).
* **Live Preview** (Ctrl+L) restarts the preview after every edit, using a private temp folder.
* Output and errors appear in the console. If third-party packages are missing, the editor tells
  you which ones. `Build > Requirements...` edits extra requirements.
* From a terminal: `py_vui run PROJECT [--venv]`. `--venv` creates `<project>/.py_vui/venv` (with
  `uv` when available, otherwise `venv` + pip) and installs the requirements there; it is the only
  step that uses the network, and only when you ask for it.

## Export

`File > Export...` (Ctrl+E) or `py_vui export`:

* **Project folder**: `main.py`, `ui.py`, `handlers.py`, `custom.py`, `requirements.txt`,
  `README.md`, `assets/`.
* **Single file**: one self-contained `main.py` (assets copied beside it).
* **Zip**: the project folder, archived.

`Build > Generate Code` (Ctrl+B) writes to `<project>/app` and preserves your code.
`Build > Build Executable (PyInstaller)...` builds a standalone app from the generated folder
(needs `pip install pyinstaller`).

## Plugins

Local widget plugins live in `~/.py_vui/plugins` or `<project>/plugins`. They are listed in
`Project > Plugins...` and run only after you enable them. See [plugins.md](./plugins.md).

## Projects, autosave and undo

* A project is a folder: `py_vui.json` (the design), `session.meta.json`, `assets/`, `app/`
  (generated). Older v1 projects open automatically; the first save upgrades them and keeps a
  `py_vui.v1.json.bak`.
* **Autosave** writes `.py_vui.autosave.json` while the project has unsaved changes. If it is
  newer than `py_vui.json` when you reopen the project, the editor offers to recover it.
* **Undo/redo** covers every edit (typing in a property coalesces into one step).
* `File > Open Recent` remembers your last projects. Settings and recents live in `~/.py_vui/`.

## Keyboard shortcuts

| Action | Keys |
|---|---|
| New / from template / open / save / save as | Ctrl+N / Ctrl+Shift+N / Ctrl+O / Ctrl+S / Ctrl+Shift+S |
| Export / preferences / quit | Ctrl+E / Ctrl+, / Ctrl+Q |
| Undo / redo | Ctrl+Z / Ctrl+Shift+Z or Ctrl+Y |
| Cut / copy / paste / duplicate / delete | Ctrl+X / C / V / D / Del |
| Select all / rename | Ctrl+A / F2 |
| Group / ungroup | Ctrl+G / Ctrl+Shift+G |
| Order: front, forward, backward, back | Ctrl+Shift+], Ctrl+], Ctrl+[, Ctrl+Shift+[ |
| Zoom in / out / fit / 100% | Ctrl+= / Ctrl+- / Ctrl+0 / Ctrl+1 |
| Grid / snap / guides / rulers | Ctrl+' / Ctrl+; / Ctrl+Shift+; / Ctrl+R |
| Generate / run / stop / restart / live | Ctrl+B / F5 / Shift+F5 / Ctrl+F5 / Ctrl+L |
| Show all shortcuts | Ctrl+/ |

On macOS, Ctrl is Cmd.
