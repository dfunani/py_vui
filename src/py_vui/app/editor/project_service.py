from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from py_vui.codegen import emit_pyside_phase1
from py_vui.model.document import ProjectDocument
from py_vui.model.project import py_vuiProject
from py_vui.model.serde import dump_json, load_json_bytes


@dataclass
class ProjectService:
    doc: ProjectDocument
    path: Path | None = None
    dirty: bool = False

    @classmethod
    def new(cls, name: str = "untitled") -> ProjectService:
        from py_vui.app.editor.factory import new_project

        project = new_project(name)
        return cls(ProjectDocument(project), path=None, dirty=True)

    @classmethod
    def open(cls, path: Path) -> ProjectService:
        project = load_json_bytes(path.read_bytes())
        return cls(ProjectDocument(project), path=path, dirty=False)

    def mark_dirty(self) -> None:
        self.dirty = True
        now = datetime.now(timezone.utc).isoformat()
        self.doc.project.meta.updated_at = now

    def save(self, path: Path | None = None) -> Path:
        target = path or self.path
        if target is None:
            raise ValueError("no save path")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(dump_json(self.doc.project), encoding="utf-8")
        self.path = target
        self.dirty = False
        return target

    def write_generated(self, project_dir: Path | None = None) -> Path:
        root = project_dir or (self.path.parent if self.path else Path.cwd())
        gen = root / "generated"
        gen.mkdir(parents=True, exist_ok=True)
        for wf in emit_pyside_phase1(self.doc.project):
            out = root / wf.path
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(wf.content, encoding="utf-8")
        return gen
