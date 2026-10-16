"""Run / live preview controller: generate -> run_spec -> QProcess, with runtime-venv creation."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QThread, QTimer, Signal

LIVE_DEBOUNCE_MS = 700


class RuntimeWorker(QThread):
    """Runs ``ensure_runtime`` off the GUI thread."""

    progress = Signal(str)
    ready = Signal(str)
    failed = Signal(str)

    def __init__(self, project_dir: Path | None, requirements: list[str], parent=None) -> None:
        super().__init__(parent)
        self.project_dir = project_dir
        self.requirements = requirements

    def run(self) -> None:
        try:
            from py_vui.services.runtime import ensure_runtime

            py = ensure_runtime(self.project_dir, self.requirements, self.progress.emit)
            self.ready.emit(str(py))
        except Exception as exc:
            self.failed.emit(str(exc))


class RunController(QObject):
    """Owns the preview process and the (optional) executable build process."""

    output = Signal(str, str)  # text, kind (out | err | info)
    runningChanged = Signal(bool)
    message = Signal(str)

    def __init__(
        self,
        service_getter: Callable[[], Any],
        parent: QObject | None = None,
        process_factory: Callable[[], Any] = QProcess,
        confirm_runtime: Callable[[list[str]], bool] | None = None,
        worker_factory: Callable[..., Any] = RuntimeWorker,
    ) -> None:
        super().__init__(parent)
        self._service = service_getter
        self._factory = process_factory
        self._confirm = confirm_runtime or (lambda _missing: True)
        self._worker_factory = worker_factory
        self.proc: Any = None
        self.build_proc: Any = None
        self.python: str | None = None  # runtime venv python chosen for this project
        self._worker: Any = None
        self._starting = False
        self.live = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(LIVE_DEBOUNCE_MS)
        self._timer.timeout.connect(self._live_fire)
        self.last_spec: Any = None

    # ------------------------------------------------------------------------ state
    @property
    def running(self) -> bool:
        return self.proc is not None and self.proc.state() != QProcess.ProcessState.NotRunning

    def reset(self) -> None:
        """Forget per-project state (call when another project is opened)."""
        self.stop()
        self.python = None

    # ------------------------------------------------------------------- run / stop
    def run(self) -> bool:
        """Generate + start the app. Returns False when nothing could be started now."""
        svc = self._service()
        if self._starting:
            return False
        self.stop(quiet=True)
        try:
            from py_vui.codegen.base import GenOptions

            svc.generate(GenOptions())
        except Exception as exc:
            self.output.emit(f"Code generation failed: {exc}\n", "err")
            self.message.emit("Generation failed")
            return False
        try:
            spec = svc.run_spec(python=self.python) if self.python else svc.run_spec()
        except Exception as exc:
            self.output.emit(f"Cannot prepare run: {exc}\n", "err")
            return False
        self.last_spec = spec
        missing = list(getattr(spec, "missing_requirements", []) or [])
        if missing and not self.python:
            if not self._confirm(missing):
                self.output.emit(
                    "Missing packages: "
                    + ", ".join(missing)
                    + " — running with the current interpreter.\n",
                    "info",
                )
            else:
                self._create_runtime(missing)
                return True
        self._start(spec)
        return True

    def _create_runtime(self, missing: list[str]) -> None:
        svc = self._service()
        self._starting = True
        self.output.emit("Creating a runtime environment for: " + ", ".join(missing) + "\n", "info")
        worker = self._worker_factory(getattr(svc, "work_dir", None), missing, self)
        worker.progress.connect(lambda line: self.output.emit(str(line).rstrip() + "\n", "info"))
        worker.ready.connect(self._runtime_ready)
        worker.failed.connect(self._runtime_failed)
        self._worker = worker
        self.runningChanged.emit(True)
        worker.start()

    def _runtime_ready(self, python: str) -> None:
        self._starting = False
        self.python = python
        self.output.emit(f"Runtime ready: {python}\n", "info")
        self.runningChanged.emit(self.running)
        try:
            spec = self._service().run_spec(python=python)
        except Exception as exc:
            self.output.emit(f"Cannot prepare run: {exc}\n", "err")
            return
        self._start(spec)

    def _runtime_failed(self, error: str) -> None:
        self._starting = False
        self.output.emit(f"Runtime environment failed: {error}\n", "err")
        self.runningChanged.emit(self.running)

    def _start(self, spec: Any) -> None:
        proc = self._factory()
        proc.setProgram(str(spec.argv[0]))
        proc.setArguments([str(a) for a in spec.argv[1:]])
        if getattr(spec, "cwd", None):
            proc.setWorkingDirectory(str(spec.cwd))
        env = QProcessEnvironment.systemEnvironment()
        for k, v in (getattr(spec, "env", None) or {}).items():
            env.insert(str(k), str(v))
        env.insert("PYTHONUNBUFFERED", "1")
        proc.setProcessEnvironment(env)
        proc.readyReadStandardOutput.connect(lambda: self._drain(proc, "out"))
        proc.readyReadStandardError.connect(lambda: self._drain(proc, "err"))
        proc.finished.connect(lambda code, _status=None: self._finished(proc, int(code)))
        proc.errorOccurred.connect(lambda err: self._error(proc, err))
        self.proc = proc
        self.output.emit("$ " + " ".join(str(a) for a in spec.argv) + "\n", "info")
        proc.start()
        self.runningChanged.emit(True)
        self.message.emit("Running preview…")

    def _drain(self, proc: Any, kind: str) -> None:
        data = proc.readAllStandardOutput() if kind == "out" else proc.readAllStandardError()
        text = bytes(data).decode("utf-8", "replace")
        if text:
            self.output.emit(text, kind)

    def _finished(self, proc: Any, code: int) -> None:
        self._drain(proc, "out")
        self._drain(proc, "err")
        if proc is self.proc:
            self.output.emit(f"Process exited with code {code}\n", "info" if code == 0 else "err")
            self.message.emit("Preview stopped" if code == 0 else f"Preview exited ({code})")
            self.runningChanged.emit(False)

    def _error(self, proc: Any, err: Any) -> None:
        if proc is self.proc and err == QProcess.ProcessError.FailedToStart:
            self.output.emit("The preview process failed to start.\n", "err")
            self.runningChanged.emit(False)

    def stop(self, quiet: bool = False) -> None:
        proc = self.proc
        if proc is None:
            return
        if proc.state() != QProcess.ProcessState.NotRunning:
            if not quiet:
                self.output.emit("Stopping preview…\n", "info")
            proc.terminate()
            if not proc.waitForFinished(1500):
                proc.kill()
                proc.waitForFinished(1500)
        if not quiet:
            self.runningChanged.emit(False)

    def restart(self) -> bool:
        return self.run()

    # ------------------------------------------------------------------ live preview
    def set_live(self, on: bool) -> None:
        self.live = on
        if on:
            self.schedule()
        else:
            self._timer.stop()

    def schedule(self) -> None:
        """Called after every document change; restarts the preview once edits settle."""
        if self.live:
            self._timer.start()

    def _live_fire(self) -> None:
        if self.live:
            self.run()

    # --------------------------------------------------------------- executable build
    def build_executable(self, onefile: bool = True) -> bool:
        svc = self._service()
        try:
            from py_vui.codegen.base import GenOptions

            svc.generate(GenOptions())
            cmd = svc.build_executable_command(onefile)
        except Exception as exc:
            self.output.emit(f"Cannot build: {exc}\n", "err")
            return False
        argv = list(getattr(cmd, "argv", cmd))
        cwd = getattr(cmd, "cwd", None) or getattr(svc, "app_dir", None)
        proc = self._factory()
        proc.setProgram(str(argv[0]))
        proc.setArguments([str(a) for a in argv[1:]])
        if cwd:
            proc.setWorkingDirectory(str(cwd))
        env = QProcessEnvironment.systemEnvironment()
        for k, v in (getattr(cmd, "env", None) or {}).items():
            env.insert(str(k), str(v))
        proc.setProcessEnvironment(env)
        proc.readyReadStandardOutput.connect(lambda: self._drain(proc, "out"))
        proc.readyReadStandardError.connect(lambda: self._drain(proc, "err"))
        proc.finished.connect(lambda code, _s=None: self._build_done(proc, int(code)))
        self.build_proc = proc
        self.output.emit("$ " + " ".join(str(a) for a in argv) + "\n", "info")
        proc.start()
        self.message.emit("Building executable…")
        return True

    def _build_done(self, proc: Any, code: int) -> None:
        self._drain(proc, "out")
        self._drain(proc, "err")
        ok = code == 0
        self.output.emit(
            "Build finished.\n" if ok else f"Build failed (exit code {code}).\n",
            "info" if ok else "err",
        )
        self.message.emit("Executable built" if ok else "Build failed")

    def shutdown(self) -> None:
        self._timer.stop()
        self.stop(quiet=True)
        if (
            self.build_proc is not None
            and self.build_proc.state() != QProcess.ProcessState.NotRunning
        ):
            self.build_proc.kill()
        if self._worker is not None and hasattr(self._worker, "wait"):
            self._worker.wait(2000)


def default_env() -> dict[str, str]:
    return dict(os.environ)
