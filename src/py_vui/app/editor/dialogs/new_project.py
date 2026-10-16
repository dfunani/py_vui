"""New-project dialog and the template gallery."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from py_vui.app.editor.dialogs.common import (
    FRAMEWORK_INFO,
    add_buttons,
    get_setting,
    make_dialog_base,
    supported_count,
)
from py_vui.app.editor.dialogs.thumbnail import render_thumbnail
from py_vui.core.registry import FRAMEWORKS


@dataclass
class _Tpl:
    id: str
    name: str
    description: str
    category: str
    tags: list[str]
    widget_types: list[str]


def list_templates() -> list[_Tpl]:
    """Templates from ``py_vui.services.templates`` (empty when the service is unavailable)."""
    try:
        from py_vui.services import templates
    except ImportError:
        return []
    out = []
    for t in templates.list_templates():
        out.append(_Tpl(
            t.id, t.name, getattr(t, "description", ""), getattr(t, "category", "") or "General",
            list(getattr(t, "tags", []) or []), list(getattr(t, "widget_types", []) or []),
        ))
    return out


def load_template(template_id: str) -> Any:
    from py_vui.services import templates

    return templates.load_template(template_id)


_thumb_cache: dict[str, QIcon] = {}


def template_icon(template_id: str, size: QSize = QSize(200, 140)) -> QIcon:
    key = f"{template_id}:{size.width()}x{size.height()}"
    if key not in _thumb_cache:
        try:
            pm = render_thumbnail(load_template(template_id), size.width(), size.height())
            _thumb_cache[key] = QIcon(pm)
        except Exception:
            _thumb_cache[key] = QIcon()
    return _thumb_cache[key]


class TemplateGalleryDialog(QDialog):
    """Grid of template cards with category filter and search. Result: ``.template_id``."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.template_id: str | None = None
        self._templates = list_templates()
        lay = make_dialog_base(self, "Template gallery", (820, 560))
        bar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search templates…")
        self.category = QComboBox()
        self.category.addItem("All categories", "")
        for c in sorted({t.category for t in self._templates}):
            self.category.addItem(c, c)
        bar.addWidget(self.search, 1)
        bar.addWidget(self.category)
        lay.addLayout(bar)
        body = QHBoxLayout()
        self.grid = QListWidget()
        self.grid.setViewMode(QListWidget.ViewMode.IconMode)
        self.grid.setIconSize(QSize(200, 140))
        self.grid.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.grid.setMovement(QListWidget.Movement.Static)
        self.grid.setGridSize(QSize(230, 190))
        self.grid.setWordWrap(True)
        self.grid.setSpacing(6)
        body.addWidget(self.grid, 1)
        side = QFrame()
        side.setFixedWidth(230)
        sl = QVBoxLayout(side)
        self.title = QLabel("Select a template")
        f = self.title.font()
        f.setBold(True)
        self.title.setFont(f)
        self.desc = QLabel("")
        self.desc.setWordWrap(True)
        self.chips = QLabel("")
        self.chips.setWordWrap(True)
        sl.addWidget(self.title)
        sl.addWidget(self.desc)
        sl.addWidget(QLabel("Widgets"))
        sl.addWidget(self.chips)
        sl.addStretch(1)
        body.addWidget(side)
        lay.addLayout(body, 1)
        self.buttons = add_buttons(self, lay)
        self.search.textChanged.connect(self._fill)
        self.category.currentIndexChanged.connect(lambda _i: self._fill())
        self.grid.currentItemChanged.connect(self._on_current)
        self.grid.itemDoubleClicked.connect(lambda _i: self.accept())
        self._fill()

    def visible_ids(self) -> list[str]:
        return [self.grid.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.grid.count())]

    def _fill(self) -> None:
        q = self.search.text().strip().lower()
        cat = self.category.currentData()
        self.grid.clear()
        for t in self._templates:
            hay = " ".join([t.name, t.description, t.category, *t.tags, *t.widget_types]).lower()
            if (cat and t.category != cat) or (q and q not in hay):
                continue
            it = QListWidgetItem(template_icon(t.id), t.name)
            it.setData(Qt.ItemDataRole.UserRole, t.id)
            it.setToolTip(t.description)
            self.grid.addItem(it)
        if self.grid.count():
            self.grid.setCurrentRow(0)
        else:
            self._on_current(None)

    def select(self, template_id: str) -> bool:
        for i in range(self.grid.count()):
            if self.grid.item(i).data(Qt.ItemDataRole.UserRole) == template_id:
                self.grid.setCurrentRow(i)
                return True
        return False

    def _on_current(self, item: QListWidgetItem | None, _prev: Any = None) -> None:
        tid = item.data(Qt.ItemDataRole.UserRole) if item else None
        t = next((x for x in self._templates if x.id == tid), None)
        if t is None:
            self.title.setText("Select a template")
            self.desc.setText("")
            self.chips.setText("")
            return
        self.title.setText(t.name)
        self.desc.setText(t.description)
        self.chips.setText("  ".join(f"[{w}]" for w in sorted(set(t.widget_types))))

    def accept(self) -> None:
        item = self.grid.currentItem()
        self.template_id = item.data(Qt.ItemDataRole.UserRole) if item else None
        super().accept()


class NewProjectDialog(QDialog):
    """Name + framework cards + template. After accept: ``.name .framework .template_id``."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.name = "Untitled"
        default_fw = get_setting("default_framework", "tkinter")
        self.framework: str = default_fw if default_fw in FRAMEWORKS else "tkinter"
        self.template_id: str | None = None
        lay = make_dialog_base(self, "New project", (640, 560))
        self.name_edit = QLineEdit(self.name)
        self.name_edit.selectAll()
        lay.addWidget(QLabel("Project name"))
        lay.addWidget(self.name_edit)
        lay.addWidget(QLabel("Framework"))
        self._group = QButtonGroup(self)
        self._radios: dict[str, QRadioButton] = {}
        for fw in FRAMEWORKS:
            label, desc = FRAMEWORK_INFO[fw]
            ok, total = supported_count(fw)
            card = QFrame()
            card.setFrameShape(QFrame.Shape.StyledPanel)
            cl = QHBoxLayout(card)
            rb = QRadioButton(label)
            rb.setChecked(fw == self.framework)
            self._group.addButton(rb)
            self._radios[fw] = rb
            info = QLabel(f"{desc}\n{ok} of {total} widgets supported")
            info.setWordWrap(True)
            info.setEnabled(False)
            cl.addWidget(rb)
            cl.addWidget(info, 1)
            lay.addWidget(card)
        lay.addWidget(QLabel("Start from"))
        tpl_row = QHBoxLayout()
        self.templates = QListWidget()
        self.templates.setIconSize(QSize(72, 50))
        blank = QListWidgetItem("Blank project")
        blank.setData(Qt.ItemDataRole.UserRole, None)
        self.templates.addItem(blank)
        for t in list_templates():
            it = QListWidgetItem(f"{t.name}  -  {t.category}")
            it.setData(Qt.ItemDataRole.UserRole, t.id)
            it.setToolTip(t.description)
            self.templates.addItem(it)
        self.templates.setCurrentRow(0)
        tpl_row.addWidget(self.templates, 1)
        gallery = QPushButton("Browse gallery…")
        gallery.setAutoDefault(False)
        gallery.clicked.connect(self._browse)
        tpl_row.addWidget(gallery, 0, Qt.AlignmentFlag.AlignTop)
        lay.addLayout(tpl_row, 1)
        add_buttons(self, lay)
        self.name_edit.setFocus()

    def set_framework(self, fw: str) -> None:
        self._radios[fw].setChecked(True)

    def set_template(self, template_id: str | None) -> bool:
        for i in range(self.templates.count()):
            if self.templates.item(i).data(Qt.ItemDataRole.UserRole) == template_id:
                self.templates.setCurrentRow(i)
                return True
        return False

    def _browse(self) -> None:
        dlg = TemplateGalleryDialog(self)
        if dlg.exec() and dlg.template_id:
            self.set_template(dlg.template_id)

    def accept(self) -> None:
        self.name = self.name_edit.text().strip() or "Untitled"
        self.framework = next((fw for fw, rb in self._radios.items() if rb.isChecked()),
                              self.framework)
        item = self.templates.currentItem()
        self.template_id = item.data(Qt.ItemDataRole.UserRole) if item else None
        super().accept()
