# Writing py_vui plugins

A plugin adds a widget type to the palette together with the code that creates it in each
framework you choose to support. Plugins are local files: py_vui never downloads anything and
never runs plugin code until you enable that plugin.

## Where plugins live

* `~/.py_vui/plugins/` available to every project (`$PY_VUI_HOME/plugins` if set)
* `<project>/plugins/` travels with one project

A plugin is a single `.py` file, or a package directory with an `__init__.py`. Files starting with
`_` or `.` are ignored.

## Security model

* **Scanning never executes code.** Name, version, description and widget type ids are read with
  `ast` from the literal `PLUGIN = {...}` dict and `WidgetSpec(...)` calls.
* A plugin runs only after you enable it (`py_vui plugins enable ID` or `Project > Plugins...`).
  Enabling records the plugin's file path; a different file claiming the same id (for example in a
  downloaded project's `plugins/` folder) is not trusted.
* Each plugin is isolated: an error during import or `register()` rolls back its registrations,
  is shown next to the plugin and never crashes the editor. Disabling unregisters everything.

## Anatomy

```python
PLUGIN = {
    "id": "rating_stars",        # unique; letters, digits, _ and -
    "name": "Rating Stars",
    "version": "1.0.0",
    "description": "Clickable star rating for Tkinter.",
}

from py_vui.codegen.base import EmitContext, EmitResult
from py_vui.core.registry import PropSpec, WidgetSpec


def _emit_tk(ctx: EmitContext) -> EmitResult:
    stars = int(ctx.node.props.get("stars", 5))
    return EmitResult(
        imports=["import tkinter as tk"],
        lines=[f"{ctx.var} = tk.Label({ctx.parent}, text='*' * {stars})"],
    )


def register(api):
    api.register_widget(WidgetSpec(
        type="rating_stars", label="Rating Stars", category="Plugins", icon="*",
        default_size=(160, 32), frameworks=frozenset({"tkinter"}),
        props=(PropSpec("stars", "int", 5, "Stars", minimum=1, maximum=10),),
    ))
    api.register_emitter("rating_stars", "tkinter", _emit_tk)
    api.add_requirement("tkinter", "some-package>=1.0")  # optional
```

`PLUGIN` must be a plain literal and `register(api)` must exist, otherwise the plugin is listed
with an error and cannot be enabled.

## The API

`api.register_widget(spec: WidgetSpec)`
: Adds the widget to the registry. `plugin=True` and `category="Plugins"` are forced. The `type`
  must be unique, including against built-ins. `frameworks` should list exactly the frameworks you
  provide emitters for. Properties (`PropSpec`) drive the inspector: kinds are `str`, `text`,
  `int`, `float`, `bool`, `choice`, `color`, `list`, `file`, `image`, `json`.

`api.register_emitter(widget_type, framework, fn)`
: `fn(ctx: EmitContext) -> EmitResult` for one framework (`tkinter`, `customtkinter`, `pyside6`,
  `pyqt6`, `kivy`). `ctx` has `project`, `node` (read `node.props`), `var` (the identifier your code
  must assign the widget to), `parent` (identifier of the parent) and `framework`. Return
  `imports` (module-level lines), `lines` (unindented statements that create `ctx.var` as a child of
  `ctx.parent`) and optionally `requirements`. The adapter positions and styles the widget after
  your code. Emit nothing but statements that use `ctx.var`, `ctx.parent` and your own imports.

`api.add_requirement(framework, package)`
: Adds a pip requirement to `requirements.txt` whenever the plugin's widgets are used with that
  framework.

Emitters should be pure functions of `ctx`. For Qt, choose the binding module from
`ctx.framework` (`PySide6` or `PyQt6`).

## Example plugins

Ready-to-copy examples live in `examples/plugins/`:

| File | Widget | Frameworks | Shows |
|---|---|---|---|
| `rating_stars.py` | clickable stars | tkinter, customtkinter | closures and event binding in emitted code |
| `toggle_group.py` | exclusive toggle buttons | tkinter, pyside6, pyqt6 | one widget, several emitters, list props |
| `status_led.py` | coloured indicator | tkinter, pyside6, pyqt6 | the smallest useful plugin |

Try one:

```bash
mkdir -p ~/.py_vui/plugins
cp examples/plugins/status_led.py ~/.py_vui/plugins/
py_vui plugins list
py_vui plugins enable status_led
```

Then open the editor: the widget appears under *Plugins* in the palette. Projects that use a
plugin widget need that plugin enabled to open; otherwise opening fails with a hint to enable it.

## Testing a plugin

```python
import ast

from py_vui.codegen.base import EmitContext, plugin_emitter
from py_vui.core import make_node, new_project
from py_vui.plugins import PluginManager

PluginManager().enable("status_led")          # registers widget + emitters
project = new_project("t", "tkinter")
node = make_node("status_led", parent_id=project.root_id, name="LED")
result = plugin_emitter("status_led", "tkinter")(EmitContext(project, node, "led", "root", "tkinter"))
ast.parse("\n".join([*result.imports, *result.lines]))   # must be valid Python
```

Use a temporary `PY_VUI_HOME` in tests and call `PluginManager().unload_all()` afterwards. See
`src/tests/test_plugins.py` for the full pattern.
