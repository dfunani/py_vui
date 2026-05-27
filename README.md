# py_vui

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)

py_vui is a visual authoring environment for Python user interfaces. **Phase 1** delivers drag-and-drop layout, property editing, and clean PySide6 code generation. **Phase 2** (planned) adds pygame integration for a small-game / interactive-media workflow.

- **Repository:** [github.com/dfunani/py_vui](https://github.com/dfunani/py_vui)
- **Design docs:** [DESIGN_SPEC](./docs/DESIGN_SPEC.md) · [IMPLEMENTATION_PLAN](./docs/IMPLEMENTATION_PLAN.md) · [IMPLEMENTATION](./docs/IMPLEMENTATION.md)

## Install (end users)

**Requirements:** Python **3.12+**, macOS, Windows, or Linux (desktop with Qt support).

After the package is [published on PyPI](./docs/PUBLISHING.md) (maintainer steps below), anyone can run:

```bash
pip install "py-vui[gui]"
py_vui
```

The PyPI install name is **`py-vui`** (hyphen); the import and CLI remain `py_vui`.

### Install from GitHub (before or without PyPI)

```bash
git clone https://github.com/dfunani/py_vui.git
cd py_vui
pip install -e ".[gui]"
py_vui
```

## Using the editor

1. **Save:** **File → Save Project As…** — pick a parent folder (e.g. `~/Documents`). The editor creates `<project-name>/` with `py_vui.json` and `session.meta.json`.
2. **Save again:** **File → Save Project** (⌘S / Ctrl+S).
3. **Open:** **File → Open Project Folder…** or **Open Recent**.
4. **Design:** drag widgets from the palette, move on canvas, edit in the inspector.
5. **Generate:** **Build → Generate Code** → writes `<project>/app/`.
6. **Export:** **Build → Export Code** — choose a parent folder; export goes to `<parent>/<project-name>/`.
7. **Run generated app:**

   ```bash
   cd ~/Documents/my-ui/app
   pip install -r requirements.txt
   python main.py
   ```

**Open sample JSON only:** **File → Open py_vui.json…** → `examples/fixtures/minimal.json`.

### Saved project folder

```
~/Documents/my-ui/
  py_vui.json
  session.meta.json
  app/              # Generate / Preview / Export
    main.py
    ui_generated.py
    requirements.txt
    README.md
```

## Developing from source

For contributors and local hacking ([CONTRIBUTING.md](./CONTRIBUTING.md)):

```bash
git clone https://github.com/dfunani/py_vui.git
cd py_vui
uv sync --extra gui --extra dev
uv run py_vui          # launch editor
uv run pytest -q       # tests
uv run ruff check src  # lint
```

Equivalent without `uv`:

```bash
pip install -e ".[gui,dev]"
py_vui
pytest -q
```

## Publishing for everyone (maintainers — your steps)

Full checklist and troubleshooting: **[docs/PUBLISHING.md](./docs/PUBLISHING.md)**.

### One-time setup

1. Create accounts on [pypi.org](https://pypi.org) and [test.pypi.org](https://test.pypi.org).
2. Create a PyPI API token (scope: project `py-vui` or whole account).
3. Confirm the name **`py-vui`** is available on PyPI (change `name` in `pyproject.toml` if not).
4. **Optional automation:** add GitHub secret `PYPI_API_TOKEN` (repo → Settings → Secrets → Actions).

### Each release

```bash
# 1. Bump version in pyproject.toml, commit, then from repo root:
python -m pip install --upgrade build twine
uv run pytest -q

# 2. Build
python -m build

# 3. Test upload (recommended)
twine upload --repository testpypi dist/*
pip install --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ \
  "py-vui[gui]==<VERSION>"
py_vui

# 4. Production upload
twine upload dist/*
# Username: __token__   Password: <your PyPI API token>

# 5. Tag on GitHub (triggers CI publish if PYPI_API_TOKEN is set)
git tag -a v0.1.0 -m "Release 0.1.0"
git push origin v0.1.0
```

Then create a **GitHub Release** for that tag with release notes.

After the first PyPI upload, tell users:

```bash
pip install "py-vui[gui]"
py_vui
```

## Phase 2 (interactive builder)

Themes, per-widget styling, **button / field actions** (inline handler editor), and **drag resize** on the canvas. See [docs/PHASE2_UI.md](./docs/PHASE2_UI.md).

**Roadmap (v1 → v2 → vfinal):** [docs/ROADMAP.md](./docs/ROADMAP.md)

## Goals

- **Familiar workflow:** palette → canvas → inspector → generated code, with undo/redo and Git-friendly project files.
- **Honest v1 scope:** standard widgets first; exotic platform APIs later.
- **Phase 2:** pygame scenes, assets, and runtime preview in the same authoring model.

## Non-goals (initial releases)

- Parity with every commercial UI builder.
- Full game-engine features beyond reasonable pygame scope.
- Mandatory cloud service; local-first by default.

## Repository layout

```
py_vui/
  docs/                 # design + PUBLISHING.md
  examples/fixtures/
  src/py_vui/
    model/              # document schema + serde
    commands/           # undo/redo
    codegen/            # PySide6 emitter
    preview/
    app/editor/         # Qt UI builder
  src/tests/
```

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md). Open issues and PRs at [github.com/dfunani/py_vui/issues](https://github.com/dfunani/py_vui/issues).

## License

[MIT](./LICENSE) — Copyright (c) 2026 Delali Funani.
