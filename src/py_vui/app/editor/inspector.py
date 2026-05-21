from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from py_vui.commands import ReplaceNode
from py_vui.model.nodes import (
    ButtonNode,
    CheckboxNode,
    LabelNode,
    LineEditNode,
    Node,
    WindowNode,
)

if TYPE_CHECKING:
    from py_vui.commands.history import History
    from py_vui.model.document import ProjectDocument


class PropertyInspector(QWidget):
    document_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._doc: ProjectDocument | None = None
        self._history: History | None = None
        self._node_id: str | None = None
        self._block = False

        layout = QVBoxLayout(self)
        self._form = QFormLayout()
        self._name = QLineEdit()
        self._name.editingFinished.connect(self._apply)
        self._text = QLineEdit()
        self._text.editingFinished.connect(self._apply)
        self._placeholder = QLineEdit()
        self._placeholder.editingFinished.connect(self._apply)
        self._checked = QCheckBox()
        self._checked.stateChanged.connect(self._apply)
        self._x = QSpinBox()
        self._x.setRange(-9999, 9999)
        self._x.valueChanged.connect(self._apply)
        self._y = QSpinBox()
        self._y.setRange(-9999, 9999)
        self._y.valueChanged.connect(self._apply)
        self._w = QSpinBox()
        self._w.setRange(1, 9999)
        self._w.valueChanged.connect(self._apply)
        self._h = QSpinBox()
        self._h.setRange(1, 9999)
        self._h.valueChanged.connect(self._apply)

        common = QGroupBox("Common")
        cf = QFormLayout(common)
        cf.addRow("Name", self._name)
        cf.addRow("X", self._x)
        cf.addRow("Y", self._y)
        cf.addRow("W", self._w)
        cf.addRow("H", self._h)
        layout.addWidget(common)

        props = QGroupBox("Properties")
        pf = QFormLayout(props)
        pf.addRow("Text", self._text)
        pf.addRow("Placeholder", self._placeholder)
        pf.addRow("Checked", self._checked)
        layout.addWidget(props)
        layout.addStretch()

    def bind(self, doc: ProjectDocument, history: History) -> None:
        self._doc = doc
        self._history = history

    def show_node(self, node_id: str | None) -> None:
        self._node_id = node_id
        self._block = True
        if not node_id or self._doc is None:
            self.setEnabled(False)
            self._block = False
            return
        self.setEnabled(True)
        node = self._doc.get_node(node_id)
        box = node.layout.box
        self._name.setText(node.name)
        self._x.setValue(int(box.x))
        self._y.setValue(int(box.y))
        self._w.setValue(int(box.w))
        self._h.setValue(int(box.h))

        self._text.setVisible(isinstance(node, (LabelNode, ButtonNode, LineEditNode, CheckboxNode)))
        self._placeholder.setVisible(isinstance(node, LineEditNode))
        self._checked.setVisible(isinstance(node, CheckboxNode))

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

    def _clone_with_edits(self, node: Node) -> Node:
        data = node.model_dump()
        data["name"] = self._name.text()
        data["layout"]["box"]["x"] = float(self._x.value())
        data["layout"]["box"]["y"] = float(self._y.value())
        data["layout"]["box"]["w"] = float(self._w.value())
        data["layout"]["box"]["h"] = float(self._h.value())

        if isinstance(node, WindowNode):
            data["props"]["title"] = self._text.text()
            data["props"]["width"] = float(self._w.value())
            data["props"]["height"] = float(self._h.value())
        elif isinstance(node, (LabelNode, ButtonNode, LineEditNode, CheckboxNode)):
            data["props"]["text"] = self._text.text()
        if isinstance(node, LineEditNode):
            data["props"]["placeholder"] = self._placeholder.text()
        if isinstance(node, CheckboxNode):
            data["props"]["checked"] = self._checked.isChecked()

        return node.__class__.model_validate(data)
