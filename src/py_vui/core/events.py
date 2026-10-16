"""Event catalog shared by every adapter.

Every handler is generated as ``def <name>(event=None):``. Adapters translate their
native callback/signal into that shape.
"""

from __future__ import annotations

from py_vui.core.registry import EventSpec

_E = EventSpec

EVENTS: dict[str, EventSpec] = {
    e.id: e
    for e in (
        # primary / command events
        _E("click", "Click", "Primary"),
        _E("change", "Value changed", "Primary"),
        _E("toggle", "Toggled", "Primary"),
        _E("select", "Selection changed", "Primary"),
        _E("submit", "Return / Enter pressed", "Primary"),
        _E("tab_change", "Tab changed", "Primary"),
        _E("cell_change", "Cell edited", "Primary"),
        _E("close", "Close requested", "Primary"),
        _E("paint", "Paint / draw", "Primary"),
        # mouse
        _E("double_click", "Double click", "Mouse"),
        _E("right_click", "Right click", "Mouse"),
        _E("middle_click", "Middle click", "Mouse"),
        _E("mouse_press", "Mouse button press", "Mouse"),
        _E("mouse_release", "Mouse button release", "Mouse"),
        _E("mouse_move", "Mouse move", "Mouse"),
        _E("mouse_enter", "Mouse enter", "Mouse"),
        _E("mouse_leave", "Mouse leave", "Mouse"),
        _E("mouse_wheel", "Mouse wheel", "Mouse"),
        # keyboard / focus
        _E("key_press", "Key press", "Keyboard"),
        _E("key_release", "Key release", "Keyboard"),
        _E("focus_in", "Focus in", "Focus"),
        _E("focus_out", "Focus out", "Focus"),
        # geometry
        _E("resize", "Resize", "Window"),
        _E("show", "Show", "Window"),
        _E("hide", "Hide", "Window"),
    )
}

#: events every widget can bind through the generic input channel
GENERIC_EVENTS: tuple[str, ...] = (
    "double_click",
    "right_click",
    "middle_click",
    "mouse_press",
    "mouse_release",
    "mouse_move",
    "mouse_enter",
    "mouse_leave",
    "mouse_wheel",
    "key_press",
    "key_release",
    "focus_in",
    "focus_out",
    "resize",
)

#: Tk event sequences for bind()-style events (tkinter / customtkinter adapters)
TK_SEQUENCES: dict[str, str] = {
    "double_click": "<Double-Button-1>",
    "right_click": "<Button-3>",
    "middle_click": "<Button-2>",
    "mouse_press": "<ButtonPress-1>",
    "mouse_release": "<ButtonRelease-1>",
    "mouse_move": "<Motion>",
    "mouse_enter": "<Enter>",
    "mouse_leave": "<Leave>",
    "mouse_wheel": "<MouseWheel>",
    "key_press": "<KeyPress>",
    "key_release": "<KeyRelease>",
    "focus_in": "<FocusIn>",
    "focus_out": "<FocusOut>",
    "resize": "<Configure>",
    "submit": "<Return>",
    "show": "<Map>",
    "hide": "<Unmap>",
}


def event_label(event_id: str) -> str:
    spec = EVENTS.get(event_id)
    return spec.label if spec else event_id
