from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class PreviewResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    status_code: int
    response: str
    error: str


def run_preview(
    project_root: Path, script: Path, *, timeout_s: float = 30.0
) -> PreviewResult:
    """Run `python entry` with cwd=`project_root` (resolved to absolute)."""

    root = project_root.resolve()
    if not root.is_dir():
        msg = f"project_root is not a directory: {root}"
        raise ValueError(msg)

    if not script.is_absolute():
        script = root / script

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
    return PreviewResult(
        status_code=proc.returncode, response=proc.stdout, error=proc.stderr
    )
