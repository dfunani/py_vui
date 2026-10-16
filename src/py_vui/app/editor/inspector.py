"""Right-hand properties panel: Properties / Style / Layout / Events for the selection."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from py_vui.app.editor.edit_context import EditContext
from py_vui.app.editor.event_editor import EventsPage
from py_vui.app.editor.layout_editor import LayoutPage
from py_vui.app.editor.prop_editors import SplitterLabel
from py_vui.app.editor.props_page import PropertiesPage
from py_vui.commands import SetAttr, SetProjectAttr
from py_vui.core.catalog import STYLE_PROPS
from py_vui.core.registry import get_spec
from py_vui.core.theme import PRESETS, theme_for_preset

if TYPE_CHECKING:
    from py_vui.commands import History
    from py_vui.core.document import ProjectDocument


def _scroll(widget: QWidget) -> QScrollArea:
    sa = QScrollArea()
    sa.setWidgetResizable(True)
    sa.setFrameShape(QFrame.Shape.NoFrame)
    sa.setWidget(widget)
    sa.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    return sa


class ProjectSummary(QWidget):
    """Shown when nothing is selected: project facts, theme quick-switch, diagnostics."""

    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._doc: ProjectDocument | None = None
        self._history: History | None = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.addWidget(SplitterLabel("Project"))
        form = QFormLayout()
        self.name = QLineEdit()
        self.name.textEdited.connect(self._rename)
        self.theme = QComboBox()
        for p in PRESETS:
            self.theme.addItem(p.title(), p)
        self.theme.activated.connect(self._theme_picked)
        self.framework = QLabel()
        self.counts = QLabel()
        change = QPushButton("Change…")
        change.setAutoDefault(False)
        change.clicked.connect(self._change_framework)
        fw = QHBoxLayout()
        fw.addWidget(self.framework, 1)
        fw.addWidget(change)
        form.addRow("Name", self.name)
        form.addRow("Theme", self.theme)
        form.addRow("Framework", fw)
        form.addRow("Content", self.counts)
        lay.addLayout(form)
        lay.addWidget(SplitterLabel("Diagnostics"))
        self.diag = QListWidget()
        lay.addWidget(self.diag, 1)
        hint = QLabel("Select a widget on the canvas to edit its properties.")
        hint.setWordWrap(True)
        hint.setEnabled(False)
        lay.addWidget(hint)

    def bind(self, doc: ProjectDocument | None, history: History | None) -> None:
        self._doc, self._history = doc, history
        self.refresh()

    def refresh(self) -> None:
        self.diag.clear()
        if self._doc is None:
            return
        p = self._doc.project
        if self.name.text() != p.meta.name:
            self.name.setText(p.meta.name)
        i = self.theme.findData(p.theme.preset)
        self.theme.setCurrentIndex(max(i, 0))
        self.framework.setText(p.framework)
        wins = len(self._doc.windows())
        self.counts.setText(
            f"{len(p.nodes)} widgets, {wins} window(s), {len(p.handlers)} handler(s)")
        diags = self._doc.diagnostics()
        if not diags:
            self.diag.addItem("No problems found.")
        for d in diags:
            self.diag.addItem(f"{d.level}: {d.message}")

    def _rename(self, text: str) -> None:
        if self._doc is None or self._history is None or not text.strip():
            return
        meta = self._doc.project.meta.model_copy(update={"name": text})
        self._history.push(self._doc, SetProjectAttr("meta", meta, label="Rename project"))
        self.changed.emit()

    def _theme_picked(self, _index: int) -> None:
        if self._doc is None or self._history is None:
            return
        preset = self.theme.currentData()
        cmd = SetProjectAttr("theme", theme_for_preset(preset), label=f"Theme: {preset}")
        cmd.merge_key = None
        self._history.push(self._doc, cmd)
        self.changed.emit()
        self.refresh()

    def _change_framework(self) -> None:
        if self._doc is None or self._history is None:
            return
        from py_vui.app.editor.dialogs import FrameworkDialog

        if FrameworkDialog(self._doc, self._history, self).exec():
            self.changed.emit()
            self.refresh()


class InspectorPanel(QWidget):
    changed = Signal()
    handler_requested = Signal(str)

    #: set by the main window to ``ProjectService.add_asset`` so picked files are copied in
    asset_importer: Callable[[Path], str] | None = None

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._doc: ProjectDocument | None = None
        self._history: History | None = None
        self._ids: list[str] = []
        self._sig: tuple | None = None
        self._ctx: EditContext | None = None
        self._pages: list[QWidget] = []
        self.props_page: PropertiesPage | None = None
        self.style_page: PropertiesPage | None = None
        self.layout_page: LayoutPage | None = None
        self.events_page: EventsPage | None = None
        self.project_dir: Path | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.header = QWidget()
        hl = QVBoxLayout(self.header)
        hl.setContentsMargins(8, 8, 8, 4)
        top = QHBoxLayout()
        self.icon = QLabel()
        f = self.icon.font()
        f.setPointSize(f.pointSize() + 4)
        self.icon.setFont(f)
        self.type_label = QLabel()
        bold = self.type_label.font()
        bold.setBold(True)
        self.type_label.setFont(bold)
        top.addWidget(self.icon)
        top.addWidget(self.type_label, 1)
        hl.addLayout(top)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Widget name")
        self.name_edit.editingFinished.connect(self.commit_name)
        hl.addWidget(self.name_edit)
        root.addWidget(self.header)

        self.tabs = QTabWidget()
        self.summary = ProjectSummary()
        self.summary.changed.connect(self.changed)
        root.addWidget(self.tabs, 1)
        root.addWidget(self.summary, 1)
        self._show_summary(True)

    # ------------------------------------------------------------- public API
    def bind(self, doc: ProjectDocument, history: History) -> None:
        self._doc, self._history = doc, history
        self._ids = []
        self._sig = None
        self.summary.bind(doc, history)
        self.set_selection([])

    def set_selection(self, ids: list[str]) -> None:
        self._ids = list(ids)
        self._rebuild(force=False)

    def refresh(self) -> None:
        self._rebuild(force=False)

    # ------------------------------------------------------------- internals
    def _show_summary(self, on: bool) -> None:
        self.summary.setVisible(on)
        self.tabs.setVisible(not on)
        self.header.setVisible(not on)

    def _live_ids(self) -> list[str]:
        if self._doc is None:
            return []
        return [i for i in self._ids if i in self._doc.project.nodes]

    def _signature(self, ids: list[str]) -> tuple:
        assert self._doc is not None
        return (
            tuple(ids),
            tuple(self._doc.project.nodes[i].type for i in ids),
            self._doc.project.framework,
        )

    def _rebuild(self, *, force: bool) -> None:
        if self._doc is None or self._history is None:
            self._show_summary(True)
            return
        ids = self._live_ids()
        if not ids:
            self._clear_tabs()
            self._sig = None
            self._show_summary(True)
            self.summary.refresh()
            return
        sig = self._signature(ids)
        if force or sig != self._sig:
            self._sig = sig
            self._build_tabs(ids)
        else:
            self._refresh_pages()
        self._refresh_header()
        self._show_summary(False)

    def _clear_tabs(self) -> None:
        current = self.tabs.currentIndex()
        self._last_tab = current if current >= 0 else getattr(self, "_last_tab", 0)
        while self.tabs.count():
            w = self.tabs.widget(0)
            self.tabs.removeTab(0)
            w.deleteLater()
        self._pages = []
        self.props_page = self.style_page = self.layout_page = self.events_page = None

    def _build_tabs(self, ids: list[str]) -> None:
        assert self._doc is not None
        self._clear_tabs()
        ctx = EditContext(
            self._doc, self._history, ids,  # type: ignore[arg-type]
            on_change=self._on_edit,
            asset_importer=self._import_asset,
            project_dir=self.project_dir,
        )
        self._ctx = ctx
        nodes = ctx.nodes
        types = {n.type for n in nodes}
        same = len(types) == 1
        spec = get_spec(nodes[0].type)
        wanted: list[tuple[str, QWidget]] = []
        if same and spec.props:
            hidden = frozenset({"menus"}) if spec.type == "window" else frozenset()
            self.props_page = PropertiesPage(ctx, spec.props, "props", hidden=hidden)
            holder = QWidget()
            hv = QVBoxLayout(holder)
            hv.setContentsMargins(0, 0, 0, 0)
            hv.addWidget(self.props_page)
            if spec.type == "window" and len(nodes) == 1:
                btn = QPushButton("Edit menus…")
                btn.setAutoDefault(False)
                btn.clicked.connect(self.edit_menus)
                self.menus_button = btn
                hv.insertWidget(0, btn)
            wanted.append(("Properties", holder))
        self.style_page = PropertiesPage(ctx, STYLE_PROPS, "style")
        wanted.append(("Style", self.style_page))
        self.layout_page = LayoutPage(ctx)
        wanted.append(("Layout", self.layout_page))
        events = EventsPage(ctx)
        if events._events_for():
            events.handler_requested.connect(self.handler_requested)
            self.events_page = events
            wanted.append(("Events", events))
        else:
            events.deleteLater()
        for title, page in wanted:
            self.tabs.addTab(_scroll(page), title)
            self._pages.append(page)
        idx = min(getattr(self, "_last_tab", 0), self.tabs.count() - 1)
        self.tabs.setCurrentIndex(max(idx, 0))

    def _refresh_pages(self) -> None:
        for p in (self.props_page, self.style_page, self.layout_page, self.events_page):
            if p is not None:
                p.refresh()

    def _refresh_header(self) -> None:
        ids = self._live_ids()
        assert self._doc is not None
        nodes = [self._doc.project.nodes[i] for i in ids]
        if len(nodes) == 1:
            spec = get_spec(nodes[0].type)
            self.icon.setText(spec.icon)
            self.type_label.setText(spec.label)
            self.name_edit.setEnabled(True)
            if not self.name_edit.hasFocus() and self.name_edit.text() != nodes[0].name:
                self.name_edit.setText(nodes[0].name)
        else:
            types = {n.type for n in nodes}
            self.icon.setText("▦")
            self.type_label.setText(
                f"{len(nodes)} widgets" + (f" ({get_spec(next(iter(types))).label})"
                                          if len(types) == 1 else " (mixed)"))
            self.name_edit.setEnabled(False)
            self.name_edit.setText("")

    def _import_asset(self, path: Path) -> str:
        if self.asset_importer is None:
            return str(path)
        return self.asset_importer(path)

    def _on_edit(self) -> None:
        self._refresh_pages()
        self._refresh_header()
        self.changed.emit()

    # ------------------------------------------------------------- actions
    def commit_name(self) -> None:
        """Apply the header name field as a SetAttr, made unique within the document."""
        if self._doc is None or self._history is None or len(self._live_ids()) != 1:
            return
        nid = self._live_ids()[0]
        node = self._doc.project.nodes[nid]
        text = self.name_edit.text().strip()
        if not text or text == node.name:
            self.name_edit.setText(node.name)
            return
        unique = self._doc.unique_name(text, exclude=nid)
        self._history.push(self._doc, SetAttr(nid, "name", unique, label="Rename widget"))
        self.name_edit.setText(unique)
        self.changed.emit()

    def edit_menus(self) -> None:
        if self._doc is None or self._history is None or len(self._live_ids()) != 1:
            return
        from py_vui.app.editor.dialogs import MenuDesignerDialog

        dlg = MenuDesignerDialog(self._doc, self._history, self._live_ids()[0], self)
        if dlg.exec():
            self._on_edit()
