"""Per-project virtualenv used to run generated apps with their 3rd-party requirements."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

Progress = Callable[[str], None] | None


def venv_python(venv_dir: Path) -> Path:
    if sys.platform == "win32":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _run(cmd: list[str], progress: Progress) -> None:
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
    )
    tail: list[str] = []
    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.rstrip()
        tail.append(line)
        del tail[:-20]
        if progress and line:
            progress(line)
    if proc.wait() != 0:
        msg = f"command failed ({proc.returncode}): {' '.join(cmd)}\n" + "\n".join(tail)
        raise RuntimeError(msg)


Runner = Callable[[list[str], Progress], None]


def _create_venv(venv_dir: Path, runner: Runner, uv: str | None, progress: Progress) -> None:
    """Create a pip-less venv (never depends on ensurepip); prefer uv when available."""
    errors: list[str] = []
    if uv:
        try:
            runner([uv, "venv", "--python", sys.executable, str(venv_dir)], progress)
            return
        except (RuntimeError, OSError) as exc:
            errors.append(f"uv venv: {exc}")
            shutil.rmtree(venv_dir, ignore_errors=True)
    try:
        runner([sys.executable, "-m", "venv", "--without-pip", str(venv_dir)], progress)
        return
    except (RuntimeError, OSError) as exc:
        errors.append(f"python -m venv: {exc}")
        shutil.rmtree(venv_dir, ignore_errors=True)
    msg = f"could not create a virtual environment in {venv_dir}:\n" + "\n".join(errors)
    raise RuntimeError(msg)


def _install(py: Path, reqs: list[str], runner: Runner, uv: str | None, progress: Progress) -> None:
    if uv:
        try:
            runner([uv, "pip", "install", "--python", str(py), *reqs], progress)
            return
        except (RuntimeError, OSError):
            if progress:
                progress("uv pip failed; falling back to pip")
    try:
        runner([str(py), "-m", "pip", "--version"], None)
    except (RuntimeError, OSError):
        try:
            runner([str(py), "-m", "ensurepip", "--upgrade", "--default-pip"], progress)
        except (RuntimeError, OSError) as exc:
            msg = (
                "cannot install requirements: pip is unavailable in the runtime environment "
                "and ensurepip failed. Install 'uv' (https://docs.astral.sh/uv/) or a Python "
                f"with pip support, or install these manually: {' '.join(reqs)}\n{exc}"
            )
            raise RuntimeError(msg) from exc
    runner([str(py), "-m", "pip", "install", "--disable-pip-version-check", *reqs], progress)


def ensure_runtime(
    project_dir: Path,
    requirements: list[str],
    progress: Progress = None,
    *,
    runner: Runner | None = None,
    uv: str | None | bool = True,
) -> Path:
    """Create/reuse ``<project_dir>/.py_vui/venv``, install ``requirements``, return its python.

    Blocking and user initiated (``pip`` uses the network): callers run it in a worker thread.
    The venv is created with ``--without-pip`` (or ``uv venv``) so a broken ``ensurepip`` cannot
    block creation; pip is only bootstrapped when packages must be installed. Installing is
    skipped when the requirement set is unchanged. ``runner`` / ``uv`` are injectable for tests
    (``uv=True`` looks it up on PATH, ``None``/``False`` disables it, a str is its path).
    """
    runner = runner or _run
    uv_path = shutil.which("uv") if uv is True else (uv or None)
    project_dir = Path(project_dir)
    venv_dir = project_dir / ".py_vui" / "venv"
    py = venv_python(venv_dir)
    if not py.exists():
        if progress:
            progress(f"Creating virtual environment in {venv_dir}")
        _create_venv(venv_dir, runner, uv_path, progress)
    reqs = sorted({r.strip() for r in requirements if r.strip()})
    stamp = venv_dir / ".py_vui_requirements"
    digest = hashlib.sha256("\n".join(reqs).encode()).hexdigest()
    if reqs and (not stamp.exists() or stamp.read_text().strip() != digest):
        if progress:
            progress("Installing: " + ", ".join(reqs))
        _install(py, reqs, runner, uv_path, progress)
        stamp.parent.mkdir(parents=True, exist_ok=True)
        stamp.write_text(digest + "\n")
    if progress:
        progress(f"Runtime ready: {py}")
    return py
