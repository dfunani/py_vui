"""GUI entry point: ``py_vui-gui`` / ``python -m py_vui``."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from py_vui import __version__


def main(argv: list[str] | None = None) -> int:
    """Start the editor. ``argv[1]`` may be a project folder or ``.json`` file to open."""
    args = list(sys.argv if argv is None else argv)
    QCoreApplication.setOrganizationName("py_vui")
    QCoreApplication.setApplicationName("py_vui")
    QCoreApplication.setApplicationVersion(__version__)
    app = QApplication.instance() or QApplication(args)

    from py_vui.app.editor.main_window import MainWindow

    window = MainWindow()
    window.show()
    if len(args) > 1 and Path(args[1]).exists():
        window.open_path(Path(args[1]), checked=True)
    else:
        window.offer_recovery()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
