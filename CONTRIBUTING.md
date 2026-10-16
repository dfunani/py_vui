# Contributing to py_vui

Thank you for helping improve py_vui. See [docs/architecture.md](./docs/architecture.md) for the
design: a framework-agnostic document model (`core`), reversible `commands`, one code-generation
`codegen` adapter per framework, `services` (project lifecycle, templates, runtime), `plugins`,
`preview` and the PySide6 editor (`app`).

## Development setup

```bash
git clone https://github.com/dfunani/py_vui.git
cd py_vui
python3.12 -m venv .venv
.venv/bin/python -m pip install -e ".[dev,gui]"
```

(On Windows use `.venv\Scripts\python`.) Use the project's `.venv` interpreter explicitly in the
commands below; do not rely on a globally activated environment.

## Before you open a PR

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check src tools examples
.venv/bin/python tools/gen_docs.py --check     # docs/frameworks.md must be up to date
```

Keep diffs focused and match the style of the files you touch (ruff, line length 100).

## Where things go

* New widget: register a `WidgetSpec` in `core/catalog.py`, add an emitter to each adapter, then
  run `.venv/bin/python tools/gen_docs.py` to refresh the support matrix.
* New template: add a v2 JSON file to `src/py_vui/templates/`; `test_templates.py` checks that it
  loads, validates and generates for every available framework.
* Every document change goes through a `Command` pushed to `History`.
* Never `exec` project content on load; plugins run only after the user enables them.
* No network calls from the editor.

## Test environments

Tests run headless: Qt tests use `QT_QPA_PLATFORM=offscreen` (set by `src/tests/conftest.py`).

* **Tkinter / CustomTkinter**: generation is verified by compiling the output; tests that need a
  display or the `tkinter` module skip themselves when unavailable. On Debian/Ubuntu install
  `python3-tk`; for GUI smoke tests under CI use `xvfb-run`.
* **Kivy**: install with `.venv/bin/python -m pip install kivy` to enable the Kivy checks; they
  skip otherwise. Set `KIVY_NO_ARGS=1` and `KIVY_NO_CONSOLELOG=1` in headless runs.
* **Adapters not installed** (`customtkinter`, `PyQt6`): adapter tests are skipped, not failed.
* Tests that touch user state set `PY_VUI_HOME` to a temp folder; do the same in new tests.

## Reporting bugs

Open an issue at [github.com/dfunani/py_vui/issues](https://github.com/dfunani/py_vui/issues) with
OS and Python version, steps to reproduce, expected vs actual behaviour, and screenshots if
UI-related.

## Publishing releases (maintainers)

Update [CHANGELOG.md](./CHANGELOG.md), bump the version in `pyproject.toml` and
`src/py_vui/__init__.py`, then push a `v*` tag; the publish workflow uploads to PyPI.
Full steps (PyPI setup, TestPyPI dry run, troubleshooting): [docs/releasing.md](./docs/releasing.md).
