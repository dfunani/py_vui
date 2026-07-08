from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from py_vui import __version__
from py_vui.codegen import emit_pyside_phase1
from py_vui.model.document import ProjectDocument
from py_vui.model.project import py_vuiProject
from py_vui.model.serde import dump_json, load_json_bytes

from py_vui.app.editor.session_paths import (
    APP_SUBDIR,
    AUTOSAVE_DOCUMENT,
    SESSION_DOCUMENT,
    SESSION_META,
    export_project_dir,
    find_session_file,
    resolve_project_dir,
    write_session_meta,
)


@dataclass
class ProjectService:
    doc: ProjectDocument
    project_dir: Path | None = None
    dirty: bool = False

    @property
    def path(self) -> Path | None:
        if self.project_dir is None:
            return None
        return self.project_dir / SESSION_DOCUMENT

    @classmethod
    def new(cls, name: str = "untitled") -> ProjectService:
        from py_vui.app.editor.factory import new_project

        project = new_project(name)
        return cls(ProjectDocument(project), project_dir=None, dirty=True)

    @classmethod
    def open(cls, location: Path) -> ProjectService:
        location = location.resolve()
        if location.is_dir():
            session_file = find_session_file(location)
            if session_file is None:
                msg = f"no {SESSION_DOCUMENT} in {location}"
                raise FileNotFoundError(msg)
            project_dir = location
        else:
            session_file = location
            project_dir = location.parent

        project = load_json_bytes(session_file.read_bytes())
        return cls(ProjectDocument(project), project_dir=project_dir, dirty=False)

    def mark_dirty(self) -> None:
        self.dirty = True
        now = datetime.now(timezone.utc).isoformat()
        self.doc.project.meta.updated_at = now

    def save(self, *, parent_dir: Path | None = None) -> Path:
        if self.project_dir is None:
            if parent_dir is None:
                raise ValueError("choose a folder with Save Project As first")
            self.project_dir = resolve_project_dir(
                parent_dir,
                self.doc.project.meta.name,
                current=self.project_dir,
            )

        self.project_dir.mkdir(parents=True, exist_ok=True)
        document_path = self.project_dir / SESSION_DOCUMENT
        document_path.write_text(dump_json(self.doc.project), encoding="utf-8")
        write_session_meta(
            self.project_dir,
            project_name=self.doc.project.meta.name,
            app_version=__version__,
        )
        self.dirty = False
        self.clear_autosave()
        return document_path

    def save_to_new_folder(self, parent_dir: Path, *, project_name: str | None = None) -> Path:
        if project_name is not None:
            self.doc.project.meta.name = project_name.strip() or "untitled"
        self.project_dir = resolve_project_dir(
            parent_dir,
            self.doc.project.meta.name,
            current=None,
        )
        return self.save()

    def project_name(self) -> str:
        return self.doc.project.meta.name

    def autosave_path(self) -> Path | None:
        if self.project_dir is None:
            return None
        return self.project_dir / AUTOSAVE_DOCUMENT

    def write_autosave(self) -> Path | None:
        path = self.autosave_path()
        if path is None or not self.dirty:
            return None
        path.write_text(dump_json(self.doc.project), encoding="utf-8")
        return path

    def clear_autosave(self) -> None:
        path = self.autosave_path()
        if path is not None and path.is_file():
            path.unlink()

    def autosave_recovery_path(self) -> Path | None:
        path = self.autosave_path()
        doc = self.path
        if path is None or not path.is_file():
            return None
        if doc is None or not doc.is_file():
            return path
        if path.stat().st_mtime > doc.stat().st_mtime:
            return path
        return None

    def app_dir(self) -> Path:
        return self.project_dir / APP_SUBDIR if self.project_dir else Path.cwd() / APP_SUBDIR

    def write_generated(self) -> list[Path]:
        if self.project_dir is None:
            raise ValueError("save the project first; app output lives in <project>/app/")
        return self.export_code_to(self.app_dir())

    def export_code_to_parent(self, parent_dir: Path) -> tuple[Path, list[Path]]:
        """Export into `<parent_dir>/<project-name>/`."""
        dest = export_project_dir(parent_dir, self.doc.project.meta.name)
        dest.mkdir(parents=True, exist_ok=True)
        written = self._write_bundle(dest)
        return dest, written

    def export_code_to(self, target_dir: Path) -> list[Path]:
        root = target_dir.resolve()
        root.mkdir(parents=True, exist_ok=True)
        return self._write_bundle(root)

    def _write_bundle(self, root: Path) -> list[Path]:
        written: list[Path] = []
        handlers_path = None
        if self.project_dir is not None:
            candidate = self.project_dir / APP_SUBDIR / "handlers.py"
            if candidate.is_file():
                handlers_path = candidate
        for wf in emit_pyside_phase1(self.doc.project, handlers_path=handlers_path):
            out = root / wf.path
            out.write_text(wf.content, encoding="utf-8")
            written.append(out)
        if self.project_dir is not None:
            meta_path = self.project_dir / SESSION_META
            if meta_path.is_file():
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                meta["last_export_at"] = datetime.now(timezone.utc).isoformat()
                meta["last_export_dir"] = str(root)
                meta_path.write_text(
                    json.dumps(meta, indent=2) + "\n", encoding="utf-8"
                )
        return written
