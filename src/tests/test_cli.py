from __future__ import annotations

import json
import shutil
import sys
import zipfile
from pathlib import Path

import pytest

from py_vui import __version__
from py_vui.cli import main
from py_vui.codegen.base import adapters
from py_vui.plugins import PluginManager

ROOT = Path(__file__).resolve().parents[2]
needs_tk = pytest.mark.skipif("tkinter" not in adapters(), reason="tkinter adapter not available")


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("PY_VUI_HOME", str(tmp_path / "home"))
    yield
    PluginManager().unload_all()


def new_project(tmp_path: Path, name="demo", *extra: str) -> Path:
    assert main(["new", name, "-o", str(tmp_path), *extra]) == 0
    return tmp_path / name


def test_version(capsys):
    from py_vui.cli import _version

    with pytest.raises(SystemExit) as e:
        main(["--version"])
    assert e.value.code == 0
    assert capsys.readouterr().out.strip() == f"py_vui {_version()}"
    assert __version__ == "0.2.0"


def test_templates_listing(capsys):
    assert main(["templates"]) == 0
    out = capsys.readouterr().out
    assert "login_form" in out and "calculator" in out
    assert main(["templates", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert len(data) >= 14 and {"id", "name", "category", "widget_types"} <= set(data[0])


def test_new_with_template(tmp_path, capsys):
    d = new_project(tmp_path, "shop", "--template", "dashboard", "--framework", "pyside6")
    assert capsys.readouterr().out.strip() == str(d)
    data = json.loads((d / "py_vui.json").read_text())
    assert data["framework"] == "pyside6" and data["meta"]["name"] == "shop"
    assert len(data["nodes"]) > 10
    assert main(["new", "shop", "-o", str(tmp_path)]) == 0  # no clobber
    assert (tmp_path / "shop-2" / "py_vui.json").is_file()


def test_new_unknown_template(tmp_path, capsys):
    assert main(["new", "x", "-t", "nope", "-o", str(tmp_path)]) == 1
    assert "unknown template" in capsys.readouterr().err


def test_framework_choices_validated(tmp_path):
    with pytest.raises(SystemExit) as e:
        main(["new", "x", "-f", "wx", "-o", str(tmp_path)])
    assert e.value.code == 2


@needs_tk
def test_gen_default_and_output(tmp_path, capsys):
    d = new_project(tmp_path, "g1", "--template", "login_form")
    assert main(["gen", str(d)]) == 0
    assert (d / "app" / "main.py").is_file() and (d / "app" / "handlers.py").is_file()
    out = tmp_path / "out"
    assert main(["gen", str(d), "-o", str(out)]) == 0
    assert (out / "ui.py").is_file()
    solo = tmp_path / "solo"
    assert main(["gen", str(d), "-o", str(solo), "--single"]) == 0
    assert (solo / "main.py").is_file() and not (solo / "ui.py").exists()


@needs_tk
def test_gen_framework_override(tmp_path):
    if "pyside6" not in adapters():
        pytest.skip("no pyside6 adapter")
    d = new_project(tmp_path, "g2")
    out = tmp_path / "qt"
    assert main(["gen", str(d), "-o", str(out), "-f", "pyside6"]) == 0
    assert "PySide6" in (out / "ui.py").read_text() + (out / "main.py").read_text()
    # the project file itself is untouched
    assert json.loads((d / "py_vui.json").read_text())["framework"] == "tkinter"


@needs_tk
def test_validate_ok_and_failures(tmp_path, capsys):
    d = new_project(tmp_path, "v1", "--template", "todo_list")
    assert main(["validate", str(d)]) == 0
    assert "OK" in capsys.readouterr().out
    bad = tmp_path / "bad.json"
    bad.write_text("{oops")
    assert main(["validate", str(bad)]) == 1
    assert "not valid JSON" in capsys.readouterr().err
    assert main(["validate", str(tmp_path / "missing")]) == 1


def test_validate_prints_warnings(tmp_path, capsys):
    d = new_project(tmp_path, "v2", "--framework", "kivy")
    data = json.loads((d / "py_vui.json").read_text())
    root = data["rootId"]
    data["nodes"]["m"] = {"id": "m", "type": "map_view", "name": "Map", "parentId": root}
    (d / "py_vui.json").write_text(json.dumps(data))
    code = main(["validate", str(d)])
    assert "not supported" in capsys.readouterr().out
    assert code in (0, 1)


def test_migrate(tmp_path, capsys):
    src = tmp_path / "old.json"
    shutil.copy(ROOT / "examples" / "fixtures" / "minimal.json", src)
    out = tmp_path / "new.json"
    assert main(["migrate", str(src), "-o", str(out)]) == 0
    assert json.loads(out.read_text())["schemaVersion"] == "2"
    assert "migrated" in capsys.readouterr().out
    assert main(["migrate", str(src)]) == 0  # in place keeps a backup
    assert json.loads(src.read_text())["schemaVersion"] == "2"
    assert (tmp_path / "old.json.v1.bak").is_file()
    assert main(["migrate", str(src)]) == 0
    assert "already v2" in capsys.readouterr().out
    assert main(["migrate", str(tmp_path / "nothing.json")]) == 1


@needs_tk
def test_export_formats(tmp_path):
    d = new_project(tmp_path, "ex", "--template", "calculator")
    assert main(["export", str(d), str(tmp_path / "p")]) == 0
    assert (tmp_path / "p" / "main.py").is_file()
    assert main(["export", str(d), str(tmp_path / "s.py"), "--format", "single"]) == 0
    assert (tmp_path / "s.py").is_file()
    assert main(["export", str(d), str(tmp_path / "z.zip"), "--format", "zip"]) == 0
    assert "ex/main.py" in zipfile.ZipFile(tmp_path / "z.zip").namelist()


@needs_tk
def test_run_executes_generated_app(tmp_path, monkeypatch):
    d = new_project(tmp_path, "r1")
    calls = {}

    def fake_call(argv, cwd, env):
        calls.update(argv=argv, cwd=cwd)
        return 7

    monkeypatch.setattr("py_vui.cli.subprocess.call", fake_call)
    assert main(["run", str(d)]) == 7
    assert calls["argv"] == [sys.executable, "main.py"]
    assert Path(calls["cwd"]) == d / "app" and (d / "app" / "main.py").is_file()


def test_plugins_commands(tmp_path, capsys, home):
    plugins = tmp_path / "home" / "plugins"
    plugins.mkdir(parents=True)
    shutil.copy(ROOT / "examples" / "plugins" / "status_led.py", plugins)
    assert main(["plugins", "list"]) == 0
    out = capsys.readouterr().out
    assert "status_led" in out and "[disabled]" in out
    assert main(["plugins", "enable", "status_led"]) == 0
    capsys.readouterr()
    main(["plugins", "list"])
    assert "[enabled]" in capsys.readouterr().out
    assert main(["plugins", "disable", "status_led"]) == 0
    assert main(["plugins", "enable", "ghost"]) == 1
    assert "ghost" in capsys.readouterr().err
    assert main(["plugins", "enable"]) == 1


def test_plugins_list_empty(capsys):
    assert main(["plugins", "list"]) == 0
    assert "no plugins found" in capsys.readouterr().out


def test_no_args_launches_gui(monkeypatch):
    import types

    called = {}
    fake = types.ModuleType("py_vui.app.qt_main")
    fake.main = lambda *a: called.setdefault("args", a) and 0
    import py_vui.app

    monkeypatch.setitem(sys.modules, "py_vui.app.qt_main", fake)
    monkeypatch.setattr(py_vui.app, "qt_main", fake, raising=False)
    assert main([]) == 0
    assert "args" in called


def test_gui_without_pyside_is_friendly(monkeypatch, capsys):
    import builtins

    real = builtins.__import__

    def fake(name, *a, **k):
        if name.startswith("py_vui.app"):
            raise ImportError("No module named 'PySide6'")
        return real(name, *a, **k)

    monkeypatch.delitem(sys.modules, "py_vui.app.qt_main", raising=False)
    monkeypatch.setattr(builtins, "__import__", fake)
    assert main(["gui"]) == 1
    assert "PySide6" in capsys.readouterr().err
