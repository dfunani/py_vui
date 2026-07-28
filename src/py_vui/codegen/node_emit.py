from __future__ import annotations

from py_vui.model.nodes import (
    ButtonNode,
    CheckboxNode,
    ComboBoxNode,
    DateEditNode,
    DialNode,
    GroupBoxNode,
    LabelNode,
    LineEditNode,
    ListWidgetNode,
    Node,
    ProgressBarNode,
    RadioButtonNode,
    ScrollAreaNode,
    SliderNode,
    SpinBoxNode,
    TableWidgetNode,
    TabWidgetNode,
    TextEditNode,
    TimeEditNode,
    ToolButtonNode,
    WindowNode,
)
from py_vui.model.project import py_vuiProject
from py_vui.model.theme import stylesheet_for_node


def widget_ctor(node: Node) -> tuple[str, str]:
    table: dict[str, tuple[str, str]] = {
        "window": ("QWidget", "QWidget()"),
        "frame": ("QFrame", "QFrame()"),
        "label": ("QLabel", "QLabel()"),
        "button": ("QPushButton", "QPushButton()"),
        "line_edit": ("QLineEdit", "QLineEdit()"),
        "checkbox": ("QCheckBox", "QCheckBox()"),
        "combo_box": ("QComboBox", "QComboBox()"),
        "text_edit": ("QTextEdit", "QTextEdit()"),
        "radio_button": ("QRadioButton", "QRadioButton()"),
        "spin_box": ("QSpinBox", "QSpinBox()"),
        "slider": ("QSlider", "QSlider()"),
        "list_widget": ("QListWidget", "QListWidget()"),
        "group_box": ("QGroupBox", "QGroupBox()"),
        "tab_widget": ("QTabWidget", "QTabWidget()"),
        "progress_bar": ("QProgressBar", "QProgressBar()"),
        "scroll_area": ("QScrollArea", "QScrollArea()"),
        "date_edit": ("QDateEdit", "QDateEdit()"),
        "time_edit": ("QTimeEdit", "QTimeEdit()"),
        "table_widget": ("QTableWidget", "QTableWidget()"),
        "dial": ("QDial", "QDial()"),
        "tool_button": ("QToolButton", "QToolButton()"),
    }
    try:
        return table[node.type]
    except KeyError as exc:
        msg = f"unsupported node type: {node.type!r}"
        raise ValueError(msg) from exc


def extra_imports(project: py_vuiProject) -> set[str]:
    extras: set[str] = set()
    for node in project.nodes.values():
        if isinstance(node, TabWidgetNode):
            extras.add("QWidget")
        if isinstance(node, WindowNode) and node.props.menus:
            extras.update({"QMenu", "QMenuBar"})
    return extras


def props_lines(project: py_vuiProject, node: Node, var: str) -> list[str]:
    theme = project.theme
    lines: list[str] = []
    b = node.layout.box
    lines.append(f"{var}.setGeometry(int({b.x}), int({b.y}), int({b.w}), int({b.h}))")
    if not node.enabled:
        lines.append(f"{var}.setEnabled(False)")
    if node.tooltip:
        lines.append(f"{var}.setToolTip({node.tooltip!r})")
    qss = stylesheet_for_node(theme=theme, node_type=node.type, style=node.style)
    if qss:
        lines.append(f"{var}.setStyleSheet({qss!r})")
    if isinstance(node, WindowNode):
        p = node.props
        lines.append(f"{var}.setWindowTitle({p.title!r})")
        lines.append(f"{var}.resize(int({p.width}), int({p.height}))")
    elif isinstance(node, LabelNode):
        lines.append(f"{var}.setText({node.props.text!r})")
    elif isinstance(node, ButtonNode):
        lines.append(f"{var}.setText({node.props.text!r})")
    elif isinstance(node, LineEditNode):
        lines.append(f"{var}.setText({node.props.text!r})")
        lines.append(f"{var}.setPlaceholderText({node.props.placeholder!r})")
    elif isinstance(node, CheckboxNode):
        lines.append(f"{var}.setText({node.props.text!r})")
        lines.append(f"{var}.setChecked({str(node.props.checked)})")
    elif isinstance(node, ComboBoxNode):
        lines.append(f"{var}.addItems({node.props.items!r})")
        lines.append(f"{var}.setCurrentIndex({node.props.current_index})")
    elif isinstance(node, TextEditNode):
        lines.append(f"{var}.setPlainText({node.props.text!r})")
        if node.props.placeholder:
            lines.append(f"{var}.setPlaceholderText({node.props.placeholder!r})")
    elif isinstance(node, RadioButtonNode):
        lines.append(f"{var}.setText({node.props.text!r})")
        lines.append(f"{var}.setChecked({str(node.props.checked)})")
    elif isinstance(node, SpinBoxNode):
        p = node.props
        lines.append(f"{var}.setRange({p.min}, {p.max})")
        lines.append(f"{var}.setValue({p.value})")
    elif isinstance(node, SliderNode):
        p = node.props
        lines.append(f"{var}.setOrientation(Qt.Orientation.Horizontal)")
        lines.append(f"{var}.setRange({p.min}, {p.max})")
        lines.append(f"{var}.setValue({p.value})")
    elif isinstance(node, ListWidgetNode):
        for item in node.props.items:
            lines.append(f"{var}.addItem({item!r})")
    elif isinstance(node, GroupBoxNode):
        lines.append(f"{var}.setTitle({node.props.title!r})")
    elif isinstance(node, TabWidgetNode):
        lines.append(f"{var}.setCurrentIndex({node.props.current_index})")
    elif isinstance(node, ProgressBarNode):
        p = node.props
        lines.append(f"{var}.setMaximum({p.max})")
        lines.append(f"{var}.setValue({p.value})")
    elif isinstance(node, ScrollAreaNode):
        lines.append(f"{var}.setWidgetResizable(True)")
    elif isinstance(node, DateEditNode):
        lines.append(f"{var}.setDate(QDate.fromString({node.props.date!r}, 'yyyy-MM-dd'))")
        lines.append(f"{var}.setCalendarPopup(True)")
    elif isinstance(node, TimeEditNode):
        lines.append(f"{var}.setTime(QTime.fromString({node.props.time!r}, 'HH:mm:ss'))")
    elif isinstance(node, TableWidgetNode):
        p = node.props
        lines.append(f"{var}.setRowCount({p.rows})")
        lines.append(f"{var}.setColumnCount({p.columns})")
    elif isinstance(node, DialNode):
        p = node.props
        lines.append(f"{var}.setRange({p.min}, {p.max})")
        lines.append(f"{var}.setValue({p.value})")
    elif isinstance(node, ToolButtonNode):
        lines.append(f"{var}.setText({node.props.text!r})")
    return lines
