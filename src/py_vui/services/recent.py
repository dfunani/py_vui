"""Recently opened projects (``$PY_VUI_HOME/recent.json``)."""

from __future__ import annotations

from pathlib import Path

from py_vui.services.settings import home_dir, read_json, write_json


class RecentProjects:
    def __init__(self, max_items: int = 10) -> None:
        self.max_items = max_items

    @property
    def _file(self) -> Path:
        return home_dir() / "recent.json"

    def _raw(self) -> list[str]:
        data = read_json(self._file, [])
        return [str(x) for x in data] if isinstance(data, list) else []

    def list(self) -> list[Path]:
        """Existing entries, most recent first."""
        return [p for p in map(Path, self._raw()) if p.exists()]

    def add(self, path: Path) -> None:
        p = str(Path(path).expanduser().resolve())
        items = [p, *[x for x in self._raw() if x != p]]
        write_json(self._file, items[: self.max_items])

    def remove(self, path: Path) -> None:
        p = str(Path(path).expanduser().resolve())
        write_json(self._file, [x for x in self._raw() if x != p])

    def clear(self) -> None:
        write_json(self._file, [])
