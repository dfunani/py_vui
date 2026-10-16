# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [0.2.0] - 2026-10-15

A ground-up rewrite on a framework-agnostic document model. Everything is free and local: no
accounts and no network calls from the editor.

### Added
- Schema v2 document model (`py_vui.core`): registry-driven widgets, absolute / flex / grid
  layouts, per-node style, events, window menus and project themes (7 presets).
- Code generation for Tkinter, CustomTkinter, PySide6, PyQt6 and Kivy, as a multi-file project or
  a single self-contained script, with merge-safe `handlers.py` and a never-overwritten `custom.py`.
- Reversible command history with coalescing undo/redo; align, distribute, group and wrap tools.
- `py_vui.services`: project lifecycle (new, open, save, save as, autosave and recovery, assets,
  generate, export to folder / single file / zip, handler sync from disk), recent projects,
  settings, run specs with missing-requirement detection, PyInstaller command and per-project
  runtime environments (`uv` or `venv` + pip).
- 14 bundled templates (login, sign-up, contact, settings, calculator, to-do, dashboard, data
  table, file converter, media player, chat, landing, empty, multi-window).
- Local plugin system: single-file or package plugins, metadata read with `ast` (never executed on
  scan), explicit enable, per-plugin error isolation, per-framework emitters; three example
  plugins in `examples/plugins/`.
- Live preview in a subprocess (`py_vui.preview`).
- `py_vui` command line: `gui`, `new`, `gen`, `validate`, `migrate`, `export`, `run`, `templates`,
  `plugins`, `--version`.
- Documentation: user guide, plugin authoring guide, framework support matrix (generated from the
  registry by `tools/gen_docs.py`) and CLI reference.

### Changed
- Schema v1 (PySide6-only) projects are migrated automatically on open; the first save keeps a
  `py_vui.v1.json.bak` backup.
- Package renamed on PyPI to `py-vui`; console entry points are `py_vui` and `py-vui`.

### Removed
- The v1 model, command and PySide-only code generator modules, and the old editor services
  (`project_service`, `project_templates`, `recent_projects`, `session_paths`, `factory`,
  `clipboard_io`, `handler_snippets`).

## [0.1.0]

- Initial release: PySide6 editor with 16 widgets and PySide6 code export.
