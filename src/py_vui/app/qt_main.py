from __future__ import annotations

import sys

EDITOR_QSS = """
QMainWindow, QDialog {
    background: #1e1e2e;
}
QWidget {
    color: #cdd6f4;
    background: #1e1e2e;
    font-size: 13px;
}
QMenuBar {
    background: #181825;
    border-bottom: 1px solid #313244;
    padding: 2px 0;
}
QMenuBar::item {
    padding: 4px 10px;
    border-radius: 4px;
}
QMenuBar::item:selected {
    background: #313244;
}
QMenu {
    background: #24273a;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 4px;
}
QMenu::item {
    padding: 6px 28px;
    border-radius: 4px;
    color: #cdd6f4;
}
QMenu::item:selected {
    background: #45475a;
}
QMenu::separator {
    background: #313244;
    height: 1px;
    margin: 4px 10px;
}
QToolBar {
    background: #181825;
    border-bottom: 1px solid #313244;
    spacing: 4px;
    padding: 4px 8px;
}
QToolButton {
    background: transparent;
    border: none;
    border-radius: 5px;
    padding: 4px 10px;
    color: #cdd6f4;
    font-size: 12px;
}
QToolButton:hover {
    background: #313244;
}
QToolButton:pressed {
    background: #45475a;
}
QDockWidget {
    color: #a6adc8;
    font-size: 11px;
    font-weight: 600;
}
QDockWidget::title {
    background: #181825;
    border-bottom: 1px solid #313244;
    padding: 6px 10px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: #a6adc8;
}
QSplitter::handle {
    background: #313244;
}
QSplitter::handle:horizontal {
    width: 1px;
}
QSplitter::handle:vertical {
    height: 1px;
}
QGroupBox {
    border: 1px solid #313244;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 6px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: #7f849c;
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.8px;
}
QListWidget {
    background: #181825;
    border: 1px solid #313244;
    border-radius: 6px;
    outline: none;
}
QListWidget::item {
    padding: 5px 8px;
    border-radius: 4px;
    margin: 1px 2px;
}
QListWidget::item:hover {
    background: #313244;
}
QListWidget::item:selected {
    background: #45475a;
    color: #cdd6f4;
}
QTreeWidget {
    background: #181825;
    border: 1px solid #313244;
    border-radius: 6px;
    outline: none;
}
QTreeWidget::item {
    padding: 3px 2px;
}
QTreeWidget::item:hover {
    background: #313244;
}
QTreeWidget::item:selected {
    background: #45475a;
}
QHeaderView::section {
    background: #181825;
    border: none;
    border-bottom: 1px solid #313244;
    padding: 4px 8px;
    color: #7f849c;
    font-size: 11px;
    font-weight: 600;
}
QLineEdit {
    background: #181825;
    border: 1px solid #45475a;
    border-radius: 5px;
    padding: 4px 8px;
    color: #cdd6f4;
    selection-background-color: #45475a;
}
QLineEdit:focus {
    border: 1px solid #89b4fa;
}
QLineEdit:placeholder {
    color: #585b70;
}
QSpinBox {
    background: #181825;
    border: 1px solid #45475a;
    border-radius: 5px;
    padding: 3px 6px;
    color: #cdd6f4;
}
QSpinBox:focus {
    border: 1px solid #89b4fa;
}
QSpinBox::up-button, QSpinBox::down-button {
    background: #313244;
    border: none;
    border-radius: 2px;
    width: 14px;
}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {
    background: #45475a;
}
QComboBox {
    background: #181825;
    border: 1px solid #45475a;
    border-radius: 5px;
    padding: 3px 8px;
    color: #cdd6f4;
}
QComboBox:focus {
    border: 1px solid #89b4fa;
}
QComboBox::drop-down {
    border: none;
    padding-right: 6px;
}
QComboBox QAbstractItemView {
    background: #24273a;
    border: 1px solid #45475a;
    border-radius: 4px;
    selection-background-color: #45475a;
    color: #cdd6f4;
}
QCheckBox {
    spacing: 6px;
    color: #cdd6f4;
}
QCheckBox::indicator {
    width: 15px;
    height: 15px;
    border: 1px solid #45475a;
    border-radius: 3px;
    background: #181825;
}
QCheckBox::indicator:checked {
    background: #89b4fa;
    border-color: #89b4fa;
}
QCheckBox::indicator:hover {
    border-color: #89b4fa;
}
QPushButton {
    background: #313244;
    border: 1px solid #45475a;
    border-radius: 5px;
    padding: 5px 14px;
    color: #cdd6f4;
    font-weight: 500;
}
QPushButton:hover {
    background: #45475a;
    border-color: #585b70;
}
QPushButton:pressed {
    background: #585b70;
}
QPlainTextEdit, QTextEdit {
    background: #181825;
    border: 1px solid #313244;
    border-radius: 5px;
    color: #cdd6f4;
    font-family: "JetBrains Mono", "Consolas", "SF Mono", monospace;
    font-size: 12px;
    selection-background-color: #45475a;
}
QStatusBar {
    background: #181825;
    border-top: 1px solid #313244;
    color: #7f849c;
    font-size: 11px;
    padding: 0 8px;
}
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #45475a;
    border-radius: 4px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover {
    background: #585b70;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    background: transparent;
    height: 8px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background: #45475a;
    border-radius: 4px;
    min-width: 20px;
}
QScrollBar::handle:horizontal:hover {
    background: #585b70;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}
QScrollBar::add-page, QScrollBar::sub-page {
    background: transparent;
}
QLabel#section_label {
    color: #7f849c;
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    padding: 6px 8px 2px 8px;
    background: transparent;
}
"""


def main() -> None:
    try:
        from PySide6.QtWidgets import QApplication
    except ModuleNotFoundError:
        print("py_vui editor requires: pip install py_vui[gui]")
        raise SystemExit(1) from None

    from py_vui.app.editor.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("py_vui")
    app.setStyleSheet(EDITOR_QSS)
    window = MainWindow()
    window.show()
    raise SystemExit(app.exec())


if __name__ == "__main__":
    main()
