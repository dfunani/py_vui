from __future__ import annotations

import ast
import sys
import textwrap
from pathlib import Path

import pytest

from py_vui.codegen import base as codegen_base
from py_vui.codegen.base import Adapter, EmitContext, EmitResult, GeneratedFile, GenOptions
from py_vui.core import ProjectDocument, make_node, new_project
from py_vui.core.registry import has_spec
from py_vui.plugins import PluginManager
from py_vui.plugins.loader import read_metadata

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "examples" / "plugins"


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("PY_VUI_HOME", str(tmp_path / "home"))
    (tmp_path / "home" / "plugins").mkdir(parents=True)
    yield tmp_path / "home"
    PluginManager().unload_all()


GOOD = textwrap.dedent('''
    from pathlib import Path
    PLUGIN = {"id": "%(id)s", "name": "Good %(id)s", "version": "1.2.3", "description": "d"}
    Path(__file__).with_name("%(id)s.ran").write_text("imported")
    from py_vui.core.registry import WidgetSpec, PropSpec

    def _emit(ctx):
        from py_vui.codegen.base import EmitResult
        return EmitResult(imports=["import tkinter as tk"],
                          lines=[f"{ctx.var} = tk.Label({ctx.parent}, text={ctx.node.props['text']!r})"])

    def register(api):
        api.register_widget(WidgetSpec(type="%(id)s_w", label="W", category="Display",
                            props=(PropSpec("text", "str", "hi"),), frameworks=frozenset({"tkinter"})))
        api.register_emitter("%(id)s_w", "tkinter", _emit)
        api.add_requirement("tkinter", "fancylib>=1")
''')


def write_plugin(directory: Path, pid: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    p = directory / f"{pid}.py"
    p.write_text(GOOD % {"id": pid})
    return p


def user_dir(home: Path) -> Path:
    return home / "plugins"


def test_scan_reads_metadata_without_executing(home):
    p = write_plugin(user_dir(home), "alpha")
    infos = PluginManager().scan()
    assert [i.id for i in infos] == ["alpha"]
    i = infos[0]
    assert (i.name, i.version, i.description, i.enabled, i.error) == (
        "Good alpha", "1.2.3", "d", False, None)
    assert i.widget_types == ["alpha_w"] and i.path == p
    assert not p.with_name("alpha.ran").exists()
    assert not has_spec("alpha_w")
    assert "py_vui_plugin_alpha" not in sys.modules


def test_scan_reports_broken_plugins(home):
    d = user_dir(home)
    (d / "syntax.py").write_text("def broken(:\n")
    (d / "nometa.py").write_text("def register(api): pass\n")
    (d / "noreg.py").write_text('PLUGIN = {"id": "noreg", "name": "x"}\n')
    (d / "_private.py").write_text("x = 1\n")
    (d / "notes.txt").write_text("ignored")
    by = {i.path.stem: i for i in PluginManager().scan()}
    assert set(by) == {"syntax", "nometa", "noreg"}
    assert all(i.error for i in by.values())
    assert "register" in by["noreg"].error
    with pytest.raises(ValueError, match="cannot be enabled"):
        PluginManager().enable("noreg")
    with pytest.raises(KeyError):
        PluginManager().enable("ghost")


def test_enable_disable_lifecycle(home):
    p = write_plugin(user_dir(home), "beta")
    mgr = PluginManager()
    info = mgr.enable("beta")
    assert info.enabled and info.loaded and p.with_name("beta.ran").exists()
    assert has_spec("beta_w") and codegen_base.plugin_emitter("beta_w", "tkinter")
    from py_vui.core.registry import get_spec

    spec = get_spec("beta_w")
    assert spec.plugin and spec.category == "Plugins"  # forced
    assert spec.requires["tkinter"] == ("fancylib>=1",)
    assert (home / "plugins.json").is_file()
    mgr.disable("beta")
    assert not has_spec("beta_w") and codegen_base.plugin_emitter("beta_w", "tkinter") is None
    assert "py_vui_plugin_beta" not in sys.modules
    assert not PluginManager().scan()[0].enabled


def test_enabled_state_persists_and_load_enabled(home):
    p = write_plugin(user_dir(home), "gamma")
    PluginManager().enable("gamma")
    PluginManager().unload_all()
    assert not has_spec("gamma_w")
    p.with_name("gamma.ran").unlink()
    loaded = PluginManager().load_enabled()
    assert [i.id for i in loaded] == ["gamma"] and has_spec("gamma_w")
    PluginManager().load_enabled()  # idempotent
    assert has_spec("gamma_w")


def test_failing_plugin_is_isolated(home):
    d = user_dir(home)
    (d / "boom.py").write_text(textwrap.dedent('''
        PLUGIN = {"id": "boom", "name": "Boom"}
        from py_vui.core.registry import WidgetSpec
        def register(api):
            api.register_widget(WidgetSpec(type="boom_w", label="B", category="Display"))
            raise RuntimeError("nope")
    '''))
    (d / "import_err.py").write_text('PLUGIN = {"id": "import_err", "name": "I"}\n'
                                     "import not_a_real_module\ndef register(api): pass\n")
    write_plugin(d, "fine")
    mgr = PluginManager()
    for pid in ("boom", "import_err"):
        with pytest.raises(RuntimeError, match="failed to load"):
            mgr.enable(pid)
    assert not has_spec("boom_w")  # rolled back
    mgr.enable("fine")
    assert has_spec("fine_w")
    assert all(not i.enabled for i in mgr.scan() if i.id in {"boom", "import_err"})


def test_load_enabled_records_error_without_raising(home):
    p = write_plugin(user_dir(home), "delta")
    PluginManager().enable("delta")
    PluginManager().unload_all()
    p.write_text(p.read_text() + "\nraise ValueError('late failure')\n")
    infos = PluginManager().load_enabled()
    assert "late failure" in infos[0].error and not infos[0].loaded


def test_project_plugins_and_path_trust(home, tmp_path):
    proj = tmp_path / "proj"
    write_plugin(proj / "plugins", "local")
    mgr = PluginManager()
    assert mgr.scan() == []
    assert [i.id for i in mgr.scan(proj)] == ["local"]
    mgr.enable("local", proj)
    assert has_spec("local_w")
    mgr.unload_all()
    # a different project shipping a plugin with the same id is NOT trusted
    evil = tmp_path / "evil"
    ep = write_plugin(evil / "plugins", "local")
    infos = PluginManager().load_enabled(evil)
    assert infos == [] and not ep.with_name("local.ran").exists() and not has_spec("local_w")
    assert [i.id for i in PluginManager().load_enabled(proj)] == ["local"]
    assert has_spec("local_w")


def test_duplicate_ids_flagged(home, tmp_path):
    write_plugin(user_dir(home), "dup")
    proj = tmp_path / "proj"
    write_plugin(proj / "plugins", "dup")
    infos = PluginManager().scan(proj)
    assert infos[0].error is None and "duplicate" in infos[1].error


def test_package_plugin(home):
    pkg = user_dir(home) / "pkgplug"
    pkg.mkdir()
    (pkg / "__init__.py").write_text(
        'PLUGIN = {"id": "pkgplug", "name": "Pkg"}\nfrom . import helper\n'
        "def register(api):\n"
        "    from py_vui.core.registry import WidgetSpec\n"
        "    api.register_widget(WidgetSpec(type=helper.TYPE, label='P', category='Display'))\n")
    (pkg / "helper.py").write_text("TYPE = 'pkgplug_w'\n")
    PluginManager().enable("pkgplug")
    assert has_spec("pkgplug_w")
    PluginManager().disable("pkgplug")
    assert not any(k.startswith("py_vui_plugin_pkgplug") for k in sys.modules)


def test_duplicate_widget_rejected(home):
    d = user_dir(home)
    (d / "clash.py").write_text(
        'PLUGIN = {"id": "clash", "name": "C"}\n'
        "def register(api):\n"
        "    from py_vui.core.registry import WidgetSpec\n"
        "    api.register_widget(WidgetSpec(type='button', label='B', category='Input'))\n")
    with pytest.raises(RuntimeError, match="already exists"):
        PluginManager().enable("clash")


class StubAdapter(Adapter):
    framework = "tkinter"
    label = "stub"

    def generate(self, project, options: GenOptions) -> list[GeneratedFile]:
        doc = ProjectDocument(project)
        names = doc.variable_names()
        lines, imports = [], set()
        for n in doc.walk():
            fn = codegen_base.plugin_emitter(n.type, self.framework)
            if fn is not None:
                res = fn(EmitContext(project, n, names[n.id], names[project.root_id], "tkinter"))
                assert isinstance(res, EmitResult)
                imports.update(res.imports)
                lines.extend(res.lines)
        return [GeneratedFile("main.py", "\n".join([*sorted(imports), *lines]) + "\n")]

    def base_requirements(self) -> list[str]:
        return []


def test_emitter_integration_with_stub_adapter(home, monkeypatch):
    write_plugin(user_dir(home), "eps")
    codegen_base.adapters()  # make sure builtin adapters were attempted first
    monkeypatch.setitem(codegen_base._ADAPTERS, "tkinter", StubAdapter())
    PluginManager().enable("eps")
    p = new_project("t", "tkinter")
    n = make_node("eps_w", parent_id=p.root_id, name="Thing", text="hello")
    p.nodes[n.id] = n
    ProjectDocument(p).validate()
    files = codegen_base.generate(p)
    src = files[0].content
    assert "import tkinter as tk" in src and "text='hello'" in src
    ast.parse(src)
    assert codegen_base.get_adapter("tkinter").requirements(p) == ["fancylib>=1"]
    PluginManager().disable("eps")
    assert codegen_base.plugin_emitter("eps_w", "tkinter") is None


def test_register_emitter_validation(home):
    from py_vui.plugins.api import PluginAPI

    api = PluginAPI("x")
    with pytest.raises(ValueError, match="unknown framework"):
        api.register_emitter("w", "wxpython", lambda c: None)
    with pytest.raises(TypeError):
        api.register_emitter("w", "tkinter", "nope")


# --------------------------------------------------------------- shipped examples
@pytest.mark.parametrize("pid", ["rating_stars", "toggle_group", "status_led"])
def test_example_plugins(pid, home):
    meta = read_metadata(EXAMPLES / f"{pid}.py")
    assert meta.error is None and meta.id == pid and meta.widget_types == [pid]
    assert (EXAMPLES / f"{pid}.py").read_text().startswith('"""')
    mgr = PluginManager()
    import shutil

    shutil.copy(EXAMPLES / f"{pid}.py", user_dir(home))
    mgr.enable(pid)
    assert has_spec(pid)
    from py_vui.core.registry import get_spec

    spec = get_spec(pid)
    p = new_project("t", "tkinter")
    n = make_node(pid, parent_id=p.root_id, name="W")
    p.nodes[n.id] = n
    for fw in sorted(spec.frameworks):
        fn = codegen_base.plugin_emitter(pid, fw)
        assert fn is not None, fw
        res = fn(EmitContext(p, n, "w", "root", fw))
        ast.parse("\n".join([*res.imports, *res.lines]))
        assert any(line.startswith("w = ") for line in res.lines)
    assert PluginManager().scan()[0].enabled
