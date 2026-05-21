from __future__ import annotations

import copy

import pytest

from py_vui.model.project import py_vuiProject, validate_project
from py_vui.model.serde import load_json


def _minimal() -> py_vuiProject:
    from pathlib import Path

    return load_json(Path("examples/fixtures/minimal.json").read_bytes())


def test_validate_ok() -> None:
    validate_project(_minimal())


def test_validate_bad_root() -> None:
    p = _minimal()
    data = p.model_dump(mode="json", by_alias=True)
    data["rootId"] = "ffffffff-ffff-4fff-8fff-ffffffffffff"
    bad = py_vuiProject.model_validate(data)
    with pytest.raises(ValueError, match="missing from nodes"):
        validate_project(bad)


def test_validate_orphan() -> None:
    p = _minimal()
    data = p.model_dump(mode="json", by_alias=True)
    nodes = copy.deepcopy(data["nodes"])
    nodes["33333333-3333-4333-8333-333333333333"]["parentId"] = (
        "ffffffff-ffff-4fff-8fff-ffffffffffff"
    )
    data["nodes"] = nodes
    bad = py_vuiProject.model_validate(data)
    with pytest.raises(ValueError, match="missing parent"):
        validate_project(bad)
