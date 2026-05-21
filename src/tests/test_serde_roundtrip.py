from __future__ import annotations

from pathlib import Path

from py_vui.model.project import validate_project
from py_vui.model.serde import dump_json, load_json


def test_minimal_fixture_roundtrip() -> None:
    raw = Path("examples/fixtures/minimal.json").read_bytes()
    project = load_json(raw)
    validate_project(project)
    out = dump_json(project)
    project2 = load_json(out)
    validate_project(project2)
    assert project2.model_dump(mode="json") == project.model_dump(mode="json")
