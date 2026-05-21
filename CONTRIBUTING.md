# Contributing to py_vui

Thank you for helping improve py_vui. The project is in active development toward Phase 1 (Qt UI builder) with Phase 2 (pygame studio) planned later.

## Before you open a PR

1. Note whether your change is **Phase 1 (UI builder)** or **Phase 2 (pygame studio)** in the issue or PR description.
2. Run tests and lint from the repo root:

   ```bash
   uv sync --extra dev --extra gui
   uv run pytest -q
   uv run ruff check src
   ```

3. Keep diffs focused; match existing style in the files you touch.

## Development setup

See [README.md](./README.md#developing-from-source) for clone, `uv`, and running the editor.

## Reporting bugs

Open an issue at [github.com/dfunani/py_vui/issues](https://github.com/dfunani/py_vui/issues) with:

- OS and Python version
- Steps to reproduce
- Expected vs actual behavior
- Screenshots if UI-related

## Publishing releases (maintainers)

See [docs/PUBLISHING.md](./docs/PUBLISHING.md).
