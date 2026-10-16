from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_frameworks_doc_is_up_to_date():
    """docs/frameworks.md tables are generated from the registry; regenerate with tools/gen_docs.py."""
    env = {**os.environ, "PY_VUI_HOME": str(ROOT / ".nonexistent-home")}
    r = subprocess.run(
        [sys.executable, "-I", str(ROOT / "tools" / "gen_docs.py"), "--check"],
        capture_output=True, text=True, env=env, cwd=ROOT,
    )
    assert r.returncode == 0, r.stdout + r.stderr


def test_docs_exist_and_cross_link():
    for name in ("user-guide", "plugins", "frameworks", "cli"):
        text = (ROOT / "docs" / f"{name}.md").read_text(encoding="utf-8")
        assert text.startswith("# ")
    guide = (ROOT / "docs" / "user-guide.md").read_text(encoding="utf-8")
    assert "plugins.md" in guide and "frameworks.md" in guide
    cli = (ROOT / "docs" / "cli.md").read_text(encoding="utf-8")
    from py_vui.cli import build_parser

    sub = next(a for a in build_parser()._actions if getattr(a, "choices", None))
    for command in sub.choices:
        assert f"`{command}" in cli, command
