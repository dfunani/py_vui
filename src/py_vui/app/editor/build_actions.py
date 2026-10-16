"""Build / Project menu behaviour for :class:`MainWindow`."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from py_vui.app.editor.main_window import MainWindow


class BuildMixin:
    # ----------------------------------------------------------------- generate / run
    def do_generate(self: MainWindow) -> None:
        from py_vui.codegen.base import GenOptions

        try:
            out = self.service.generate(GenOptions())
        except Exception as exc:
            self.console.append(f"Code generation failed: {exc}\n", "err")
            self.console_dock.show()
            self.console_dock.raise_()
            self.flash("Generation failed")
            return
        self.console.append(f"Generated app in {out}\n", "info")
        self.flash(f"Generated app in {out}")
        self.code_panel.refresh()

    def show_console(self: MainWindow) -> None:
        self.console_dock.show()
        self.console_dock.raise_()

    def do_run(self: MainWindow) -> None:
        self.show_console()
        self.controller.run()

    def do_stop(self: MainWindow) -> None:
        self.controller.stop()

    def do_restart(self: MainWindow) -> None:
        self.show_console()
        self.controller.restart()

    def do_live_preview(self: MainWindow, on: bool) -> None:
        self.controller.set_live(on)
        if on:
            self.show_console()
        self.flash("Live preview on" if on else "Live preview off")

    def do_export(self: MainWindow) -> None:
        from py_vui.app.editor.dialogs import ExportDialog

        ExportDialog(self.service, self).exec()

    def do_build_exe(self: MainWindow) -> None:
        choice = self.prompts.choose(
            "Build executable",
            "Build a standalone executable with PyInstaller.\n"
            "PyInstaller must be installed in this Python environment.",
            ["One file", "One folder"],
        )
        if choice is None:
            return
        self.show_console()
        self.controller.build_executable(onefile=choice == "One file")

    def do_requirements(self: MainWindow) -> None:
        from py_vui.app.editor.dialogs import RequirementsDialog

        RequirementsDialog(self.doc, self.history, self).exec()
        self.after_edit()

    def do_sync_handlers(self: MainWindow) -> None:
        try:
            n = self.service.sync_handlers_from_disk()
        except Exception as exc:
            self.prompts.error("Cannot sync handlers", str(exc))
            return
        self.canvas.refresh()
        self.after_edit()
        self.flash(f"Synced {n} handler(s) from disk" if n else "Handlers are already in sync")

    # ---------------------------------------------------------------------- project
    def do_framework(self: MainWindow) -> None:
        from py_vui.app.editor.dialogs import FrameworkDialog

        FrameworkDialog(self.doc, self.history, self).exec()
        self.canvas.refresh()
        self.after_edit()

    def on_framework_combo(self: MainWindow, _index: int = 0) -> None:
        """The combo preselects its choice in the dialog; the dialog confirms / applies it."""
        from py_vui.app.editor.dialogs import FrameworkDialog

        chosen = self.fw_combo.currentText()
        dlg = FrameworkDialog(self.doc, self.history, self)
        if chosen != self.doc.project.framework and hasattr(dlg, "select"):
            dlg.select(chosen)
        dlg.exec()
        self.canvas.refresh()
        self.after_edit()
        self.fw_combo.setCurrentText(self.doc.project.framework)

    def do_theme(self: MainWindow) -> None:
        from py_vui.app.editor.dialogs import ThemeEditorDialog

        ThemeEditorDialog(self.doc, self.history, self).exec()
        self.canvas.refresh()
        self.after_edit()

    def do_assets(self: MainWindow) -> None:
        from py_vui.app.editor.dialogs import AssetManagerDialog

        AssetManagerDialog(self.service, self).exec()
        self.canvas.set_base_dir(self.service.work_dir)
        self.canvas.scene_.sync()
        self.canvas.refresh()
        self.after_edit()

    def do_menus(self: MainWindow) -> None:
        from py_vui.app.editor.dialogs import MenuDesignerDialog

        win = self.canvas.window_id or self.doc.project.root_id
        if self.doc.get_node(win).type != "window":
            win = self.doc.project.root_id
        MenuDesignerDialog(self.doc, self.history, win, self).exec()
        self.canvas.refresh()
        self.after_edit()

    def do_plugins(self: MainWindow) -> None:
        from py_vui.app.editor.dialogs import PluginManagerDialog

        PluginManagerDialog(self, self.service.project_dir).exec()
        self.toolbox.refresh()
        self.canvas.refresh()
        self.after_edit()

    def do_add_dialog(self: MainWindow) -> None:
        self.canvas.add_dialog()

    # ------------------------------------------------------------------------ help
    def do_shortcuts(self: MainWindow) -> None:
        from py_vui.app.editor.dialogs import ShortcutsDialog

        ShortcutsDialog(self).exec()

    def do_about(self: MainWindow) -> None:
        from py_vui.app.editor.dialogs import AboutDialog

        AboutDialog(self).exec()
