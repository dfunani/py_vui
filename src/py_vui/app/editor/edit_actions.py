"""Edit-menu behaviour for :class:`MainWindow` (clipboard, align, order, grouping…)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from py_vui.app.editor import edit_ops
from py_vui.app.editor.canvas_drop import container_mode
from py_vui.commands import (
    Batch,
    Command,
    RemoveSubtree,
    SetAttr,
    SetField,
    align_nodes,
    distribute_nodes,
    match_size,
)

if TYPE_CHECKING:
    from py_vui.app.editor.main_window import MainWindow


class EditMixin:
    # ---------------------------------------------------------------- plumbing
    def push(
        self: MainWindow, cmd: Command, select: list[str] | None = None, source: str | None = None
    ) -> bool:
        """Push a command, refresh everything and optionally select ``select``."""
        try:
            self.history.push(self.doc, cmd)
        except ValueError as exc:
            self.flash(f"Cannot do that: {exc}")
            return False
        self.canvas.refresh()
        if select is not None:
            self.select(select)
        self.after_edit(source)
        return True

    def do_undo(self: MainWindow) -> None:
        self.canvas.cancel_inline_edit()
        if self.history.undo(self.doc):
            self.canvas.refresh()
            self.after_edit()

    def do_redo(self: MainWindow) -> None:
        if self.history.redo(self.doc):
            self.canvas.refresh()
            self.after_edit()

    # --------------------------------------------------------------- clipboard
    def do_copy(self: MainWindow) -> None:
        if edit_ops.copy_to_clipboard(self.doc, self.canvas.selection):
            self.flash("Copied")

    def do_cut(self: MainWindow) -> None:
        if edit_ops.copy_to_clipboard(self.doc, self.canvas.selection):
            self.do_delete()

    def do_paste(self: MainWindow) -> None:
        target = edit_ops.paste_target(
            self.doc, self.canvas.selection, self.canvas.window_id or self.doc.project.root_id
        )
        res = edit_ops.paste_command(self.doc, target)
        if res is None:
            self.flash("Nothing to paste")
            return
        self.push(res[0], select=res[1])

    def do_duplicate(self: MainWindow) -> None:
        res = edit_ops.duplicate_command(self.doc, self.canvas.selection)
        if res is not None:
            self.push(res[0], select=res[1])

    def do_delete(self: MainWindow) -> None:
        cmd = edit_ops.delete_command(self.doc, self.canvas.selection)
        if cmd is None:
            if self.canvas.selection and any(
                self.doc.get_node(i).locked for i in self.canvas.selection
            ):
                self.flash("Unlock the widget before deleting it")
            return
        parent = self.doc.get_node(self.canvas.selection[0]).parent_id
        self.push(cmd, select=[parent] if parent else [])

    def do_select_all(self: MainWindow) -> None:
        self.canvas.select_all()

    def do_rename(self: MainWindow) -> None:
        if len(self.canvas.selection) == 1:
            self.tree_dock.raise_()
            self.tree.start_rename(self.canvas.selection[0])

    # ---------------------------------------------------------------- arrange
    def _arrangeable(self: MainWindow, need: int = 1) -> list[str]:
        ids = self.canvas.movable_ids()
        if len(ids) < need:
            return []
        parents = {self.doc.get_node(i).parent_id for i in ids}
        if len(parents) != 1:
            self.flash("Select widgets that share the same container")
            return []
        parent = self.doc.get_node(next(iter(parents)))  # type: ignore[arg-type]
        if container_mode(parent) != "absolute":
            self.flash(
                "Align / distribute applies to absolute layouts; this container is "
                f"{container_mode(parent)}"
            )
            return []
        return ids

    def _align(self: MainWindow, mode: str) -> None:
        ids = self._arrangeable()
        if ids:
            self.push(align_nodes(self.doc, ids, mode))  # type: ignore[arg-type]

    def do_align_left(self: MainWindow) -> None:
        self._align("left")

    def do_align_center(self: MainWindow) -> None:
        self._align("center")

    def do_align_right(self: MainWindow) -> None:
        self._align("right")

    def do_align_top(self: MainWindow) -> None:
        self._align("top")

    def do_align_middle(self: MainWindow) -> None:
        self._align("middle")

    def do_align_bottom(self: MainWindow) -> None:
        self._align("bottom")

    def do_distribute_h(self: MainWindow) -> None:
        ids = self._arrangeable(3)
        if ids:
            self.push(distribute_nodes(self.doc, ids, "horizontal"))

    def do_distribute_v(self: MainWindow) -> None:
        ids = self._arrangeable(3)
        if ids:
            self.push(distribute_nodes(self.doc, ids, "vertical"))

    def _same(self: MainWindow, width: bool, height: bool) -> None:
        ids = self._arrangeable(2)
        if not ids:
            return
        order = [i for i in self.canvas.selection if i in ids]
        self.push(match_size(self.doc, order, width=width, height=height))

    def do_same_width(self: MainWindow) -> None:
        self._same(True, False)

    def do_same_height(self: MainWindow) -> None:
        self._same(False, True)

    def do_same_size(self: MainWindow) -> None:
        self._same(True, True)

    def _z(self: MainWindow, mode: str) -> None:
        cmd = edit_ops.z_order_command(self.doc, self.canvas.selection, mode)
        if cmd is not None:
            self.push(cmd)

    def do_z_front(self: MainWindow) -> None:
        self._z("front")

    def do_z_back(self: MainWindow) -> None:
        self._z("back")

    def do_z_forward(self: MainWindow) -> None:
        self._z("forward")

    def do_z_backward(self: MainWindow) -> None:
        self._z("backward")

    # --------------------------------------------------------------- grouping
    def wrap_selection(self: MainWindow, container_type: str = "frame") -> None:
        res = edit_ops.group_command(self.doc, self.canvas.selection, container_type)
        if res is None:
            self.flash("Select widgets that share the same container to wrap them")
            return
        self.push(res[0], select=[res[1]])

    def do_group(self: MainWindow) -> None:
        self.wrap_selection("frame")

    def do_ungroup(self: MainWindow) -> None:
        if len(self.canvas.selection) != 1:
            return
        res = edit_ops.ungroup_command(self.doc, self.canvas.selection[0])
        if res is None:
            self.flash("Select a container that has children to ungroup it")
            return
        self.push(res[0], select=res[1])

    def toggle_selection_flag(self: MainWindow, flag: str) -> None:
        ids = edit_ops.top_level_ids(self.doc, self.canvas.selection)
        if not ids:
            return
        new = not getattr(self.doc.get_node(ids[0]), flag)
        label = {"locked": "Lock" if new else "Unlock", "visible": "Show" if new else "Hide"}[flag]
        self.push(Batch([SetAttr(i, flag, new, label=label) for i in ids], label=label))

    # ------------------------------------------------------------------ tabs
    def add_tab(self: MainWindow, node_id: str) -> None:
        node = self.doc.get_node(node_id)
        tabs = list(node.props.get("tabs") or [])
        tabs.append(f"Tab {len(tabs) + 1}")
        self.push(
            Batch(
                [
                    SetField(node_id, "props", "tabs", tabs, label="Add tab", merge_key="tabs:add"),
                    SetField(
                        node_id,
                        "props",
                        "current",
                        len(tabs) - 1,
                        label="Add tab",
                        merge_key="tabs:add2",
                    ),
                ],
                label="Add tab",
            )
        )

    def remove_tab(self: MainWindow, node_id: str) -> None:
        node = self.doc.get_node(node_id)
        tabs = list(node.props.get("tabs") or [])
        if len(tabs) <= 1:
            self.flash("A tab view needs at least one tab")
            return
        cur = max(0, min(int(node.props.get("current", 0)), len(tabs) - 1))
        cmds: list[Command] = []
        for k in self.doc.children(node_id):
            if k.page == cur:
                cmds.append(RemoveSubtree(k.id, label="Remove tab"))
            elif k.page > cur:
                cmds.append(SetAttr(k.id, "page", k.page - 1, label="Remove tab"))
        del tabs[cur]
        cmds.append(
            SetField(node_id, "props", "tabs", tabs, label="Remove tab", merge_key="tabs:rm")
        )
        cmds.append(
            SetField(
                node_id,
                "props",
                "current",
                min(cur, len(tabs) - 1),
                label="Remove tab",
                merge_key="tabs:rm2",
            )
        )
        self.push(Batch(cmds, label="Remove tab"), select=[node_id])

    def open_handler(self: MainWindow, name: str) -> None:
        self.code_dock.show()
        self.code_dock.raise_()
        self.code_panel.open_handler(name)
