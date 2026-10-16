"""File-menu behaviour: new / open / save / recent / autosave / recovery / drops."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtGui import QAction

from py_vui.app.editor.dialogs.common import get_setting
from py_vui.app.editor.mime import IMAGE_SUFFIXES

if TYPE_CHECKING:
    from py_vui.app.editor.main_window import MainWindow


class ProjectMixin:
    # ------------------------------------------------------------------ guards
    def maybe_save(self: MainWindow) -> bool:
        """Return True when it is safe to discard / replace the current document."""
        if not self.service.dirty:
            return True
        answer = self.prompts.ask_unsaved(self.doc.project.meta.name)
        if answer == "cancel":
            return False
        if answer == "save":
            return self.do_save()
        return True

    # ---------------------------------------------------------------- new / open
    def do_new(self: MainWindow) -> None:
        from py_vui.app.editor.dialogs import NewProjectDialog

        if not self.maybe_save():
            return
        dlg = NewProjectDialog(self)
        if dlg.exec():
            self.start_project(dlg.name, dlg.framework, dlg.template_id)

    def do_new_template(self: MainWindow) -> None:
        from py_vui.app.editor.dialogs import NewProjectDialog, TemplateGalleryDialog

        if not self.maybe_save():
            return
        gallery = TemplateGalleryDialog(self)
        if not gallery.exec():
            return
        dlg = NewProjectDialog(self)
        dlg.set_template(gallery.template_id)
        if dlg.exec():
            self.start_project(dlg.name, dlg.framework, dlg.template_id)

    def start_project(self: MainWindow, name: str, framework: str, template: str | None) -> None:
        try:
            self.service.new_project(name, framework, template)
        except Exception as exc:
            self.prompts.error("Cannot create project", str(exc))
            return
        self.after_load()

    def do_open(self: MainWindow) -> None:
        if not self.maybe_save():
            return
        folder = self.prompts.choose_dir("Open project folder")
        if folder is not None:
            self.open_path(folder, checked=True)

    def do_import_json(self: MainWindow) -> None:
        if not self.maybe_save():
            return
        f = self.prompts.choose_open_file("Import project JSON", "Project (*.json);;All files (*)")
        if f is not None:
            self.open_path(f, checked=True)

    def open_path(self: MainWindow, path: Path | str, checked: bool = False) -> bool:
        if not checked and not self.maybe_save():
            return False
        try:
            self.service.open(Path(path))
        except Exception as exc:
            self.prompts.error("Cannot open project", str(exc))
            self.recent.remove(Path(path))
            return False
        self.after_load()
        if self.service.migrated:
            self.flash(
                "Opened an older project file and upgraded it to the current format "
                "(a .bak copy is written on save)"
            )
        return True

    def after_load(self: MainWindow) -> None:
        """Rebind every panel to the (new) document."""
        self.controller.reset()
        self.console.clear()
        self.bind_document()
        if self.service.project_dir is not None:
            self.recent.add(self.service.project_dir)
            self.offer_recovery()
        self.settings.setValue("last_project", str(self.service.project_dir or ""))

    def fill_recent_menu(self: MainWindow) -> None:
        menu = self.recent_menu
        menu.clear()
        items = self.recent.list()
        for p in items:
            act = QAction(str(p), menu)
            act.triggered.connect(lambda _=False, pp=p: self.open_path(pp))
            menu.addAction(act)
        if not items:
            empty = QAction("(no recent projects)", menu)
            empty.setEnabled(False)
            menu.addAction(empty)
        else:
            menu.addSeparator()
            clear = QAction("Clear list", menu)
            clear.triggered.connect(self.recent.clear)
            menu.addAction(clear)

    # --------------------------------------------------------------------- save
    def do_save(self: MainWindow) -> bool:
        if self.service.project_dir is None:
            return self.do_save_as()
        try:
            self.service.save()
        except Exception as exc:
            self.prompts.error("Cannot save", str(exc))
            return False
        self.after_save()
        return True

    def do_save_as(self: MainWindow) -> bool:
        parent = self.prompts.choose_dir("Choose a folder to create the project in")
        if parent is None:
            return False
        name = self.prompts.prompt_text("Save project", "Project name:", self.doc.project.meta.name)
        if name is None:
            return False
        try:
            self.service.save_as(parent, name)
        except Exception as exc:
            self.prompts.error("Cannot save", str(exc))
            return False
        self.after_save()
        return True

    def after_save(self: MainWindow) -> None:
        if self.service.project_dir is not None:
            self.recent.add(self.service.project_dir)
        self.canvas.set_base_dir(self.service.work_dir)
        self._wire_inspector_assets()
        self.update_chrome()
        self.flash(f"Saved to {self.service.project_dir}")

    def do_quit(self: MainWindow) -> None:
        self.close()

    # --------------------------------------------------- autosave / recovery
    def autosave_tick(self: MainWindow) -> None:
        if self.service.dirty:
            try:
                self.service.autosave()
            except Exception as exc:  # pragma: no cover - disk problems
                self.flash(f"Autosave failed: {exc}")

    def restart_autosave(self: MainWindow) -> None:
        secs = int(get_setting("autosave_seconds", 60) or 0)
        self.autosave_timer.stop()
        if secs > 0:
            self.autosave_timer.start(secs * 1000)

    def offer_recovery(self: MainWindow) -> bool:
        if not self.check_recovery:
            return False
        try:
            path = self.service.recovery_path()
        except Exception:
            return False
        if path is None:
            return False
        if self.prompts.confirm(
            "Recover unsaved changes?",
            "An autosave newer than the saved project was found.\nRestore it?",
            yes="Recover",
        ):
            try:
                self.service.recover()
            except Exception as exc:
                self.prompts.error("Cannot recover", str(exc))
                return False
            self.bind_document()
            self.flash("Recovered unsaved changes")
            return True
        return False

    # --------------------------------------------------------------------- drops
    def on_files_dropped(self: MainWindow, paths: list[str], scene_pt=None) -> None:
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QImageReader

        offset = 0.0
        for raw in paths:
            p = Path(raw)
            suffix = p.suffix.lower()
            if suffix == ".json":
                self.open_path(p)
                return
            if suffix not in IMAGE_SUFFIXES:
                continue
            try:
                rel = self.service.add_asset(p)
            except Exception as exc:
                self.flash(f"Cannot import {p.name}: {exc}")
                continue
            natural = QImageReader(str(p)).size()
            size = None
            if natural.isValid() and natural.width() > 0 and natural.height() > 0:
                k = min(1.0, 260 / natural.width(), 260 / natural.height())
                size = (round(natural.width() * k), round(natural.height() * k))
            pt = (
                QPointF(scene_pt.x() + offset, scene_pt.y() + offset)
                if scene_pt is not None
                else None
            )
            self.canvas.add_widget("image", pt, props={"source": rel}, size=size)
            offset += 20
