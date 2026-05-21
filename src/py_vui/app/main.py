from __future__ import annotations
from PySide6.QtWidgets import QApplication, QLabel, QWidget


def main() -> None:
    app = QApplication([])
    window = QWidget()
    window.setWindowTitle("py_vui (stub)")
    label = QLabel("Editor shell not implemented yet.", parent=window)
    label.move(12, 12)
    window.resize(420, 120)
    window.show()
    app.exec()


if __name__ == "__main__":
    main()
