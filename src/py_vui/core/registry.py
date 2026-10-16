"""Widget registry: the single source of truth for every widget type.

The editor (palette, inspector, canvas), the validators and every code-generation
adapter are driven by :class:`WidgetSpec` entries registered here. Plugins add
more specs at runtime via :func:`register`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

PropKind = Literal[
    "str", "text", "int", "float", "bool", "choice", "color", "list", "file", "image", "json"
]

FRAMEWORKS: tuple[str, ...] = ("tkinter", "customtkinter", "pyside6", "pyqt6", "kivy")
FrameworkId = Literal["tkinter", "customtkinter", "pyside6", "pyqt6", "kivy"]

Category = Literal["Window", "Layout", "Input", "Display", "Data", "Plugins"]


@dataclass(frozen=True)
class PropSpec:
    name: str
    kind: PropKind = "str"
    default: Any = ""
    label: str = ""
    group: str = "General"
    choices: tuple[str, ...] = ()
    minimum: float | None = None
    maximum: float | None = None
    help: str = ""
    #: frameworks this property applies to (empty = all that support the widget)
    frameworks: frozenset[str] = frozenset()

    @property
    def title(self) -> str:
        return self.label or self.name.replace("_", " ").title()


@dataclass(frozen=True)
class EventSpec:
    """A user-bindable event. Generated handlers always have the shape ``def h(event=None)``."""

    id: str
    label: str
    group: str = "General"


@dataclass(frozen=True)
class WidgetSpec:
    type: str
    label: str
    category: Category
    icon: str = "▫"
    default_size: tuple[int, int] = (120, 32)
    min_size: tuple[int, int] = (16, 16)
    container: bool = False
    #: containers whose children are arranged into numbered pages (tabview)
    paged: bool = False
    props: tuple[PropSpec, ...] = ()
    #: event ids (see :data:`py_vui.core.events.EVENTS`) this widget can bind
    events: tuple[str, ...] = ()
    #: frameworks that can render this widget natively / via a known package
    frameworks: frozenset[str] = frozenset(FRAMEWORKS)
    #: extra pip requirements per framework (plugin widgets)
    requires: dict[str, tuple[str, ...]] = field(default_factory=dict)
    plugin: bool = False
    description: str = ""

    def prop(self, name: str) -> PropSpec | None:
        for p in self.props:
            if p.name == name:
                return p
        return None

    def default_props(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for p in self.props:
            d = p.default
            out[p.name] = list(d) if isinstance(d, list) else d
        return out

    def supports(self, framework: str) -> bool:
        return framework in self.frameworks


_REGISTRY: dict[str, WidgetSpec] = {}


def register(spec: WidgetSpec, *, replace: bool = False) -> WidgetSpec:
    if spec.type in _REGISTRY and not replace:
        msg = f"widget type already registered: {spec.type!r}"
        raise ValueError(msg)
    _REGISTRY[spec.type] = spec
    return spec


def unregister(type_id: str) -> None:
    _REGISTRY.pop(type_id, None)


def get_spec(type_id: str) -> WidgetSpec:
    try:
        return _REGISTRY[type_id]
    except KeyError as exc:
        msg = f"unknown widget type: {type_id!r}"
        raise KeyError(msg) from exc


def has_spec(type_id: str) -> bool:
    return type_id in _REGISTRY


def all_specs() -> list[WidgetSpec]:
    return list(_REGISTRY.values())


def specs_for(framework: str) -> list[WidgetSpec]:
    return [s for s in _REGISTRY.values() if s.supports(framework)]


def requirements_for(types: set[str], framework: str) -> list[str]:
    reqs: set[str] = set()
    for t in types:
        if t in _REGISTRY:
            reqs.update(_REGISTRY[t].requires.get(framework, ()))
    return sorted(reqs)
