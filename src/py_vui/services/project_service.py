"""Project lifecycle: new / open / save / autosave / generate / export / assets / run.

Pure Python (no Qt). The editor owns one :class:`ProjectService` and reads ``service.doc`` and
``service.history`` after :meth:`new_project` / :meth:`open` (both replace those objects).
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from py_vui import __version__
from py_vui.codegen import base as codegen
from py_vui.codegen.base import GeneratedFile, GenOptions
from py_vui.codegen.merge_regions import sync_handlers_from_source
from py_vui.commands import Batch, History, SetHandler, SetProjectAttr
from py_vui.core import ProjectDocument, new_project
from py_vui.core.model import HandlerDef, Project
from py_vui.core.registry import requirements_for
from py_vui.core.serde import dump_json, load_json

PROJECT_FILE = "py_vui.json"
META_FILE = "session.meta.json"
AUTOSAVE_FILE = ".py_vui.autosave.json"
APP_DIR = "app"
ASSETS_DIR = "assets"
SESSION_FORMAT = "py_vui-session-v2"

#: pip distribution name (lower case) -> importable module
_IMPORT_NAMES = {
    "pillow": "PIL", "pyside6": "PySide6", "pyqt6": "PyQt6", "kivy": "kivy",
    "tkvideoplayer": "tkVideoPlayer", "pyyaml": "yaml", "opencv-python": "cv2",
    "python-dateutil": "dateutil", "beautifulsoup4": "bs4", "scikit-learn": "sklearn",
}
_REQ_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


@dataclass
class RunSpec:
    argv: list[str]
    cwd: Path
    env: dict[str, str]
    missing_requirements: list[str] = field(default_factory=list)


def slugify(name: str) -> str:
    s = re.sub(r"[^\w\- ]+", "", name.strip())
    s = re.sub(r"[\s_]+", "-", s).strip("-").lower()
    return s or "untitled"


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _friendly_load_error(path: Path, exc: Exception) -> ValueError:
    if isinstance(exc, json.JSONDecodeError):
        return ValueError(f"{path.name} is not valid JSON ({exc.msg} at line {exc.lineno}).")
    if isinstance(exc, ValidationError):
        first = exc.errors()[0]
        where = ".".join(str(p) for p in first.get("loc", ()))
        return ValueError(
            f"{path.name} is not a valid py_vui project: {first.get('msg')} ({where})."
        )
    text = str(exc)
    if "unknown type" in text:
        text += " (a plugin that provides this widget may need to be enabled)"
    return ValueError(f"{path.name} cannot be opened: {text}")


class ProjectService:
    doc: ProjectDocument
    history: History
    project_dir: Path | None
    #: True when the last open() upgraded an older (schema v1) file
    migrated: bool
    saved_revision: int

    def __init__(self) -> None:
        self._staging: tempfile.TemporaryDirectory[str] | None = None
        self.source_path: Path | None = None
        self.new_project("Untitled")

    # ------------------------------------------------------------------ state
    @property
    def dirty(self) -> bool:
        return self.history.revision != self.saved_revision

    @property
    def project(self) -> Project:
        return self.doc.project

    @property
    def path(self) -> Path | None:
        return self.project_dir / PROJECT_FILE if self.project_dir else None

    def _reset(self, project: Project, project_dir: Path | None) -> None:
        self.doc = ProjectDocument(project)
        self.history = History()
        self.project_dir = project_dir
        self.saved_revision = self.history.revision
        self.migrated = False
        self.source_path = None
        self._drop_staging()

    def _drop_staging(self) -> None:
        if self._staging is not None:
            self._staging.cleanup()
            self._staging = None

    def _staging_dir(self) -> Path:
        if self._staging is None:
            self._staging = tempfile.TemporaryDirectory(prefix="py_vui_")
        return Path(self._staging.name)

    @property
    def work_dir(self) -> Path:
        """Folder holding ``assets/`` and ``app/``: the project dir, or a temp dir if unsaved."""
        return self.project_dir if self.project_dir is not None else self._staging_dir()

    # -------------------------------------------------------------------- new
    def new_project(
        self, name: str = "Untitled", framework: str = "tkinter", template: str | None = None
    ) -> None:
        if template:
            from py_vui.services.templates import load_template

            project = load_template(template, framework)
            project.meta.name = name
        else:
            project = new_project(name, framework)
        project.meta.created_at = project.meta.updated_at = datetime.now(UTC).isoformat()
        self._reset(project, None)

    # ------------------------------------------------------------------- open
    def open(self, path: Path) -> None:
        path = Path(path).expanduser().resolve()
        if path.is_dir():
            file = path / PROJECT_FILE
            if not file.is_file():
                msg = f"No {PROJECT_FILE} found in {path}. Choose a py_vui project folder."
                raise ValueError(msg)
        elif path.is_file():
            file = path
        else:
            msg = f"{path} does not exist."
            raise ValueError(msg)
        try:
            raw = json.loads(file.read_bytes())
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            raise _friendly_load_error(file, exc) from exc
        if not isinstance(raw, dict) or "nodes" not in raw:
            msg = f"{file.name} is not a py_vui project (no 'nodes')."
            raise ValueError(msg)
        migrated = str(raw.get("schemaVersion", "1")) != "2"
        self._load_plugins(file.parent)
        try:
            project = load_json(file.read_bytes())
            ProjectDocument(project).validate()
        except (ValidationError, ValueError, KeyError, TypeError) as exc:
            raise _friendly_load_error(file, exc) from exc
        project_dir = file.parent if file.name == PROJECT_FILE else None
        self._reset(project, project_dir)
        self.migrated = migrated
        self.source_path = file
        if migrated or project_dir is None:
            # needs a save to persist the upgrade / to get a project folder
            self.saved_revision = self.history.revision - 1

    @staticmethod
    def _load_plugins(project_dir: Path) -> None:
        try:
            from py_vui.plugins.manager import PluginManager

            PluginManager().load_enabled(project_dir)
        except Exception:
            pass

    # ------------------------------------------------------------------- save
    def _write_meta(self, **extra: Any) -> None:
        assert self.project_dir is not None
        meta_path = self.project_dir / META_FILE
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if not isinstance(meta, dict):
                meta = {}
        except (OSError, ValueError):
            meta = {}
        meta.update(
            format=SESSION_FORMAT, project_name=self.project.meta.name,
            saved_at=datetime.now(UTC).isoformat(), py_vui_version=__version__,
            document=PROJECT_FILE, app_output_dir=APP_DIR, framework=self.project.framework,
        )
        meta.update(extra)
        _atomic_write(meta_path, (json.dumps(meta, indent=2) + "\n").encode("utf-8"))

    def save(self) -> Path:
        if self.project_dir is None:
            msg = "This project has no folder yet. Use Save As to choose where to put it."
            raise ValueError(msg)
        pd = self.project_dir
        pd.mkdir(parents=True, exist_ok=True)
        (pd / ASSETS_DIR).mkdir(exist_ok=True)
        target = pd / PROJECT_FILE
        if self.migrated and target.is_file():
            backup = pd / "py_vui.v1.json.bak"
            if not backup.exists():
                shutil.copy2(target, backup)
        self.project.meta.updated_at = datetime.now(UTC).isoformat()
        _atomic_write(target, dump_json(self.project).encode("utf-8"))
        self._write_meta()
        self._clear_autosave()
        self.saved_revision = self.history.revision
        self.migrated = False
        return target

    def save_as(self, parent_dir: Path, name: str | None = None) -> Path:
        """Create ``<parent>/<slug(name)>/`` (``-2``, ``-3`` … if taken) and save there."""
        parent = Path(parent_dir).expanduser().resolve()
        if name is not None and name.strip():
            self.project.meta.name = name.strip()
        slug = slugify(self.project.meta.name)
        dest = parent / slug
        n = 2
        while dest.exists() and not (self.project_dir and dest == self.project_dir.resolve()):
            dest = parent / f"{slug}-{n}"
            n += 1
        old_root, old_dir = self.work_dir, self.project_dir
        dest.mkdir(parents=True, exist_ok=True)
        if old_dir is None or old_dir.resolve() != dest.resolve():
            self._copy_assets(old_root, dest)
            custom = old_root / APP_DIR / "custom.py"
            if custom.is_file():
                (dest / APP_DIR).mkdir(exist_ok=True)
                shutil.copy2(custom, dest / APP_DIR / "custom.py")
        self.project_dir = dest
        self.source_path = None
        self._drop_staging()
        return self.save()

    def _copy_assets(self, src_root: Path, dest_root: Path) -> None:
        roots = [src_root]
        if self.source_path is not None:
            roots.append(self.source_path.parent)
        for rel in self._asset_paths():
            src = next((r / rel for r in roots if (r / rel).is_file()), None)
            if src is None:
                continue
            dst = dest_root / rel
            if dst.exists() and dst.stat().st_size == src.stat().st_size and (
                dst.stat().st_mtime >= src.stat().st_mtime
            ):
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.resolve() != dst.resolve():
                shutil.copy2(src, dst)

    # -------------------------------------------------------------- autosave
    @property
    def _autosave_file(self) -> Path | None:
        return self.project_dir / AUTOSAVE_FILE if self.project_dir else None

    def autosave(self) -> Path | None:
        f = self._autosave_file
        if f is None or not self.dirty:
            return None
        _atomic_write(f, dump_json(self.project).encode("utf-8"))
        return f

    def _clear_autosave(self) -> None:
        f = self._autosave_file
        if f is not None and f.is_file():
            f.unlink()

    def recovery_path(self) -> Path | None:
        f = self._autosave_file
        if f is None or not f.is_file():
            return None
        doc = self.path
        if doc is None or not doc.is_file() or f.stat().st_mtime > doc.stat().st_mtime:
            return f
        return None

    def recover(self) -> None:
        f = self.recovery_path()
        if f is None:
            msg = "There is no autosave to recover."
            raise ValueError(msg)
        try:
            project = load_json(f.read_bytes())
            ProjectDocument(project).validate()
        except (ValidationError, ValueError, KeyError) as exc:
            raise _friendly_load_error(f, exc) from exc
        self.doc.project = project
        self.history.clear()
        self.history.revision += 1  # now differs from saved_revision => dirty
        self.migrated = False

    # ------------------------------------------------------------ generation
    @property
    def app_dir(self) -> Path:
        return self.work_dir / APP_DIR

    def requirements(self) -> list[str]:
        p = self.project
        try:
            return codegen.get_adapter(p.framework).requirements(p)
        except KeyError:
            types = {n.type for n in p.nodes.values()}
            return sorted({*requirements_for(types, p.framework), *p.extra_requirements})

    def generated_files(self, options: GenOptions | None = None) -> list[GeneratedFile]:
        try:
            return codegen.generate(self.project, options or GenOptions())
        except KeyError as exc:
            raise ValueError(str(exc.args[0] if exc.args else exc)) from exc

    def _asset_paths(self) -> list[str]:
        refs = set(self.project.assets)
        for n in self.project.nodes.values():
            for v in (*n.props.values(), *n.style.values()):
                if isinstance(v, str) and v.startswith(ASSETS_DIR + "/"):
                    refs.add(v)
        return sorted(r for r in refs if not Path(r).is_absolute() and ".." not in Path(r).parts)

    def write_files(
        self, dest: Path, files: list[GeneratedFile], *, assets: bool = True
    ) -> list[Path]:
        """Write generated files into ``dest`` (never escaping it) and copy project assets."""
        dest = Path(dest)
        dest.mkdir(parents=True, exist_ok=True)
        root = dest.resolve()
        written: list[Path] = []
        for f in files:
            out = (root / f.path).resolve()
            if root != out and root not in out.parents:
                msg = f"generated file escapes the output folder: {f.path}"
                raise ValueError(msg)
            if not f.overwrite and out.exists():
                continue
            out.parent.mkdir(parents=True, exist_ok=True)
            if f.data is not None:
                out.write_bytes(f.data)
            else:
                out.write_text(f.content, encoding="utf-8", newline="\n")
            written.append(out)
        if assets:
            self._copy_assets(self.work_dir, root)
        return written

    def _external_handler_edits(self) -> bool:
        """True when app/handlers.py was changed outside the editor since we last wrote it."""
        hp = self.app_dir / "handlers.py"
        if not hp.is_file():
            return False
        text = hp.read_text(encoding="utf-8")
        meta = self._read_meta()
        known = meta.get("generated_handlers_sha256")
        if known:
            return known != _sha(text)
        return not self.dirty and self.path is not None and (
            self.path.is_file() and hp.stat().st_mtime > self.path.stat().st_mtime
        )

    def _read_meta(self) -> dict[str, Any]:
        if self.project_dir is None:
            return {}
        try:
            data = json.loads((self.project_dir / META_FILE).read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def generate(self, options: GenOptions | None = None) -> Path:
        """Write the app to ``<project>/app`` (a temp dir when unsaved); keep user code."""
        if self.project_dir is not None and self._external_handler_edits():
            self.sync_handlers_from_disk()
        opts = options or GenOptions()
        out = self.app_dir
        hp, cp = out / "handlers.py", out / "custom.py"
        for name, p in (("handlers.py", hp), ("custom.py", cp)):
            if p.is_file():
                opts.existing.setdefault(name, p.read_text(encoding="utf-8"))
        files = self.generated_files(opts)
        self.write_files(out, files)
        if self.project_dir is not None:
            sha = _sha(hp.read_text(encoding="utf-8")) if hp.is_file() else None
            self._write_meta(
                last_generate_at=datetime.now(UTC).isoformat(), last_export_dir=str(out),
                generated_handlers_sha256=sha,
            )
        return out

    def _export_files(
        self, layout: str, framework: str | None, include_requirements: bool
    ) -> list[GeneratedFile]:
        project = self.project
        if framework and framework != project.framework:
            project = project.model_copy(update={"framework": framework})
        try:
            files = codegen.generate(project, GenOptions(layout=layout))
        except KeyError as exc:
            raise ValueError(str(exc.args[0] if exc.args else exc)) from exc
        if not include_requirements:
            files = [f for f in files if f.path != "requirements.txt"]
        return files

    def export(
        self,
        dest: Path,
        fmt: str = "project",
        *,
        include_assets: bool = True,
        include_requirements: bool = True,
        framework: str | None = None,
    ) -> Path:
        """Export to ``dest``: a folder (``project``/``single``) or a ``.zip`` file.

        ``framework`` overrides the project's target framework for this export only (the
        document is not modified). ``include_assets`` / ``include_requirements`` leave the
        ``assets/`` folder / ``requirements.txt`` out of the result.
        """
        dest = Path(dest).expanduser()
        opts = {"framework": framework, "include_requirements": include_requirements}
        if fmt == "project":
            self.write_files(dest, self._export_files("project", **opts), assets=include_assets)
            return dest
        if fmt == "single":
            files = self._export_files("single", **opts)
            if dest.suffix == ".py":
                main = next((f for f in files if f.path == "main.py"), None)
                if main is None:
                    msg = "the code generator produced no main.py"
                    raise ValueError(msg)
                others = [f for f in files if f is not main]
                self.write_files(dest.parent, others, assets=include_assets)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(main.content, encoding="utf-8", newline="\n")
                return dest
            self.write_files(dest, files, assets=include_assets)
            return dest
        if fmt == "zip":
            if dest.is_dir():
                dest = dest / f"{slugify(self.project.meta.name)}.zip"
            elif dest.suffix != ".zip":
                dest = dest.with_name(dest.name + ".zip")
            dest.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="py_vui_zip_") as tmp:
                self.write_files(
                    Path(tmp), self._export_files("project", **opts), assets=include_assets
                )
                top = slugify(self.project.meta.name)
                with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
                    for f in sorted(Path(tmp).rglob("*")):
                        if f.is_file():
                            zf.write(f, f"{top}/{f.relative_to(tmp).as_posix()}")
            return dest
        msg = f"unknown export format {fmt!r} (use project, single or zip)"
        raise ValueError(msg)

    # ---------------------------------------------------------------- assets
    def add_asset(self, src: Path) -> str:
        src = Path(src).expanduser()
        if not src.is_file():
            msg = f"{src} is not a file."
            raise ValueError(msg)
        folder = self.work_dir / ASSETS_DIR
        folder.mkdir(parents=True, exist_ok=True)
        stem, suffix = re.sub(r"[^\w.\-]+", "_", src.stem), src.suffix
        dst, n = folder / f"{stem}{suffix}", 2
        data = src.read_bytes()
        while dst.exists() and dst.read_bytes() != data:
            dst = folder / f"{stem}_{n}{suffix}"
            n += 1
        if not dst.exists():
            dst.write_bytes(data)
        rel = f"{ASSETS_DIR}/{dst.name}"
        if rel not in self.project.assets:
            self._set_assets([*self.project.assets, rel], "Add asset")
        return rel

    def _set_assets(self, assets: list[str], label: str) -> None:
        cmd = SetProjectAttr("assets", assets, label)
        cmd.merge_key = None  # one undo step per asset operation
        self.history.push(self.doc, cmd)

    def remove_asset(self, rel: str) -> None:
        """Drop an asset from the project. The file stays on disk so undo keeps working."""
        if rel in self.project.assets:
            self._set_assets([a for a in self.project.assets if a != rel], "Remove asset")

    # --------------------------------------------------------------- handlers
    def sync_handlers_from_disk(self) -> int:
        """Pull edited handler bodies / module code from ``app/handlers.py`` (undoable)."""
        hp = self.app_dir / "handlers.py"
        if not hp.is_file():
            return 0
        scratch = self.project.model_copy(deep=True)
        changed = sync_handlers_from_source(scratch, hp.read_text(encoding="utf-8"))
        if not changed:
            return 0
        cmds: list[Any] = [
            SetHandler(name, HandlerDef(name=name, body=h.body), "Sync handler")
            for name, h in scratch.handlers.items()
            if self.project.handlers[name].body != h.body
        ]
        if scratch.custom_code != self.project.custom_code:
            cmds.append(SetProjectAttr("custom_code", scratch.custom_code, "Sync module code"))
        self.history.push(self.doc, Batch(cmds, "Sync code from disk"))
        return changed

    # -------------------------------------------------------------------- run
    def _probe_missing(self, python: Path, reqs: list[str]) -> list[str]:
        mods: dict[str, str] = {}
        for r in reqs:
            m = _REQ_NAME.match(r)
            if m:
                name = m.group(1)
                mods[r] = _IMPORT_NAMES.get(name.lower(), name.replace("-", "_"))
        if self.project.framework == "tkinter" or self.project.framework == "customtkinter":
            mods["python3-tk (tkinter)"] = "tkinter"
        if not mods:
            return []
        if Path(python).resolve() == Path(sys.executable).resolve():
            return [r for r, mod in mods.items() if not self._importable(mod)]
        code = (
            "import importlib.util, json, sys\n"
            "mods = json.loads(sys.argv[1])\n"
            "print(json.dumps([r for r, m in mods.items()\n"
            "                  if importlib.util.find_spec(m) is None]))\n"
        )
        try:
            out = subprocess.run(
                [str(python), "-c", code, json.dumps(mods)],
                capture_output=True, text=True, timeout=30, check=True,
            ).stdout
            return list(json.loads(out.strip().splitlines()[-1]))
        except (OSError, subprocess.SubprocessError, ValueError, IndexError):
            return list(mods)

    @staticmethod
    def _importable(mod: str) -> bool:
        try:
            return importlib.util.find_spec(mod) is not None
        except (ImportError, ValueError):
            return False

    def run_spec(self, python: Path | None = None) -> RunSpec:
        py = Path(python) if python else Path(sys.executable)
        env = dict(os.environ)
        env["PYTHONUNBUFFERED"] = "1"
        env.pop("PYTHONHOME", None)
        return RunSpec(
            argv=[str(py), "main.py"], cwd=self.app_dir, env=env,
            missing_requirements=self._probe_missing(py, self.requirements()),
        )

    def build_executable_command(self, onefile: bool = True) -> list[str]:
        cmd = [
            sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
            "--name", slugify(self.project.meta.name),
            "--onefile" if onefile else "--onedir",
        ]
        if (self.app_dir / ASSETS_DIR).is_dir() or self.project.assets:
            cmd += ["--add-data", f"{ASSETS_DIR}{os.pathsep}{ASSETS_DIR}"]
        return [*cmd, "main.py"]
