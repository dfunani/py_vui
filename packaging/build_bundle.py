"""Build a standalone desktop bundle of the py_vui editor with PyInstaller.

    python packaging/build_bundle.py --name py_vui-macOS

Produces ``dist-bundle/<name>.zip`` (the one-folder app, zipped).
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="py_vui")
    args = ap.parse_args()

    out = ROOT / "dist-bundle"
    work = ROOT / "build" / "pyinstaller"
    shutil.rmtree(out, ignore_errors=True)
    cmd = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
        "--name", "py_vui",
        "--distpath", str(out / "app"), "--workpath", str(work), "--specpath", str(work),
        "--collect-data", "py_vui",
        "--collect-submodules", "py_vui",
        str(ROOT / "packaging" / "launcher.py"),
    ]
    subprocess.run(cmd, check=True)
    archive = shutil.make_archive(str(out / args.name), "zip", out / "app")
    shutil.rmtree(out / "app")
    print(f"bundle: {archive}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
