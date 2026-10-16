"""``py_vui`` command line: launch the editor or work with projects headlessly."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from py_vui.core.registry import FRAMEWORKS


def _version() -> str:
    try:
        from importlib.metadata import PackageNotFoundError, version

        for dist in ("py-vui", "py_vui"):
            try:
                return version(dist)
            except PackageNotFoundError:
                continue
    except Exception:
        pass
    from py_vui import __version__

    return __version__


def _err(msg: str) -> int:
    print(f"error: {msg}", file=sys.stderr)
    return 1


def _open(path: str):
    from py_vui.services.project_service import ProjectService

    svc = ProjectService()
    svc.open(Path(path))
    return svc


# --------------------------------------------------------------------------- commands
def cmd_gui(args: argparse.Namespace) -> int:
    try:
        from py_vui.app import qt_main
    except ImportError as exc:
        return _err(
            f"the editor needs PySide6 ({exc}). Install it with:  pip install 'py-vui[gui]'"
        )
    if args.path:
        sys.argv = [sys.argv[0], args.path]
    import inspect

    params = inspect.signature(qt_main.main).parameters
    result = qt_main.main([args.path] if args.path else []) if params else qt_main.main()
    return result if isinstance(result, int) else 0


def cmd_new(args: argparse.Namespace) -> int:
    from py_vui.services.project_service import ProjectService

    svc = ProjectService()
    svc.new_project(args.name, args.framework, args.template)
    path = svc.save_as(Path(args.output or "."), args.name)
    print(path.parent)
    return 0


def cmd_gen(args: argparse.Namespace) -> int:
    from py_vui.codegen.base import GenOptions

    svc = _open(args.project)
    if args.framework:
        svc.project.framework = args.framework
    opts = GenOptions(layout="single" if args.single else "project")
    if args.output:
        out = svc.export(Path(args.output), "single" if args.single else "project")
    else:
        if svc.project_dir is None:
            return _err("project has no folder; pass -o OUT")
        out = svc.generate(opts)
    print(out)
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    from py_vui.codegen.base import GenOptions, check_syntax

    svc = _open(args.project)
    problems = 0
    for d in svc.doc.diagnostics():
        where = svc.project.nodes[d.node_id].name if d.node_id else "project"
        print(f"{d.level}: {where}: {d.message}")
        problems += d.level == "error"
    try:
        errors = check_syntax(svc.generated_files(GenOptions()))
    except ValueError as exc:
        print(f"warning: code generation skipped: {exc}")
        errors = []
    for e in errors:
        print(f"error: generated code: {e}")
    problems += len(errors)
    if svc.migrated:
        print("note: project uses an older schema and was migrated in memory")
    if problems == 0:
        print("OK")
    return 1 if problems else 0


def cmd_migrate(args: argparse.Namespace) -> int:
    from py_vui.services.project_service import PROJECT_FILE

    svc = _open(args.input)
    src = Path(args.input)
    src_file = src / PROJECT_FILE if src.is_dir() else src
    if args.output:
        out = Path(args.output)
        if out.is_dir() or not out.suffix:
            out = out / PROJECT_FILE
    else:
        out = src_file
    from py_vui.core.serde import dump_json

    out.parent.mkdir(parents=True, exist_ok=True)
    if out.resolve() == src_file.resolve() and svc.migrated:
        shutil.copy2(src_file, src_file.with_name(src_file.name + ".v1.bak"))
    out.write_text(dump_json(svc.project), encoding="utf-8")
    print(f"{'migrated' if svc.migrated else 'already v2'}: {out}")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    svc = _open(args.project)
    print(svc.export(Path(args.dest), args.format))
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    svc = _open(args.project)
    if args.framework:
        svc.project.framework = args.framework
    svc.generate()
    python = None
    if args.venv:
        if svc.project_dir is None:
            return _err("--venv needs a saved project")
        from py_vui.services.runtime import ensure_runtime

        python = ensure_runtime(svc.project_dir, svc.requirements(),
                               lambda m: print(m, file=sys.stderr))
    spec = svc.run_spec(python)
    if spec.missing_requirements:
        print("warning: missing packages: " + ", ".join(spec.missing_requirements)
              + "\n  install them (pip install -r app/requirements.txt) or use --venv",
              file=sys.stderr)
    return subprocess.call(spec.argv, cwd=str(spec.cwd), env=spec.env)


def cmd_templates(args: argparse.Namespace) -> int:
    from py_vui.services.templates import list_templates

    items = list_templates()
    if args.json:
        print(json.dumps([t.__dict__ for t in items], indent=2))
        return 0
    width = max(len(t.id) for t in items)
    for t in items:
        print(f"{t.id:<{width}}  [{t.category}] {t.description}")
    return 0


def cmd_plugins(args: argparse.Namespace) -> int:
    from py_vui.plugins.manager import PluginManager

    mgr = PluginManager()
    if args.action == "list":
        infos = mgr.scan(Path(args.project) if args.project else None)
        if not infos:
            print(f"no plugins found (looked in {', '.join(map(str, mgr.search_dirs()))})")
        for i in infos:
            state = "enabled" if i.enabled else "disabled"
            print(f"{i.id}  v{i.version}  [{state}]  {i.name}"
                  + (f"  ERROR: {i.error}" if i.error else ""))
        return 0
    if not args.id:
        return _err(f"plugins {args.action} needs a plugin id")
    try:
        if args.action == "enable":
            mgr.enable(args.id, Path(args.project) if args.project else None)
            print(f"enabled {args.id}")
        else:
            mgr.disable(args.id)
            print(f"disabled {args.id}")
    except (KeyError, ValueError, RuntimeError) as exc:
        return _err(str(exc.args[0] if isinstance(exc, KeyError) else exc))
    return 0


# ------------------------------------------------------------------------------ parser
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="py_vui", description="Visual drag-and-drop GUI builder for Python."
    )
    p.add_argument("--version", action="version", version=f"py_vui {_version()}")
    sub = p.add_subparsers(dest="command")

    s = sub.add_parser("gui", help="launch the editor (default)")
    s.add_argument("path", nargs="?")
    s.set_defaults(fn=cmd_gui)

    s = sub.add_parser("new", help="create a project folder")
    s.add_argument("name")
    s.add_argument("--framework", "-f", choices=FRAMEWORKS, default="tkinter")
    s.add_argument("--template", "-t")
    s.add_argument("-o", "--output", help="parent directory (default: current)")
    s.set_defaults(fn=cmd_new)

    s = sub.add_parser("gen", help="generate code")
    s.add_argument("project")
    s.add_argument("-o", "--output")
    s.add_argument("--framework", "-f", choices=FRAMEWORKS)
    s.add_argument("--single", action="store_true", help="one self-contained main.py")
    s.set_defaults(fn=cmd_gen)

    s = sub.add_parser("validate", help="check a project; non-zero exit on errors")
    s.add_argument("project")
    s.set_defaults(fn=cmd_validate)

    s = sub.add_parser("migrate", help="upgrade an older project file to schema v2")
    s.add_argument("input")
    s.add_argument("-o", "--output")
    s.set_defaults(fn=cmd_migrate)

    s = sub.add_parser("export", help="export code (folder, single script or zip)")
    s.add_argument("project")
    s.add_argument("dest")
    s.add_argument("--format", choices=("project", "single", "zip"), default="project")
    s.set_defaults(fn=cmd_export)

    s = sub.add_parser("run", help="generate and run the app")
    s.add_argument("project")
    s.add_argument("--framework", "-f", choices=FRAMEWORKS)
    s.add_argument("--venv", action="store_true", help="install requirements into a project venv")
    s.set_defaults(fn=cmd_run)

    s = sub.add_parser("templates", help="list bundled templates")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_templates)

    s = sub.add_parser("plugins", help="list / enable / disable plugins")
    s.add_argument("action", choices=("list", "enable", "disable"))
    s.add_argument("id", nargs="?")
    s.add_argument("--project", help="project folder whose plugins/ should be searched")
    s.set_defaults(fn=cmd_plugins)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not getattr(args, "fn", None):
        args = argparse.Namespace(fn=cmd_gui, path=None)
    try:
        return int(args.fn(args) or 0)
    except (ValueError, KeyError, FileNotFoundError, OSError) as exc:
        return _err(str(exc.args[0] if isinstance(exc, KeyError) and exc.args else exc))


def gui_main() -> int:
    """Entry point for the ``py_vui-gui`` launcher: always opens the editor."""
    return main(["gui", *sys.argv[1:2]])


if __name__ == "__main__":
    raise SystemExit(main())
