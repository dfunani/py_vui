"""Shared helpers for the editor GUI tests (offscreen Qt, synthesized input)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

import pytest
from PySide6.QtCore import QObject, QPointF, QProcess, QSettings, Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from py_vui.core import make_node


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    return app


@pytest.fixture
def home(tmp_path, monkeypatch):
    h = tmp_path / "home"
    h.mkdir()
    monkeypatch.setenv("PY_VUI_HOME", str(h))
    return h


class FakeProcess(QObject):
    """Drop-in for QProcess: records configuration, lets tests emit output / finish."""

    readyReadStandardOutput = Signal()
    readyReadStandardError = Signal()
    finished = Signal(int, QProcess.ExitStatus)
    errorOccurred = Signal(QProcess.ProcessError)
    instances: list[FakeProcess] = []

    def __init__(self) -> None:
        super().__init__()
        self.program = ""
        self.args: list[str] = []
        self.cwd = ""
        self.env = None
        self._state = QProcess.ProcessState.NotRunning
        self._out = b""
        self._err = b""
        self.started = 0
        FakeProcess.instances.append(self)

    def setProgram(self, p: str) -> None:
        self.program = p

    def setArguments(self, a: list[str]) -> None:
        self.args = list(a)

    def setWorkingDirectory(self, d: str) -> None:
        self.cwd = d

    def setProcessEnvironment(self, e) -> None:
        self.env = e

    def start(self) -> None:
        self._state = QProcess.ProcessState.Running
        self.started += 1

    def state(self):
        return self._state

    def terminate(self) -> None:
        self.finish(0)

    def kill(self) -> None:
        self.finish(9)

    def waitForFinished(self, _ms: int = 0) -> bool:
        return True

    def readAllStandardOutput(self) -> bytes:
        out, self._out = self._out, b""
        return out

    def readAllStandardError(self) -> bytes:
        err, self._err = self._err, b""
        return err

    # test controls
    def emit_out(self, text: str) -> None:
        self._out += text.encode()
        self.readyReadStandardOutput.emit()

    def emit_err(self, text: str) -> None:
        self._err += text.encode()
        self.readyReadStandardError.emit()

    def finish(self, code: int = 0) -> None:
        if self._state != QProcess.ProcessState.NotRunning:
            self._state = QProcess.ProcessState.NotRunning
            self.finished.emit(code, QProcess.ExitStatus.NormalExit)


def make_window(tmp_path: Path, framework: str = "tkinter", template: str | None = None, **kw):
    """A MainWindow bound to a fresh real ProjectService (settings isolated in tmp_path)."""
    from py_vui.app.editor.main_window import MainWindow
    from py_vui.services import ProjectService

    svc = ProjectService()
    svc.new_project("Test", framework, template)
    settings = QSettings(str(tmp_path / "editor.ini"), QSettings.Format.IniFormat)
    kw.setdefault("check_recovery", False)
    kw.setdefault("restore_state", False)
    kw.setdefault("theme", "dark")
    win = MainWindow(service=svc, settings=settings, **kw)
    win.show()
    QApplication.processEvents()
    return win


def dispose(win) -> None:
    """Close without prompting."""
    from shiboken6 import delete

    win.service.saved_revision = win.history.revision
    win.close()
    QApplication.processEvents()
    delete(win)


def add_nodes(win, *specs):
    """Add nodes directly to the document (parent defaults to the window) and sync the UI."""
    ids = []
    root = win.doc.project.root_id
    for type_id, kw in specs:
        parent = kw.pop("parent_id", root)
        n = make_node(type_id, parent_id=parent, **kw)
        n.z_index = sum(1 for o in win.doc.project.nodes.values() if o.parent_id == parent)
        win.doc.project.nodes[n.id] = n
        ids.append(n.id)
    win.canvas.refresh()
    win.after_edit()
    return ids


# --------------------------------------------------------------------------- input synthesis
def view_pos(canvas, scene_pt: QPointF):
    return canvas.mapFromScene(scene_pt)


def send_mouse(
    canvas,
    kind,
    scene_pt,
    button=Qt.MouseButton.LeftButton,
    buttons=None,
    mods=Qt.KeyboardModifier.NoModifier,
) -> None:
    from PySide6.QtCore import QEvent

    pos = QPointF(
        canvas.mapFromScene(QPointF(*scene_pt) if isinstance(scene_pt, tuple) else scene_pt)
    )
    if buttons is None:
        buttons = button if kind != QEvent.Type.MouseButtonRelease else Qt.MouseButton.NoButton
    ev = QMouseEvent(kind, pos, canvas.viewport().mapToGlobal(pos), button, buttons, mods)
    QApplication.sendEvent(canvas.viewport(), ev)


def press(canvas, pt, mods=Qt.KeyboardModifier.NoModifier, button=Qt.MouseButton.LeftButton):
    from PySide6.QtCore import QEvent

    send_mouse(canvas, QEvent.Type.MouseButtonPress, pt, button, button, mods)


def move(canvas, pt, mods=Qt.KeyboardModifier.NoModifier, button=Qt.MouseButton.LeftButton):
    from PySide6.QtCore import QEvent

    send_mouse(canvas, QEvent.Type.MouseMove, pt, Qt.MouseButton.NoButton, button, mods)


def release(canvas, pt, mods=Qt.KeyboardModifier.NoModifier, button=Qt.MouseButton.LeftButton):
    from PySide6.QtCore import QEvent

    send_mouse(canvas, QEvent.Type.MouseButtonRelease, pt, button, Qt.MouseButton.NoButton, mods)


def click(canvas, pt, mods=Qt.KeyboardModifier.NoModifier) -> None:
    press(canvas, pt, mods)
    release(canvas, pt, mods)


def drag(canvas, a, b, mods=Qt.KeyboardModifier.NoModifier, steps: int = 5) -> None:
    """Press at scene point ``a``, move in ``steps`` and release at ``b``."""
    ax, ay = a
    bx, by = b
    press(canvas, a, mods)
    for i in range(1, steps + 1):
        t = i / steps
        move(canvas, (ax + (bx - ax) * t, ay + (by - ay) * t), mods)
    release(canvas, b, mods)


def centre(canvas, node_id: str) -> tuple[float, float]:
    c = canvas.node_scene_rect(node_id).center()
    return c.x(), c.y()
