from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QProcess, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class LivePreviewDock(QWidget):
    status_message = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._proc: QProcess | None = None
        self._app_dir: Path | None = None

        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        self._start_btn = QPushButton("Start preview")
        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setEnabled(False)
        self._start_btn.clicked.connect(self.start_preview)
        self._stop_btn.clicked.connect(self.stop_preview)
        row.addWidget(self._start_btn)
        row.addWidget(self._stop_btn)
        row.addStretch()
        layout.addLayout(row)
        self._label = QLabel("Preview runs your generated app in a separate process.")
        self._label.setWordWrap(True)
        layout.addWidget(self._label)

    def set_app_dir(self, app_dir: Path | None) -> None:
        self._app_dir = app_dir
        if app_dir is None:
            self._label.setText("Save the project and generate code to enable live preview.")
        else:
            self._label.setText(f"Preview app: {app_dir / 'main.py'}")

    def start_preview(self) -> None:
        if self._app_dir is None:
            self.status_message.emit("Save project and generate code first.")
            return
        entry = self._app_dir / "main.py"
        if not entry.is_file():
            self.status_message.emit("main.py missing — run Build → Generate Code.")
            return
        self.stop_preview()
        self._proc = QProcess(self)
        self._proc.setProgram(sys.executable)
        self._proc.setArguments([str(entry)])
        self._proc.setWorkingDirectory(str(self._app_dir))
        self._proc.finished.connect(self._on_finished)
        self._proc.start()
        self._stop_btn.setEnabled(True)
        self._start_btn.setEnabled(False)
        self.status_message.emit(f"Preview started: {entry}")

    def stop_preview(self) -> None:
        if self._proc is not None and self._proc.state() != QProcess.ProcessState.NotRunning:
            self._proc.kill()
            self._proc.waitForFinished(2000)
        self._proc = None
        self._stop_btn.setEnabled(False)
        self._start_btn.setEnabled(True)

    def restart_preview(self) -> None:
        if self._proc is not None and self._proc.state() != QProcess.ProcessState.NotRunning:
            self.stop_preview()
        self.start_preview()

    def _on_finished(self, code: int, _status) -> None:
        self._stop_btn.setEnabled(False)
        self._start_btn.setEnabled(True)
        self.status_message.emit(f"Preview exited ({code})")
