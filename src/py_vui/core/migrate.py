"""Upgrade schema v1 (PySide-only) projects to v2."""

from __future__ import annotations

from typing import Any

from py_vui.core.model import SCHEMA_VERSION

_TYPE_MAP = {
    "line_edit": "entry", "text_edit": "text", "radio_button": "radio",
    "spin_box": "spinbox", "combo_box": "combobox", "list_widget": "listbox",
    "group_box": "label_frame", "tab_widget": "tabview", "progress_bar": "progressbar",
    "scroll_area": "scroll_frame", "date_edit": "date_entry", "time_edit": "time_entry",
    "table_widget": "table",
}
_PROP_MAP: dict[str, dict[str, str]] = {
    "spinbox": {"min": "minimum", "max": "maximum"},
    "slider": {"min": "minimum", "max": "maximum"},
    "dial": {"min": "minimum", "max": "maximum"},
    "progressbar": {"max": "maximum"},
    "combobox": {"currentIndex": "current"},
    "tabview": {"currentIndex": "current"},
    "date_entry": {"date": "date"},
}
_EVENT_PROPS = {
    "onClick": "click", "onReturn": "submit", "onToggle": "toggle", "onChange": "change",
    "onSelect": "select", "onSelection": "select", "onCellChanged": "cell_change",
}
_THEME_PRESET_OK = {"light", "dark", "modern", "ocean"}


def migrate_v1(raw: dict[str, Any]) -> dict[str, Any]:
    nodes: dict[str, Any] = {}
    for nid, n in raw.get("nodes", {}).items():
        t = _TYPE_MAP.get(n["type"], n["type"])
        props = dict(n.get("props", {}))
        events: dict[str, str] = {}
        for k in list(props):
            if k in _EVENT_PROPS:
                v = props.pop(k)
                if v:
                    events[_EVENT_PROPS[k]] = v
        for old, new in _PROP_MAP.get(t, {}).items():
            if old in props:
                props[new] = props.pop(old)
        if t == "tabview":
            props["tabs"] = [x["title"] if isinstance(x, dict) else x for x in props.get("tabs", [])]
        if t == "table":
            cols = int(props.pop("columns", 3))
            rows = int(props.pop("rows", 3))
            props["columns"] = [f"Column {i + 1}" for i in range(cols)]
            props["rows"] = [["" for _ in range(cols)] for _ in range(rows)]
        if t == "window":
            props.pop("menus", None) if not props.get("menus") else None
        if t == "listbox" and "items" not in props:
            props["items"] = ["Item 1", "Item 2"]
        layout = n.get("layout", {})
        style = {k: v for k, v in (n.get("style") or {}).items() if v is not None}
        if "border_radius" in style:
            style["corner_radius"] = style.pop("border_radius")
        node: dict[str, Any] = {
            "id": nid, "type": t, "name": n.get("name", t), "parentId": n.get("parentId"),
            "zIndex": n.get("zIndex", 0), "box": layout.get("box", {}),
            "anchors": layout.get("anchors", {}), "props": props, "style": style,
            "events": events, "enabled": n.get("enabled", True), "tooltip": n.get("tooltip", ""),
        }
        if n.get("tabIndex") is not None:
            node["tabIndex"] = n["tabIndex"]
        nodes[nid] = node
    # drop menu item handler references into the json menus prop (kept as-is)
    theme = dict(raw.get("theme", {}))
    if theme.get("preset") not in _THEME_PRESET_OK:
        theme["preset"] = "modern"
    handlers = {
        k: {"name": v.get("name", k), "body": v.get("body", v.get("source", "pass"))}
        for k, v in raw.get("handlers", {}).items()
    }
    return {
        "schemaVersion": SCHEMA_VERSION, "meta": raw.get("meta", {"name": "Untitled"}),
        "framework": "pyside6", "rootId": raw["rootId"], "nodes": nodes, "theme": theme,
        "handlers": handlers, "tabOrder": raw.get("tabOrder", []),
    }


def migrate(raw: dict[str, Any]) -> dict[str, Any]:
    version = str(raw.get("schemaVersion", "1"))
    if version == "1":
        return migrate_v1(raw)
    if version == SCHEMA_VERSION:
        return raw
    msg = f"unsupported schemaVersion {version!r}"
    raise ValueError(msg)
