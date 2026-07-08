from __future__ import annotations

HANDLER_SNIPPETS: dict[str, str] = {
    "Print message": 'print("Hello from py_vui")',
    "Message box": (
        "from PySide6.QtWidgets import QMessageBox\n"
        'QMessageBox.information(None, "py_vui", "Done!")'
    ),
    "Close window": (
        "from PySide6.QtWidgets import QApplication\n"
        "for w in QApplication.topLevelWidgets():\n"
        "    w.close()"
    ),
    "Log selection": 'print("event fired")',
}
