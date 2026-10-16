"""Shared building blocks for the PySide6 / PyQt6 adapters.

Nothing here imports Qt: it only produces *source text* (QSS, palette code, import lines).
"""

from __future__ import annotations

import io
import keyword
import re
import tokenize
from dataclasses import dataclass
from pprint import pformat
from typing import Any

from py_vui.core.model import Node, Project
from py_vui.core.theme import ProjectTheme, resolve_style


@dataclass(frozen=True)
class Binding:
    """The only things that differ between the two Python Qt bindings."""

    framework: str
    package: str  # import root, e.g. "PySide6"
    signal: str  # "Signal" / "pyqtSignal"
    label: str
    requirement: str


PYSIDE6 = Binding("pyside6", "PySide6", "Signal", "PySide6 (Qt for Python)", "PySide6>=6.6")
PYQT6 = Binding("pyqt6", "PyQt6", "pyqtSignal", "PyQt6", "PyQt6>=6.6")

# Qt names the generated code may use -> sub-module they live in (same in both bindings, Qt 6).
_CORE = ["Qt", "QObject", "QEvent", "QDate", "QTime", "QPoint", "QRect", "QRectF", "QSize", "QTimer", "QMargins"]
_GUI = ["QAction", "QColor", "QFont", "QIcon", "QPixmap", "QPainter", "QKeySequence", "QPalette", "QTextOption", "QPen", "QBrush", "QCursor"]
_WIDGETS = ["QApplication", "QWidget", "QMainWindow", "QDialog", "QFrame", "QGroupBox", "QTabWidget", "QScrollArea", "QSplitter", "QLabel", "QPushButton", "QToolButton", "QLineEdit", "QPlainTextEdit", "QCheckBox", "QRadioButton", "QButtonGroup", "QSlider", "QDial", "QSpinBox", "QDoubleSpinBox", "QComboBox", "QListWidget", "QAbstractItemView", "QDateEdit", "QTimeEdit", "QTableWidget", "QTableWidgetItem", "QTreeWidget", "QTreeWidgetItem", "QCalendarWidget", "QProgressBar", "QColorDialog", "QVBoxLayout", "QHBoxLayout", "QGridLayout", "QLayout", "QSizePolicy", "QToolTip", "QMenu", "QMenuBar", "QStyle", "QStyleOption", "QStylePainter", "QStyleOptionButton"]

QT_MODULES: dict[str, str] = {
    **dict.fromkeys(_CORE, "QtCore"),
    **dict.fromkeys(_GUI, "QtGui"),
    **dict.fromkeys(_WIDGETS, "QtWidgets"),
}

HEADER_DOC = "py_vui generated Qt user interface"


def import_lines(code: str, binding: Binding) -> list[str]:
    """``from <pkg>.<mod> import ...`` lines for every Qt name actually used in ``code``."""
    names: set[str] = set()
    try:
        for tok in tokenize.generate_tokens(io.StringIO(code).readline):
            if tok.type == tokenize.NAME:
                names.add(tok.string)
    except (tokenize.TokenError, IndentationError):  # pragma: no cover - defensive
        names = set(re.findall(r"[A-Za-z_]\w*", code))
    by_mod: dict[str, set[str]] = {}
    for n in names:
        mod = QT_MODULES.get(n)
        if mod:
            by_mod.setdefault(mod, set()).add(n)
    if binding.signal in names:
        by_mod.setdefault("QtCore", set()).add(binding.signal)
    out = []
    for mod in ("QtCore", "QtGui", "QtWidgets"):
        if mod in by_mod:
            out.append(_wrap_import(f"{binding.package}.{mod}", sorted(by_mod[mod])))
    return out


def _wrap_import(module: str, names: list[str]) -> str:
    one = f"from {module} import {', '.join(names)}"
    if len(one) <= 96:
        return one
    body = "".join(f"    {n},\n" for n in names)
    return f"from {module} import (\n{body})"


# ----------------------------------------------------------------------------- literals
def lit(value: Any) -> str:
    """Deterministic python literal (multi-line for big containers)."""
    if isinstance(value, (list, tuple, dict)) and len(repr(value)) > 70:
        return pformat(value, width=72, compact=True, sort_dicts=False)
    return repr(value)


def num(value: Any, default: float = 0) -> int | float:
    """int when integral else float (for readable ``setRange(0, 100)`` lines)."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        f = float(default)
    return int(f) if f == int(f) else f


def to_int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


def py_names(names: dict[str, str]) -> dict[str, str]:
    """Make ``ProjectDocument.variable_names()`` safe as python locals (keywords, builtins)."""
    reserved = set(keyword.kwlist) | {
        "list", "dict", "str", "int", "float", "set", "len", "range", "print", "type", "id",
        "object", "property", "super", "min", "max", "sum", "any", "all", "map", "filter",
        "open", "round", "sorted", "enumerate", "zip", "isinstance", "getattr", "hasattr",
        "handlers", "theme", "ui", "custom", "event", "build_ui", "start", "app", "sys",
        "os", "self", "root",
    }
    out: dict[str, str] = {}
    used: set[str] = set()
    for nid, name in names.items():
        cand = f"{name}_w" if name in reserved else name
        base, i = cand, 2
        while cand in used or cand in reserved:
            cand = f"{base}_{i}"
            i += 1
        used.add(cand)
        out[nid] = cand
    return out


def asset_path(project: Project, value: str) -> str:
    """Normalise an image/icon prop to the ``assets/<file>`` path used by generated apps."""
    v = (value or "").replace("\\", "/").strip()
    if not v:
        return ""
    base = v.rsplit("/", 1)[-1]
    if v.startswith("assets/"):
        return v
    if v.startswith("/") or re.match(r"^[A-Za-z]:/", v):  # absolute -> copied into assets/
        known = {a.replace("\\", "/").rsplit("/", 1)[-1] for a in project.assets}
        return f"assets/{base}" if base in known else v
    if "/" not in v:
        return f"assets/{v}"
    return v


# ------------------------------------------------------------------------------ colours
_COLOR_RE = re.compile(r"^[#A-Za-z0-9(),.% ]{1,40}$")


def css_color(value: Any, fallback: str = "") -> str:
    v = str(value or "").strip()
    return v if _COLOR_RE.match(v) else fallback


def css_font(value: Any) -> str:
    return re.sub(r'["\\\']', "", str(value or "")).strip()


# ---------------------------------------------------------------------------- app theme
def base_qss(t: ProjectTheme) -> str:
    """Application-wide stylesheet derived from the project theme (all widgets covered)."""
    c = {
        "P": css_color(t.primary, "#2563eb"),
        "PH": css_color(t.primary_hover, "#1d4ed8"),
        "BG": css_color(t.background, "#f4f4f5"),
        "SF": css_color(t.surface, "#ffffff"),
        "TX": css_color(t.text, "#18181b"),
        "MU": css_color(t.muted_text, "#71717a"),
        "BT": css_color(t.button_text, "#ffffff"),
        "BD": css_color(t.border, "#d4d4d8"),
    }
    r = t.button_radius
    bw = t.border_width
    fam = css_font(t.font_family) or "sans-serif"
    q = f"""\
* {{ font-family: "{fam}"; font-size: {t.font_size}px; }}
QWidget {{ color: {c['TX']}; }}
QLabel {{ background: transparent; }}
QToolTip {{ background-color: {c['SF']}; color: {c['TX']}; border: 1px solid {c['BD']}; \
padding: 3px; }}

QPushButton, QToolButton {{ background-color: {c['P']}; color: {c['BT']}; border: none; \
border-radius: {r}px; padding: 5px 14px; }}
QPushButton:hover, QToolButton:hover {{ background-color: {c['PH']}; }}
QPushButton:pressed, QToolButton:pressed {{ background-color: {c['PH']}; }}
QPushButton:checked, QToolButton:checked {{ background-color: {c['PH']}; }}
QPushButton:disabled, QToolButton:disabled {{ background-color: {c['BD']}; color: {c['MU']}; }}

QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QDateEdit, QTimeEdit, \
QComboBox {{
    background-color: {c['SF']}; color: {c['TX']}; border: {bw}px solid {c['BD']};
    border-radius: 4px; padding: 3px 6px;
    selection-background-color: {c['P']}; selection-color: {c['BT']};
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, \
QDateEdit:focus, QTimeEdit:focus, QComboBox:focus {{ border-color: {c['P']}; }}
QLineEdit:disabled, QPlainTextEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, \
QDateEdit:disabled, QTimeEdit:disabled, QComboBox:disabled {{ color: {c['MU']}; \
background-color: {c['BG']}; }}
QComboBox QAbstractItemView {{ background-color: {c['SF']}; color: {c['TX']}; \
border: 1px solid {c['BD']}; selection-background-color: {c['P']}; \
selection-color: {c['BT']}; outline: 0; }}

QListWidget, QTableWidget, QTreeWidget {{
    background-color: {c['SF']}; color: {c['TX']}; border: {bw}px solid {c['BD']};
    border-radius: 4px; outline: 0; gridline-color: {c['BD']};
    selection-background-color: {c['P']}; selection-color: {c['BT']};
    alternate-background-color: {c['BG']};
}}
QListWidget::item, QTreeWidget::item {{ padding: 2px 4px; }}
QHeaderView::section {{ background-color: {c['BG']}; color: {c['TX']}; border: none; \
border-bottom: 1px solid {c['BD']}; padding: 4px 6px; }}
QTableCornerButton::section {{ background-color: {c['BG']}; border: none; }}

QTabWidget::pane {{ border: {bw}px solid {c['BD']}; background-color: {c['SF']}; top: -1px; }}
QTabBar::tab {{ background-color: {c['BG']}; color: {c['MU']}; padding: 6px 14px; \
border: 1px solid {c['BD']}; border-bottom: none; border-top-left-radius: 4px; \
border-top-right-radius: 4px; margin-right: 2px; }}
QTabBar::tab:selected {{ background-color: {c['SF']}; color: {c['TX']}; }}
QTabBar::tab:hover:!selected {{ color: {c['TX']}; }}

QGroupBox {{ background-color: {c['SF']}; border: {bw}px solid {c['BD']}; \
border-radius: 6px; margin-top: 10px; padding-top: 6px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; color: {c['TX']}; }}

QProgressBar {{ background-color: {c['SF']}; border: {bw}px solid {c['BD']}; \
border-radius: 4px; text-align: center; color: {c['TX']}; }}
QProgressBar::chunk {{ background-color: {c['P']}; border-radius: 3px; }}

QSlider::groove:horizontal {{ height: 4px; background: {c['BD']}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {c['P']}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {c['P']}; width: 16px; height: 16px; \
margin: -6px 0; border-radius: 8px; }}
QSlider::groove:vertical {{ width: 4px; background: {c['BD']}; border-radius: 2px; }}
QSlider::add-page:vertical {{ background: {c['P']}; border-radius: 2px; }}
QSlider::handle:vertical {{ background: {c['P']}; width: 16px; height: 16px; \
margin: 0 -6px; border-radius: 8px; }}

QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {c['BD']}; border-radius: 5px; min-height: 24px; }}
QScrollBar::handle:vertical:hover {{ background: {c['MU']}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 0; }}
QScrollBar::handle:horizontal {{ background: {c['BD']}; border-radius: 5px; min-width: 24px; }}
QScrollBar::handle:horizontal:hover {{ background: {c['MU']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QSplitter::handle {{ background-color: {c['BD']}; }}
QSplitter::handle:horizontal {{ width: 3px; }}
QSplitter::handle:vertical {{ height: 3px; }}

QMenuBar {{ background-color: {c['SF']}; color: {c['TX']}; border-bottom: 1px solid {c['BD']}; }}
QMenuBar::item {{ padding: 4px 10px; background: transparent; }}
QMenuBar::item:selected {{ background-color: {c['BG']}; }}
QMenu {{ background-color: {c['SF']}; color: {c['TX']}; border: 1px solid {c['BD']}; \
padding: 4px; }}
QMenu::item {{ padding: 5px 24px; border-radius: 3px; }}
QMenu::item:selected {{ background-color: {c['P']}; color: {c['BT']}; }}
QMenu::item:disabled {{ color: {c['MU']}; }}
QMenu::separator {{ height: 1px; background: {c['BD']}; margin: 4px 8px; }}

QCalendarWidget QToolButton {{ background-color: transparent; color: {c['TX']}; }}
QCalendarWidget QToolButton:hover {{ background-color: {c['BG']}; }}
QCalendarWidget QMenu {{ background-color: {c['SF']}; }}
QCalendarWidget QSpinBox {{ background-color: {c['SF']}; }}
QCalendarWidget QWidget#qt_calendar_navigationbar {{ background-color: {c['BG']}; }}
QCalendarWidget QAbstractItemView {{ background-color: {c['SF']}; color: {c['TX']}; \
selection-background-color: {c['P']}; selection-color: {c['BT']}; outline: 0; }}
QCalendarWidget QAbstractItemView:disabled {{ color: {c['MU']}; }}
"""
    return q


def theme_code(project: Project) -> str:
    """Python source (no imports) defining ``STYLESHEET``, ``make_palette`` and ``apply_theme``."""
    t = project.theme
    sheet = base_qss(t).replace('"""', "'''")
    pal = {
        "Window": t.background, "WindowText": t.text, "Base": t.surface,
        "AlternateBase": t.background, "Text": t.text, "Button": t.surface,
        "ButtonText": t.text, "Highlight": t.primary, "HighlightedText": t.button_text,
        "ToolTipBase": t.surface, "ToolTipText": t.text, "PlaceholderText": t.muted_text,
        "Link": t.primary, "BrightText": t.button_text,
    }
    pal_lines = "\n".join(
        f"        QPalette.ColorRole.{k}: {css_color(v, '#808080')!r}," for k, v in pal.items()
    )
    muted = css_color(t.muted_text, "#808080")
    return f'''\
STYLESHEET = """
{sheet}"""


def make_palette():
    """Colour palette matching the project theme (used with the Fusion style)."""
    palette = QPalette()
    roles = {{
{pal_lines}
    }}
    for role, color in roles.items():
        palette.setColor(role, QColor(color))
    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor({muted!r}))
    return palette


def apply_theme(app):
    """Apply the project theme to a QApplication (Fusion style + palette + stylesheet)."""
    app.setStyle("Fusion")
    app.setPalette(make_palette())
    app.setStyleSheet(STYLESHEET)
'''


# ------------------------------------------------------------------------- node styling
_BUTTONISH = {"button", "tool_button"}
_CONTAINERS = {"frame", "label_frame", "scroll_frame", "paned_window"}
_RELIEF = {
    "flat": "none", "raised": "outset", "sunken": "inset", "groove": "groove",
    "ridge": "ridge", "solid": "solid",
}


def explicit_style(style: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in style.items():
        if k in ("bold", "italic", "underline"):
            if v:
                out[k] = True
        elif k in ("border_width", "corner_radius"):
            if isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0:
                out[k] = int(v)
        elif k == "font_size":
            if v:
                out[k] = int(v)
        elif v not in ("", None):
            out[k] = v
    return out


def node_qss(theme: ProjectTheme, node: Node, var: str, *, placeholder: bool = False) -> str:
    """QSS rules (``#var`` selectors) for one node: theme baseline + explicit ``node.style``."""
    res = resolve_style(theme, node.type, node.style)
    ex = explicit_style(node.style)
    t = node.type
    d: dict[str, str] = {}
    bw = int(res["border_width"])  # type: ignore[call-overload]
    bc = css_color(res["border_color"], theme.border)

    def border(width: int, style: str = "solid") -> str:
        return "none" if width <= 0 and style == "solid" else f"{max(width, 1)}px {style} {bc}"

    if t in ("window", "toplevel"):
        d["background-color"] = css_color(res["background"], theme.background)
        d["color"] = css_color(res["foreground"], theme.text)
    elif t in _CONTAINERS:
        d["background-color"] = css_color(res["background"], theme.surface)
        d["color"] = css_color(res["foreground"], theme.text)
        if t != "paned_window":
            d["border"] = border(bw)
            d["border-radius"] = f"{int(res['corner_radius'])}px"  # type: ignore[call-overload]
    elif t == "separator":
        d["background-color"] = css_color(ex.get("background") or bc, bc)
        d["border"] = "none"
    elif t == "canvas":
        d["background-color"] = css_color(res["background"], theme.surface)
    elif placeholder:
        d.update({"border": f"1px dashed {css_color(theme.muted_text, '#888')}",
                  "color": css_color(theme.muted_text, "#888"),
                  "background-color": "transparent", "border-radius": "4px"})

    if "background" in ex:
        d["background-color"] = css_color(ex["background"], d.get("background-color", ""))
    if "foreground" in ex:
        d["color"] = css_color(ex["foreground"], d.get("color", ""))
    if "font_family" in ex:
        d["font-family"] = f'"{css_font(ex["font_family"])}"'
    if "font_size" in ex:
        d["font-size"] = f"{ex['font_size']}px"
    if "bold" in ex:
        d["font-weight"] = "bold"
    if "italic" in ex:
        d["font-style"] = "italic"
    if "underline" in ex:
        d["text-decoration"] = "underline"
    if "border_width" in ex or "border_color" in ex:
        d["border"] = border(bw)
    if "corner_radius" in ex:
        d["border-radius"] = f"{ex['corner_radius']}px"
    relief = ex.get("relief")
    if relief in _RELIEF:
        d["border"] = border(max(bw, 2), _RELIEF[relief]) if relief != "flat" else "none"
    d = {k: v for k, v in d.items() if v}

    rules = []
    if d:
        body = "; ".join(f"{k}: {v}" for k, v in d.items())
        rules.append(f"#{var} {{ {body}; }}")
    hover = css_color(node.style.get("hover_color"))
    if hover:
        rules.append(f"#{var}:hover {{ background-color: {hover}; }}")
    elif t in _BUTTONISH and "background" in ex:
        rules.append(f"#{var}:hover {{ background-color: {d['background-color']}; }}")
    if t == "segmented_button":
        rules.extend(_segmented_rules(theme, var, d, hover))
    if t == "scroll_frame":
        rules.append(f"#{var}_content {{ background: transparent; border: none; }}")
    return "\n".join(rules)


def _segmented_rules(theme: ProjectTheme, var: str, d: dict[str, str], hover: str) -> list[str]:
    sf = css_color(theme.surface, "#fff")
    bd = css_color(d.get("border-color") or theme.border, "#ccc")
    tx = css_color(d.get("color") or theme.text, "#000")
    r = theme.button_radius
    bw = max(theme.border_width, 1)
    return [
        f"#{var} QPushButton {{ background-color: {css_color(d.get('background-color'), sf)}; "
        f"color: {tx}; border: {bw}px solid {bd}; border-radius: 0; padding: 5px 14px; "
        f"margin-left: -1px; }}",
        f"#{var} QPushButton:hover:!checked {{ background-color: "
        f"{hover or css_color(theme.background, '#eee')}; }}",
        f"#{var} QPushButton:checked {{ background-color: {css_color(theme.primary, '#26c')}; "
        f"color: {css_color(theme.button_text, '#fff')}; }}",
        f'#{var} QPushButton[segment="first"] {{ border-top-left-radius: {r}px; '
        f"border-bottom-left-radius: {r}px; margin-left: 0; }}",
        f'#{var} QPushButton[segment="last"] {{ border-top-right-radius: {r}px; '
        f"border-bottom-right-radius: {r}px; }}",
        f'#{var} QPushButton[segment="only"] {{ border-radius: {r}px; margin-left: 0; }}',
    ]


CURSORS = {
    "arrow": "ArrowCursor", "hand": "PointingHandCursor", "ibeam": "IBeamCursor",
    "cross": "CrossCursor", "wait": "WaitCursor", "forbidden": "ForbiddenCursor",
    "size_all": "SizeAllCursor",
}
