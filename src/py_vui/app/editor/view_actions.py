"""View menu, zoom / device combos and preferences for :class:`MainWindow`."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QApplication

from py_vui.app.editor import editor_theme
from py_vui.app.editor.actions import refresh_icons
from py_vui.app.editor.dialogs.common import get_setting, set_setting
from py_vui.app.editor.icons import clear_icon_cache
from py_vui.app.editor.menus import DEVICE_PRESETS

if TYPE_CHECKING:
    from py_vui.app.editor.main_window import MainWindow


class ViewMixin:
    # ------------------------------------------------------------------- zoom
    def do_zoom_in(self: MainWindow) -> None:
        self.canvas.zoom_in()

    def do_zoom_out(self: MainWindow) -> None:
        self.canvas.zoom_out()

    def do_zoom_fit(self: MainWindow) -> None:
        self.canvas.fit()

    def do_zoom_100(self: MainWindow) -> None:
        self.canvas.actual_size()

    def apply_zoom_text(self: MainWindow, text: str) -> None:
        m = re.search(r"(\d+(?:\.\d+)?)", text)
        if m:
            self.canvas.set_zoom(float(m.group(1)) / 100)

    def on_zoom_changed(self: MainWindow, zoom: float) -> None:
        self.zoom_combo.setEditText(f"{round(zoom * 100)}%")
        self.status.set_zoom(zoom)

    # ----------------------------------------------------------------- toggles
    def do_toggle_grid(self: MainWindow, on: bool) -> None:
        self.canvas.set_option("show_grid", on)

    def do_toggle_snap(self: MainWindow, on: bool) -> None:
        self.canvas.set_option("snap_to_grid", on)
        set_setting("snap_enabled", on)

    def do_toggle_guides(self: MainWindow, on: bool) -> None:
        self.canvas.set_option("smart_guides", on)
        self.canvas.set_option("show_guides", on)

    def do_toggle_rulers(self: MainWindow, on: bool) -> None:
        self.host.set_rulers_visible(on)

    # ------------------------------------------------------------------ themes
    def do_theme_dark(self: MainWindow, on: bool) -> None:
        if on:
            self.set_editor_theme("dark")

    def do_theme_light(self: MainWindow, on: bool) -> None:
        if on:
            self.set_editor_theme("light")

    def do_theme_auto(self: MainWindow, on: bool) -> None:
        if on:
            self.set_editor_theme("system")

    def set_editor_theme(self: MainWindow, choice: str, persist: bool = True) -> None:
        """``choice``: dark | light | system."""
        app = QApplication.instance()
        editor_theme.apply_theme(app, choice)  # type: ignore[arg-type]
        clear_icon_cache()
        refresh_icons(self.act)
        self.current_theme_choice = choice
        for key, val in (
            ("theme_dark", "dark"),
            ("theme_light", "light"),
            ("theme_auto", "system"),
        ):
            act = self.act[key]
            act.blockSignals(True)
            act.setChecked(val == choice)
            act.blockSignals(False)
        if persist:
            set_setting("editor_theme", choice)
        if getattr(self, "toolbox", None) is not None:
            self.toolbox.refresh()
            self.tree.bind(self.doc, self.history)
            self.tree.set_selection(self.canvas.selection)
            self.canvas.viewport().update()
            self.host.top_ruler.update()
            self.host.left_ruler.update()

    # ----------------------------------------------------------- device presets
    def on_device_combo(self: MainWindow, index: int) -> None:
        _name, size = DEVICE_PRESETS[index]
        win = self.canvas.window_id
        if win is None:
            return
        node = self.doc.get_node(win)
        cur = (int(node.props.get("width", 640)), int(node.props.get("height", 480)))
        if size is None:
            text = self.prompts.prompt_text(
                "Window size", "Width × height (e.g. 800x600):", f"{cur[0]}x{cur[1]}"
            )
            m = re.match(r"^\s*(\d+)\s*[x×,]\s*(\d+)\s*$", text or "")
            if not m:
                self.sync_device_combo()
                return
            size = (int(m.group(1)), int(m.group(2)))
        self.set_window_size(size)

    def set_window_size(self: MainWindow, size: tuple[int, int]) -> None:
        size = (max(100, size[0]), max(100, size[1]))
        self.canvas.apply_window_size(size)
        self.sync_device_combo()

    def sync_device_combo(self: MainWindow) -> None:
        win = self.canvas.window_id
        if win is None or win not in self.doc.project.nodes:
            return
        node = self.doc.get_node(win)
        cur = (int(node.props.get("width", 640)), int(node.props.get("height", 480)))
        idx = 0
        for i, (_n, size) in enumerate(DEVICE_PRESETS):
            if size == cur:
                idx = i
                break
        else:
            idx = len(DEVICE_PRESETS) - 1
        self.device_combo.setCurrentIndex(idx)
        if idx == len(DEVICE_PRESETS) - 1:
            self.device_combo.setItemText(idx, f"Custom  {cur[0]} × {cur[1]}")
        else:
            self.device_combo.setItemText(len(DEVICE_PRESETS) - 1, "Custom…")

    # ------------------------------------------------------------- preferences
    def do_preferences(self: MainWindow) -> None:
        from py_vui.app.editor.dialogs import PreferencesDialog

        if PreferencesDialog(self).exec():
            self.load_preferences()

    def load_preferences(self: MainWindow) -> None:
        self.canvas.grid_size = int(get_setting("grid_size", 8) or 8)
        snap = bool(get_setting("snap_enabled", True))
        self.act["toggle_snap"].setChecked(snap)
        self.canvas.set_option("snap_to_grid", snap)
        self.set_editor_theme(str(get_setting("editor_theme", "system")), persist=False)
        self.restart_autosave()
        self.canvas.viewport().update()
