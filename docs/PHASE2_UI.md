# Phase 2 — Interactive UI builder (not pygame)

Extends Phase 1 with styling, themes, and event handlers without changing the core wire format version (`schemaVersion: 1`).

## Themes

- Project-level **Theme** preset: Light, Dark, Modern, Ocean
- Inspector: **Project → Theme**
- Canvas preview and generated `theme.py` use the same tokens (colors, font, button radius)

## Per-widget appearance

- **Enabled** toggle
- Optional **background**, **foreground**, **font size**, **corner radius** overrides
- Empty fields inherit from the project theme

## Actions (listeners)

| Widget     | Signal            | Property in JSON   |
|-----------|-------------------|--------------------|
| Button    | `clicked`         | `props.onClick`    |
| Line edit | `returnPressed`   | `props.onReturn`   |
| Checkbox  | `toggled`         | `props.onToggle`   |

### Inspector workflow

1. Select a button (or line edit / checkbox).
2. **Actions → New** creates a handler stub (e.g. `on_submit_clicked`).
3. Edit Python statements in the inline editor; click **Apply handler code**.
4. Pick a handler from the dropdown or type a name.

### Generated app layout

```
app/
  main.py           # applies theme, builds UI, wires handlers
  ui_generated.py   # widgets + WIDGETS registry + stylesheets
  theme.py          # apply_theme(app)
  handlers.py       # your callback bodies
  interactions.py   # .connect() wiring
```

Example handler body:

```python
print("Saved!")
```

Codegen wraps it as:

```python
def on_submit_clicked() -> None:
    print("Saved!")
```

## Resize on canvas

Select any widget (including the main window). Drag the **orange corner/edge handles** to resize. Changes are undoable and sync to the inspector W/H fields.

## Regenerate after edits

Use **Build → Generate Code** or **Export Code** so `handlers.py` and `interactions.py` stay in sync with the project file.
