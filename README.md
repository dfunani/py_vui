# py_vui

[![CI](https://github.com/dfunani/py_vui/actions/workflows/ci.yml/badge.svg)](https://github.com/dfunani/py_vui/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)

**A free, local, drag-and-drop GUI builder for Python.** Design a window visually, bind events to Python
handlers, and export clean, readable code for **Tkinter, CustomTkinter, PySide6, PyQt6 or Kivy**.
No account, no paywall, no network calls. Every feature is included.

- 36 widgets: inputs, containers, tabs, scroll areas, splitters, tables, trees, canvas, images, plus plugin
  widgets (calendar, time picker, map viewer, chart, video player, pandas table, color picker).
- **Three layout managers** per container: absolute, flex (row/column, gap, justify, align, wrap, grow) and grid
  (weights, spans, sticky).
- IDE-style editor: toolbox, widget tree, canvas with zoom, rulers, guides and snapping, inspector
  (Properties / Style / Layout / Events), built-in Python code editor for handlers, console and live preview.
- Multiple windows (dialogs), menu designer, themes (7 presets + editable tokens), asset manager, 14 templates.
- Local **plugin system** for third-party widgets, a `py_vui` CLI for headless generation, and PyInstaller bundling.
- Generated code is plain Python you own. Handler code survives regeneration.

See [docs/parity.md](./docs/parity.md) for how this maps to pyuibuilder.com.

## Install

```bash
pip install py-vui          # editor + code generators (PySide6 is the only heavy dependency)
py_vui                      # launch the editor
```

Optional extras to *preview* generated apps: `py-vui[customtkinter]`, `[pyqt6]`, `[kivy]`, `[plugins]`
(or `[all]`). The editor can also create a per-project preview virtualenv for you.
Python 3.12+ on macOS, Windows and Linux. Tkinter apps need a Python built with Tk.

Prebuilt desktop bundles are attached to each [GitHub release](https://github.com/dfunani/py_vui/releases).

## Quick start

1. **File ▸ New** (pick a framework and optionally a template).
2. Drag widgets from the toolbox onto the canvas, or double-click to insert.
3. Arrange with absolute positioning, or switch a container to **flex** / **grid** in the Layout tab.
4. In **Events**, create a handler for `click`, `change`, etc. and edit it in the Code panel.
5. **Build ▸ Run** (or the live-preview toggle) to try it. **Build ▸ Export** writes the app.

Generated app:

```
my-app/
  main.py  ui.py  handlers.py  custom.py  requirements.txt  README.md  assets/
```
`handlers.py` keeps your code between the `# py_vui:` markers when you regenerate; `custom.py` is never
overwritten. Export as a single self-contained script with **Export ▸ Single file**.

## CLI

```bash
py_vui new "My App" --framework customtkinter --template login_form
py_vui gen my-app/py_vui.json -o out --framework pyside6
py_vui validate my-app/py_vui.json
py_vui run my-app/py_vui.json
py_vui plugins list
```

Full reference: [docs/cli.md](./docs/cli.md).

## Documentation

[User guide](./docs/user-guide.md) · [Frameworks & widget support](./docs/frameworks.md) ·
[Plugins](./docs/plugins.md) · [CLI](./docs/cli.md) · [Architecture](./docs/architecture.md) ·
[pyuibuilder parity](./docs/parity.md) · [Releasing](./docs/releasing.md) · [Changelog](./CHANGELOG.md)

## Developing

```bash
git clone https://github.com/dfunani/py_vui.git && cd py_vui
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q
.venv/bin/ruff check src
```
See [CONTRIBUTING.md](./CONTRIBUTING.md) for the Tk/Kivy test environments and the release process.

## License

MIT. Generated code is yours to use commercially.
