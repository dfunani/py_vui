# Command line

`py_vui` (also `py-vui`) is installed with the package. With no arguments it opens the editor.

```
py_vui [--version] <command> [options]
```

Errors are printed as `error: ...` on stderr with exit status 1. No command contacts the network
(except `run --venv`, which runs `pip`/`uv` at your request).

| Command | Purpose |
|---|---|
| `gui [PATH]` | Open the editor, optionally on a project folder or `.json`. Needs PySide6 (`pip install "py-vui[gui]"`). |
| `new NAME [-f FRAMEWORK] [-t TEMPLATE] [-o DIR]` | Create `DIR/<name>/` (`py_vui.json`, `session.meta.json`, `assets/`). Prints the folder. |
| `gen PROJECT [-o OUT] [-f FRAMEWORK] [--single]` | Generate code. Without `-o`: into `<project>/app` (your `custom.py` and handler edits are kept). `-f` overrides the framework for this run only. |
| `validate PROJECT` | Print diagnostics and syntax-check generated code. Exit 1 on errors. |
| `migrate IN [-o OUT]` | Upgrade an old (schema v1) project file to v2. In place keeps `IN.v1.bak`. |
| `export PROJECT DEST [--format project\|single\|zip]` | Write a runnable folder, a single `.py`, or a `.zip`. |
| `run PROJECT [-f FRAMEWORK] [--venv]` | Generate and run. `--venv` installs requirements into `<project>/.py_vui/venv` first. Exits with the app's status. |
| `templates [--json]` | List the bundled templates. |
| `plugins list\|enable\|disable [ID] [--project DIR]` | Manage local plugins (see [plugins.md](./plugins.md)). |

`PROJECT` is a project folder or any project `.json` file. Frameworks: `tkinter`, `customtkinter`,
`pyside6`, `pyqt6`, `kivy`.

## Examples

```bash
py_vui templates
py_vui new shop -t dashboard -f pyside6 -o ~/projects
py_vui validate ~/projects/shop
py_vui gen ~/projects/shop            # writes ~/projects/shop/app
py_vui export ~/projects/shop shop.zip --format zip
py_vui run ~/projects/shop --venv
py_vui migrate old_project.json -o new/py_vui.json
```

## Environment

* `PY_VUI_HOME` replaces `~/.py_vui` (settings, recent projects, plugins and their enabled state).
  Useful for tests and portable installs.
