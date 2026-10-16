"""Discovery (static, via ``ast``) and loading (executing) of plugin files."""

from __future__ import annotations

import ast
import importlib.util
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_\-]*$")
MODULE_PREFIX = "py_vui_plugin_"


@dataclass
class PluginMeta:
    id: str
    name: str
    version: str = "0.0.0"
    description: str = ""
    path: Path = field(default_factory=Path)
    widget_types: list[str] = field(default_factory=list)
    error: str | None = None


def entry_file(path: Path) -> Path:
    return path / "__init__.py" if path.is_dir() else path


def candidates(directory: Path) -> list[Path]:
    """Plugin files / packages directly inside ``directory``."""
    if not directory.is_dir():
        return []
    out = []
    for p in sorted(directory.iterdir()):
        if p.name.startswith(("_", ".")):
            continue
        if p.is_file() and p.suffix == ".py" or p.is_dir() and (p / "__init__.py").is_file():
            out.append(p)
    return out


def _literal_assignments(tree: ast.Module) -> dict[str, Any]:
    found: dict[str, Any] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id == "PLUGIN":
                try:
                    found["PLUGIN"] = ast.literal_eval(node.value)
                except (ValueError, SyntaxError):
                    found["PLUGIN"] = None
    return found


def _widget_types(tree: ast.Module) -> list[str]:
    consts = {
        t.id: n.value.value
        for n in tree.body
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant)
        and isinstance(n.value.value, str)
        for t in n.targets if isinstance(t, ast.Name)
    }

    def text(node: ast.expr) -> str | None:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.Name):
            return consts.get(node.id)
        return None

    types: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            if (fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", "")) == "WidgetSpec":
                cands = [kw.value for kw in node.keywords if kw.arg == "type"]
                cands += node.args[:1]
                types += [t for t in map(text, cands) if t]
    return list(dict.fromkeys(types))


def read_metadata(path: Path) -> PluginMeta:
    """Read plugin metadata WITHOUT importing or executing the plugin."""
    fallback = path.stem if path.is_file() else path.name
    meta = PluginMeta(id=fallback, name=fallback, path=path)
    try:
        source = entry_file(path).read_text(encoding="utf-8")
        tree = ast.parse(source, str(path))
    except (OSError, SyntaxError, UnicodeDecodeError, ValueError) as exc:
        meta.error = f"cannot read plugin: {exc}"
        return meta
    info = _literal_assignments(tree).get("PLUGIN")
    meta.widget_types = _widget_types(tree)
    if not isinstance(info, dict) or not info.get("id"):
        meta.error = "missing PLUGIN = {'id': ..., 'name': ...} metadata"
        return meta
    pid = str(info["id"])
    if not _ID.match(pid):
        meta.error = f"invalid plugin id {pid!r}"
        return meta
    meta.id = pid
    meta.name = str(info.get("name") or pid)
    meta.version = str(info.get("version") or "0.0.0")
    meta.description = str(info.get("description") or "")
    has_register = any(
        isinstance(n, ast.FunctionDef) and n.name == "register" for n in tree.body
    )
    if not has_register:
        meta.error = "plugin has no register(api) function"
    return meta


def module_name(plugin_id: str) -> str:
    return MODULE_PREFIX + re.sub(r"\W", "_", plugin_id)


def load_module(path: Path, plugin_id: str) -> ModuleType:
    """Import (execute) the plugin. Only call for plugins the user explicitly enabled."""
    name = module_name(plugin_id)
    entry = entry_file(path)
    spec = importlib.util.spec_from_file_location(
        name, entry, submodule_search_locations=[str(path)] if path.is_dir() else None
    )
    if spec is None or spec.loader is None:
        msg = f"cannot import plugin from {path}"
        raise ImportError(msg)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        unload_module(plugin_id)
        raise
    return module


def unload_module(plugin_id: str) -> None:
    name = module_name(plugin_id)
    for key in [k for k in sys.modules if k == name or k.startswith(name + ".")]:
        del sys.modules[key]
