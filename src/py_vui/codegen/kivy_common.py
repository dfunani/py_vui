"""Pieces shared by the Kivy adapter: colour parsing and the generated runtime helpers.

The helpers are plain Python source that is pasted (only the ones a project uses) into the
generated ``ui.py`` / single-file ``main.py``. Keeping them as source (instead of a runtime
package) means generated apps have no dependency on py_vui.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# --------------------------------------------------------------------------- colours
_NAMED = {
    "white": "#ffffff", "black": "#000000", "red": "#ff0000", "green": "#008000",
    "blue": "#0000ff", "yellow": "#ffff00", "orange": "#ffa500", "purple": "#800080",
    "gray": "#808080", "grey": "#808080", "pink": "#ffc0cb", "cyan": "#00ffff",
    "magenta": "#ff00ff", "brown": "#a52a2a", "transparent": "#00000000",
}
_HEX = re.compile(r"^#?([0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")


def parse_color(value: object) -> tuple[float, float, float, float] | None:
    """``'#rgb' | '#rrggbb' | '#rrggbbaa' | name`` -> RGBA floats (None when unparsable)."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().lower()
    text = _NAMED.get(text, text)
    m = _HEX.match(text)
    if not m:
        return None
    h = m.group(1)
    if len(h) in (3, 4):
        h = "".join(c * 2 for c in h)
    if len(h) == 6:
        h += "ff"
    r, g, b, a = (int(h[i : i + 2], 16) / 255 for i in range(0, 8, 2))
    return (r, g, b, a)


def num(v: float) -> str:
    """Compact deterministic number literal."""
    f = float(v)
    if f == int(f):
        return str(int(f))
    return f"{round(f, 3):g}"


def rgba_src(c: tuple[float, float, float, float]) -> str:
    return "(" + ", ".join(num(round(x, 3)) for x in c) + ")"


def mix(a: tuple[float, ...], b: tuple[float, ...], t: float) -> tuple[float, float, float, float]:
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(4))  # type: ignore[return-value]


# --------------------------------------------------------------------------- kivy imports
#: class / function name -> module that provides it
KIVY_MODULES: dict[str, str] = {
    "Config": "kivy.config",
    "Window": "kivy.core.window",
    "dp": "kivy.metrics",
    "Clock": "kivy.clock",
    "Animation": "kivy.animation",
    "Color": "kivy.graphics",
    "Line": "kivy.graphics",
    "Ellipse": "kivy.graphics",
    "RoundedRectangle": "kivy.graphics",
    "BooleanProperty": "kivy.properties",
    "NumericProperty": "kivy.properties",
    "StringProperty": "kivy.properties",
    "ListProperty": "kivy.properties",
    "Widget": "kivy.uix.widget",
    "Label": "kivy.uix.label",
    "Button": "kivy.uix.button",
    "ToggleButton": "kivy.uix.togglebutton",
    "CheckBox": "kivy.uix.checkbox",
    "Switch": "kivy.uix.switch",
    "Slider": "kivy.uix.slider",
    "Spinner": "kivy.uix.spinner",
    "TextInput": "kivy.uix.textinput",
    "Image": "kivy.uix.image",
    "AsyncImage": "kivy.uix.image",
    "FloatLayout": "kivy.uix.floatlayout",
    "BoxLayout": "kivy.uix.boxlayout",
    "AnchorLayout": "kivy.uix.anchorlayout",
    "GridLayout": "kivy.uix.gridlayout",
    "ScrollView": "kivy.uix.scrollview",
    "TabbedPanel": "kivy.uix.tabbedpanel",
    "TabbedPanelItem": "kivy.uix.tabbedpanel",
    "Splitter": "kivy.uix.splitter",
    "Popup": "kivy.uix.popup",
    "TreeView": "kivy.uix.treeview",
    "TreeViewLabel": "kivy.uix.treeview",
    "ActionBar": "kivy.uix.actionbar",
    "ActionView": "kivy.uix.actionbar",
    "ActionPrevious": "kivy.uix.actionbar",
    "ActionGroup": "kivy.uix.actionbar",
    "ActionButton": "kivy.uix.actionbar",
    "ActionToggleButton": "kivy.uix.actionbar",
    "ActionSeparator": "kivy.uix.actionbar",
}


@dataclass(frozen=True)
class Helper:
    name: str
    source: str
    #: other helpers this one calls
    needs: tuple[str, ...] = ()
    #: names from KIVY_MODULES it uses
    kivy: tuple[str, ...] = ()
    #: plain ``import x`` lines it uses
    std: tuple[str, ...] = ()


_H: list[Helper] = []


def _helper(name: str, source: str, needs=(), kivy=(), std=()) -> None:
    _H.append(Helper(name, source.strip("\n") + "\n", tuple(needs), tuple(kivy), tuple(std)))


_helper("asset", '''
_HERE = os.path.dirname(os.path.abspath(__file__))


def asset(path):
    """Resolve a bundled file (assets/<name>) relative to this module."""
    if not path or path.startswith(("http://", "https://")) or os.path.isabs(path):
        return path
    return os.path.join(_HERE, path)
''', std=("os",))

_helper("event", '''
class UiEvent:
    """What handlers receive: ``.widget`` plus details such as value, pos, key, index..."""

    def __init__(self, widget=None, **info):
        self.widget = widget
        self.__dict__.update(info)

    def __repr__(self):
        return f"UiEvent({self.__dict__!r})"


def _fire(handler, widget=None, **info):
    handler(UiEvent(widget, **info))
    return False  # never swallow the Kivy event
''')

_helper("pin", '''
def _pin(widget, parent, x, y, w, h, pw, ph, anchors="lt"):
    """Place ``widget`` at design coordinates (origin top-left, in dp) inside ``parent``.

    Kivy's origin is bottom-left, so the position is derived from the parent's top edge.
    ``anchors`` lists the edges (l, t, r, b) the widget stays pinned to when the parent is
    resized; pinning opposite edges stretches the widget, pinning none keeps it centred.
    """
    k = dp(1)
    left, top, right, bottom = ("l" in anchors, "t" in anchors, "r" in anchors, "b" in anchors)
    rm, bm = pw - x - w, ph - y - h

    def update(*_):
        width, height = parent.width / k, parent.height / k
        if left and right:
            nx, nw = x, width - x - rm
        elif right:
            nx, nw = width - rm - w, w
        elif left:
            nx, nw = x, w
        else:
            nx, nw = x + (width - pw) / 2, w
        if top and bottom:
            ny, nh = y, height - y - bm
        elif bottom:
            ny, nh = height - bm - h, h
        elif top:
            ny, nh = y, h
        else:
            ny, nh = y + (height - ph) / 2, h
        nw, nh = max(0, nw), max(0, nh)
        widget.size = (nw * k, nh * k)
        widget.pos = (parent.x + nx * k, parent.y + parent.height - (ny + nh) * k)

    parent.bind(pos=update, size=update)
    update()
''', kivy=("dp",))

_helper("grid", '''
def _grid(parent, items, col_weights, row_weights, col_gap, row_gap, pad):
    """Lay ``items`` out in rows/columns inside ``parent`` (spans, sticky and weights).

    items: (widget, row, col, row_span, col_span, sticky, w, h) in design dp;
    pad: (top, right, bottom, left). Mirrors the py_vui editor's grid layout.
    """
    k = dp(1)
    ncols = max([len(col_weights)] + [i[2] + i[4] for i in items])
    nrows = max([len(row_weights)] + [i[1] + i[3] for i in items])
    min_w, min_h = [0.0] * ncols, [0.0] * nrows
    for _w, r, c, rs, cs, _s, w, h in items:
        if cs == 1:
            min_w[c] = max(min_w[c], w)
        if rs == 1:
            min_h[r] = max(min_h[r], h)

    def tracks(count, weights, total, gap, mins):
        sizes = list(mins)
        free = total - sum(sizes) - gap * max(0, count - 1)
        wsum = sum(weights[i] if i < len(weights) else 0 for i in range(count))
        if wsum > 0 and free > 0:
            for i in range(count):
                sizes[i] += free * (weights[i] if i < len(weights) else 0) / wsum
        return sizes

    def update(*_):
        width, height = parent.width / k, parent.height / k
        iw, ih = max(0, width - pad[1] - pad[3]), max(0, height - pad[0] - pad[2])
        cw = tracks(ncols, col_weights, iw, col_gap, min_w)
        rh = tracks(nrows, row_weights, ih, row_gap, min_h)
        xs, ys = [0.0], [0.0]
        for c in cw:
            xs.append(xs[-1] + c + col_gap)
        for r in rh:
            ys.append(ys[-1] + r + row_gap)
        for widget, r, c, rs, cs, sticky, w, h in items:
            cell_w = xs[c + cs] - col_gap - xs[c]
            cell_h = ys[r + rs] - row_gap - ys[r]
            if "e" in sticky and "w" in sticky:
                w, x = cell_w, xs[c]
            elif "e" in sticky:
                x = xs[c] + cell_w - w
            elif "w" in sticky:
                x = xs[c]
            else:
                x = xs[c] + (cell_w - w) / 2
            if "n" in sticky and "s" in sticky:
                h, y = cell_h, ys[r]
            elif "s" in sticky:
                y = ys[r] + cell_h - h
            elif "n" in sticky:
                y = ys[r]
            else:
                y = ys[r] + (cell_h - h) / 2
            w, h = max(1, w), max(1, h)
            widget.size = (w * k, h * k)
            widget.pos = (parent.x + (pad[3] + x) * k,
                          parent.y + parent.height - (pad[0] + y + h) * k)

    parent.bind(pos=update, size=update)
    update()
''', kivy=("dp",))

_helper("paint", '''
def _paint(widget, color, radius=0, border=0, border_color=None, hover=None, down=None):
    """Draw a (rounded) background and optional border behind ``widget``.

    ``hover`` / ``down`` are the fill colours while the mouse is over it / it is pressed.
    Returns the fill ``Color`` instruction.
    """
    r, b = dp(radius), dp(border)
    with widget.canvas.before:
        if b:
            Color(*(border_color or color))
            edge = RoundedRectangle(radius=[r])
        fill = Color(*color)
        face = RoundedRectangle(radius=[max(0, r - b)])

    def sync(*_):
        if b:
            edge.pos, edge.size = widget.pos, widget.size
        face.pos = (widget.x + b, widget.y + b)
        face.size = (max(0, widget.width - 2 * b), max(0, widget.height - 2 * b))

    widget.bind(pos=sync, size=sync)
    sync()
    if hover or down:
        flags = {"over": False}

        def tint(*_):
            pressed = down and getattr(widget, "state", "normal") == "down"
            fill.rgba = down if pressed else hover if flags["over"] and hover else color

        def over(inside):
            flags["over"] = inside
            tint()

        if down and hasattr(widget, "state"):
            widget.bind(state=tint)
        if hover:
            _hover(widget, lambda pos: over(True), lambda: over(False))
    return fill
''', needs=("hover",), kivy=("Color", "RoundedRectangle", "dp"))

_helper("hover", '''
def _hover(widget, enter=None, leave=None, move=None):
    """Call enter(pos) / leave() / move(pos) while the mouse moves over ``widget``."""
    state = {"inside": False}

    def on_mouse(_window, pos):
        inside = widget.get_root_window() is not None and widget.collide_point(
            *widget.to_widget(*pos)
        )
        if inside and not state["inside"]:
            state["inside"] = True
            if enter:
                enter(pos)
        elif not inside and state["inside"]:
            state["inside"] = False
            if leave:
                leave()
        if inside and move:
            move(pos)

    Window.bind(mouse_pos=on_mouse)
''', kivy=("Window",))

_helper("fit", '''
def _fit(widget):
    """Let a Label/Button honour halign/valign inside its bounds."""
    widget.bind(size=lambda w, s: setattr(w, "text_size", s))
    widget.text_size = widget.size
''')

_helper("vcenter", '''
def _vcenter(field, pad_x=8):
    """Vertically centre the text of a single-line TextInput."""
    def update(*_):
        field.padding = [dp(pad_x), max(dp(2), (field.height - field.line_height) / 2)]

    field.bind(size=update)
    update()
''', kivy=("dp",))

_helper("limit", '''
def _limit(widget, max_length):
    """Cap the length of a TextInput."""
    widget.bind(text=lambda w, v: setattr(w, "text", v[:max_length]) if len(v) > max_length else 0)
''')

_helper("cursor", '''
def _cursor(widget, name):
    """Show a system mouse cursor while hovering ``widget``."""
    def set_cursor(value):
        try:
            Window.set_system_cursor(value)
        except Exception:  # not supported by this window provider
            pass

    _hover(widget, lambda pos: set_cursor(name), lambda: set_cursor("arrow"))
''', needs=("hover",), kivy=("Window",))

_helper("tip", '''
def _tip(widget, text):
    """Tooltip: a small label next to the mouse while hovering ``widget``."""
    tip = Label(text=text, size_hint=(None, None), color=(1, 1, 1, 1), font_size=dp(12))
    with tip.canvas.before:
        Color(0.1, 0.1, 0.12, 0.95)
        box = RoundedRectangle(radius=[dp(4)])

    def sync(*_):
        box.pos, box.size = tip.pos, tip.size

    tip.bind(pos=sync, size=sync)
    shown = []

    def show(pos, _dt=None):
        tip.texture_update()
        tip.size = (tip.texture_size[0] + dp(16), tip.texture_size[1] + dp(8))
        tip.pos = (min(pos[0] + dp(12), max(0, Window.width - tip.width)),
                   max(0, pos[1] - tip.height - dp(12)))
        if not shown:
            Window.add_widget(tip)
            shown.append(True)

    pending = []

    def enter(pos):
        pending[:] = [Clock.schedule_once(lambda dt: show(pos), 0.4)]

    def leave():
        for ev in pending:
            ev.cancel()
        pending.clear()
        if shown:
            shown.clear()
            Window.remove_widget(tip)

    _hover(widget, enter, leave)
''', needs=("hover",), kivy=("Label", "Color", "RoundedRectangle", "Window", "Clock", "dp"))

_helper("icon", '''
def _icon(widget, source, position="left"):
    """Show an image next to the text of a Label/Button and shift the text to make room."""
    img = Image(source=asset(source), size_hint=(None, None))
    widget.add_widget(img)
    gap = dp(6)

    def sync(*_):
        s = max(0, min(widget.height - dp(8), dp(32)))
        img.size = (s, s)
        tw, th = widget.texture_size
        cx, cy = widget.x + widget.width / 2, widget.y + widget.height / 2
        if position in ("left", "right"):
            group = s + gap + tw
            halign = getattr(widget, "halign", "center")
            if halign == "left":
                start = widget.x + dp(8)
            elif halign == "right":
                start = widget.x + widget.width - dp(8) - group
            else:
                start = cx - group / 2
            if position == "left":
                img.pos = (start, cy - s / 2)
                widget.padding = [s + gap, 0, 0, 0]
            else:
                img.pos = (start + tw + gap, cy - s / 2)
                widget.padding = [0, 0, s + gap, 0]
        elif position == "top":
            img.pos = (cx - s / 2, cy + (s + gap + th) / 2 - s)
            widget.padding = [0, s + gap, 0, 0]
        elif position == "bottom":
            img.pos = (cx - s / 2, cy - (s + gap + th) / 2)
            widget.padding = [0, 0, 0, s + gap]
        else:  # center: image behind the text
            img.pos = (cx - s / 2, cy - s / 2)

    widget.bind(pos=sync, size=sync, texture_size=sync)
    sync()
''', needs=("asset",), kivy=("Image", "dp"))

_helper("on", '''
_BUTTON_OF = {"click": "left", "double_click": "left", "right_click": "right",
              "middle_click": "middle"}
_TOUCH_EVENTS = ("click", "double_click", "right_click", "middle_click", "mouse_press",
                 "mouse_release", "mouse_wheel")


def _active(widget):
    """Should a key event be delivered to ``widget``?"""
    if widget is Window or hasattr(widget, "_is_open"):
        return widget is Window or widget._is_open
    if hasattr(widget, "focus"):
        return bool(widget.focus)
    return widget.collide_point(*widget.to_widget(*Window.mouse_pos))


def _on(widget, event_id, handler):
    """Bind a generic input event; ``handler`` receives a UiEvent."""

    def fire(*_args, **info):
        handler(UiEvent(widget, **info))
        return False

    if event_id in _TOUCH_EVENTS:
        def on_touch(_w, touch):
            if not widget.collide_point(*touch.pos):
                return False
            button = getattr(touch, "button", "left")
            wheel = button.startswith("scroll")
            if event_id == "mouse_wheel":
                ok = wheel
            elif wheel:
                ok = False
            elif event_id in _BUTTON_OF:
                ok = button == _BUTTON_OF[event_id]
                ok = ok and (event_id != "double_click" or bool(getattr(touch, "is_double_tap", 0)))
            else:
                ok = True
            if ok:
                fire(pos=tuple(touch.pos), button=button, touch=touch)
            return False

        if event_id in ("click", "mouse_release"):
            widget.bind(on_touch_up=on_touch)
        else:
            widget.bind(on_touch_down=on_touch)
    elif event_id == "mouse_move":
        _hover(widget, move=lambda pos: fire(pos=pos))
    elif event_id == "mouse_enter":
        _hover(widget, enter=lambda pos: fire(pos=pos))
    elif event_id == "mouse_leave":
        _hover(widget, leave=fire)
    elif event_id == "key_press":
        def key_down(_win, key, scancode=None, codepoint=None, modifiers=None, *_a):
            if _active(widget):
                fire(key=key, scancode=scancode, text=codepoint, modifiers=list(modifiers or []))
            return False

        Window.bind(on_key_down=key_down)
    elif event_id == "key_release":
        def key_up(_win, key, scancode=None, *_a):
            if _active(widget):
                fire(key=key, scancode=scancode)
            return False

        Window.bind(on_key_up=key_up)
    elif event_id in ("focus_in", "focus_out"):
        want = event_id == "focus_in"
        try:
            widget.bind(focus=lambda w, v: fire(value=v) if bool(v) == want else None)
        except KeyError:  # widget cannot take focus
            pass
    elif event_id == "resize":
        widget.bind(size=lambda w, s: fire(size=tuple(s)))
    elif event_id in ("show", "hide", "close"):
        if widget is Window:
            name = {"show": "on_show", "hide": "on_minimize", "close": "on_request_close"}
        else:
            name = {"show": "on_open", "hide": "on_dismiss", "close": "on_dismiss"}
        widget.bind(**{name[event_id]: lambda *a: fire()})
''', needs=("event", "hover"), kivy=("Window",))

_helper("shortcut", '''
_KEYCODES = {"enter": 13, "return": 13, "esc": 27, "escape": 27, "tab": 9, "space": 32,
             "backspace": 8, "delete": 127, "up": 273, "down": 274, "right": 275, "left": 276,
             **{f"f{i}": 281 + i for i in range(1, 13)}}
_MODS = {"ctrl": "ctrl", "control": "ctrl", "cmd": "ctrl", "command": "ctrl", "meta": "ctrl",
         "shift": "shift", "alt": "alt", "option": "alt"}


def _shortcut(spec, handler):
    """Bind a keyboard shortcut such as 'Ctrl+O' (Cmd counts as Ctrl on macOS)."""
    *mods, key = [p.strip().lower() for p in spec.split("+")]
    wanted = {_MODS.get(m, m) for m in mods}
    code = _KEYCODES.get(key, ord(key) if len(key) == 1 else None)

    def on_key(_win, keycode, scancode=None, codepoint=None, modifiers=None, *_a):
        have = {_MODS.get(m, m) for m in (modifiers or [])}
        if keycode == code and have == wanted:
            handler(UiEvent(Window, shortcut=spec))
        return False

    Window.bind(on_key_down=on_key)
''', needs=("event",), kivy=("Window",))

_helper("taborder", '''
def _tab_order(widgets):
    """Chain keyboard focus (Tab / Shift+Tab) through ``widgets`` in the given order."""
    chain = [w for w in widgets if hasattr(w, "focus_next")]
    for a, b in zip(chain, chain[1:] + chain[:1]):
        a.focus_next = b
        b.focus_previous = a
''')

_helper("Option", '''
class Option(BoxLayout):
    """Checkbox / radio button / switch with a caption: ``.active``, ``.text``, ``.control``."""

    __events__ = ("on_click",)
    active = BooleanProperty(False)
    text = StringProperty("")

    def __init__(self, text="", kind="check", group=None, active=False, color=(0, 0, 0, 1),
                 font_size=None, **kw):
        super().__init__(orientation="horizontal", spacing=dp(6), **kw)
        self.kind = kind
        if kind == "switch":
            self.control = Switch(size_hint=(None, 1), width=dp(83))
            self.control.bind(on_touch_up=self._control_up)
        else:
            self.control = CheckBox(group=group if kind == "radio" else None, color=color,
                                    allow_no_selection=kind != "radio", size_hint=(None, 1),
                                    width=dp(28))
            self.control.bind(on_release=lambda *a: self.dispatch("on_click"))
        self.label = Label(text=text, color=color, halign="left", valign="middle",
                           font_size=font_size or dp(13))
        _fit(self.label)
        self.label.bind(on_touch_up=self._label_up)
        self.add_widget(self.control)
        self.add_widget(self.label)
        self.control.active = self.active = active
        self.text = text
        self.control.bind(active=lambda w, v: setattr(self, "active", v))
        self.bind(active=lambda w, v: setattr(self.control, "active", v),
                  text=lambda w, v: setattr(self.label, "text", v))

    def toggle(self):
        self.active = True if self.kind == "radio" else not self.active

    def _control_up(self, widget, touch):
        if widget.collide_point(*touch.pos):
            self.dispatch("on_click")
        return False

    def _label_up(self, widget, touch):
        if widget.collide_point(*touch.pos) and not self.disabled:
            self.toggle()
            self.dispatch("on_click")
        return False

    def on_click(self, *args):
        pass
''', needs=("fit",),
        kivy=("BoxLayout", "BooleanProperty", "StringProperty", "Switch", "CheckBox", "Label", "dp"))

_helper("SliderRow", '''
class SliderRow(BoxLayout):
    """A Slider with a live value read-out; ``.value`` mirrors the slider (``.slider``)."""

    value = NumericProperty(0)

    def __init__(self, slider, color=(0, 0, 0, 1), font_size=None, decimals=0, **kw):
        vertical = slider.get("orientation") == "vertical"
        super().__init__(orientation="vertical" if vertical else "horizontal", spacing=dp(8), **kw)
        self.slider = Slider(**slider)
        self.readout = Label(color=color, font_size=font_size or dp(13))
        if vertical:
            self.readout.size_hint, self.readout.height = (1, None), dp(24)
        else:
            self.readout.size_hint, self.readout.width = (None, 1), dp(44)
        if vertical:
            self.add_widget(self.readout)
            self.add_widget(self.slider)
        else:
            self.add_widget(self.slider)
            self.add_widget(self.readout)
        fmt = "{:.%df}" % decimals
        self.value = self.slider.value
        self.readout.text = fmt.format(self.slider.value)
        self.slider.bind(value=lambda w, v: setattr(self, "value", v))
        self.slider.bind(value=lambda w, v: setattr(self.readout, "text", fmt.format(v)))
        self.bind(value=lambda w, v: setattr(self.slider, "value", v))
''', kivy=("BoxLayout", "NumericProperty", "Slider", "Label", "dp"))

_helper("SpinBox", '''
class SpinBox(BoxLayout):
    """Numeric field with - / + buttons: ``.value`` (clamped to minimum..maximum)."""

    value = NumericProperty(0)

    def __init__(self, minimum=0, maximum=100, value=0, step=1, decimals=0, wrap=False,
                 color=(0, 0, 0, 1), field=(1, 1, 1, 1), accent=(0.4, 0.4, 0.9, 1),
                 accent_hover=None, button_text=(1, 1, 1, 1), border=(0.8, 0.8, 0.8, 1),
                 font_size=None, **kw):
        super().__init__(orientation="horizontal", spacing=dp(3), **kw)
        self.minimum, self.maximum, self.step = minimum, maximum, step
        self.decimals, self.wrap = decimals, wrap
        fs = font_size or dp(13)
        flat = dict(background_normal="", background_down="", background_color=(0, 0, 0, 0),
                    color=button_text, font_size=fs, size_hint=(None, 1), width=dp(32))
        self.minus, self.plus = Button(text="-", **flat), Button(text="+", **flat)
        for b in (self.minus, self.plus):
            _paint(b, accent, 4, hover=accent_hover or accent)
        self.field = TextInput(
            multiline=False, halign="center", font_size=fs, foreground_color=color,
            cursor_color=color, input_filter="int" if decimals == 0 else "float",
            background_normal="", background_active="", background_color=(0, 0, 0, 0))
        _paint(self.field, field, 4, 1, border)
        _vcenter(self.field, 4)
        self.add_widget(self.minus)
        self.add_widget(self.field)
        self.add_widget(self.plus)
        self.minus.bind(on_release=lambda *a: self.step_by(-1))
        self.plus.bind(on_release=lambda *a: self.step_by(1))
        self.field.bind(on_text_validate=self._commit, focus=lambda w, v: v or self._commit())
        self.value = min(max(value, minimum), maximum)
        self.field.text = self._fmt(self.value)

    def _fmt(self, v):
        return f"{v:.{self.decimals}f}"

    def step_by(self, direction):
        v = self.value + direction * self.step
        if self.wrap and v > self.maximum:
            v = self.minimum
        elif self.wrap and v < self.minimum:
            v = self.maximum
        self.value = round(v, 6)

    def _commit(self, *_):
        try:
            self.value = float(self.field.text)
        except ValueError:
            pass
        self.field.text = self._fmt(self.value)

    def on_value(self, _w, v):
        clamped = min(max(v, self.minimum), self.maximum)
        if clamped != v:
            self.value = clamped
        else:
            self.field.text = self._fmt(v)
''', needs=("paint", "vcenter"),
        kivy=("BoxLayout", "NumericProperty", "Button", "TextInput", "dp"))

_helper("ListBox", '''
class ListBox(ScrollView):
    """Scrollable list of selectable rows: ``.items``, ``.selection`` (indices), ``on_select``."""

    __events__ = ("on_select",)
    selection = ListProperty([])

    def __init__(self, items=(), multiple=False, color=(0, 0, 0, 1), selected=(0.4, 0.4, 0.9, 1),
                 selected_text=(1, 1, 1, 1), font_size=None, row_height=30, **kw):
        super().__init__(**kw)
        self.multiple, self.color, self.selected = multiple, color, selected
        self.selected_text, self.row_height = selected_text, row_height
        self.font_size = font_size or dp(13)
        self.box = BoxLayout(orientation="vertical", size_hint_y=None)
        self.box.bind(minimum_height=self.box.setter("height"))
        self.add_widget(self.box)
        self.set_items(items)

    def set_items(self, items):
        self.box.clear_widgets()
        self.items = [str(i) for i in items]
        self.selection = []
        self.rows = []
        group = None if self.multiple else f"listbox{id(self)}"
        for index, text in enumerate(self.items):
            row = ToggleButton(
                text=text, group=group, allow_no_selection=self.multiple, size_hint_y=None,
                height=dp(self.row_height), color=self.color, font_size=self.font_size,
                halign="left", valign="middle", background_normal="", background_down="",
                background_color=(0, 0, 0, 0))
            _fit(row)
            row.padding_x = dp(8)
            _paint(row, (0, 0, 0, 0), down=self.selected)
            row.bind(state=lambda w, s, i=index: self._changed(i, s, w))
            self.rows.append(row)
            self.box.add_widget(row)

    def select(self, *indices):
        """Select rows programmatically (single mode keeps the last index)."""
        chosen = indices if self.multiple else indices[-1:]
        for i, row in enumerate(self.rows):
            if i in chosen:
                row.state = "down"
            elif not self.multiple:
                row.state = "normal"

    def _changed(self, index, state, row):
        row.color = self.selected_text if state == "down" else self.color
        chosen = set(self.selection)
        if self.multiple:
            chosen.add(index) if state == "down" else chosen.discard(index)
        elif state == "down":
            chosen = {index}
        else:
            return
        new = sorted(chosen)
        if new != list(self.selection):
            self.selection = new
            self.dispatch("on_select", new)

    def on_select(self, *args):
        pass
''', needs=("fit", "paint"),
        kivy=("ScrollView", "ListProperty", "BoxLayout", "ToggleButton", "dp"))

_helper("Segmented", '''
class Segmented(BoxLayout):
    """Row of mutually exclusive toggle buttons: ``.current`` (index), ``.items``."""

    current = NumericProperty(-1)

    def __init__(self, items=(), current=0, color=(0, 0, 0, 1), normal=(1, 1, 1, 1),
                 selected=(0.4, 0.4, 0.9, 1), selected_text=(1, 1, 1, 1), border=(0.8, 0.8, 0.8, 1),
                 font_size=None, **kw):
        super().__init__(orientation="horizontal", spacing=dp(1), **kw)
        self.items = [str(i) for i in items]
        self.buttons = []
        group = f"segmented{id(self)}"
        for index, text in enumerate(self.items):
            b = ToggleButton(text=text, group=group, allow_no_selection=False, color=color,
                             font_size=font_size or dp(13), background_normal="",
                             background_down="", background_color=(0, 0, 0, 0))
            _paint(b, normal, 0, 1, border, down=selected)
            b.bind(state=lambda w, s, i=index, c=color, sc=selected_text: self._state(i, s, w, c, sc))
            self.buttons.append(b)
            self.add_widget(b)
        if 0 <= current < len(self.buttons):
            self.buttons[current].state = "down"
        self.current = current if 0 <= current < len(self.buttons) else -1

    def _state(self, index, state, button, color, selected_text):
        button.color = selected_text if state == "down" else color
        if state == "down":
            self.current = index

    def on_current(self, _w, value):
        for i, button in enumerate(self.buttons):
            button.state = "down" if i == int(value) else "normal"
''', needs=("paint",), kivy=("BoxLayout", "NumericProperty", "ToggleButton", "dp"))

_helper("Table", '''
class Table(BoxLayout):
    """Grid of cells with an optional header: ``.rows``, ``.selection`` (row indices).

    Events: ``on_select(row, values)`` and ``on_cell_change(row, column, value)``.
    """

    __events__ = ("on_select", "on_cell_change")

    def __init__(self, columns=(), rows=(), header=True, editable=False, selection="single",
                 color=(0, 0, 0, 1), header_bg=(0.9, 0.9, 0.9, 1), selected=(0.8, 0.85, 1, 1),
                 font_size=None, row_height=30, **kw):
        super().__init__(orientation="vertical", **kw)
        self.columns = [str(c) for c in columns]
        self.editable, self.mode, self.color = editable, selection, color
        self.selected, self.font_size, self.row_height = selected, font_size or dp(13), row_height
        self.selection = []
        self.rows = []
        self.cells = []
        if header and self.columns:
            head = GridLayout(cols=len(self.columns), size_hint_y=None, height=dp(row_height),
                              spacing=dp(1))
            for title in self.columns:
                cell = Label(text=title, bold=True, color=color, font_size=self.font_size)
                _paint(cell, header_bg)
                head.add_widget(cell)
            self.add_widget(head)
        self.scroll = ScrollView()
        self.grid = GridLayout(cols=max(1, len(self.columns)), size_hint_y=None, spacing=dp(1),
                               row_default_height=dp(row_height), row_force_default=True)
        self.grid.bind(minimum_height=self.grid.setter("height"))
        self.scroll.add_widget(self.grid)
        self.add_widget(self.scroll)
        self.set_rows(rows)

    def set_rows(self, rows):
        self.grid.clear_widgets()
        self.rows = [[str(v) for v in row] for row in rows]
        self.cells, self.selection = [], []
        for r, row in enumerate(self.rows):
            line = []
            for c in range(len(self.columns)):
                text = row[c] if c < len(row) else ""
                if self.editable:
                    cell = TextInput(
                        text=text, multiline=False, font_size=self.font_size,
                        foreground_color=self.color, cursor_color=self.color,
                        background_normal="", background_active="", background_color=(0, 0, 0, 0))
                    _vcenter(cell, 6)
                    cell.bind(text=lambda w, v, r=r, c=c: self._edited(r, c, v),
                              focus=lambda w, v, r=r: v and self._pick(r))
                else:
                    cell = Button(
                        text=text, color=self.color, font_size=self.font_size, halign="left",
                        valign="middle", background_normal="", background_down="",
                        background_color=(0, 0, 0, 0))
                    _fit(cell)
                    cell.padding_x = dp(6)
                    cell.bind(on_release=lambda w, r=r: self._pick(r))
                cell.fill = _paint(cell, (0, 0, 0, 0))
                line.append(cell)
                self.grid.add_widget(cell)
            self.cells.append(line)

    def _edited(self, r, c, value):
        while len(self.rows[r]) <= c:
            self.rows[r].append("")
        self.rows[r][c] = value
        self.dispatch("on_cell_change", r, c, value)

    def _pick(self, r):
        if self.mode == "none":
            return
        if self.mode == "multiple" and r in self.selection:
            self.selection.remove(r)
        elif self.mode == "multiple":
            self.selection.append(r)
        else:
            self.selection = [r]
        for i, line in enumerate(self.cells):
            for cell in line:
                cell.fill.rgba = self.selected if i in self.selection else (0, 0, 0, 0)
        self.dispatch("on_select", r, list(self.rows[r]))

    def on_select(self, *args):
        pass

    def on_cell_change(self, *args):
        pass
''', needs=("fit", "paint", "vcenter"),
        kivy=("BoxLayout", "GridLayout", "Label", "Button", "TextInput", "ScrollView", "dp"))

_helper("tree", '''
def _tree(items, header="Items", show_header=False, color=(0, 0, 0, 1), font_size=None, **kw):
    """Scrollable tree from ``[{"text": ..., "children": [...]}]``; the TreeView is ``.tree``."""
    scroll = ScrollView(**kw)
    tree = TreeView(hide_root=not show_header, size_hint_y=None,
                    root_options={"text": header, "color": color})
    tree.bind(minimum_height=tree.setter("height"))

    def add(parent, nodes):
        for item in nodes:
            data = item if isinstance(item, dict) else {"text": str(item)}
            node = tree.add_node(
                TreeViewLabel(text=str(data.get("text", "")), color=color,
                              font_size=font_size or dp(13)), parent)
            add(node, data.get("children", []))

    add(None, items)
    scroll.add_widget(tree)
    scroll.tree = tree
    return scroll
''', kivy=("ScrollView", "TreeView", "TreeViewLabel", "dp"))

_helper("Progress", '''
class Progress(Widget):
    """Progress bar (horizontal or vertical) drawn with the theme colours."""

    value = NumericProperty(0)
    maximum = NumericProperty(100)

    def __init__(self, vertical=False, fill=(0.4, 0.4, 0.9, 1), track=(0.85, 0.85, 0.85, 1),
                 color=(0, 0, 0, 1), show_text=False, indeterminate=False, radius=4,
                 font_size=None, **kw):
        super().__init__(**kw)
        self.vertical = vertical
        with self.canvas:
            Color(*track)
            self._track = RoundedRectangle(radius=[dp(radius)])
            Color(*fill)
            self._fill = RoundedRectangle(radius=[dp(radius)])
        self._label = None
        if show_text:
            self._label = Label(color=color, font_size=font_size or dp(12))
            self.add_widget(self._label)
        self.bind(pos=self._draw, size=self._draw, value=self._draw, maximum=self._draw)
        self._draw()
        if indeterminate:
            self.start()

    def start(self):
        """Bounce the bar back and forth (indeterminate mode)."""
        anim = Animation(value=self.maximum, d=1.2) + Animation(value=0, d=1.2)
        anim.repeat = True
        anim.start(self)

    def _draw(self, *_):
        self._track.pos, self._track.size = self.pos, self.size
        frac = 0 if self.maximum <= 0 else min(max(self.value / self.maximum, 0), 1)
        self._fill.pos = self.pos
        if self.vertical:
            self._fill.size = (self.width, self.height * frac)
        else:
            self._fill.size = (self.width * frac, self.height)
        if self._label is not None:
            self._label.text = f"{round(frac * 100)}%"
            self._label.center = (self.x + self.width / 2, self.y + self.height / 2)
''', kivy=("Widget", "NumericProperty", "Color", "RoundedRectangle", "Label", "Animation", "dp"))

_helper("Paint", '''
class Paint(Widget):
    """Free-drawing surface. Set ``.painter = fn(widget)``; draw on ``widget.canvas``."""

    painter = None

    def __init__(self, **kw):
        super().__init__(**kw)
        self.bind(pos=self.repaint, size=self.repaint)

    def repaint(self, *_):
        self.canvas.clear()
        if self.painter is not None:
            self.painter(self)
''', kivy=("Widget",))

_helper("Calendar", '''
class Calendar(BoxLayout):
    """Month calendar: ``.date`` ("YYYY-MM-DD") and the ``on_change`` event."""

    __events__ = ("on_change",)
    date = StringProperty("")

    def __init__(self, date="", monday_first=True, week_numbers=False, color=(0, 0, 0, 1),
                 accent=(0.4, 0.4, 0.9, 1), accent_text=(1, 1, 1, 1), font_size=None, **kw):
        super().__init__(orientation="vertical", spacing=dp(4), **kw)
        try:
            current = datetime.date.fromisoformat(date)
        except ValueError:
            current = datetime.date.today()
        self.date = current.isoformat()
        self._view = current.replace(day=1)
        self._opts = (monday_first, week_numbers, color, accent, accent_text, font_size or dp(13))
        flat = dict(background_normal="", background_down="", background_color=(0, 0, 0, 0),
                    color=color, font_size=self._opts[5])
        head = BoxLayout(size_hint_y=None, height=dp(32))
        self._title = Label(color=color, bold=True, font_size=self._opts[5])
        prev = Button(text="<", size_hint_x=None, width=dp(36), **flat)
        nxt = Button(text=">", size_hint_x=None, width=dp(36), **flat)
        prev.bind(on_release=lambda *a: self._shift(-1))
        nxt.bind(on_release=lambda *a: self._shift(1))
        for w in (prev, self._title, nxt):
            head.add_widget(w)
        self.add_widget(head)
        self._grid = GridLayout(cols=8 if week_numbers else 7, spacing=dp(2))
        self.add_widget(self._grid)
        self._build()

    def _shift(self, months):
        index = self._view.year * 12 + self._view.month - 1 + months
        self._view = datetime.date(index // 12, index % 12 + 1, 1)
        self._build()

    def _build(self):
        monday_first, week_numbers, color, accent, accent_text, fs = self._opts
        view = self._view
        self._title.text = f"{view:%B %Y}"
        grid = self._grid
        grid.clear_widgets()
        first = 0 if monday_first else 6
        if week_numbers:
            grid.add_widget(Label(text="#", color=color, font_size=fs))
        for i in range(7):
            grid.add_widget(Label(text=calendar.day_abbr[(first + i) % 7], color=color,
                                  bold=True, font_size=fs))
        for week in calendar.Calendar(firstweekday=first).monthdatescalendar(view.year, view.month):
            if week_numbers:
                grid.add_widget(Label(text=str(week[0].isocalendar()[1]), color=color,
                                      font_size=fs))
            for day in week:
                chosen = day.isoformat() == self.date
                dim = (color[0], color[1], color[2], 0.4)
                button = Button(text=str(day.day), font_size=fs, background_normal="",
                                background_down="",
                                color=accent_text if chosen else color if day.month == view.month else dim,
                                background_color=accent if chosen else (0, 0, 0, 0))
                button.bind(on_release=lambda w, d=day: self.pick(d))
                grid.add_widget(button)

    def pick(self, day):
        self.date = day.isoformat()
        self._view = day.replace(day=1)
        self._build()
        self.dispatch("on_change", self.date)

    def on_change(self, *args):
        pass
''', kivy=("BoxLayout", "StringProperty", "Label", "Button", "GridLayout", "dp"),
        std=("calendar", "datetime"))

_helper("flexh", '''
def _flex(parent, items, row, gap, justify, align, wrap, pad):
    """Flex layout with wrapping and grow-on-top-of-basis, like the py_vui editor.

    items: (widget, w, h, grow, align_self, (top, right, bottom, left)) in design dp;
    pad: (top, right, bottom, left). Re-lays out whenever ``parent`` moves or resizes.
    """
    k = dp(1)

    def msize(it):
        m = it[5]
        return (it[1] if row else it[2]) + ((m[3] + m[1]) if row else (m[0] + m[2]))

    def update(*_):
        width, height = parent.width / k, parent.height / k
        iw, ih = max(0, width - pad[1] - pad[3]), max(0, height - pad[0] - pad[2])
        main_size, cross_size = (iw, ih) if row else (ih, iw)
        lines, used = [[]], 0
        for it in items:
            size = msize(it)
            if wrap and lines[-1] and used + size + gap > main_size:
                lines.append([])
                used = 0
            used += size + (gap if lines[-1] else 0)
            lines[-1].append(it)
        line_cross = cross_size / len(lines) if wrap and len(lines) > 1 else cross_size
        cross_pos = 0
        for line in lines:
            if not line:
                continue
            free = main_size - sum(msize(i) for i in line) - gap * (len(line) - 1)
            grow_total = sum(i[3] for i in line)
            sizes = [msize(i) + (free * i[3] / grow_total if grow_total > 0 and free > 0 else 0)
                     for i in line]
            pos, between = 0, gap
            if grow_total == 0 or free <= 0:
                if justify == "center":
                    pos = max(0, free) / 2
                elif justify == "end":
                    pos = max(0, free)
                elif justify == "space_between" and len(line) > 1 and free > 0:
                    between = gap + free / (len(line) - 1)
                elif justify == "space_around" and free > 0:
                    between = gap + free / len(line)
                    pos = between / 2 - gap / 2
            for (widget, w, h, _grow, self_align, m), size in zip(line, sizes, strict=True):
                mode = align if self_align == "auto" else self_align
                main_len = size - ((m[3] + m[1]) if row else (m[0] + m[2]))
                avail = line_cross - ((m[0] + m[2]) if row else (m[3] + m[1]))
                if mode == "stretch":
                    cross_len, cross_off = avail, 0
                else:
                    cross_len = min(h if row else w, avail)
                    cross_off = {"start": 0, "center": (avail - cross_len) / 2,
                                 "end": avail - cross_len}[mode]
                main_off = pos + (m[3] if row else m[0])
                cross_abs = cross_pos + cross_off + (m[0] if row else m[3])
                if row:
                    x, y, bw, bh = pad[3] + main_off, pad[0] + cross_abs, main_len, cross_len
                else:
                    x, y, bw, bh = pad[3] + cross_abs, pad[0] + main_off, cross_len, main_len
                bw, bh = max(1, bw), max(1, bh)
                widget.size = (bw * k, bh * k)
                widget.pos = (parent.x + x * k, parent.y + parent.height - (y + bh) * k)
                pos += size + between
            cross_pos += line_cross + gap

    parent.bind(pos=update, size=update)
    update()
''', kivy=("dp",))

_helper("scrollbar", '''
def _scrollbar(field, color=(0.5, 0.5, 0.5, 0.6), width=6):
    """Draw a thin scroll indicator on the right edge of a multi-line TextInput."""
    with field.canvas.after:
        Color(*color)
        bar = RoundedRectangle(radius=[dp(width) / 2])

    def update(*_):
        content = max(field.minimum_height, 1)
        if content <= field.height:
            bar.size = (0, 0)
            return
        span = content - field.height
        done = min(max(field.scroll_y / span, 0), 1)
        bar_h = max(dp(16), field.height * field.height / content)
        bar.size = (dp(width), bar_h)
        bar.pos = (field.x + field.width - dp(width) - dp(2),
                   field.y + field.height - bar_h - (field.height - bar_h) * done)

    field.bind(pos=update, size=update, text=update, scroll_y=update, minimum_height=update)
    update()
''', kivy=("Color", "RoundedRectangle", "dp"))

_helper("lock", '''
def _lock_axes(lock_x, lock_y, width, height):
    """Keep one window axis fixed (Kivy only has an all-or-nothing resizable flag)."""
    state = {"busy": False}

    def on_resize(win, w, h):
        k = dp(1)
        if state["busy"]:
            return
        want_w = width * k if lock_x else w
        want_h = height * k if lock_y else h
        if abs(want_w - w) > 1 or abs(want_h - h) > 1:
            state["busy"] = True
            try:
                win.size = (want_w / k, want_h / k)
            finally:
                state["busy"] = False

    Window.bind(on_resize=on_resize)
''', kivy=("Window", "dp"))

_helper("dates", '''
def _parse_date(text, fmt):
    """ISO date for ``text`` written with strftime ``fmt`` (None when it is not a date)."""
    try:
        return datetime.datetime.strptime(text, fmt).date().isoformat()
    except ValueError:
        return None
''', std=("datetime",))

_helper("Dial", '''
class Dial(Widget):
    """Rotary control drawn with canvas arcs; drag or click to set ``.value``."""

    value = NumericProperty(0)
    minimum = NumericProperty(0)
    maximum = NumericProperty(100)

    def __init__(self, track=(0.8, 0.8, 0.8, 1), fill=(0.4, 0.4, 0.9, 1), knob=(1, 1, 1, 1),
                 **kw):
        super().__init__(**kw)
        with self.canvas:
            Color(*track)
            self._track = Line(width=dp(3), cap="round")
            Color(*fill)
            self._arc = Line(width=dp(3), cap="round")
            Color(*knob)
            self._dot = Ellipse()
        self.bind(pos=self._draw, size=self._draw, value=self._draw, minimum=self._draw,
                  maximum=self._draw)
        self._draw()

    def _fraction(self):
        span = self.maximum - self.minimum
        return 0 if span == 0 else min(max((self.value - self.minimum) / span, 0), 1)

    def _draw(self, *_):
        d = max(0, min(self.width, self.height) - dp(14))
        cx, cy = self.x + self.width / 2, self.y + self.height / 2
        box = (cx - d / 2, cy - d / 2, d, d)
        end = -135 + 270 * self._fraction()
        self._track.ellipse = (*box, -135, 135)
        self._arc.ellipse = (*box, -135, end)
        r = dp(5)
        ang = math.radians(end)  # 0 deg = 12 o'clock, clockwise
        self._dot.pos = (cx + math.sin(ang) * d / 2 - r, cy + math.cos(ang) * d / 2 - r)
        self._dot.size = (2 * r, 2 * r)

    def _set_from(self, touch):
        cx, cy = self.x + self.width / 2, self.y + self.height / 2
        angle = math.degrees(math.atan2(touch.x - cx, touch.y - cy))  # clockwise from top
        frac = min(max((angle + 135) / 270, 0), 1)
        self.value = round(self.minimum + frac * (self.maximum - self.minimum))

    def on_touch_down(self, touch):
        if self.disabled or not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)
        touch.grab(self)
        self._set_from(touch)
        return True

    def on_touch_move(self, touch):
        if touch.grab_current is self:
            self._set_from(touch)
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            return True
        return super().on_touch_up(touch)
''', kivy=("Widget", "NumericProperty", "Color", "Line", "Ellipse", "dp"), std=("math",))

_helper("PaintScroll", '''
class PaintScroll(ScrollView):
    """Scrollable drawing surface: draw on ``.surface`` (make it larger than the view to scroll)."""

    def __init__(self, **kw):
        super().__init__(do_scroll_x=True, do_scroll_y=True, bar_width=dp(8), **kw)
        self.surface = Paint(size_hint=(None, None))
        self.add_widget(self.surface)

    @property
    def painter(self):
        return self.surface.painter

    @painter.setter
    def painter(self, fn):
        self.surface.painter = fn

    def repaint(self):
        self.surface.repaint()
''', needs=("Paint",), kivy=("ScrollView", "dp"))

_helper("ComboEdit", '''
class ComboEdit(BoxLayout):
    """Editable dropdown: a TextInput plus a Spinner button listing ``.values``."""

    text = StringProperty("")
    values = ListProperty([])

    def __init__(self, text="", values=(), color=(0, 0, 0, 1), arrow=(0.5, 0.5, 0.5, 1),
                 font_size=None, **kw):
        super().__init__(orientation="horizontal", **kw)
        self.field = TextInput(
            text=text, multiline=False, font_size=font_size or dp(13), foreground_color=color,
            cursor_color=color, background_normal="", background_active="",
            background_color=(0, 0, 0, 0))
        _vcenter(self.field)
        self.picker = Spinner(
            text="v", values=list(values), size_hint=(None, 1), width=dp(28), color=arrow,
            background_normal="", background_down="", background_color=(0, 0, 0, 0))
        self.add_widget(self.field)
        self.add_widget(self.picker)
        self.text, self.values = text, list(values)
        self.picker.bind(text=self._picked)
        self.field.bind(text=lambda w, v: setattr(self, "text", v))
        self.bind(text=self._sync_text, values=lambda w, v: setattr(self.picker, "values", v))

    def _sync_text(self, _w, value):
        if self.field.text != value:
            self.field.text = value

    def _picked(self, _w, value):
        if value != "v":
            self.text = value
            self.picker.text = "v"
''', needs=("vcenter",), kivy=("BoxLayout", "StringProperty", "ListProperty", "TextInput",
                               "Spinner", "dp"))

HELPERS: dict[str, Helper] = {h.name: h for h in _H}
ORDER: list[str] = [h.name for h in _H]
