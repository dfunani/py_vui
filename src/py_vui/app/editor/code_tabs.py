"""The four tabs of the code panel: Handlers, Module code, Generated, Requirements."""

from __future__ import annotations

import keyword
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from py_vui.app.editor.code_check import check_handler, check_module, check_source
from py_vui.app.editor.code_editor import CodeEditorView
from py_vui.app.editor.completion import members_for
from py_vui.app.editor.highlighter import PythonHighlighter
from py_vui.app.editor.ui_colors import ErrorBanner
from py_vui.codegen import GenOptions, check_syntax, get_adapter
from py_vui.commands import Batch, Command, SetField, SetHandler, SetProjectAttr
from py_vui.core.model import HandlerDef

if TYPE_CHECKING:
    from py_vui.commands import History
    from py_vui.core.document import ProjectDocument


def is_valid_handler_name(name: str) -> bool:
    return name.isidentifier() and not keyword.iskeyword(name)


def _btn(text: str, tip: str = "") -> QPushButton:
    b = QPushButton(text)
    b.setToolTip(tip)
    b.setAutoDefault(False)
    return b


class _TabBase(QWidget):
    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.doc: ProjectDocument | None = None
        self.history: History | None = None
        self.service: Any = None

    def bind(self, doc: ProjectDocument, history: History, service: Any = None) -> None:
        self.doc, self.history, self.service = doc, history, service
        self.refresh()

    def refresh(self) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def _push(self, cmd: Command) -> None:
        assert self.doc is not None and self.history is not None
        self.history.push(self.doc, cmd)
        self.changed.emit()


# ----------------------------------------------------------------------------- handlers
class HandlersTab(_TabBase):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current: str | None = None
        self._loading = False
        self._list_sig: tuple | None = None
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        split = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(split)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(4, 4, 4, 4)
        self.list = QListWidget()
        self.list.currentItemChanged.connect(self._on_select)
        ll.addWidget(self.list, 1)
        row = QHBoxLayout()
        self.add_btn = _btn("+ New", "Add a handler")
        self.rename_btn = _btn("Rename")
        self.delete_btn = _btn("Delete", "Delete (bindings are removed)")
        for b in (self.add_btn, self.rename_btn, self.delete_btn):
            row.addWidget(b)
        ll.addLayout(row)
        self.add_btn.clicked.connect(self._ask_add)
        self.rename_btn.clicked.connect(self._ask_rename)
        self.delete_btn.clicked.connect(self._ask_delete)
        split.addWidget(left)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(4, 4, 4, 4)
        rl.setSpacing(2)
        self.signature = QLabel("")
        self.signature.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        font = self.signature.font()
        font.setFamily("Menlo")
        font.setStyleHint(font.StyleHint.Monospace)
        self.signature.setFont(font)
        self.view = CodeEditorView()
        self.editor = self.view.editor
        self.editor.textChanged.connect(self._on_text)
        self.editor.set_member_provider(lambda ctx: members_for(ctx, self.doc))
        self.status = QLabel("")
        rl.addWidget(self.signature)
        rl.addWidget(self.view, 1)
        rl.addWidget(self.status)
        split.addWidget(right)
        split.setStretchFactor(1, 1)
        split.setSizes([200, 600])
        self._set_enabled(False)

    # ------------------------------------------------------------- queries
    def usage(self, name: str) -> list[str]:
        assert self.doc is not None
        return [f"{n.name}.{ev}" for n in self.doc.walk() for ev, h in n.events.items()
                if h == name]

    def handler_names(self) -> list[str]:
        return list(self.doc.project.handlers) if self.doc else []

    def current(self) -> str | None:
        return self._current

    # ------------------------------------------------------------- refresh
    def refresh(self) -> None:
        if self.doc is None:
            return
        names = sorted(self.doc.project.handlers)
        sig = (tuple((n, tuple(self.usage(n))) for n in names),)
        if sig != self._list_sig:
            self._list_sig = sig
            self._fill_list(names)
        if self._current not in self.doc.project.handlers:
            self._current = names[0] if names else None
            self._select_in_list(self._current)
        self._load_current()
        words = [*names, "WIDGETS", "WINDOWS", "event", *self.doc.variable_names().values()]
        self.editor.set_completions(words)

    def _fill_list(self, names: list[str]) -> None:
        self.list.blockSignals(True)
        self.list.clear()
        for n in names:
            uses = self.usage(n)
            item = QListWidgetItem(n if not uses else f"{n}\n   {', '.join(uses[:3])}"
                                   + (" …" if len(uses) > 3 else ""))
            item.setData(Qt.ItemDataRole.UserRole, n)
            item.setToolTip(", ".join(uses) if uses else "Not bound to any event")
            self.list.addItem(item)
        self.list.blockSignals(False)
        self._select_in_list(self._current)

    def _select_in_list(self, name: str | None) -> None:
        self.list.blockSignals(True)
        self.list.setCurrentRow(-1)
        for i in range(self.list.count()):
            if self.list.item(i).data(Qt.ItemDataRole.UserRole) == name:
                self.list.setCurrentRow(i)
        self.list.blockSignals(False)

    def _set_enabled(self, on: bool) -> None:
        self.editor.setEnabled(on)
        self.rename_btn.setEnabled(on)
        self.delete_btn.setEnabled(on)

    def _load_current(self) -> None:
        assert self.doc is not None
        name = self._current
        h = self.doc.project.handlers.get(name) if name else None
        self._set_enabled(h is not None)
        self.signature.setText(f"def {name}(event=None):" if h else "")
        if h is None:
            self._loading = True
            self.editor.setPlainText("")
            self._loading = False
            self.status.setText("No handler selected.")
            self.editor.set_problem(None)
            return
        if h.body != self.editor.toPlainText():
            self._loading = True
            self.editor.set_code(h.body)
            self._loading = False
        self._check()

    def _on_select(self, item: QListWidgetItem | None, _prev: Any = None) -> None:
        self._current = item.data(Qt.ItemDataRole.UserRole) if item else None
        if self.doc is not None:
            self._load_current()

    def select(self, name: str) -> bool:
        if self.doc is None or name not in self.doc.project.handlers:
            return False
        self._current = name
        self._select_in_list(name)
        self._load_current()
        return True

    # ------------------------------------------------------------- editing
    def _on_text(self) -> None:
        if self._loading or self.doc is None or self._current is None:
            return
        body = self.editor.toPlainText()
        h = self.doc.project.handlers.get(self._current)
        if h is None or h.body == body:
            return
        self._push(SetHandler(self._current, HandlerDef(name=self._current, body=body)))
        self._check()

    def _check(self) -> None:
        problem = check_handler(self.editor.toPlainText(), self._current or "f")
        self.editor.set_problem(problem)
        self.status.setText("Syntax OK" if problem is None else f"Syntax error - {problem}")

    def add_handler(self, name: str | None = None, body: str = "pass") -> str | None:
        assert self.doc is not None
        handlers = self.doc.project.handlers
        if name is None:
            i = 1
            while f"handler_{i}" in handlers:
                i += 1
            name = f"handler_{i}"
        if not is_valid_handler_name(name) or name in handlers:
            return None
        cmd = SetHandler(name, HandlerDef(name=name, body=body), label="New handler")
        cmd.merge_key = None
        self._push(cmd)
        self._current = name
        self.refresh()
        return name

    def rename_handler(self, old: str, new: str) -> bool:
        assert self.doc is not None
        handlers = self.doc.project.handlers
        if old not in handlers or new in handlers or not is_valid_handler_name(new):
            return False
        cmds: list[Command] = [
            SetHandler(old, None),
            SetHandler(new, HandlerDef(name=new, body=handlers[old].body)),
        ]
        for n in self.doc.walk():
            for ev, h in n.events.items():
                if h == old:
                    cmds.append(SetField(n.id, "events", ev, new))
        self._push(Batch(cmds, label=f"Rename handler {old}"))
        self._current = new
        self.refresh()
        return True

    def delete_handler(self, name: str) -> bool:
        assert self.doc is not None
        if name not in self.doc.project.handlers:
            return False
        cmds: list[Command] = [SetHandler(name, None)]
        for n in self.doc.walk():
            for ev, h in n.events.items():
                if h == name:
                    cmds.append(SetField(n.id, "events", ev, None))
        self._push(Batch(cmds, label=f"Delete handler {name}"))
        if self._current == name:
            self._current = None
        self.refresh()
        return True

    # ------------------------------------------------------------- UI slots
    def _ask_add(self) -> None:
        name, ok = QInputDialog.getText(self, "New handler", "Function name:")
        if not ok:
            return
        if self.add_handler(name.strip() or None) is None:
            QMessageBox.warning(self, "New handler", "Pick a unique valid Python identifier.")

    def _ask_rename(self) -> None:
        if self._current is None:
            return
        new, ok = QInputDialog.getText(self, "Rename handler", "New name:", text=self._current)
        if ok and new != self._current and not self.rename_handler(self._current, new.strip()):
            QMessageBox.warning(self, "Rename", "Pick a unique valid Python identifier.")

    def _ask_delete(self) -> None:
        if self._current is None:
            return
        uses = self.usage(self._current)
        if uses:
            ans = QMessageBox.question(
                self, "Delete handler",
                f"{self._current} is bound to {', '.join(uses)}.\nDelete and unbind it?")
            if ans != QMessageBox.StandardButton.Yes:
                return
        self.delete_handler(self._current)


# ----------------------------------------------------------------------------- module code
class ModuleTab(_TabBase):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._loading = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        hint = QLabel("Imports, globals and helper functions placed at the top of handlers.py.")
        hint.setEnabled(False)
        self.view = CodeEditorView()
        self.editor = self.view.editor
        self.status = QLabel("")
        lay.addWidget(hint)
        lay.addWidget(self.view, 1)
        lay.addWidget(self.status)
        self.editor.textChanged.connect(self._on_text)
        self.editor.set_member_provider(lambda ctx: members_for(ctx, self.doc))

    def refresh(self) -> None:
        if self.doc is None:
            return
        code = self.doc.project.custom_code
        if code != self.editor.toPlainText():
            self._loading = True
            self.editor.set_code(code)
            self._loading = False
        self._check()

    def _check(self) -> None:
        p = check_module(self.editor.toPlainText())
        self.editor.set_problem(p)
        self.status.setText("Syntax OK" if p is None else f"Syntax error - {p}")

    def _on_text(self) -> None:
        if self._loading or self.doc is None:
            return
        text = self.editor.toPlainText()
        if text != self.doc.project.custom_code:
            self._push(SetProjectAttr("custom_code", text, label="Edit module code"))
        self._check()


# ----------------------------------------------------------------------------- generated
class GeneratedTab(_TabBase):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._files: dict[str, Any] = {}
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        bar = QHBoxLayout()
        self.layout_combo = QComboBox()
        self.layout_combo.addItem("Project (multi-file)", "project")
        self.layout_combo.addItem("Single file", "single")
        self.file_combo = QComboBox()
        self.refresh_btn = _btn("Refresh")
        self.copy_btn = _btn("Copy")
        bar.addWidget(QLabel("Layout"))
        bar.addWidget(self.layout_combo)
        bar.addWidget(QLabel("File"))
        bar.addWidget(self.file_combo, 1)
        bar.addWidget(self.refresh_btn)
        bar.addWidget(self.copy_btn)
        lay.addLayout(bar)
        self.banner = ErrorBanner("")
        self.banner.setVisible(False)
        lay.addWidget(self.banner)
        self.view = CodeEditorView(highlight=False, read_only=True)
        self.editor = self.view.editor
        self.highlighter = PythonHighlighter(self.editor.document())
        lay.addWidget(self.view, 1)
        self.refresh_btn.clicked.connect(self.refresh)
        self.copy_btn.clicked.connect(self.copy)
        self.file_combo.currentIndexChanged.connect(lambda _i: self._show_selected())
        self.layout_combo.currentIndexChanged.connect(lambda _i: self.refresh())

    def refresh(self) -> None:
        if self.doc is None or self.service is None:
            return
        opts = GenOptions(layout=self.layout_combo.currentData())
        try:
            files = self.service.generated_files(opts)
        except Exception as exc:
            self._files = {}
            self.file_combo.blockSignals(True)
            self.file_combo.clear()
            self.file_combo.blockSignals(False)
            self.editor.setPlainText("")
            self.banner.setText(f"Code generation failed: {exc}")
            self.banner.setVisible(True)
            return
        previous = self.file_combo.currentData()
        self._files = {f.path: f for f in files}
        self.file_combo.blockSignals(True)
        self.file_combo.clear()
        for f in files:
            self.file_combo.addItem(f.path, f.path)
        idx = self.file_combo.findData(previous)
        self.file_combo.setCurrentIndex(max(idx, 0))
        self.file_combo.blockSignals(False)
        errors = check_syntax([f for f in files if f.path.endswith(".py")])
        if errors:
            self.banner.setText("Generated code has syntax errors: " + "; ".join(errors[:3]))
        self.banner.setVisible(bool(errors))
        self._show_selected()

    def _show_selected(self) -> None:
        path = self.file_combo.currentData()
        f = self._files.get(path)
        if f is None:
            return
        is_py = path.endswith(".py")
        self.highlighter.setDocument(self.editor.document() if is_py else None)
        text = "(binary file)" if f.data is not None else f.content
        self.editor.set_code(text)
        if is_py and f.data is None:
            problem = check_source(text, path)
            self.editor.set_problem(problem)

    def file_names(self) -> list[str]:
        return list(self._files)

    def copy(self) -> None:
        QGuiApplication.clipboard().setText(self.editor.toPlainText())


# ----------------------------------------------------------------------------- requirements
class RequirementsEditor(_TabBase):
    """Computed requirements (read-only) + editable extra requirements."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._loading = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        self.framework_label = QLabel("")
        lay.addWidget(self.framework_label)
        lay.addWidget(QLabel("Computed from the widgets you use:"))
        self.computed = QListWidget()
        lay.addWidget(self.computed, 1)
        lay.addWidget(QLabel("Extra requirements (one per line, e.g. requests>=2.31):"))
        self.extra = QPlainTextEdit()
        self.extra.setPlaceholderText("package==1.2.3")
        lay.addWidget(self.extra, 1)
        self.extra.textChanged.connect(self._on_text)

    def refresh(self) -> None:
        if self.doc is None:
            return
        p = self.doc.project
        self.framework_label.setText(f"Target framework: {p.framework}")
        self.computed.clear()
        try:
            for r in get_adapter(p.framework).requirements(p):
                self.computed.addItem(r)
        except KeyError as exc:
            self.computed.addItem(f"(unavailable: {exc})")
        text = "\n".join(p.extra_requirements)
        if text != self.extra.toPlainText().rstrip("\n") and not self.extra.hasFocus():
            self._loading = True
            self.extra.setPlainText(text)
            self._loading = False

    def lines(self) -> list[str]:
        return [ln.strip() for ln in self.extra.toPlainText().splitlines() if ln.strip()]

    def _on_text(self) -> None:
        if self._loading or self.doc is None:
            return
        lines = self.lines()
        if lines != self.doc.project.extra_requirements:
            self._push(SetProjectAttr("extra_requirements", lines, label="Edit requirements"))
            self.refresh_computed_only()

    def refresh_computed_only(self) -> None:
        assert self.doc is not None
        self.computed.clear()
        p = self.doc.project
        try:
            for r in get_adapter(p.framework).requirements(p):
                self.computed.addItem(r)
        except KeyError:
            pass


__all__ = [
    "GeneratedTab", "HandlersTab", "ModuleTab", "RequirementsEditor", "is_valid_handler_name",
]
