# py_vui

py_vui is a visual authoring environment for Python user interfaces. **Phase 1** delivers a capable alternative to **pyUIBuilder**: drag-and-drop layout, property editing, and clean Python code generation. **Phase 2** layers **pygame** integration so the same authoring model can target a small-game / interactive-media “studio” workflow (scenes, assets, runtime preview).

Authoritative technical detail lives in:

- [Design specification](./docs/DESIGN_SPEC.md)
- [Implementation plan](./docs/IMPLEMENTATION_PLAN.md)
- [Implementation](./docs/IMPLEMENTATION.md) — full copy-paste spec (Phase 1 UI + Phase 2 pygame): wire format, schemas, and every source file

## Goals

- **Familiar workflow**: palette → canvas → inspector → generated code, with undo/redo and project files that diff well in Git.
- **Honest scope for v1**: standard widgets and layouts first; exotic platform APIs later.
- **Phase 2 unlock**: one binary (or app bundle) that can preview pygame scenes and export a runnable project skeleton.

## Non-goals (initial releases)

- Replacing every feature of every commercial UI builder.
- Full game-engine parity (physics, ECS, networked multiplayer) beyond what pygame reasonably supports.
- Shipping a proprietary cloud service; local-first is the default stance.

## Quickstart

```bash
uv sync --extra gui --extra dev
uv run py_vui          # launch the visual editor
uv run pytest -q       # run tests
```

### Editor workflow

1. **Drag** widgets from the left palette onto the canvas (drop on a parent frame/window).
2. **Move** widgets by dragging them on the canvas; edit **X/Y/W/H** in the inspector.
3. **File → Save** writes `py_vui.json` in your project folder.
4. **Build → Generate Code** writes `generated/ui_generated.py` and `generated/main.py`.
5. **Build → Preview** (F5) runs the generated app in a subprocess.

Open the sample project: `examples/fixtures/minimal.json`.

## Repository layout

```
py_vui/
  docs/
  examples/fixtures/
  src/py_vui/
    model/              # document schema + serde
    commands/           # undo/redo commands
    codegen/            # PySide6 emitter
    preview/            # subprocess preview runner
    app/editor/         # Qt UI builder (palette, canvas, inspector)
  src/tests/
```

## Contributing (future)

Once code exists: issues and PRs should reference whether the change belongs to **Phase 1 (UI builder)** or **Phase 2 (pygame studio)** to keep the roadmap legible.

## License

TBD.
