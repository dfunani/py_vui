from __future__ import annotations

import json
import os
import shutil
import sys
import time
import zipfile
from pathlib import Path

import pytest

from py_vui.codegen.base import adapters
from py_vui.commands import SetField, SetHandler
from py_vui.core import make_node
from py_vui.core.model import HandlerDef
from py_vui.core.serde import dump_json
from py_vui.preview.runner import PreviewProcess, run_preview
from py_vui.services import RecentProjects, settings
from py_vui.services.project_service import ProjectService, RunSpec, slugify
from py_vui.services.runtime import ensure_runtime

ROOT = Path(__file__).resolve().parents[2]
needs_tk = pytest.mark.skipif("tkinter" not in adapters(), reason="tkinter adapter not available")


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("PY_VUI_HOME", str(tmp_path / "home"))
    return tmp_path / "home"


def add_button(svc: ProjectService, name: str = "Go", handler: str | None = None):
    n = make_node("button", parent_id=svc.project.root_id, name=name, x=10, y=10)
    from py_vui.commands import AddNode

    svc.history.push(svc.doc, AddNode(n))
    if handler:
        svc.history.push(svc.doc, SetHandler(handler, HandlerDef(name=handler, body="print(1)")))
        svc.history.push(svc.doc, SetField(n.id, "events", "click", handler))
    return n


def saved(tmp_path: Path, name: str = "My App") -> ProjectService:
    svc = ProjectService()
    svc.new_project(name)
    svc.save_as(tmp_path, name)
    return svc


# ------------------------------------------------------------------ lifecycle
def test_new_project_defaults():
    svc = ProjectService()
    assert svc.project.meta.name == "Untitled"
    assert svc.project.framework == "tkinter"
    assert svc.project_dir is None and not svc.dirty and not svc.migrated
    svc.new_project("X", "pyside6", template="login_form")
    assert svc.project.meta.name == "X" and svc.project.framework == "pyside6"
    assert len(svc.project.nodes) > 3


def test_save_requires_folder():
    with pytest.raises(ValueError, match="Save As"):
        ProjectService().save()


def test_save_as_layout_and_dirty(tmp_path):
    svc = ProjectService()
    svc.new_project("My App")
    add_button(svc)
    assert svc.dirty
    path = svc.save_as(tmp_path)
    d = tmp_path / "my-app"
    assert path == d / "py_vui.json"
    assert (d / "session.meta.json").is_file() and (d / "assets").is_dir()
    assert svc.project_dir == d and not svc.dirty
    add_button(svc, "Two")
    assert svc.dirty
    svc.save()
    assert not svc.dirty
    other = ProjectService()
    other.new_project("My App")
    assert other.save_as(tmp_path).parent.name == "my-app-2"
    assert slugify("  Hello World! ") == "hello-world"


def test_open_dir_file_roundtrip(tmp_path):
    svc = saved(tmp_path)
    add_button(svc, "Btn")
    svc.save()
    for target in (svc.project_dir, svc.project_dir / "py_vui.json"):
        again = ProjectService()
        again.open(target)
        assert again.project == svc.project
        assert again.project_dir == svc.project_dir and not again.dirty and not again.migrated


def test_open_foreign_json_needs_save_as(tmp_path):
    svc = ProjectService()
    svc.open(ROOT / "examples" / "minimal.json")
    assert svc.project_dir is None and svc.dirty
    svc.save_as(tmp_path)
    assert (tmp_path / "minimal" / "py_vui.json").is_file()


def test_open_errors(tmp_path):
    svc = ProjectService()
    with pytest.raises(ValueError, match="does not exist"):
        svc.open(tmp_path / "nope")
    with pytest.raises(ValueError, match="py_vui.json"):
        svc.open(tmp_path)
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    with pytest.raises(ValueError, match="not valid JSON"):
        svc.open(bad)
    bad.write_text('{"hello": 1}')
    with pytest.raises(ValueError, match="not a py_vui project"):
        svc.open(bad)
    bad.write_text(json.dumps({"schemaVersion": "2", "nodes": {}}))
    with pytest.raises(ValueError, match="not a valid"):
        svc.open(bad)
    # a failed open leaves the current document intact
    assert svc.project.meta.name == "Untitled"


def test_v1_migration_on_open_and_save(tmp_path):
    d = tmp_path / "old"
    d.mkdir()
    shutil.copy(ROOT / "examples" / "fixtures" / "minimal.json", d / "py_vui.json")
    svc = ProjectService()
    svc.open(d)
    assert svc.migrated and svc.dirty and svc.project.schema_version == "2"
    svc.save()
    assert not svc.migrated and not svc.dirty
    assert (d / "py_vui.v1.json.bak").is_file()
    assert json.loads((d / "py_vui.json").read_text())["schemaVersion"] == "2"
    again = ProjectService()
    again.open(d)
    assert not again.migrated


def test_autosave_and_recover(tmp_path):
    svc = saved(tmp_path)
    assert svc.autosave() is None  # clean
    assert ProjectService().autosave() is None  # unsaved
    n = add_button(svc, "Unsaved")
    auto = svc.autosave()
    assert auto == svc.project_dir / ".py_vui.autosave.json"
    assert svc.recovery_path() is None or auto.stat().st_mtime > (svc.path.stat().st_mtime)
    now = time.time()
    os.utime(svc.path, (now - 100, now - 100))
    os.utime(auto, (now, now))
    fresh = ProjectService()
    fresh.open(svc.project_dir)
    assert n.id not in fresh.project.nodes
    assert fresh.recovery_path() == auto
    fresh.recover()
    assert n.id in fresh.project.nodes and fresh.dirty
    fresh.save()
    assert not auto.exists() and fresh.recovery_path() is None
    with pytest.raises(ValueError):
        fresh.recover()


# --------------------------------------------------------------------- assets
def test_assets_unsaved_then_save_as(tmp_path):
    img = tmp_path / "pic one.png"
    img.write_bytes(b"\x89PNG-fake")
    svc = ProjectService()
    rel = svc.add_asset(img)
    assert rel == "assets/pic_one.png" and svc.project.assets == [rel]
    assert svc.add_asset(img) == rel and svc.project.assets == [rel]  # identical => reused
    img2 = tmp_path / "sub" / "pic one.png"
    img2.parent.mkdir()
    img2.write_bytes(b"different")
    assert svc.add_asset(img2) == "assets/pic_one_2.png"
    svc.save_as(tmp_path / "proj")
    assert (svc.project_dir / "assets" / "pic_one.png").read_bytes() == b"\x89PNG-fake"
    assert (svc.project_dir / "assets" / "pic_one_2.png").read_bytes() == b"different"
    svc.history.undo(svc.doc)
    assert svc.project.assets == [rel]
    svc.remove_asset(rel)
    assert svc.project.assets == []
    with pytest.raises(ValueError):
        svc.add_asset(tmp_path / "missing.png")


# ------------------------------------------------------------------ generation
@needs_tk
def test_generate_roundtrip_and_user_code(tmp_path):
    svc = saved(tmp_path)
    add_button(svc, "Go", "on_go")
    img = tmp_path / "logo.png"
    img.write_bytes(b"png")
    svc.add_asset(img)
    files = svc.generated_files()
    assert {"main.py", "ui.py", "handlers.py"} <= {f.path for f in files}
    app = svc.generate()
    assert app == svc.project_dir / "app"
    assert (app / "main.py").is_file() and (app / "assets" / "logo.png").is_file()
    compile((app / "ui.py").read_text(), "ui.py", "exec")
    # custom.py is user owned
    (app / "custom.py").write_text("# mine\n")
    svc.generate()
    assert (app / "custom.py").read_text() == "# mine\n"
    # editing a handler in the editor is regenerated
    svc.history.push(svc.doc, SetHandler("on_go", HandlerDef(name="on_go", body="print('editor')")))
    svc.generate()
    assert "print('editor')" in (app / "handlers.py").read_text()


@needs_tk
def test_handler_sync_from_disk(tmp_path):
    svc = saved(tmp_path)
    add_button(svc, "Go", "on_go")
    app = svc.generate()
    hp = app / "handlers.py"
    hp.write_text(hp.read_text().replace("print(1)", "print('from disk')"))
    assert svc.sync_handlers_from_disk() == 1
    assert svc.project.handlers["on_go"].body.strip() == "print('from disk')"
    assert svc.sync_handlers_from_disk() == 0
    assert svc.history.undo(svc.doc)
    assert svc.project.handlers["on_go"].body == "print(1)"


@needs_tk
def test_generate_pulls_external_handler_edits(tmp_path):
    svc = saved(tmp_path)
    add_button(svc, "Go", "on_go")
    app = svc.generate()
    hp = app / "handlers.py"
    hp.write_text(hp.read_text().replace("print(1)", "print('edited in IDE')"))
    svc.generate()
    assert "print('edited in IDE')" in hp.read_text()
    assert svc.project.handlers["on_go"].body.strip() == "print('edited in IDE')"


@needs_tk
def test_generate_unsaved_uses_temp_dir():
    svc = ProjectService()
    out = svc.generate()
    assert (out / "main.py").is_file() and svc.project_dir is None


@needs_tk
def test_export_formats(tmp_path):
    svc = saved(tmp_path)
    add_button(svc, "Go", "on_go")
    img = tmp_path / "a.png"
    img.write_bytes(b"x")
    svc.add_asset(img)
    out = svc.export(tmp_path / "out_project")
    assert (out / "main.py").is_file() and (out / "assets" / "a.png").is_file()
    single = svc.export(tmp_path / "solo.py", "single")
    assert single.is_file() and "def on_go" in single.read_text()
    z = svc.export(tmp_path, "zip")
    assert z.name == "my-app.zip"
    names = zipfile.ZipFile(z).namelist()
    assert "my-app/main.py" in names and "my-app/assets/a.png" in names
    z2 = svc.export(tmp_path / "named", "zip")
    assert z2.suffix == ".zip"
    with pytest.raises(ValueError, match="unknown export format"):
        svc.export(tmp_path / "x", "rar")


def test_write_files_rejects_escape(tmp_path):
    from py_vui.codegen.base import GeneratedFile

    svc = ProjectService()
    with pytest.raises(ValueError, match="escapes"):
        svc.write_files(tmp_path / "o", [GeneratedFile("../evil.py", "x")])


# ------------------------------------------------------------------------ run
def test_run_spec_and_missing(tmp_path):
    svc = saved(tmp_path)
    svc.project.extra_requirements.append("definitely_not_installed_pkg>=1")
    spec = svc.run_spec()
    assert isinstance(spec, RunSpec)
    assert spec.argv == [sys.executable, "main.py"] and spec.cwd == svc.project_dir / "app"
    assert spec.env["PYTHONUNBUFFERED"] == "1"
    assert "definitely_not_installed_pkg>=1" in spec.missing_requirements
    svc.project.extra_requirements = ["pytest>=1"]
    assert "pytest>=1" not in svc.run_spec().missing_requirements


def test_probe_other_interpreter(tmp_path):
    svc = ProjectService()
    svc.project.extra_requirements.append("definitely_not_installed_pkg")
    wrapper = tmp_path / "py.sh"
    wrapper.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n')
    wrapper.chmod(0o755)
    if sys.platform == "win32":
        pytest.skip("shell wrapper")
    assert "definitely_not_installed_pkg" in svc.run_spec(wrapper).missing_requirements


def test_build_executable_command(tmp_path):
    svc = saved(tmp_path)
    cmd = svc.build_executable_command()
    assert "PyInstaller" in cmd and "--onefile" in cmd and cmd[-1] == "main.py"
    assert "--onedir" in svc.build_executable_command(onefile=False)


def test_preview_runner(tmp_path):
    script = tmp_path / "hello.py"
    script.write_text("import sys\nprint('hi')\nprint('err', file=sys.stderr)\nsys.exit(3)\n")
    res = run_preview(tmp_path, Path("hello.py"))
    assert (res.returncode, res.stdout.strip(), res.stderr.strip()) == (3, "hi", "err")
    assert res.status_code == 3 and res.response == res.stdout and res.error == res.stderr
    with pytest.raises(ValueError):
        run_preview(tmp_path, Path("missing.py"))
    spec = RunSpec([sys.executable, "hello.py"], tmp_path, dict(os.environ), [])
    proc = PreviewProcess(spec).start()
    assert proc.wait(20) == 3
    out = dict()
    for stream, line in proc.drain():
        out.setdefault(stream, []).append(line)
    assert out == {"stdout": ["hi"], "stderr": ["err"]}
    assert not proc.running
    proc.stop()


def test_preview_process_stop(tmp_path):
    (tmp_path / "loop.py").write_text("import time\ntime.sleep(60)\n")
    spec = RunSpec([sys.executable, "loop.py"], tmp_path, dict(os.environ), [])
    proc = PreviewProcess(spec).start()
    assert proc.running
    proc.stop()
    assert not proc.running


def test_ensure_runtime_creates_venv_for_real(tmp_path):
    py = ensure_runtime(tmp_path, [], uv=None)
    assert py.exists() and py.parent.parent.name == "venv"
    assert ensure_runtime(tmp_path, [], uv=None) == py  # reuse


class FakeRunner:
    """Records commands; creates the venv python on ``venv`` / ``uv venv`` like the real tools."""

    def __init__(self, fail: tuple[str, ...] = ()):
        self.calls: list[list[str]] = []
        self.fail = fail

    def __call__(self, cmd, progress=None):
        self.calls.append(list(cmd))
        joined = " ".join(cmd)
        if any(f in joined for f in self.fail):
            raise RuntimeError(f"boom: {joined}")
        target = None
        if "venv" in cmd and ("--without-pip" in cmd or cmd[1] == "venv"):
            target = Path(cmd[-1])
        if target is not None:
            from py_vui.services.runtime import venv_python

            py = venv_python(target)
            py.parent.mkdir(parents=True, exist_ok=True)
            py.write_text("")


def test_ensure_runtime_uv_path(tmp_path):
    r = FakeRunner()
    py = ensure_runtime(tmp_path, ["a>=1", "b"], runner=r, uv="/bin/uv")
    assert r.calls[0][:2] == ["/bin/uv", "venv"]
    assert r.calls[1][:3] == ["/bin/uv", "pip", "install"] and "a>=1" in r.calls[1]
    assert str(py) in r.calls[1]
    n = len(r.calls)
    ensure_runtime(tmp_path, ["b", "a>=1"], runner=r, uv="/bin/uv")  # same set: nothing to do
    assert len(r.calls) == n


def test_ensure_runtime_pip_path(tmp_path):
    r = FakeRunner()
    ensure_runtime(tmp_path, ["a"], runner=r, uv=None)
    assert r.calls[0][1:4] == ["-m", "venv", "--without-pip"]
    assert r.calls[1][1:4] == ["-m", "pip", "--version"]
    assert r.calls[2][1:4] == ["-m", "pip", "install"]


def test_ensure_runtime_bootstraps_pip_with_ensurepip(tmp_path):
    r = FakeRunner(fail=("pip --version",))
    ensure_runtime(tmp_path, ["a"], runner=r, uv=None)
    assert any("ensurepip" in " ".join(c) for c in r.calls)
    assert r.calls[-1][1:4] == ["-m", "pip", "install"]


def test_ensure_runtime_fallbacks_and_errors(tmp_path):
    # uv venv fails -> python -m venv; uv pip fails -> pip
    r = FakeRunner(fail=("uv venv", "uv pip"))
    msgs: list[str] = []
    ensure_runtime(tmp_path / "a", ["x"], msgs.append, runner=r, uv="uv")
    flat = [" ".join(c) for c in r.calls]
    assert any("--without-pip" in c for c in flat) and any("-m pip install" in c for c in flat)
    assert any("falling back" in m for m in msgs)
    # no pip and no ensurepip -> clear error
    r2 = FakeRunner(fail=("pip --version", "ensurepip"))
    with pytest.raises(RuntimeError, match="pip is unavailable"):
        ensure_runtime(tmp_path / "b", ["x"], runner=r2, uv=None)
    # nothing can create a venv
    r3 = FakeRunner(fail=("venv",))
    with pytest.raises(RuntimeError, match="could not create a virtual environment"):
        ensure_runtime(tmp_path / "c", [], runner=r3, uv="uv")
    assert not (tmp_path / "c" / ".py_vui" / "venv").exists()


def test_executable_command_end_to_end_with_fake_runner(tmp_path):
    """The PyInstaller command is runnable from the generated app dir (runner is faked)."""
    img = tmp_path / "i.png"
    img.write_bytes(b"x")
    svc = saved(tmp_path)
    svc.add_asset(img)
    seen = {}

    def fake_run(cmd, cwd):
        seen["cmd"], seen["cwd"] = cmd, Path(cwd)
        dist = Path(cwd) / "dist"
        dist.mkdir()
        (dist / cmd[cmd.index("--name") + 1]).write_text("binary")
        return 0

    if "tkinter" in adapters():
        app = svc.generate()
    else:
        app = svc.app_dir
        app.mkdir(parents=True)
        (app / "main.py").write_text("print(1)\n")
    cmd = svc.build_executable_command(onefile=True)
    assert fake_run(cmd, app) == 0
    assert seen["cwd"] == app and (app / seen["cmd"][-1]).is_file()
    assert cmd[:3] == [sys.executable, "-m", "PyInstaller"]
    assert cmd[cmd.index("--name") + 1] == "my-app" and "--windowed" in cmd
    data = cmd[cmd.index("--add-data") + 1]
    assert data == f"assets{os.pathsep}assets"
    assert (app / "dist" / "my-app").read_text() == "binary"
    assert "--onedir" in svc.build_executable_command(onefile=False)
    assert "--onefile" not in svc.build_executable_command(onefile=False)


# ------------------------------------------------------------ settings / recent
def test_settings_roundtrip(home):
    assert settings.get("theme", "dark") == "dark"
    settings.set("theme", "light")
    assert settings.get("theme") == "light"
    assert json.loads((home / "settings.json").read_text())["theme"] == "light"
    (home / "settings.json").write_text("garbage")
    assert settings.get("theme", "x") == "x"


def test_recent_projects(tmp_path):
    r = RecentProjects(max_items=2)
    a, b, c = (tmp_path / n for n in "abc")
    for p in (a, b, c):
        p.mkdir()
        r.add(p)
    assert r.list() == [c.resolve(), b.resolve()]  # capped, newest first
    r.add(b)
    assert r.list()[0] == b.resolve()
    shutil.rmtree(c)
    assert r.list() == [b.resolve()]  # missing paths dropped
    r.remove(b)
    assert r.list() == []
    r.add(a)
    r.clear()
    assert r.list() == []


def test_dump_stable(tmp_path):
    svc = saved(tmp_path)
    assert svc.path.read_text() == dump_json(svc.project)


@needs_tk
def test_export_options_assets_requirements_framework(tmp_path):
    svc = saved(tmp_path)
    add_button(svc, "Go", "on_go")
    img = tmp_path / "a.png"
    img.write_bytes(b"x")
    svc.add_asset(img)
    out = svc.export(tmp_path / "lean", include_assets=False, include_requirements=False)
    assert (out / "main.py").is_file()
    assert not (out / "assets").exists() and not (out / "requirements.txt").exists()
    full = svc.export(tmp_path / "full")
    assert (full / "assets" / "a.png").is_file() and (full / "requirements.txt").is_file()
    z = svc.export(tmp_path / "lean.zip", "zip", include_assets=False, include_requirements=False)
    names = zipfile.ZipFile(z).namelist()
    assert "my-app/main.py" in names
    assert not any("assets" in n or n.endswith("requirements.txt") for n in names)
    single = svc.export(tmp_path / "s.py", "single", include_assets=False)
    assert single.is_file()
    # framework override affects the output only, never the document
    before = svc.project.framework
    qt = svc.export(tmp_path / "qt", framework="pyside6")
    assert "PySide6" in (qt / "ui.py").read_text(encoding="utf-8")
    assert svc.project.framework == before
