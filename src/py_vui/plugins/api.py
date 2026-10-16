"""The object handed to a plugin's ``register(api)`` function.

Writing a plugin
================

A plugin is one ``.py`` file (or a package directory with ``__init__.py``) dropped into
``~/.py_vui/plugins/`` or ``<project>/plugins/``. It must define a ``PLUGIN`` dict of *literal*
metadata (py_vui reads it with ``ast`` without running your code) and a ``register(api)`` function
(run only after the user enables the plugin)::

    PLUGIN = {
        "id": "my_rating",            # unique, [a-z0-9_]
        "name": "Rating Stars",
        "version": "1.0.0",
        "description": "A 1-5 star rating widget for Tkinter.",
    }

    from py_vui.codegen.base import EmitContext, EmitResult
    from py_vui.core.registry import PropSpec, WidgetSpec


    def _emit_tk(ctx: EmitContext) -> EmitResult:
        # ctx.var: name to assign the widget to; ctx.parent: parent widget variable;
        # ctx.node.props: values of the PropSpecs below. py_vui adds placement/styling afterwards.
        stars = int(ctx.node.props.get("stars", 5))
        return EmitResult(
            imports=["import tkinter as tk"],
            lines=[f"{ctx.var} = tk.Label({ctx.parent}, text='*' * {stars})"],
        )


    def register(api):
        api.register_widget(WidgetSpec(
            type="my_rating", label="Rating", category="Plugins", icon="*",
            default_size=(140, 28), frameworks=frozenset({"tkinter"}),
            props=(PropSpec("stars", "int", 5, "Stars", minimum=1, maximum=10),),
            events=("change",),
        ))
        api.register_emitter("my_rating", "tkinter", _emit_tk)
        api.add_requirement("tkinter", "some-package>=1.0")   # optional, goes to requirements.txt

Rules: widget ``type`` ids must be unique; emitted code must only use the names ``ctx.var`` and
``ctx.parent`` plus what it imports; emitters should be pure functions of ``ctx``.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from typing import Any

from py_vui.codegen import base as codegen_base
from py_vui.core import registry
from py_vui.core.registry import FRAMEWORKS, WidgetSpec

Emitter = Callable[[Any], Any]


class PluginAPI:
    """Per-plugin registration facade that remembers everything so it can be undone."""

    def __init__(self, plugin_id: str) -> None:
        self.plugin_id = plugin_id
        self._specs: dict[str, WidgetSpec] = {}
        self._emitters: list[tuple[str, str]] = []
        self._requirements: dict[str, list[str]] = {}

    @property
    def widget_types(self) -> list[str]:
        return list(self._specs)

    def register_widget(self, spec: WidgetSpec) -> WidgetSpec:
        if spec.type in self._specs:
            msg = f"widget {spec.type!r} registered twice by plugin {self.plugin_id!r}"
            raise ValueError(msg)
        if registry.has_spec(spec.type):
            msg = f"widget type {spec.type!r} already exists; choose another id"
            raise ValueError(msg)
        spec = dataclasses.replace(spec, plugin=True, category="Plugins")
        self._specs[spec.type] = self._with_requirements(spec)
        registry.register(self._specs[spec.type])
        return self._specs[spec.type]

    def register_emitter(self, widget_type: str, framework: str, fn: Emitter) -> None:
        if framework not in FRAMEWORKS:
            msg = f"unknown framework {framework!r}; use one of {', '.join(FRAMEWORKS)}"
            raise ValueError(msg)
        if not callable(fn):
            msg = "emitter must be callable: fn(EmitContext) -> EmitResult"
            raise TypeError(msg)
        codegen_base.register_plugin_emitter(widget_type, framework, fn)
        self._emitters.append((widget_type, framework))

    def add_requirement(self, framework: str, package: str) -> None:
        """Add a pip requirement used when generating ``framework`` code with this plugin's widgets."""
        reqs = self._requirements.setdefault(framework, [])
        if package not in reqs:
            reqs.append(package)
        for t, spec in list(self._specs.items()):
            self._specs[t] = self._with_requirements(spec)
            registry.register(self._specs[t], replace=True)

    def _with_requirements(self, spec: WidgetSpec) -> WidgetSpec:
        if not self._requirements:
            return spec
        merged = {fw: tuple(r) for fw, r in spec.requires.items()}
        for fw, pkgs in self._requirements.items():
            merged[fw] = tuple(dict.fromkeys([*merged.get(fw, ()), *pkgs]))
        return dataclasses.replace(spec, requires=merged)

    def unregister_all(self) -> None:
        for t in self._specs:
            registry.unregister(t)
        for key in self._emitters:
            codegen_base._PLUGIN_EMITTERS.pop(key, None)
        self._specs.clear()
        self._emitters.clear()
