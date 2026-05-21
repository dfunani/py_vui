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

1. **Save your work:** **File → Save Project As…** — choose a parent folder (e.g. `~/Documents`). The editor creates `<name>/` (e.g. `untitled/`, `my-form/`).
2. **Save again:** **File → Save Project** (⌘S) updates `py_vui.json` and `session.meta.json` in that folder.
3. **Open later:** **File → Open Project Folder…** or **Open Recent**.
4. **Edit:** drag widgets, move on canvas, inspector for properties.
5. **Generate app:** **Build → Generate Code** → `<project>/app/`.
6. **Run:**
   ```bash
   cd ~/Documents/untitled/app
   pip install -r requirements.txt
   python main.py
   ```

Sample JSON only: **File → Open py_vui.json…** → `examples/fixtures/minimal.json`.

### Saved project folder

```
~/Documents/my-ui/
  py_vui.json
  session.meta.json
  app/              # created by Generate / Preview
    main.py
    ui_generated.py
    requirements.txt
    README.md
```

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
