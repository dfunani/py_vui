from __future__ import annotations

import sys


def main() -> None:
    try:
        from PySide6.QtWidgets import QApplication
    except ModuleNotFoundError:
        print("py_vui editor requires: pip install py_vui[gui]")
        raise SystemExit(1) from None

    from py_vui.app.editor.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("py_vui")
    window = MainWindow()
    window.show()
    raise SystemExit(app.exec())


if __name__ == "__main__":
    main()
