from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class PreviewResult:
    returncode: int
    stdout: str
    stderr: str


def run_preview(project_root: Path, entry: Path, *, timeout_s: float = 30.0) -> PreviewResult:
    root = project_root.resolve()
    if not root.is_dir():
        msg = f"project_root is not a directory: {root}"
        raise ValueError(msg)
    script = entry if entry.is_absolute() else (root / entry)
    if not script.is_file():
        msg = f"entry script missing: {script}"
        raise ValueError(msg)

    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=timeout_s,
        check=False,
    )
    return PreviewResult(proc.returncode, proc.stdout, proc.stderr)
