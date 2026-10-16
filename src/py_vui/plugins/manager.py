"""Plugin discovery, enable/disable state and (explicit-consent) loading.

* ``scan()`` only *reads* metadata with ``ast``. Plugin code is never executed by scanning.
* A plugin runs only after ``enable(id)``; the enabled state (id -> file path) is stored in
  ``$PY_VUI_HOME/plugins.json``. A different file claiming an enabled id (e.g. a downloaded
  project's ``plugins/`` folder) is NOT trusted: the stored path must match.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from py_vui.plugins import loader
from py_vui.plugins.api import PluginAPI
from py_vui.services.settings import home_dir, read_json, write_json


@dataclass
class PluginInfo:
    id: str
    name: str
    version: str
    description: str
    path: Path
    enabled: bool = False
    error: str | None = None
    widget_types: list[str] = field(default_factory=list)
    loaded: bool = False


#: plugin id -> its live registrations (shared by all manager instances in the process)
_LOADED: dict[str, PluginAPI] = {}
_LOAD_ERRORS: dict[str, str] = {}


class PluginManager:
    def __init__(self, project_dir: Path | None = None) -> None:
        self.project_dir = Path(project_dir) if project_dir else None

    # ----------------------------------------------------------------- paths
    @staticmethod
    def user_dir() -> Path:
        return home_dir() / "plugins"

    def search_dirs(self, project_dir: Path | None = None) -> list[Path]:
        pd = project_dir or self.project_dir
        return [self.user_dir(), *([pd / "plugins"] if pd else [])]

    @staticmethod
    def _state_file() -> Path:
        return home_dir() / "plugins.json"

    def _enabled(self) -> dict[str, str]:
        data = read_json(self._state_file(), {})
        raw = data.get("enabled", {}) if isinstance(data, dict) else {}
        return {str(k): str(v) for k, v in raw.items()} if isinstance(raw, dict) else {}

    def _save_enabled(self, enabled: dict[str, str]) -> None:
        write_json(self._state_file(), {"enabled": enabled})

    # ------------------------------------------------------------------ scan
    def scan(self, project_dir: Path | None = None) -> list[PluginInfo]:
        enabled = self._enabled()
        out: list[PluginInfo] = []
        seen: set[str] = set()
        for directory in self.search_dirs(project_dir):
            for path in loader.candidates(directory):
                meta = loader.read_metadata(path)
                error = meta.error
                if meta.id in seen:
                    error = error or f"duplicate plugin id {meta.id!r}"
                seen.add(meta.id)
                is_on = enabled.get(meta.id) == str(path.resolve())
                if is_on:
                    error = error or _LOAD_ERRORS.get(meta.id)
                out.append(PluginInfo(
                    id=meta.id, name=meta.name, version=meta.version,
                    description=meta.description, path=path, enabled=is_on, error=error,
                    widget_types=meta.widget_types, loaded=meta.id in _LOADED,
                ))
        return out

    def _find(self, plugin_id: str, project_dir: Path | None = None) -> PluginInfo:
        for info in self.scan(project_dir):
            if info.id == plugin_id:
                return info
        msg = f"no plugin with id {plugin_id!r}"
        raise KeyError(msg)

    # ---------------------------------------------------------- enable/disable
    def enable(self, plugin_id: str, project_dir: Path | None = None) -> PluginInfo:
        """Mark a plugin as trusted and load it now. Raises if it cannot be loaded."""
        _LOAD_ERRORS.pop(plugin_id, None)
        info = self._find(plugin_id, project_dir)
        problem = loader.read_metadata(info.path).error
        if problem:
            msg = f"plugin {plugin_id!r} cannot be enabled: {problem}"
            raise ValueError(msg)
        enabled = self._enabled()
        enabled[plugin_id] = str(info.path.resolve())
        self._save_enabled(enabled)
        self._unload(plugin_id)
        self._load(info)
        if plugin_id in _LOAD_ERRORS:
            enabled.pop(plugin_id, None)
            self._save_enabled(enabled)
            raise RuntimeError(f"plugin {plugin_id!r} failed to load: {_LOAD_ERRORS[plugin_id]}")
        return self._find(plugin_id, project_dir)

    def disable(self, plugin_id: str) -> None:
        enabled = self._enabled()
        enabled.pop(plugin_id, None)
        self._save_enabled(enabled)
        self._unload(plugin_id)
        _LOAD_ERRORS.pop(plugin_id, None)

    # --------------------------------------------------------------- loading
    def load_enabled(self, project_dir: Path | None = None) -> list[PluginInfo]:
        """Load every enabled plugin (errors are recorded per plugin, never raised)."""
        for info in self.scan(project_dir):
            if info.enabled and not info.loaded and not info.error:
                self._load(info)
        return [i for i in self.scan(project_dir) if i.enabled]

    def unload_all(self) -> None:
        for pid in list(_LOADED):
            self._unload(pid)

    @staticmethod
    def _load(info: PluginInfo) -> None:
        api = PluginAPI(info.id)
        _LOAD_ERRORS.pop(info.id, None)
        try:
            module = loader.load_module(info.path, info.id)
            register = getattr(module, "register", None)
            if not callable(register):
                msg = "plugin has no register(api) function"
                raise TypeError(msg)
            register(api)
        except Exception as exc:
            api.unregister_all()
            loader.unload_module(info.id)
            _LOAD_ERRORS[info.id] = f"{type(exc).__name__}: {exc}"
            return
        _LOADED[info.id] = api

    @staticmethod
    def _unload(plugin_id: str) -> None:
        api = _LOADED.pop(plugin_id, None)
        if api is not None:
            api.unregister_all()
        loader.unload_module(plugin_id)
