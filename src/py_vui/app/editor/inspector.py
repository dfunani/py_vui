from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from py_vui.commands import ReplaceNode
from py_vui.model.interaction import HandlerDef, default_handler_name
from py_vui.model.nodes import (
    ButtonNode,
    CheckboxNode,
    LabelNode,
    LineEditNode,
    Node,
    WindowNode,
)
from py_vui.model.theme import WidgetStyle, theme_for_preset

if TYPE_CHECKING:
    from py_vui.commands.history import History
    from py_vui.model.document import ProjectDocument


class PropertyInspector(QWidget):
    document_changed = Signal()
    document_dirty = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._doc: ProjectDocument | None = None
        self._history: History | None = None
        self._node_id: str | None = None
        self._block = False

        layout = QVBoxLayout(self)

        project = QGroupBox("Project")
        pf = QFormLayout(project)
        self._project_name = QLineEdit()
        self._project_name.editingFinished.connect(self._apply_project_name)
        self._theme_preset = QComboBox()
        for preset in ("light", "dark", "modern", "ocean"):
            self._theme_preset.addItem(preset.title(), preset)
        self._theme_preset.currentIndexChanged.connect(self._apply_theme_preset)
        pf.addRow("Project name", self._project_name)
        pf.addRow("Theme", self._theme_preset)
        layout.addWidget(project)

        common = QGroupBox("Layout")
        cf = QFormLayout(common)
        self._name = QLineEdit()
        self._name.editingFinished.connect(self._apply)
        self._enabled = QCheckBox("Enabled")
        self._enabled.stateChanged.connect(self._apply)
        self._x = QSpinBox()
        self._x.setRange(-9999, 9999)
        self._y = QSpinBox()
        self._y.setRange(-9999, 9999)
        self._w = QSpinBox()
        self._w.setRange(1, 9999)
        self._h = QSpinBox()
        self._h.setRange(1, 9999)
        for spin in (self._x, self._y, self._w, self._h):
            spin.editingFinished.connect(self._apply)
        cf.addRow("Widget name", self._name)
        cf.addRow("", self._enabled)
        cf.addRow("X", self._x)
        cf.addRow("Y", self._y)
        cf.addRow("W", self._w)
        cf.addRow("H", self._h)
        layout.addWidget(common)

        props = QGroupBox("Content")
        prop_form = QFormLayout(props)
        self._text = QLineEdit()
        self._text.editingFinished.connect(self._apply)
        self._placeholder = QLineEdit()
        self._placeholder.editingFinished.connect(self._apply)
        self._checked = QCheckBox()
        self._checked.stateChanged.connect(self._apply)
        prop_form.addRow("Text / title", self._text)
        prop_form.addRow("Placeholder", self._placeholder)
        prop_form.addRow("Checked", self._checked)
        layout.addWidget(props)

        appearance = QGroupBox("Appearance")
        af = QFormLayout(appearance)
        self._bg = QLineEdit()
        self._bg.setPlaceholderText("e.g. #2563eb (empty = theme)")
        self._bg.editingFinished.connect(self._apply)
        self._fg = QLineEdit()
        self._fg.setPlaceholderText("text color")
        self._fg.editingFinished.connect(self._apply)
        self._font_size = QSpinBox()
        self._font_size.setRange(0, 48)
        self._font_size.setSpecialValueText("theme")
        self._font_size.editingFinished.connect(self._apply)
        self._radius = QSpinBox()
        self._radius.setRange(0, 32)
        self._radius.setSpecialValueText("theme")
        self._radius.editingFinished.connect(self._apply)
        af.addRow("Background", self._bg)
        af.addRow("Foreground", self._fg)
        af.addRow("Font size", self._font_size)
        af.addRow("Corner radius", self._radius)
        layout.addWidget(appearance)

        self._interaction_group = QGroupBox("Actions")
        interaction_layout = QVBoxLayout(self._interaction_group)
        handler_row = QHBoxLayout()
        self._handler_name = QComboBox()
        self._handler_name.setEditable(True)
        self._handler_name.currentTextChanged.connect(self._on_handler_name_changed)
        self._new_handler_btn = QPushButton("New")
        self._new_handler_btn.clicked.connect(self._create_handler_from_widget)
        handler_row.addWidget(self._handler_name, stretch=1)
        handler_row.addWidget(self._new_handler_btn)
        interaction_layout.addWidget(QLabel("Handler function:"))
        interaction_layout.addLayout(handler_row)
        self._handler_body = QPlainTextEdit()
        self._handler_body.setPlaceholderText(
            'Python statements, e.g.\nprint("Hello!")\n'
            "dialog = QMessageBox.information(None, 'Hi', 'Clicked')"
        )
        self._handler_body.setMinimumHeight(100)
        self._apply_handler_btn = QPushButton("Apply handler code")
        self._apply_handler_btn.clicked.connect(self._apply_handler_body)
        interaction_layout.addWidget(self._handler_body)
        interaction_layout.addWidget(self._apply_handler_btn)
        layout.addWidget(self._interaction_group)
        layout.addStretch()

    def bind(self, doc: ProjectDocument, history: History) -> None:
        self._doc = doc
        self._history = history
        self._refresh_project_fields()

    def _refresh_project_fields(self) -> None:
        if self._doc is None:
            return
        self._project_name.blockSignals(True)
        self._theme_preset.blockSignals(True)
        self._project_name.setText(self._doc.project.meta.name)
        idx = self._theme_preset.findData(self._doc.project.theme.preset)
        if idx >= 0:
            self._theme_preset.setCurrentIndex(idx)
        self._project_name.blockSignals(False)
        self._theme_preset.blockSignals(False)

    def _apply_project_name(self) -> None:
        if self._block or self._doc is None:
            return
        new_name = self._project_name.text().strip() or "untitled"
        if new_name == self._doc.project.meta.name:
            return
        self._doc.project.meta.name = new_name
        self.document_dirty.emit()

    def _apply_theme_preset(self) -> None:
        if self._block or self._doc is None:
            return
        preset = self._theme_preset.currentData()
        if not preset:
            return
        self._doc.project.theme = theme_for_preset(preset)
        self.document_changed.emit()

    def _refresh_handler_list(self, *, select: str | None = None) -> None:
        if self._doc is None:
            return
        self._handler_name.blockSignals(True)
        current = select or self._handler_name.currentText()
        self._handler_name.clear()
        self._handler_name.addItem("(none)", "")
        for name in sorted(self._doc.project.handlers):
            self._handler_name.addItem(name, name)
        idx = self._handler_name.findData(current)
        if idx >= 0:
            self._handler_name.setCurrentIndex(idx)
        elif current:
            self._handler_name.setEditText(current)
        self._handler_name.blockSignals(False)

    def _current_handler_name(self) -> str | None:
        text = self._handler_name.currentText().strip()
        if not text or text == "(none)":
            return None
        return text

    def _load_handler_body(self, name: str | None) -> None:
        self._handler_body.blockSignals(True)
        if not name or self._doc is None:
            self._handler_body.clear()
        else:
            handler = self._doc.project.handlers.get(name)
            self._handler_body.setPlainText(handler.body if handler else "")
        self._handler_body.blockSignals(False)

    def _on_handler_name_changed(self) -> None:
        if self._block:
            return
        name = self._current_handler_name()
        self._load_handler_body(name)
        self._apply_handler_binding()

    def _create_handler_from_widget(self) -> None:
        if self._block or self._doc is None or not self._node_id:
            return
        node = self._doc.get_node(self._node_id)
        name = default_handler_name(node.name)
        if name not in self._doc.project.handlers:
            self._doc.project.handlers[name] = HandlerDef(
                name=name,
                body='print("clicked")',
            )
        self._refresh_handler_list(select=name)
        self._load_handler_body(name)
        self._apply_handler_binding(force_name=name)
        self.document_changed.emit()

    def _apply_handler_body(self) -> None:
        if self._block or self._doc is None:
            return
        name = self._current_handler_name()
        if not name:
            return
        body = self._handler_body.toPlainText().strip() or "pass"
        self._doc.project.handlers[name] = HandlerDef(name=name, body=body)
        self._refresh_handler_list(select=name)
        self.document_dirty.emit()

    def _apply_handler_binding(self, *, force_name: str | None = None) -> None:
        if self._block or not self._node_id or self._doc is None or self._history is None:
            return
        node = self._doc.get_node(self._node_id)
        handler = force_name if force_name is not None else self._current_handler_name()
        before = node
        data = node.model_dump()
        if isinstance(node, ButtonNode):
            data["props"]["onClick"] = handler
        elif isinstance(node, LineEditNode):
            data["props"]["onReturn"] = handler
        elif isinstance(node, CheckboxNode):
            data["props"]["onToggle"] = handler
        else:
            return
        after = node.__class__.model_validate(data)
        if after.model_dump() == before.model_dump():
            return
        if handler and handler not in self._doc.project.handlers:
            self._doc.project.handlers[handler] = HandlerDef(
                name=handler,
                body=self._handler_body.toPlainText().strip() or "pass",
            )
        self._history.push(self._doc, ReplaceNode(before=before, after=after))
        self.document_changed.emit()

    def show_node(self, node_id: str | None) -> None:
        self._node_id = node_id
        self._refresh_project_fields()
        self._refresh_handler_list()
        if not node_id or self._doc is None:
            self.setEnabled(False)
            return
        self.setEnabled(True)
        node = self._doc.get_node(node_id)
        box = node.layout.box
        if isinstance(node, WindowNode):
            display_w = int(node.props.width)
            display_h = int(node.props.height)
        else:
            display_w = int(box.w)
            display_h = int(box.h)

        self._block = True
        for widget, value in (
            (self._name, node.name),
            (self._x, int(box.x)),
            (self._y, int(box.y)),
            (self._w, display_w),
            (self._h, display_h),
        ):
            widget.blockSignals(True)
            if isinstance(widget, QLineEdit):
                widget.setText(str(value))
            else:
                widget.setValue(value)
            widget.blockSignals(False)

        self._enabled.blockSignals(True)
        self._enabled.setChecked(node.enabled)
        self._enabled.blockSignals(False)

        self._text.setVisible(
            isinstance(node, (WindowNode, LabelNode, ButtonNode, LineEditNode, CheckboxNode))
        )
        self._placeholder.setVisible(isinstance(node, LineEditNode))
        self._checked.setVisible(isinstance(node, CheckboxNode))
        has_action = isinstance(node, (ButtonNode, LineEditNode, CheckboxNode))
        self._interaction_group.setVisible(has_action)
        for w in (
            self._handler_name,
            self._new_handler_btn,
            self._handler_body,
            self._apply_handler_btn,
        ):
            w.setVisible(has_action)

        self._text.blockSignals(True)
        self._placeholder.blockSignals(True)
        self._checked.blockSignals(True)
        if isinstance(node, WindowNode):
            self._text.setText(node.props.title)
        elif isinstance(node, LabelNode):
            self._text.setText(node.props.text)
        elif isinstance(node, ButtonNode):
            self._text.setText(node.props.text)
        elif isinstance(node, LineEditNode):
            self._text.setText(node.props.text)
            self._placeholder.setText(node.props.placeholder)
        elif isinstance(node, CheckboxNode):
            self._text.setText(node.props.text)
            self._checked.setChecked(node.props.checked)
        else:
            self._text.clear()
        self._text.blockSignals(False)
        self._placeholder.blockSignals(False)
        self._checked.blockSignals(False)

        style = node.style or WidgetStyle()
        self._bg.blockSignals(True)
        self._fg.blockSignals(True)
        self._font_size.blockSignals(True)
        self._radius.blockSignals(True)
        self._bg.setText(style.background or "")
        self._fg.setText(style.foreground or "")
        self._font_size.setValue(style.font_size or 0)
        self._radius.setValue(style.border_radius if style.border_radius is not None else 0)
        self._bg.blockSignals(False)
        self._fg.blockSignals(False)
        self._font_size.blockSignals(False)
        self._radius.blockSignals(False)

        handler: str | None = None
        if isinstance(node, ButtonNode):
            handler = node.props.on_click
        elif isinstance(node, LineEditNode):
            handler = node.props.on_return
        elif isinstance(node, CheckboxNode):
            handler = node.props.on_toggle
        self._refresh_handler_list(select=handler or "")
        self._load_handler_body(handler)

        self._block = False

    def _apply(self) -> None:
        if self._block or not self._node_id or self._doc is None or self._history is None:
            return
        before = self._doc.get_node(self._node_id)
        after = self._clone_with_edits(before)
        if after.model_dump() == before.model_dump():
            return
        self._history.push(self._doc, ReplaceNode(before=before, after=after))
        self.document_changed.emit()

    def _parse_style(self) -> WidgetStyle | None:
        bg = self._bg.text().strip() or None
        fg = self._fg.text().strip() or None
        fs = self._font_size.value()
        radius = self._radius.value()
        if not any((bg, fg, fs, radius)):
            return None
        return WidgetStyle(
            background=bg,
            foreground=fg,
            font_size=fs if fs > 0 else None,
            border_radius=radius if radius > 0 else None,
        )

    def _clone_with_edits(self, node: Node) -> Node:
        data = node.model_dump()
        data["name"] = self._name.text()
        data["enabled"] = self._enabled.isChecked()
        data["style"] = self._parse_style()
        data["layout"]["box"]["x"] = float(self._x.value())
        data["layout"]["box"]["y"] = float(self._y.value())
        data["layout"]["box"]["w"] = float(self._w.value())
        data["layout"]["box"]["h"] = float(self._h.value())

        if isinstance(node, WindowNode):
            data["props"]["title"] = self._text.text()
            w = float(self._w.value())
            h = float(self._h.value())
            data["props"]["width"] = w
            data["props"]["height"] = h
            data["layout"]["box"]["w"] = w
            data["layout"]["box"]["h"] = h
        elif isinstance(node, (LabelNode, ButtonNode, LineEditNode, CheckboxNode)):
            data["props"]["text"] = self._text.text()
        if isinstance(node, LineEditNode):
            data["props"]["placeholder"] = self._placeholder.text()
        if isinstance(node, CheckboxNode):
            data["props"]["checked"] = self._checked.isChecked()

        return node.__class__.model_validate(data)
