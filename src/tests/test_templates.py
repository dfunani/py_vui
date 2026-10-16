from __future__ import annotations

import pytest

from py_vui.codegen.base import GenOptions, adapters, check_syntax, generate
from py_vui.core import ProjectDocument
from py_vui.core.layout_engine import resolve_children
from py_vui.core.serde import dump_json, load_json
from py_vui.services.templates import list_templates, load_template

IDS = [t.id for t in list_templates()]


def test_catalog_size_and_metadata():
    infos = list_templates()
    assert len(infos) >= 14 and len(set(IDS)) == len(IDS)
    assert IDS[0] == "empty"
    for t in infos:
        assert t.name and t.description and t.category and t.tags
        assert "window" in t.widget_types


def test_expected_templates_present():
    assert {
        "login_form", "sign_up_form", "contact_form", "settings_dialog", "calculator",
        "todo_list", "dashboard", "data_table_viewer", "file_converter", "media_player",
        "chat_window", "landing_page", "empty", "multi_window_app",
    } <= set(IDS)


def test_layout_modes_covered():
    modes = set()
    for tid in IDS:
        doc = ProjectDocument(load_template(tid))
        modes |= {n.layout.mode for n in doc.project.nodes.values() if n.layout}
    assert modes == {"absolute", "flex", "grid"}


@pytest.mark.parametrize("tid", IDS)
def test_template_loads_and_validates(tid):
    p = load_template(tid)
    doc = ProjectDocument(p)
    doc.validate()
    assert p.framework == "tkinter" and p.schema_version == "2"
    assert load_json(dump_json(p)) == p  # serde round trip
    for d in doc.diagnostics():
        assert d.level != "error", d.message
        assert "missing" not in d.message and "unknown property" not in d.message, d.message
    for n in p.nodes.values():  # every window is resolvable by the layout engine
        if n.layout is not None and n.layout.mode != "absolute":
            resolve_children(doc, n.id)
    for h in p.handlers.values():
        compile(f"def {h.name}(event=None):\n" + "".join(f"    {ln}\n" for ln in h.body.splitlines()),
                h.name, "exec")


@pytest.mark.parametrize("tid", IDS)
def test_fresh_ids_each_load(tid):
    a, b = load_template(tid), load_template(tid)
    assert not set(a.nodes) & set(b.nodes)
    assert a.root_id != b.root_id
    assert [n.name for n in a.nodes.values()] == [n.name for n in b.nodes.values()]


def test_framework_override_and_unknown():
    assert load_template("empty", "pyside6").framework == "pyside6"
    with pytest.raises(KeyError, match="unknown template"):
        load_template("nope")


@pytest.mark.parametrize("framework", ["tkinter", "customtkinter", "pyside6", "pyqt6", "kivy"])
@pytest.mark.parametrize("tid", IDS)
def test_template_generates(tid, framework):
    if framework not in adapters():
        pytest.skip(f"{framework} adapter not available")
    p = load_template(tid, framework)
    for layout in ("project", "single"):
        files = generate(p, GenOptions(layout=layout))
        assert files and check_syntax(files) == []
        assert any(f.path == "main.py" for f in files)
