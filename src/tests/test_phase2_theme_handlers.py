from __future__ import annotations

from pathlib import Path

from py_vui.codegen import emit_pyside_phase1
from py_vui.model.interaction import HandlerDef
from py_vui.model.nodes import ButtonNode, ButtonProps
from py_vui.model.serde import dump_json, load_json
from py_vui.model.theme import theme_for_preset


def test_theme_and_handlers_roundtrip() -> None:
    p = load_json(Path("examples/fixtures/minimal.json").read_bytes())
    p.theme = theme_for_preset("dark")
    p.handlers["on_ok"] = HandlerDef(name="on_ok", body='print("ok")')
    for node in p.nodes.values():
        if isinstance(node, ButtonNode):
            node.props = ButtonProps(text=node.props.text, on_click="on_ok")
    raw = dump_json(p)
    loaded = load_json(raw)
    assert loaded.theme.preset == "dark"
    assert "on_ok" in loaded.handlers


def test_emit_includes_theme_handlers_interactions() -> None:
    p = load_json(Path("examples/fixtures/minimal.json").read_bytes())
    p.handlers["on_test"] = HandlerDef(name="on_test", body="pass")
    for node in list(p.nodes.values()):
        if node.type == "button":
            node.props.on_click = "on_test"  # type: ignore[union-attr]
    files = {f.path: f.content for f in emit_pyside_phase1(p)}
    assert "theme.py" in files
    assert "handlers.py" in files
    assert "interactions.py" in files
    assert "def on_test" in files["handlers.py"]
    assert "apply_theme" in files["main.py"]
    assert "WIDGETS" in files["ui_generated.py"]
    assert "setStyleSheet" in files["ui_generated.py"]
