"""Run a generated app in a subprocess (never in the editor process).

* :func:`run_preview` blocking one-shot run (kept for compatibility).
* :class:`PreviewProcess` non-blocking process with captured output, for live preview docks.
* :class:`PreviewSession` regenerates the in-memory project into a private temp folder and
  (re)starts it, so the preview always reflects the current document without touching
  ``<project>/app``.
"""

from __future__ import annotations

import queue
import shutil
import subprocess
import sys
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from py_vui.services.project_service import ProjectService, RunSpec


@dataclass(frozen=True, slots=True)
class PreviewResult:
    returncode: int
    stdout: str
    stderr: str

    # aliases used by older callers
    @property
    def status_code(self) -> int:
        return self.returncode

    @property
    def response(self) -> str:
        return self.stdout

    @property
    def error(self) -> str:
        return self.stderr


def run_preview(
    project_root: Path, entry: Path, *, timeout_s: float = 30.0, python: Path | None = None
) -> PreviewResult:
    root = Path(project_root).resolve()
    if not root.is_dir():
        msg = f"project_root is not a directory: {root}"
        raise ValueError(msg)
    script = entry if Path(entry).is_absolute() else root / entry
    if not script.is_file():
        msg = f"entry script missing: {script}"
        raise ValueError(msg)
    try:
        proc = subprocess.run(
            [str(python or sys.executable), str(script)], cwd=str(root), capture_output=True,
            text=True, timeout=timeout_s, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        err = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        return PreviewResult(-9, out, err + f"\n[timed out after {timeout_s:g}s]")
    return PreviewResult(proc.returncode, proc.stdout, proc.stderr)


class PreviewProcess:
    """A running app. Output lines are collected by reader threads; poll :meth:`drain`."""

    def __init__(self, spec: RunSpec) -> None:
        self.spec = spec
        self._q: queue.Queue[tuple[str, str]] = queue.Queue()
        self._proc: subprocess.Popen[str] | None = None
        self._threads: list[threading.Thread] = []

    def start(self) -> PreviewProcess:
        self._proc = subprocess.Popen(
            self.spec.argv, cwd=str(self.spec.cwd), env=self.spec.env, text=True, bufsize=1,
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        for name, stream in (("stdout", self._proc.stdout), ("stderr", self._proc.stderr)):
            t = threading.Thread(target=self._pump, args=(name, stream), daemon=True)
            t.start()
            self._threads.append(t)
        return self

    def _pump(self, name: str, stream) -> None:
        try:
            for line in stream:
                self._q.put((name, line.rstrip("\n")))
        except ValueError:  # stream closed
            pass

    @property
    def running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    @property
    def returncode(self) -> int | None:
        return None if self._proc is None else self._proc.poll()

    def drain(self) -> list[tuple[str, str]]:
        """Return and clear ``[(stream, line), ...]`` received since the last call."""
        out = []
        while True:
            try:
                out.append(self._q.get_nowait())
            except queue.Empty:
                return out

    def wait(self, timeout: float | None = None) -> int:
        assert self._proc is not None
        rc = self._proc.wait(timeout)
        for t in self._threads:
            t.join(1)
        return rc

    def stop(self, grace: float = 2.0) -> None:
        p = self._proc
        if p is None or p.poll() is not None:
            return
        p.terminate()
        try:
            p.wait(grace)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait()


class PreviewSession:
    """Live preview of a :class:`ProjectService` document."""

    def __init__(self, service: ProjectService, python: Path | None = None) -> None:
        self.service = service
        self.python = python
        self.process: PreviewProcess | None = None
        self._dir: Path | None = None

    @property
    def preview_dir(self) -> Path:
        if self._dir is None:
            self._dir = Path(tempfile.mkdtemp(prefix="py_vui_preview_"))
        return self._dir

    def start(self) -> PreviewProcess:
        """Stop any running preview, regenerate the app and launch it."""
        self.stop()
        files = self.service.generated_files()
        app = self.preview_dir / "app"
        if app.exists():
            shutil.rmtree(app, ignore_errors=True)
        self.service.write_files(app, files)
        spec = self.service.run_spec(self.python)
        spec.cwd = app
        self.process = PreviewProcess(spec).start()
        return self.process

    restart = start

    def stop(self) -> None:
        if self.process is not None:
            self.process.stop()

    def close(self) -> None:
        self.stop()
        if self._dir is not None:
            shutil.rmtree(self._dir, ignore_errors=True)
            self._dir = None
