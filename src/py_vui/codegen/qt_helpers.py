"""Runtime helper snippets emitted into generated Qt apps (only the ones that are used).

Every snippet is plain python text; ``@SIGNAL@`` is replaced by ``Signal`` / ``pyqtSignal``.
"""

from __future__ import annotations

HELPERS: dict[str, str] = {}
#: emission order (dependencies first)
ORDER = (
    "asset", "fill", "events", "anchors", "flow", "canvas", "stacked", "image", "switch", "color_button",
    "connect_any",
)

HELPERS["asset"] = '''\
def _asset(path):
    """Resolve an asset path relative to this script (works from any working directory)."""
    if os.path.isabs(path):
        return path
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
'''

HELPERS["fill"] = '''\
def _fill_table(table, rows):
    """Fill a QTableWidget from a list of rows."""
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            table.setItem(r, c, QTableWidgetItem(str(value)))


def _fill_tree(parent, items):
    """Recursively add ``{"text": ..., "children": [...]}`` entries to a QTreeWidget."""
    for spec in items:
        if isinstance(spec, str):
            spec = {"text": spec}
        item = QTreeWidgetItem(parent, [str(spec.get("text", ""))])
        _fill_tree(item, spec.get("children", []))
'''

HELPERS["events"] = '''\
_SIMPLE_EVENTS = {
    QEvent.Type.MouseButtonDblClick: "double_click",
    QEvent.Type.MouseMove: "mouse_move",
    QEvent.Type.Enter: "mouse_enter",
    QEvent.Type.Leave: "mouse_leave",
    QEvent.Type.Wheel: "mouse_wheel",
    QEvent.Type.KeyPress: "key_press",
    QEvent.Type.KeyRelease: "key_release",
    QEvent.Type.FocusIn: "focus_in",
    QEvent.Type.FocusOut: "focus_out",
    QEvent.Type.Resize: "resize",
    QEvent.Type.Show: "show",
    QEvent.Type.Hide: "hide",
    QEvent.Type.Close: "close",
}


class _Events(QObject):
    """Routes raw Qt events to handlers. Callbacks receive the QEvent."""

    def __init__(self, widget, callbacks):
        super().__init__(widget)
        self._callbacks = callbacks
        if widget.focusPolicy() == Qt.FocusPolicy.NoFocus and (
            "key_press" in callbacks or "key_release" in callbacks
        ):
            widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        targets = [widget]
        viewport = getattr(widget, "viewport", None)
        if callable(viewport):
            targets.append(viewport())
        for target in targets:
            if "mouse_move" in callbacks:
                target.setMouseTracking(True)
            target.installEventFilter(self)

    def eventFilter(self, obj, event):
        kind = event.type()
        keys = []
        if kind == QEvent.Type.MouseButtonPress:
            keys.append("mouse_press")
            if event.button() == Qt.MouseButton.RightButton:
                keys.append("right_click")
            elif event.button() == Qt.MouseButton.MiddleButton:
                keys.append("middle_click")
        elif kind == QEvent.Type.MouseButtonRelease:
            keys.append("mouse_release")
            if event.button() == Qt.MouseButton.LeftButton and obj.rect().contains(
                event.position().toPoint()
            ):
                keys.append("click")
        elif kind in _SIMPLE_EVENTS:
            keys.append(_SIMPLE_EVENTS[kind])
        for key in keys:
            callback = self._callbacks.get(key)
            if callback is not None:
                callback(event)
        if kind == QEvent.Type.Close and "close" in self._callbacks:
            return not event.isAccepted()  # a handler may call event.ignore() to veto
        return False
'''

HELPERS["anchors"] = '''\
class _Anchors(QObject):
    """Keeps right/bottom anchored children pinned to their container edges on resize."""

    def __init__(self, container, size):
        super().__init__(container)
        self._size = size  # (width, height) or a callable returning it (resolved lazily)
        self._items = []
        container.installEventFilter(self)

    def add(self, widget, x, y, w, h, left, top, right, bottom):
        self._items.append((widget, x, y, w, h, left, top, right, bottom))

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Resize:
            self.apply(event.size().width(), event.size().height())
        return False

    def apply(self, width, height):
        if callable(self._size):
            self._size = self._size()
        dx, dy = width - self._size[0], height - self._size[1]
        for widget, x, y, w, h, left, top, right, bottom in self._items:
            if left and right:
                nx, nw = x, w + dx
            elif right:
                nx, nw = x + dx, w
            elif left:
                nx, nw = x, w
            else:
                nx, nw = x + dx / 2, w
            if top and bottom:
                ny, nh = y, h + dy
            elif bottom:
                ny, nh = y + dy, h
            elif top:
                ny, nh = y, h
            else:
                ny, nh = y + dy / 2, h
            widget.setGeometry(round(nx), round(ny), max(1, round(nw)), max(1, round(nh)))
'''

HELPERS["flow"] = '''\
class _FlowLayout(QLayout):
    """Layout that wraps onto new rows (or columns when ``vertical``): flex ``wrap``."""

    def __init__(self, parent=None, margins=(0, 0, 0, 0), hspacing=8, vspacing=8,
                 vertical=False):
        super().__init__(parent)
        self._vertical = vertical
        self._items = []
        self._hspace = hspacing
        self._vspace = vspacing
        self.setContentsMargins(*margins)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return not self._vertical

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        return size + QSize(m.left() + m.right(), m.top() + m.bottom())

    def _do_layout(self, rect, test_only):
        m = self.contentsMargins()
        area = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        if self._vertical:
            x, y, column_width = area.x(), area.y(), 0
            for item in self._items:
                size = item.sizeHint()
                if y > area.y() and y + size.height() > area.bottom() + 1:
                    y = area.y()
                    x += column_width + self._hspace
                    column_width = 0
                if not test_only:
                    item.setGeometry(QRect(QPoint(x, y), size))
                y += size.height() + self._vspace
                column_width = max(column_width, size.width())
            return rect.height()
        x, y, line_height = area.x(), area.y(), 0
        for item in self._items:
            size = item.sizeHint()
            if x > area.x() and x + size.width() > area.right() + 1:
                x = area.x()
                y += line_height + self._vspace
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), size))
            x += size.width() + self._hspace
            line_height = max(line_height, size.height())
        return y + line_height - rect.y() + m.bottom()
'''

HELPERS["stacked"] = '''\
class _StackedButton(QPushButton):
    """Push button with its icon above (or below) the text."""

    def __init__(self, text, icon, below=False, parent=None):
        super().__init__(text, parent)
        self._below = below
        self.setIcon(icon)
        self.setIconSize(QSize(24, 24))

    def sizeHint(self):
        base = super().sizeHint()
        metrics = self.fontMetrics()
        width = max(metrics.horizontalAdvance(self.text()), self.iconSize().width()) + 28
        height = self.iconSize().height() + metrics.height() + 20
        return QSize(max(base.width(), width), max(base.height(), height))

    def paintEvent(self, event):
        painter = QStylePainter(self)
        option = QStyleOptionButton()
        self.initStyleOption(option)
        option.text = ""
        option.icon = QIcon()
        painter.drawControl(QStyle.ControlElement.CE_PushButton, option)
        icon_size = self.iconSize()
        text_height = self.fontMetrics().height()
        top = (self.height() - (icon_size.height() + 4 + text_height)) // 2
        if self._below:
            text_y, icon_y = top, top + text_height + 4
        else:
            icon_y, text_y = top, top + icon_size.height() + 4
        mode = QIcon.Mode.Normal if self.isEnabled() else QIcon.Mode.Disabled
        pixmap = self.icon().pixmap(icon_size, mode)
        ratio = pixmap.devicePixelRatio() or 1
        pw, ph = pixmap.width() / ratio, pixmap.height() / ratio
        painter.drawPixmap(
            int((self.width() - pw) / 2), int(icon_y + (icon_size.height() - ph) / 2), pixmap
        )
        painter.setPen(self.palette().color(QPalette.ColorRole.ButtonText))
        painter.drawText(
            QRectF(0, text_y, self.width(), text_height),
            self.text().replace("&&", "&"),
            QTextOption(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter),
        )
'''

HELPERS["canvas"] = '''\
class _PaintEvent:
    """Passed to the ``paint`` handler: draw with ``event.painter`` inside ``event.rect``."""

    def __init__(self, widget, painter, event):
        self.widget = widget
        self.painter = painter
        self.rect = widget.rect()
        self.event = event


class _Canvas(QWidget):
    """Free-drawing surface: the ``paint`` handler receives a QPainter-carrying event."""

    def __init__(self, parent=None, on_paint=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._on_paint = on_paint

    def paintEvent(self, event):
        painter = QPainter(self)
        option = QStyleOption()
        option.initFrom(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, option, painter, self)
        if self._on_paint is not None:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            try:
                self._on_paint(_PaintEvent(self, painter, event))
            finally:
                painter.end()
        else:
            painter.end()
'''

HELPERS["image"] = '''\
class _ImageLabel(QLabel):
    """QLabel showing an image with a fit mode: contain, stretch or none."""

    def __init__(self, path, fit="contain", alt="", parent=None):
        super().__init__(parent)
        self._fit = fit
        self._pixmap = QPixmap(path) if path else QPixmap()
        if self._pixmap.isNull():
            self.setText(alt)
            self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        elif fit == "stretch":
            self.setScaledContents(True)
            self.setPixmap(self._pixmap)
        elif fit == "none":
            self.setPixmap(self._pixmap)
            self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        else:
            self.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
            self.setMinimumSize(1, 1)
            self._rescale()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._fit == "contain" and not self._pixmap.isNull():
            self._rescale()

    def _rescale(self):
        self.setPixmap(
            self._pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
'''

HELPERS["switch"] = '''\
class _Switch(QCheckBox):
    """Checkable toggle drawn as a sliding pill."""

    def __init__(self, text="", parent=None, on_color="#2563eb", off_color="#d4d4d8"):
        super().__init__(text, parent)
        self._on = QColor(on_color)
        self._off = QColor(off_color)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def sizeHint(self):
        metrics = self.fontMetrics()
        extra = 8 + metrics.horizontalAdvance(self.text()) if self.text() else 0
        return QSize(40 + extra, max(24, metrics.height() + 4))

    def hitButton(self, pos):
        return self.rect().contains(pos)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.isEnabled():
            painter.setOpacity(0.5)
        top = (self.height() - 22) / 2
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._on if self.isChecked() else self._off)
        painter.drawRoundedRect(QRectF(0, top, 40, 22), 11, 11)
        painter.setBrush(QColor("#ffffff"))
        painter.drawEllipse(QRectF(21 if self.isChecked() else 3, top + 3, 16, 16))
        if self.text():
            painter.setPen(self.palette().color(QPalette.ColorRole.WindowText))
            painter.drawText(
                QRectF(48, 0, max(0, self.width() - 48), self.height()),
                self.text(),
                QTextOption(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            )
'''

HELPERS["color_button"] = '''\
class _ColorButton(QPushButton):
    """Button that opens a QColorDialog and shows the chosen colour as an icon swatch."""

    colorChanged = @SIGNAL@(str)

    def __init__(self, text="Pick color", color="#ff0000", parent=None):
        super().__init__(text, parent)
        self._color = color
        self._refresh()
        self.clicked.connect(self._pick)

    def color(self):
        return self._color

    def setColor(self, color):
        if color != self._color:
            self._color = color
            self._refresh()
            self.colorChanged.emit(color)

    def _pick(self, *_):
        chosen = QColorDialog.getColor(QColor(self._color), self)
        if chosen.isValid():
            self.setColor(chosen.name())

    def _refresh(self):
        swatch = QPixmap(16, 16)
        swatch.fill(QColor(self._color))
        self.setIcon(QIcon(swatch))
'''

HELPERS["connect_any"] = '''\
def _connect_any(widget, names, callback):
    """Connect ``callback`` to the first signal of ``widget`` named in ``names``."""
    for name in names:
        signal = getattr(widget, name, None)
        if signal is not None and hasattr(signal, "connect"):
            signal.connect(callback)
            return True
    return False
'''

#: helper name -> helpers it needs as well
DEPENDS: dict[str, tuple[str, ...]] = {}


def render(names: set[str], signal: str) -> str:
    parts = [HELPERS[n].replace("@SIGNAL@", signal) for n in ORDER if n in names]
    return "\n\n".join(parts)
