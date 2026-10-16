"""Reusable typed value editors shared by the inspector, dialogs and code panels.

Every editor exposes the same tiny protocol::

    valueChanged = Signal(object)   # emitted on user edits only
    set_value(value)                # programmatic update, never emits
    value() -> object

Colours come from the application palette so the editors follow the editor theme.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtGui import QColor, QFontDatabase, QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from py_vui.app.editor.ui_colors import ErrorLabel, error_color
from py_vui.core.registry import PropSpec

AssetImporter = Callable[[Path], str]

_INT_LIMIT = 1_000_000_000


def parse_color(text: str) -> QColor | None:
    """Return a valid QColor for ``#rgb``/``#rrggbb``/``#aarrggbb``/names, else None."""
    text = text.strip()
    if not text:
        return None
    c = QColor(text)
    return c if c.isValid() else None


class ValueEditor(QWidget):
    """Base class: documents the protocol and gives a default ``changed`` helper."""

    valueChanged = Signal(object)

    _mixed = False
    #: shown by editors that cannot render a "mixed" state any other way
    MIXED_TEXT = "— mixed —"

    def is_mixed(self) -> bool:
        return self._mixed

    def set_mixed(self, on: bool) -> None:
        """Show that a multi-selection disagrees on this field (call after ``set_value``)."""
        if on == self._mixed:
            return
        self._mixed = on
        self._show_mixed(on)

    def _clear_mixed(self) -> None:
        """Leave the mixed state (called by ``set_value`` and by every user edit)."""
        if self._mixed:
            self._mixed = False
            self._show_mixed(False)

    def _show_mixed(self, on: bool) -> None:  # pragma: no cover - overridden
        return

    def set_value(self, value: Any) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def value(self) -> Any:  # pragma: no cover - interface
        raise NotImplementedError

    def _margins(self) -> QHBoxLayout:
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        return lay


# --------------------------------------------------------------------------- simple editors
class TextEdit(ValueEditor):
    """Single-line (``multiline=False``) or multi-line string editor."""

    def __init__(self, multiline: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lay = self._margins()
        self._multi = multiline
        if multiline:
            self._w: QPlainTextEdit | QLineEdit = QPlainTextEdit()
            self._w.setFixedHeight(72)
            self._w.setTabChangesFocus(True)
            self._w.textChanged.connect(self._user)
        else:
            self._w = QLineEdit()
            self._w.textChanged.connect(self._user)
        self._placeholder = ""
        lay.addWidget(self._w)

    def _user(self, *_a: Any) -> None:
        self._clear_mixed()
        self.valueChanged.emit(self.value())

    def _show_mixed(self, on: bool) -> None:
        with QSignalBlocker(self._w):
            if on:
                self._placeholder = self._w.placeholderText()
                self._w.clear()
                self._w.setPlaceholderText(self.MIXED_TEXT)
            else:
                self._w.setPlaceholderText(self._placeholder)

    def set_value(self, value: Any) -> None:
        self._clear_mixed()
        text = "" if value is None else str(value)
        if text == self.value():
            return
        with QSignalBlocker(self._w):
            if isinstance(self._w, QPlainTextEdit):
                self._w.setPlainText(text)
            else:
                self._w.setText(text)

    def value(self) -> str:
        return self._w.toPlainText() if isinstance(self._w, QPlainTextEdit) else self._w.text()

    def set_placeholder(self, text: str) -> None:
        self._placeholder = text
        self._w.setPlaceholderText(text)


class NumberEdit(ValueEditor):
    """Int/float spin box. ``scrub_label()`` returns a label that edits the value by dragging."""

    def __init__(
        self,
        *,
        is_float: bool = False,
        minimum: float | None = None,
        maximum: float | None = None,
        decimals: int = 2,
        step: float | None = None,
        suffix: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        lay = self._margins()
        self._float = is_float
        lo = -_INT_LIMIT if minimum is None else minimum
        hi = _INT_LIMIT if maximum is None else maximum
        self._lo = lo
        if is_float:
            self._spin: QSpinBox | QDoubleSpinBox = QDoubleSpinBox()
            self._spin.setDecimals(decimals)
            self._spin.setRange(float(lo), float(hi))
            self._spin.setSingleStep(step or 0.1)
        else:
            self._spin = QSpinBox()
            self._spin.setRange(int(lo), int(hi))
            self._spin.setSingleStep(int(step or 1))
        if suffix:
            self._spin.setSuffix(suffix)
        self._spin.setKeyboardTracking(True)
        self._spin.setButtonSymbols(QSpinBox.ButtonSymbols.UpDownArrows)
        self._spin.valueChanged.connect(self._user)
        lay.addWidget(self._spin)

    def _user(self, v: Any) -> None:
        if self._mixed and v == self._spin.minimum():
            return  # the "—" placeholder position, not a real value
        self._clear_mixed()
        self.valueChanged.emit(v)

    def _show_mixed(self, on: bool) -> None:
        with QSignalBlocker(self._spin):
            if on:
                low = self._lo - 1
                self._spin.setMinimum(low)  # type: ignore[arg-type]
                self._spin.setSpecialValueText("—")
                self._spin.setValue(low)  # type: ignore[arg-type]
            else:
                self._spin.setSpecialValueText("")
                self._spin.setMinimum(self._lo)  # type: ignore[arg-type]

    def set_range(self, lo: float, hi: float) -> None:
        self._clear_mixed()
        self._lo = lo
        self._spin.setRange(lo, hi)  # type: ignore[arg-type]

    def set_value(self, value: Any) -> None:
        self._clear_mixed()
        try:
            v = float(value) if self._float else int(float(value))
        except (TypeError, ValueError):
            v = 0.0 if self._float else 0
        with QSignalBlocker(self._spin):
            self._spin.setValue(v)  # type: ignore[arg-type]

    def value(self) -> float | int:
        return self._spin.value()

    def spin(self) -> QSpinBox | QDoubleSpinBox:
        return self._spin

    def scrub_label(self, text: str) -> QLabel:
        return ScrubLabel(text, self)


class ScrubLabel(QLabel):
    """Label that drags its NumberEdit up/down (horizontal drag, 1 step per 4 px)."""

    def __init__(self, text: str, target: NumberEdit) -> None:
        super().__init__(text)
        self._target = target
        self._press_x: int | None = None
        self._start = 0.0
        self.setCursor(Qt.CursorShape.SizeHorCursor)

    def mousePressEvent(self, e: QMouseEvent) -> None:
        self._press_x = int(e.position().x())
        self._start = float(self._target.value())

    def mouseMoveEvent(self, e: QMouseEvent) -> None:
        if self._press_x is None:
            return
        steps = (int(e.position().x()) - self._press_x) / 4
        sp = self._target.spin()
        self._target.set_value(self._start + steps * sp.singleStep())
        self._target.valueChanged.emit(self._target.value())

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:
        self._press_x = None


class BoolEdit(ValueEditor):
    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lay = self._margins()
        self._cb = QCheckBox(text)
        self._cb.stateChanged.connect(self._user)
        lay.addWidget(self._cb)

    def _user(self, state: int) -> None:
        if state == Qt.CheckState.PartiallyChecked.value:
            return
        self._clear_mixed()
        self.valueChanged.emit(self._cb.isChecked())

    def _show_mixed(self, on: bool) -> None:
        with QSignalBlocker(self._cb):
            if on:
                self._cb.setTristate(True)
                self._cb.setCheckState(Qt.CheckState.PartiallyChecked)
            else:
                self._cb.setTristate(False)

    def set_value(self, value: Any) -> None:
        self._clear_mixed()
        with QSignalBlocker(self._cb):
            self._cb.setChecked(bool(value))

    def value(self) -> bool:
        return self._cb.isChecked()


class ChoiceEdit(ValueEditor):
    """Combo box over string choices; the empty string is shown as ``empty_label``."""

    def __init__(
        self,
        choices: tuple[str, ...] | list[str],
        *,
        empty_label: str = "(default)",
        editable: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        lay = self._margins()
        self._empty = empty_label
        self._cb = QComboBox()
        self._cb.setEditable(editable)
        for c in choices:
            self._cb.addItem(c or empty_label, c)
        if editable:
            self._cb.editTextChanged.connect(self._user)
        self._cb.currentIndexChanged.connect(self._user)
        lay.addWidget(self._cb)

    _MIX = "\0mixed"

    def _user(self, *_a: Any) -> None:
        if self._mixed and self._cb.currentData() == self._MIX:
            return
        self._clear_mixed()
        self.valueChanged.emit(self.value())

    def _show_mixed(self, on: bool) -> None:
        with QSignalBlocker(self._cb):
            if on:
                self._cb.insertItem(0, "—", self._MIX)
                self._cb.setCurrentIndex(0)
            else:
                cur = self._cb.currentData()
                idx = self._cb.findData(self._MIX)
                if idx >= 0:
                    self._cb.removeItem(idx)
                if cur != self._MIX:
                    self._cb.setCurrentIndex(max(self._cb.findData(cur), 0))

    def set_choices(self, choices: list[str]) -> None:
        self._clear_mixed()
        with QSignalBlocker(self._cb):
            cur = self.value()
            self._cb.clear()
            for c in choices:
                self._cb.addItem(c or self._empty, c)
        self.set_value(cur)

    def set_value(self, value: Any) -> None:
        self._clear_mixed()
        v = "" if value is None else str(value)
        with QSignalBlocker(self._cb):
            idx = self._cb.findData(v)
            if idx < 0:
                self._cb.addItem(v or self._empty, v)
                idx = self._cb.count() - 1
            self._cb.setCurrentIndex(idx)

    def value(self) -> str:
        data = self._cb.currentData()
        if self._cb.isEditable() and self._cb.currentText() != self._cb.itemText(
            self._cb.currentIndex()
        ):
            return self._cb.currentText()
        return "" if data is None else str(data)

    def combo(self) -> QComboBox:
        return self._cb


class FontEdit(ChoiceEdit):
    """Font family chooser backed by QFontDatabase; empty = inherit from theme."""

    def __init__(self, parent: QWidget | None = None) -> None:
        families = [""] + list(QFontDatabase.families())
        super().__init__(families, empty_label="(theme font)", editable=False, parent=parent)
        self._cb.setMaxVisibleItems(20)


class RadioEdit(ValueEditor):
    """Horizontal radio group over (value, label) options."""

    def __init__(self, options: list[tuple[str, str]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lay = self._margins()
        self._group = QButtonGroup(self)
        self._buttons: dict[str, QRadioButton] = {}
        for value, text in options:
            b = QRadioButton(text)
            self._group.addButton(b)
            self._buttons[value] = b
            lay.addWidget(b)
            b.toggled.connect(lambda on, v=value: on and self._user(v))
        lay.addStretch(1)

    def _user(self, v: str) -> None:
        self._clear_mixed()
        self.valueChanged.emit(v)

    def _show_mixed(self, on: bool) -> None:
        if not on:
            return
        self._group.setExclusive(False)
        for b in self._buttons.values():
            with QSignalBlocker(b):
                b.setChecked(False)
        self._group.setExclusive(True)

    def set_value(self, value: Any) -> None:
        self._clear_mixed()
        b = self._buttons.get(str(value))
        if b is None:
            return
        with QSignalBlocker(b):
            b.setChecked(True)

    def value(self) -> str:
        for v, b in self._buttons.items():
            if b.isChecked():
                return v
        return ""

    def button(self, value: str) -> QRadioButton:
        return self._buttons[value]


# --------------------------------------------------------------------------- colour
class ColorEdit(ValueEditor):
    """Swatch button (QColorDialog) + hex field + clear button. Empty value = inherit."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lay = self._margins()
        self._fallback = ""
        self._btn = QToolButton()
        self._btn.setFixedSize(26, 22)
        self._btn.setToolTip("Pick a colour")
        self._btn.clicked.connect(self._pick)
        self._hex = QLineEdit()
        self._hex.setPlaceholderText("theme")
        self._hex.setMaxLength(9)
        self._hex.textEdited.connect(self._typed)
        self._clear = QToolButton()
        self._clear.setText("✕")
        self._clear.setToolTip("Clear (use theme colour)")
        self._clear.clicked.connect(self._cleared)
        lay.addWidget(self._btn)
        lay.addWidget(self._hex, 1)
        lay.addWidget(self._clear)
        self._paint()

    def set_fallback(self, color: str) -> None:
        """Colour previewed in the swatch while the value is empty."""
        self._fallback = color
        self._paint()

    def _show_mixed(self, on: bool) -> None:
        with QSignalBlocker(self._hex):
            if on:
                self._hex.clear()
            self._hex.setPlaceholderText(self.MIXED_TEXT if on else "theme")
        self._paint()

    def set_value(self, value: Any) -> None:
        self._clear_mixed()
        text = "" if not value else str(value)
        if text != self._hex.text():
            with QSignalBlocker(self._hex):
                self._hex.setText(text)
        self._paint()

    def value(self) -> str:
        return self._hex.text().strip()

    def _paint(self) -> None:
        c = parse_color(self._hex.text()) or parse_color(self._fallback)
        if c is None:
            self._btn.setStyleSheet("")
            self._btn.setText("∅")
            return
        self._btn.setText("")
        empty = not self._hex.text().strip()
        border = "1px dashed palette(mid)" if empty else "1px solid palette(mid)"
        self._btn.setStyleSheet(f"background:{c.name(QColor.NameFormat.HexArgb)};border:{border};")

    def _typed(self, text: str) -> None:
        text = text.strip()
        if text and parse_color(text) is None:
            self._hex.setStyleSheet(f"border:1px solid {error_color(self.palette()).name()};")
            return
        self._hex.setStyleSheet("")
        self._clear_mixed()
        self._paint()
        self.valueChanged.emit(text)

    def _cleared(self) -> None:
        self.set_value("")
        self.valueChanged.emit("")

    def _pick(self) -> None:
        start = parse_color(self._hex.text()) or parse_color(self._fallback) or QColor("#ffffff")
        c = QColorDialog.getColor(
            start, self, "Choose colour", QColorDialog.ColorDialogOption.ShowAlphaChannel
        )
        if c.isValid():
            text = c.name() if c.alpha() == 255 else c.name(QColor.NameFormat.HexArgb)
            self.set_value(text)
            self.valueChanged.emit(text)


# --------------------------------------------------------------------------- list
class ListEdit(ValueEditor):
    """Editable list with add / remove / move up / move down."""

    def __init__(
        self, *, numeric: bool = False, add_default: str | None = None,
        height: int = 92, parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._numeric = numeric
        self._add_default = add_default
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(2)
        self._list = QListWidget()
        self._list.setFixedHeight(height)
        self._list.itemChanged.connect(lambda _i: self._emit())
        outer.addWidget(self._list)
        row = QHBoxLayout()
        row.setSpacing(2)
        for text, tip, slot in (
            ("+", "Add item", self._add),
            ("−", "Remove selected", self._remove),
            ("↑", "Move up", lambda: self._move(-1)),
            ("↓", "Move down", lambda: self._move(1)),
        ):
            b = QToolButton()
            b.setText(text)
            b.setToolTip(tip)
            b.clicked.connect(slot)
            row.addWidget(b)
        row.addStretch(1)
        outer.addLayout(row)

    def _item(self, text: str) -> QListWidgetItem:
        it = QListWidgetItem(text)
        it.setFlags(it.flags() | Qt.ItemFlag.ItemIsEditable)
        return it

    def _show_mixed(self, on: bool) -> None:
        with QSignalBlocker(self._list):
            self._list.clear()
            if on:
                it = QListWidgetItem(self.MIXED_TEXT)
                it.setFlags(Qt.ItemFlag.NoItemFlags)
                self._list.addItem(it)

    def set_value(self, value: Any) -> None:
        self._clear_mixed()
        items = [str(v) for v in value] if isinstance(value, list | tuple) else []
        if items == [self._list.item(i).text() for i in range(self._list.count())]:
            return
        with QSignalBlocker(self._list):
            self._list.clear()
            for t in items:
                self._list.addItem(self._item(t))

    def value(self) -> list[Any]:
        out: list[Any] = []
        if self._mixed:
            return out
        for i in range(self._list.count()):
            t = self._list.item(i).text()
            if self._numeric:
                try:
                    out.append(int(t))
                except ValueError:
                    try:
                        out.append(float(t))
                    except ValueError:
                        out.append(0)
            else:
                out.append(t)
        return out

    def _emit(self) -> None:
        self._clear_mixed()
        self.valueChanged.emit(self.value())

    def _add(self) -> None:
        self._clear_mixed()
        n = self._list.count() + 1
        default = self._add_default or ("100" if self._numeric else f"Item {n}")
        it = self._item(default)
        self._list.addItem(it)
        self._list.setCurrentItem(it)
        self._emit()

    def _remove(self) -> None:
        if self._mixed:
            return
        row = self._list.currentRow()
        if row >= 0:
            self._list.takeItem(row)
            self._emit()

    def _move(self, delta: int) -> None:
        if self._mixed:
            return
        row = self._list.currentRow()
        new = row + delta
        if row < 0 or not 0 <= new < self._list.count():
            return
        with QSignalBlocker(self._list):
            it = self._list.takeItem(row)
            self._list.insertItem(new, it)
            self._list.setCurrentRow(new)
        self._emit()

    def list_widget(self) -> QListWidget:
        return self._list


# --------------------------------------------------------------------------- json
class JsonEdit(ValueEditor):
    """JSON editor with live validation. Only valid documents are emitted."""

    def __init__(self, height: int = 90, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        self._edit = QPlainTextEdit()
        self._edit.setFixedHeight(height)
        self._edit.setTabChangesFocus(True)
        mono = self._edit.font()
        mono.setFamily("Menlo")
        mono.setStyleHint(mono.StyleHint.Monospace)
        self._edit.setFont(mono)
        self._status = ErrorLabel("")
        self._edit.textChanged.connect(self._changed)
        lay.addWidget(self._edit)
        lay.addWidget(self._status)
        self._valid = True

    def error(self) -> str:
        return self._status.text()

    def is_valid(self) -> bool:
        return self._valid

    def _show_mixed(self, on: bool) -> None:
        with QSignalBlocker(self._edit):
            if on:
                self._edit.clear()
            self._edit.setPlaceholderText(self.MIXED_TEXT if on else "")
        self._valid = True
        self._status.setText("")

    def set_value(self, value: Any) -> None:
        self._clear_mixed()
        try:
            if self._valid and json.loads(self._edit.toPlainText() or "null") == value:
                return
        except ValueError:
            pass
        with QSignalBlocker(self._edit):
            self._edit.setPlainText(json.dumps(value, indent=2, ensure_ascii=False))
        self._valid = True
        self._status.setText("")

    def value(self) -> Any:
        try:
            return json.loads(self._edit.toPlainText() or "null")
        except ValueError:
            return None

    def setText(self, text: str) -> None:
        self._edit.setPlainText(text)

    def _changed(self) -> None:
        try:
            val = json.loads(self._edit.toPlainText() or "null")
        except ValueError as exc:
            self._valid = False
            self._status.setText(f"Invalid JSON: {exc}")
            return
        self._valid = True
        self._status.setText("")
        self._clear_mixed()
        self.valueChanged.emit(val)


# --------------------------------------------------------------------------- file / image
class FileEdit(ValueEditor):
    """Path field with a browse button; ``importer`` copies picked files into the project."""

    importer: AssetImporter | None

    def __init__(
        self, *, image: bool = False, importer: AssetImporter | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._image = image
        self.importer = importer
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(2)
        row = QHBoxLayout()
        row.setSpacing(4)
        self._line = QLineEdit()
        self._line.setPlaceholderText("image path" if image else "file path")
        self._line.textChanged.connect(self._typed)
        self._browse = QToolButton()
        self._browse.setText("…")
        self._browse.clicked.connect(self._choose)
        row.addWidget(self._line, 1)
        row.addWidget(self._browse)
        outer.addLayout(row)
        self._preview = QLabel()
        self._preview.setVisible(False)
        self._preview.setFrameShape(QFrame.Shape.StyledPanel)
        outer.addWidget(self._preview)
        self.project_dir: Path | None = None

    def _show_mixed(self, on: bool) -> None:
        with QSignalBlocker(self._line):
            if on:
                self._line.clear()
            self._line.setPlaceholderText(
                self.MIXED_TEXT if on else ("image path" if self._image else "file path"))
        self._update_preview()

    def set_value(self, value: Any) -> None:
        self._clear_mixed()
        text = "" if not value else str(value)
        if text != self._line.text():
            with QSignalBlocker(self._line):
                self._line.setText(text)
        self._update_preview()

    def value(self) -> str:
        return self._line.text()

    def _typed(self, text: str) -> None:
        self._clear_mixed()
        self._update_preview()
        self.valueChanged.emit(text)

    def _update_preview(self) -> None:
        if not self._image:
            return
        text = self._line.text().strip()
        path = Path(text) if text else None
        if path is not None and not path.is_absolute() and self.project_dir is not None:
            path = self.project_dir / path
        pm = QPixmap(str(path)) if path is not None and path.is_file() else QPixmap()
        if pm.isNull():
            self._preview.setVisible(False)
            return
        self._preview.setPixmap(pm.scaledToHeight(48, Qt.TransformationMode.SmoothTransformation))
        self._preview.setVisible(True)

    def pick(self, path: Path) -> None:
        """Programmatic equivalent of choosing ``path`` in the dialog (also used by tests)."""
        text = str(path)
        if self.importer is not None:
            try:
                text = self.importer(path)
            except Exception:
                text = str(path)
        self.set_value(text)
        self.valueChanged.emit(text)

    def _choose(self) -> None:
        flt = (
            "Images (*.png *.jpg *.jpeg *.gif *.bmp *.svg *.ico *.webp);;All files (*)"
            if self._image else "All files (*)"
        )
        fn, _ = QFileDialog.getOpenFileName(self, "Choose file", "", flt)
        if fn:
            self.pick(Path(fn))


# --------------------------------------------------------------------------- misc
class SplitterLabel(QWidget):
    """Section heading with a rule: ``Title ─────``."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 6, 0, 2)
        lay.setSpacing(6)
        self._label = QLabel(text.upper())
        f = self._label.font()
        f.setBold(True)
        f.setPointSizeF(max(f.pointSizeF() - 1, 7))
        self._label.setFont(f)
        self._label.setEnabled(False)
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        lay.addWidget(self._label)
        lay.addWidget(line, 1)

    def setText(self, text: str) -> None:
        self._label.setText(text.upper())


def small_button(text: str, tip: str = "") -> QPushButton:
    b = QPushButton(text)
    b.setToolTip(tip)
    b.setAutoDefault(False)
    return b


def make_editor(
    spec: PropSpec,
    *,
    importer: AssetImporter | None = None,
    sample: Any = None,
) -> ValueEditor:
    """Build the right editor for ``spec.kind``. ``sample`` is the current value (for list typing)."""
    kind = spec.kind
    if kind == "text":
        return TextEdit(multiline=True)
    if kind == "int":
        return NumberEdit(minimum=spec.minimum, maximum=spec.maximum)
    if kind == "float":
        return NumberEdit(is_float=True, minimum=spec.minimum, maximum=spec.maximum)
    if kind == "bool":
        return BoolEdit()
    if kind == "choice":
        return ChoiceEdit(spec.choices)
    if kind == "color":
        return ColorEdit()
    if kind == "list":
        numeric = spec.name == "sizes" or (
            isinstance(spec.default, list)
            and bool(spec.default)
            and all(isinstance(v, int | float) and not isinstance(v, bool) for v in spec.default)
        )
        return ListEdit(numeric=numeric)
    if kind == "json":
        return JsonEdit()
    if kind in ("file", "image"):
        return FileEdit(image=kind == "image", importer=importer)
    return TextEdit()
