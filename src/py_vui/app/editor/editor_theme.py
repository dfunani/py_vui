"""Editor (IDE chrome) light / dark themes: palettes, stylesheet and OS detection."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication


@dataclass(frozen=True)
class EditorPalette:
    name: str
    window: str
    panel: str
    base: str
    alt: str
    text: str
    muted: str
    border: str
    accent: str
    accent_text: str
    hover: str
    canvas: str
    canvas_dot: str
    ruler: str
    guide: str
    smart: str
    selection: str

    def color(self, key: str) -> QColor:
        return QColor(getattr(self, key))


DARK = EditorPalette(
    name="dark",
    window="#1e1f26",
    panel="#262833",
    base="#1a1b22",
    alt="#2d303c",
    text="#e4e6ef",
    muted="#8b90a5",
    border="#383b4a",
    accent="#6c8cff",
    accent_text="#ffffff",
    hover="#33364a",
    canvas="#14151a",
    canvas_dot="#3a3d4d",
    ruler="#20222b",
    guide="#22d3ee",
    smart="#f472b6",
    selection="#6c8cff",
)
LIGHT = EditorPalette(
    name="light",
    window="#f3f4f8",
    panel="#ffffff",
    base="#ffffff",
    alt="#eceef5",
    text="#1f2230",
    muted="#6b7085",
    border="#d5d8e3",
    accent="#3b5bdb",
    accent_text="#ffffff",
    hover="#e4e8f7",
    canvas="#dfe2ec",
    canvas_dot="#b8bccd",
    ruler="#f3f4f8",
    guide="#0891b2",
    smart="#db2777",
    selection="#3b5bdb",
)
PALETTES = {"dark": DARK, "light": LIGHT}
_current: EditorPalette = DARK


def current_palette() -> EditorPalette:
    return _current


def system_prefers_dark(app: QGuiApplication | None = None) -> bool:
    """Best-effort OS colour-scheme detection (dark when unknown)."""
    app = app or QGuiApplication.instance()  # type: ignore[assignment]
    if app is None:
        return True
    try:
        scheme = app.styleHints().colorScheme()
        if scheme == Qt.ColorScheme.Dark:
            return True
        if scheme == Qt.ColorScheme.Light:
            return False
    except AttributeError:  # pragma: no cover - old Qt
        pass
    return True


def resolve_theme_name(choice: str) -> str:
    """``auto`` follows the OS; anything unknown falls back to dark."""
    if choice in PALETTES:
        return choice
    return "dark" if system_prefers_dark() else "light"


def build_stylesheet(p: EditorPalette) -> str:
    return f"""
QWidget {{ background: {p.window}; color: {p.text}; font-size: 12px; }}
QMainWindow, QDialog {{ background: {p.window}; }}
QToolTip {{ background: {p.panel}; color: {p.text}; border: 1px solid {p.border}; padding: 4px; }}
QMenuBar {{ background: {p.panel}; border-bottom: 1px solid {p.border}; }}
QMenuBar::item {{ padding: 4px 10px; background: transparent; border-radius: 4px; }}
QMenuBar::item:selected {{ background: {p.hover}; }}
QMenu {{ background: {p.panel}; border: 1px solid {p.border}; padding: 4px; }}
QMenu::item {{ padding: 5px 26px 5px 22px; border-radius: 4px; background: transparent; }}
QMenu::item:selected {{ background: {p.accent}; color: {p.accent_text}; }}
QMenu::item:disabled {{ color: {p.muted}; }}
QMenu::separator {{ height: 1px; background: {p.border}; margin: 4px 8px; }}
QToolBar {{ background: {p.panel}; border: none; border-bottom: 1px solid {p.border};
    spacing: 2px; padding: 3px 6px; }}
QToolBar::separator {{ width: 1px; background: {p.border}; margin: 4px 6px; }}
QToolButton {{ background: transparent; border: 1px solid transparent; border-radius: 5px;
    padding: 3px 6px; }}
QToolButton:hover {{ background: {p.hover}; }}
QToolButton:checked {{ background: {p.hover}; border-color: {p.accent}; }}
QToolButton:pressed {{ background: {p.alt}; }}
QToolButton:disabled {{ color: {p.muted}; }}
QPushButton {{ background: {p.alt}; border: 1px solid {p.border}; border-radius: 5px;
    padding: 5px 12px; }}
QPushButton:hover {{ border-color: {p.accent}; }}
QPushButton:default {{ background: {p.accent}; color: {p.accent_text}; border-color: {p.accent}; }}
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTextBrowser {{
    background: {p.base}; border: 1px solid {p.border}; border-radius: 5px; padding: 3px 6px;
    selection-background-color: {p.accent}; selection-color: {p.accent_text}; }}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{ border-color: {p.accent}; }}
QComboBox QAbstractItemView {{ background: {p.panel}; border: 1px solid {p.border};
    selection-background-color: {p.accent}; selection-color: {p.accent_text}; }}
QComboBox::drop-down {{ border: none; width: 18px; }}
QTreeView, QListView, QListWidget, QTreeWidget, QTableView {{ background: {p.base};
    border: 1px solid {p.border}; alternate-background-color: {p.alt}; outline: 0; }}
QTreeView::item, QListView::item {{ padding: 2px; border-radius: 3px; }}
QTreeView::item:hover, QListView::item:hover {{ background: {p.hover}; }}
QTreeView::item:selected, QListView::item:selected {{ background: {p.accent};
    color: {p.accent_text}; }}
QHeaderView::section {{ background: {p.panel}; border: none; border-right: 1px solid {p.border};
    padding: 3px 6px; color: {p.muted}; }}
QDockWidget {{ titlebar-close-icon: none; }}
QDockWidget::title {{ background: {p.panel}; padding: 5px 8px; border-bottom: 1px solid {p.border};
    text-align: left; }}
QTabWidget::pane {{ border: 1px solid {p.border}; top: -1px; }}
QTabBar {{ background: transparent; }}
QTabBar::tab {{ background: {p.window}; border: 1px solid {p.border}; border-bottom: none;
    padding: 5px 12px; margin-right: 1px; border-top-left-radius: 5px;
    border-top-right-radius: 5px; color: {p.muted}; }}
QTabBar::tab:selected {{ background: {p.panel}; color: {p.text};
    border-top: 2px solid {p.accent}; }}
QTabBar::tab:hover:!selected {{ background: {p.hover}; }}
QStatusBar {{ background: {p.panel}; border-top: 1px solid {p.border}; }}
QStatusBar::item {{ border: none; }}
QScrollBar:vertical {{ background: transparent; width: 11px; margin: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 11px; margin: 0; }}
QScrollBar::handle {{ background: {p.border}; border-radius: 4px; min-height: 24px;
    min-width: 24px; }}
QScrollBar::handle:hover {{ background: {p.muted}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QSplitter::handle {{ background: {p.border}; }}
QCheckBox::indicator, QRadioButton::indicator {{ width: 14px; height: 14px; }}
QGroupBox {{ border: 1px solid {p.border}; border-radius: 6px; margin-top: 10px;
    padding-top: 8px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; color: {p.muted}; }}
QToolBar QLabel {{ background: transparent; }}
QToolBar QWidget#toolbarSpacer {{ background: transparent; }}
QLabel#sectionTitle {{ color: {p.muted}; font-weight: 600; }}
QToolButton#categoryHeader {{ text-align: left; font-weight: 600; color: {p.muted};
    border: none; padding: 5px 6px; background: {p.panel}; }}
QFrame#separatorLine {{ background: {p.border}; }}
"""


def _qpalette(p: EditorPalette) -> QPalette:
    """A full QPalette so palette-driven widgets (code editors, text edits) match the chrome."""
    pal = QPalette()
    for role, key in (
        (QPalette.ColorRole.Window, "window"), (QPalette.ColorRole.WindowText, "text"),
        (QPalette.ColorRole.Base, "base"), (QPalette.ColorRole.AlternateBase, "alt"),
        (QPalette.ColorRole.Text, "text"), (QPalette.ColorRole.Button, "panel"),
        (QPalette.ColorRole.ButtonText, "text"), (QPalette.ColorRole.ToolTipBase, "panel"),
        (QPalette.ColorRole.ToolTipText, "text"), (QPalette.ColorRole.Highlight, "accent"),
        (QPalette.ColorRole.HighlightedText, "accent_text"),
        (QPalette.ColorRole.PlaceholderText, "muted"), (QPalette.ColorRole.Link, "accent"),
    ):
        pal.setColor(role, p.color(key))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText,
                 QPalette.ColorRole.ButtonText):
        pal.setColor(QPalette.ColorGroup.Disabled, role, p.color("muted"))
    return pal


def apply_theme(app: QApplication | None, choice: str) -> EditorPalette:
    """Apply ``dark`` / ``light`` / ``auto`` to the whole application and return the palette."""
    global _current
    palette = PALETTES[resolve_theme_name(choice)]
    _current = palette
    if app is not None:
        # re-polishing every widget is expensive: only touch what actually changed
        if app.style().objectName().lower() != "fusion":
            app.setStyle("Fusion")
        app.setPalette(_qpalette(palette))
        sheet = build_stylesheet(palette)
        if app.styleSheet() != sheet:
            app.setStyleSheet(sheet)
    return palette
