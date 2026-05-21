from __future__ import annotations

from pathlib import Path

from py_vui.codegen import emit_pyside_phase1
from py_vui.model.serde import load_json


def test_emit_minimal_contains_expected_symbols() -> None:
    p = load_json(Path("examples/fixtures/minimal.json").read_bytes())
    files = {f.path: f.content for f in emit_pyside_phase1(p)}
    ui = files["generated/ui_generated.py"]
    assert "def build_ui():" in ui
    assert "QFrame" in ui
    assert "QLabel" in ui
    main = files["generated/main.py"]
    assert "QApplication" in main
    assert "from ui_generated import build_ui" in main
