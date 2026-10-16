"""Shared machinery of the ``tkinter`` and ``customtkinter`` code generators.

:class:`TkGenerator` walks the document and writes one Python function per window.  The
two adapters only differ in how a *widget* is created (``tk_adapter.TkGen`` /
``ctk_adapter.CtkGen`` define ``w_<widget type>`` methods); everything else lives here:

* layout planning (absolute ``place`` / flex and grid via ``grid``),
* event binding, menus, tooltips, tab order, enabled / visible,
* the ttk style registry, helper classes that are only emitted when used,
* project (``main.py`` + ``ui.py`` + ``handlers.py`` ...) and single-file output.
"""

from __future__ import annotations

import json
import keyword
import re
import textwrap
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from py_vui.codegen.base import (
    HEADER,
    EmitContext,
    GeneratedFile,
    GenOptions,
    handlers_file,
    plugin_emitter,
)
from py_vui.core.document import ProjectDocument
from py_vui.core.events import TK_SEQUENCES
from py_vui.core.model import ContainerLayout, Node, Project
from py_vui.core.registry import get_spec
from py_vui.core.theme import resolve_style

LINE = 100

#: identifiers the generated modules use themselves; widget variables must not shadow them
RESERVED = frozenset({
    "tk", "ttk", "ctk", "os", "sys", "style", "asset", "handlers", "ui", "root", "app", "self",
    "main", "build_ui", "WIDGETS", "WINDOWS", "VARS", "APP_DIR", "FONT", "Tooltip", "Dial",
    "Switch", "TimeEntry", "ScrollFrame", "Spinbox", "SimpleNamespace", "colorchooser",
    "configure_styles", "load_image", "add_placeholder", "enable_cell_edit", "stretch",
    "bind_text_change", "grab_when_visible", "parent", "menubar", "event", "value", "item",
    "row", "widget", "segment", "picker", "existing", "chosen",
})

CURSORS = {
    "arrow": "arrow", "hand": "hand2", "ibeam": "xterm", "cross": "crosshair",
    "wait": "watch", "forbidden": "X_cursor", "size_all": "fleur",
}

#: modifier names accepted in menu shortcuts -> Tk modifier names
_MODIFIERS = {
    "ctrl": "Control", "control": "Control", "cmd": "Command", "command": "Command",
    "meta": "Command", "alt": "Alt", "option": "Alt", "shift": "Shift",
}


# ----------------------------------------------------------------------------- literals
class Raw(str):
    """A snippet of Python source that :func:`py` must emit verbatim."""


def py(value: Any) -> str:
    """Render ``value`` as a deterministic Python literal (double-quoted strings)."""
    if isinstance(value, Raw):
        return str(value)
    if value is None or isinstance(value, bool):
        return repr(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(int(value)) if value == int(value) else repr(round(value, 4))
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, tuple):
        inner = ", ".join(py(v) for v in value)
        return f"({inner},)" if len(value) == 1 else f"({inner})"
    if isinstance(value, list):
        return "[" + ", ".join(py(v) for v in value) + "]"
    if isinstance(value, dict):
        return "{" + ", ".join(f"{py(k)}: {py(v)}" for k, v in value.items()) + "}"
    return repr(value)


def num(value: Any, default: float = 0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def px(value: Any) -> int:
    return int(round(num(value)))


def pad_value(lo: float, hi: float) -> Any:
    lo, hi = px(lo), px(hi)
    return lo if lo == hi else (lo, hi)


def chars(width: float) -> int:
    """Approximate width in characters of a Tk text-like widget for a pixel width."""
    return max(1, round(width / 8))


def text_lines(height: float) -> int:
    return max(1, round(height / 16))


def shortcut_sequence(shortcut: str) -> str | None:
    """``"Ctrl+Shift+S"`` -> ``"<Control-Shift-S>"`` (letters lower-case without Shift)."""
    parts = [p.strip() for p in shortcut.replace(" ", "").split("+") if p.strip()]
    if not parts:
        return None
    key, mods = parts[-1], [_MODIFIERS.get(p.lower(), p.title()) for p in parts[:-1]]
    if len(key) == 1:
        key = key.upper() if "Shift" in mods else key.lower()
    elif key.lower().startswith("f") and key[1:].isdigit():
        key = key.upper()
    else:
        key = {"enter": "Return", "esc": "Escape", "del": "Delete", "space": "space",
               "tab": "Tab", "return": "Return", "escape": "Escape",
               "delete": "Delete"}.get(key.lower(), key)
    return "<" + "-".join([*mods, key]) + ">"


# ------------------------------------------------------------------------------ helpers
#: name -> (module imports, source, dependencies); emitted once, only when used
HELPERS: dict[str, tuple[tuple[str, ...], str, tuple[str, ...]]] = {}


def _helper(name: str, source: str, imports: tuple[str, ...] = (), deps: tuple[str, ...] = ()):
    HELPERS[name] = (imports, textwrap.dedent(source).strip("\n") + "\n", deps)


_helper("asset", '''
    def asset(path):
        """Absolute path of a project-relative resource such as ``assets/logo.png``."""
        return os.path.join(APP_DIR, *str(path).split("/"))
''')

_helper("load_image", '''
    def load_image(path, size=None, fit="contain"):
        """Load ``path`` as a PhotoImage (Pillow when available); ``None`` if it is missing."""
        full = asset(path)
        if not os.path.exists(full):
            return None
        try:
            from PIL import Image, ImageTk

            picture = Image.open(full)
            if size and fit == "stretch":
                picture = picture.resize(size)
            elif size and fit == "contain":
                picture.thumbnail(size)
            return ImageTk.PhotoImage(picture)
        except Exception:  # no Pillow / no Tk support in Pillow: use Tk's own PNG / GIF loader
            try:
                return tk.PhotoImage(file=full)
            except tk.TclError:
                return None
''', deps=("asset",))

_helper("Tooltip", '''
    class Tooltip:
        """Show ``text`` in a small popup while the mouse hovers over ``widget``."""

        def __init__(self, widget, text, delay=500):
            self.widget, self.text, self.delay = widget, text, delay
            self._tip = None
            self._after = None
            widget.bind("<Enter>", self._schedule, add="+")
            widget.bind("<Leave>", self._hide, add="+")
            widget.bind("<ButtonPress>", self._hide, add="+")

        def _schedule(self, _event=None):
            self._hide()
            self._after = self.widget.after(self.delay, self._show)

        def _show(self):
            x = self.widget.winfo_rootx() + 12
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
            self._tip = tip = tk.Toplevel(self.widget)
            tip.wm_overrideredirect(True)
            tip.wm_geometry(f"+{x}+{y}")
            tk.Label(tip, text=self.text, background="#ffffe0", foreground="#111111",
                     relief="solid", borderwidth=1, padx=6, pady=2, justify="left").pack()

        def _hide(self, _event=None):
            if self._after is not None:
                self.widget.after_cancel(self._after)
                self._after = None
            if self._tip is not None:
                self._tip.destroy()
                self._tip = None
''')

_helper("add_placeholder", '''
    def add_placeholder(entry, variable, text, color="#9ca3af", background="#ffffff", x=4):
        """Show ``text`` inside an empty entry (an overlay label: ``entry.get()`` stays clean)."""
        hint = ttk.Label(entry, text=text, foreground=color, background=background)
        hint.bind("<Button-1>", lambda _e: entry.focus_set())

        def refresh(*_):
            if variable.get():
                hint.place_forget()
            else:
                hint.place(x=x, rely=0.5, anchor="w")

        variable.trace_add("write", refresh)
        refresh()
        return hint
''')

_helper("bind_text_change", '''
    def bind_text_change(widget, command):
        """Call ``command()`` whenever the contents of a Text / CTkTextbox change."""
        callbacks = widget.__dict__.setdefault("_change_callbacks", [])
        callbacks.append(command)
        if len(callbacks) > 1:  # one <<Modified>> binding serves every callback
            return

        def on_modified(_event=None):
            if widget.edit_modified():
                widget.edit_modified(False)
                for callback in list(callbacks):
                    callback()

        widget.bind("<<Modified>>", on_modified, add="+")
''')

_helper("add_text_placeholder", '''
    def add_text_placeholder(widget, text, color="#9ca3af", background="#ffffff"):
        """Show ``text`` inside an empty Text / CTkTextbox (overlay label; contents stay clean)."""
        hint = tk.Label(widget, text=text, foreground=color, background=background, anchor="w")
        hint.bind("<Button-1>", lambda _e: widget.focus_set())

        def refresh():
            if widget.get("1.0", "end-1c"):
                hint.place_forget()
            else:
                hint.place(x=6, y=4)

        bind_text_change(widget, refresh)
        refresh()
        return hint
''', deps=("bind_text_change",))

_helper("Dial", '''
    class Dial(tk.Canvas):
        """Rotary control drawn on a canvas. Drag, click or use the wheel to change ``get()``."""

        def __init__(self, master, minimum=0, maximum=100, value=0, command=None,
                     background="#ffffff", foreground="#6366f1", track="#d4d4d8",
                     text="#18181b", **kw):
            kw.setdefault("width", 80)
            kw.setdefault("height", 80)
            super().__init__(master, background=background, highlightthickness=0, **kw)
            self.minimum, self.maximum, self.command = minimum, maximum, command
            self.colors = (track, foreground, text)
            self._value = max(minimum, min(maximum, value))
            self.bind("<Configure>", lambda _e: self._draw())
            self.bind("<Button-1>", self._drag)
            self.bind("<B1-Motion>", self._drag)
            self.bind("<MouseWheel>", self._wheel)

        def get(self):
            return self._value

        def set(self, value, notify=False):
            value = int(max(self.minimum, min(self.maximum, round(value))))
            changed = value != self._value
            self._value = value
            self._draw()
            if notify and changed and self.command:
                self.command()

        def _fraction(self):
            span = (self.maximum - self.minimum) or 1
            return (self._value - self.minimum) / span

        def _size(self):
            width = self.winfo_width()
            height = self.winfo_height()
            if width <= 1 or height <= 1:
                width, height = int(self.cget("width")), int(self.cget("height"))
            return width, height

        def _draw(self):
            track, accent, text = self.colors
            width, height = self._size()
            cx, cy = width / 2, height / 2
            radius = max(4, min(width, height) / 2 - 6)
            box = (cx - radius, cy - radius, cx + radius, cy + radius)
            self.delete("all")
            self.create_arc(box, start=225, extent=-270, style="arc", width=6, outline=track)
            self.create_arc(box, start=225, extent=-270 * self._fraction(), style="arc",
                            width=6, outline=accent)
            angle = math.radians(225 - 270 * self._fraction())
            self.create_line(cx, cy, cx + radius * 0.7 * math.cos(angle),
                             cy - radius * 0.7 * math.sin(angle), width=3, fill=accent,
                             capstyle="round")
            self.create_text(cx, cy + radius * 0.45, text=str(self._value), fill=text)

        def _drag(self, event):
            width, height = self._size()
            angle = math.degrees(math.atan2(height / 2 - event.y, event.x - width / 2))
            offset = (225 - angle) % 360
            if offset > 270:
                offset = 0 if offset > 315 else 270
            span = self.maximum - self.minimum
            self.set(self.minimum + span * offset / 270, notify=True)

        def _wheel(self, event):
            self.set(self._value + (1 if event.delta > 0 else -1), notify=True)
''', imports=("import math",))

_helper("Switch", '''
    class Switch(tk.Frame):
        """A toggle switch (pill + knob) with a text label; ``get()`` returns True when on."""

        def __init__(self, master, text="", value=False, command=None, background="#ffffff",
                     foreground="#18181b", on="#6366f1", off="#d4d4d8", font=None, **kw):
            super().__init__(master, background=background, **kw)
            self.variable = tk.BooleanVar(value=value)
            self.command = command
            self._colors = (on, off)
            self.canvas = tk.Canvas(self, width=42, height=22, highlightthickness=0,
                                    background=background, cursor="hand2")
            self.canvas.pack(side="left")
            self.label = tk.Label(self, text=text, background=background,
                                  foreground=foreground, font=font)
            self.label.pack(side="left", padx=(8, 0))
            for widget in (self.canvas, self.label):
                widget.bind("<Button-1>", lambda _e: self.invoke(), add="+")
            self.variable.trace_add("write", lambda *_: self._draw())
            self._draw()

        def get(self):
            return self.variable.get()

        def set(self, value):
            self.variable.set(bool(value))

        def invoke(self):
            if str(self.canvas.cget("cursor")) == "arrow":  # disabled
                return
            self.variable.set(not self.variable.get())
            if self.command:
                self.command()

        def configure(self, cnf=None, **kw):
            if kw.get("state") in ("disabled", "normal"):
                self.canvas.configure(cursor="arrow" if kw["state"] == "disabled" else "hand2")
                kw.pop("state")
            return super().configure(cnf, **kw) if (cnf or kw) else None

        config = configure

        def _draw(self):
            on, off = self._colors
            state = self.variable.get()
            self.canvas.delete("all")
            self.canvas.create_oval(1, 1, 21, 21, fill=on if state else off, outline="")
            self.canvas.create_oval(21, 1, 41, 21, fill=on if state else off, outline="")
            self.canvas.create_rectangle(11, 1, 31, 21, fill=on if state else off, outline="")
            x = 31 if state else 11
            self.canvas.create_oval(x - 8, 3, x + 8, 19, fill="#ffffff", outline="")
''')

_helper("TimeEntry", '''
    class TimeEntry(ttk.Frame):
        """Hour / minute / (second) spin boxes; ``get()`` returns ``"HH:MM:SS"``."""

        def __init__(self, master, value="12:00:00", show_seconds=True, command=None, **kw):
            super().__init__(master, **kw)
            parts = (str(value).split(":") + ["00", "00", "00"])[:3]
            self.fields = 3 if show_seconds else 2
            self.vars = [tk.StringVar(value=p.zfill(2)) for p in parts]
            for index, limit in enumerate((23, 59, 59)[: self.fields]):
                if index:
                    ttk.Label(self, text=":").pack(side="left")
                ttk.Spinbox(self, from_=0, to=limit, width=3, wrap=True, format="%02.0f",
                            justify="center", textvariable=self.vars[index]).pack(side="left")
                if command:
                    self.vars[index].trace_add("write", lambda *_: command())

        def get(self):
            return ":".join(v.get().zfill(2) for v in self.vars[: self.fields])

        def set(self, value):
            for var, part in zip(self.vars, str(value).split(":")):
                var.set(part.zfill(2))
''')

_helper("enable_cell_edit", '''
    def enable_cell_edit(tree, command=None):
        """Edit Treeview cells in place on double click; ``command(event)`` runs after an edit."""

        def edit(item, column):
            bbox = tree.bbox(item, column)
            if not bbox:
                return None
            x, y, width, height = bbox
            box = ttk.Entry(tree)
            box.insert(0, tree.set(item, column))
            box.select_range(0, "end")
            box.place(x=x, y=y, width=width, height=height)
            box.focus_set()
            done = []

            def commit(_event=None):
                if done:
                    return
                done.append(True)
                value = box.get()
                tree.set(item, column, value)
                box.destroy()
                if command:
                    command(SimpleNamespace(widget=tree, item=item, column=column, value=value))

            box.bind("<Return>", commit)
            box.bind("<FocusOut>", commit)
            box.bind("<Escape>", lambda _e: (done.append(True), box.destroy()))
            return box

        def on_double_click(event):
            if tree.identify_region(event.x, event.y) == "cell":
                edit(tree.identify_row(event.y), tree.identify_column(event.x))

        tree.bind("<Double-Button-1>", on_double_click, add="+")
        tree.edit_cell = edit
''', imports=("from types import SimpleNamespace",))

_helper("ScrollFrame", '''
    class ScrollFrame(ttk.Frame):
        """A frame whose ``content`` child scrolls (``orient``: vertical, horizontal or both)."""

        def __init__(self, master, orient="vertical", content_width=0, content_height=0,
                     background=None, content_style=None, **kw):
            super().__init__(master, **kw)
            if "width" in kw or "height" in kw:
                self.grid_propagate(False)
            self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0)
            if background:
                self.canvas.configure(background=background)
            self.content = ttk.Frame(self.canvas)
            if content_style:
                self.content.configure(style=content_style)
            if content_width or content_height:
                self.content.configure(width=content_width or 1, height=content_height or 1)
            self._window = self.canvas.create_window((0, 0), window=self.content, anchor="nw")
            self.columnconfigure(0, weight=1)
            self.rowconfigure(0, weight=1)
            self.canvas.grid(row=0, column=0, sticky="nsew")
            if orient in ("vertical", "both"):
                bar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
                bar.grid(row=0, column=1, sticky="ns")
                self.canvas.configure(yscrollcommand=bar.set)
            if orient in ("horizontal", "both"):
                bar = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
                bar.grid(row=1, column=0, sticky="ew")
                self.canvas.configure(xscrollcommand=bar.set)
            self.fit_width = not content_width and orient == "vertical"
            self.fit_height = not content_height and orient == "horizontal"
            self.content.bind("<Configure>", self._on_content, add="+")
            self.canvas.bind("<Configure>", self._on_canvas, add="+")
            self.canvas.bind("<Enter>", lambda _e: self.canvas.bind_all("<MouseWheel>", self._wheel))
            self.canvas.bind("<Leave>", lambda _e: self.canvas.unbind_all("<MouseWheel>"))

        def _on_content(self, _event):
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))

        def _on_canvas(self, event):
            if self.fit_width:
                self.canvas.itemconfigure(self._window, width=event.width)
            if self.fit_height:
                self.canvas.itemconfigure(self._window, height=event.height)

        def _wheel(self, event):
            step = -event.delta // 120 if abs(event.delta) >= 120 else -event.delta
            self.canvas.yview_scroll(int(step), "units")
''')

_helper("grab_when_visible", '''
    def grab_when_visible(window, tries=40):
        """Make ``window`` modal as soon as it is mapped (``grab_set`` fails before that)."""
        try:
            window.grab_set()
        except tk.TclError:
            if tries > 0 and window.winfo_exists():
                window.after(50, grab_when_visible, window, tries - 1)
''')

_helper("set_sashes", '''
    def set_sashes(paned, positions, tries=20):
        """Place the sashes of a paned window once it has been given its real size."""
        horizontal = str(paned.cget("orient")) == "horizontal"
        size = paned.winfo_width() if horizontal else paned.winfo_height()
        if size <= 1 and tries > 0:
            paned.after(50, set_sashes, paned, positions, tries - 1)
            return
        for index, position in enumerate(positions):
            try:
                if hasattr(paned, "sashpos"):  # ttk.PanedWindow
                    paned.sashpos(index, position)
                else:  # tk.PanedWindow
                    paned.sash_place(index, position if horizontal else 1,
                                     1 if horizontal else position)
            except tk.TclError:
                break
''')

_HELPER_ORDER = ("asset", "load_image", "Tooltip", "add_placeholder", "bind_text_change", "add_text_placeholder", "Dial",
                 "Switch", "TimeEntry", "enable_cell_edit", "ScrollFrame", "grab_when_visible", "set_sashes")


# ------------------------------------------------------------------------------- state
@dataclass
class Made:
    """What a widget emitter produced."""

    var: str  # the widget (registered in WIDGETS, event target)
    outer: str = ""  # what the geometry manager places (wrapper frame); defaults to ``var``
    #: width/height are constructor arguments (customtkinter) rather than place()/grid() options
    sized: bool = False
    #: background that children (labels, radios ...) should blend into
    bg: str = ""
    #: expression of the parent for children, by page index
    target: Callable[[int], str] | None = None
    #: design-time size of the area children are positioned in (default: the node's own size)
    child_size: tuple[float, float] | None = None
    #: called after the children have been emitted (paned window sash positions ...)
    post: Callable[[], None] | None = None
    #: native widget state kind for enabled/disabled: "ttk" | "config" | "ctk" | ""
    state: str = "ttk"
    #: does the widget take a ``tooltip`` binding (always true unless a placeholder)
    placeholder: bool = False

    def __post_init__(self) -> None:
        self.outer = self.outer or self.var


@dataclass
class Place:
    """Planned geometry for one child."""

    manager: str  # "place" | "grid" | "add"
    kwargs: dict[str, Any] = field(default_factory=dict)
    #: absolute placement raw data (x, y, w, h, anchors, parent size)
    box: tuple[float, float, float, float] | None = None
    anchors: Any = None
    size: tuple[float, float] = (0, 0)


@dataclass
class StyleDef:
    name: str
    cls: str
    options: dict[str, Any]
    mapping: dict[str, list[tuple[str, Any]]]


class TkGenerator:
    """Walks a project and writes the Python for one Tk dialect (``tkinter`` or ``customtkinter``)."""

    framework = "tkinter"
    def __init__(self, project: Project, options: GenOptions) -> None:
        self.project = project
        self.options = options
        self.doc = ProjectDocument(project)
        self.theme = project.theme
        self.single = options.layout == "single"
        self.prefix = "" if self.single else "handlers."
        self.names = self._unique_names()
        self.used: set[str] = set(self.names.values())
        self.imports: set[str] = set()
        self.requirements: set[str] = set()
        self.helpers: set[str] = set()
        self.styles: dict[str, StyleDef] = {}
        self._style_keys: dict[str, str] = {}
        self.out: list[str] = []
        self.depth = 1
        # per-scope state
        self.scope_widgets: list[tuple[str, str]] = []
        self.scope_vars: list[tuple[str, str]] = []
        self.scope_groups: dict[str, str] = {}
        self.scope_tabs: dict[str, str] = {}
        self.cur: dict[str, str] = {}
        self.in_flow = False

    # ------------------------------------------------------------------ names & output
    def _unique_names(self) -> dict[str, str]:
        names = self.doc.variable_names()
        handler_names = set(self.project.handlers) if self.single else set()
        taken = set(names.values())
        for nid, var in list(names.items()):
            if var in RESERVED or keyword.iskeyword(var) or var in handler_names:
                cand = f"{var}_w"
                while cand in taken:
                    cand += "_"
                taken.add(cand)
                names[nid] = cand
        return names

    def aux(self, var: str, suffix: str) -> str:
        cand, i = f"{var}_{suffix}", 2
        while cand in self.used:
            cand = f"{var}_{suffix}{i}"
            i += 1
        self.used.add(cand)
        return cand

    def emit(self, line: str = "") -> None:
        self.out.append(("    " * self.depth + line) if line else "")

    def assign(self, var: str, ctor: str, args: list[str], kw: dict[str, Any]) -> None:
        """``var = ctor(args..., key=value...)`` wrapped at the line limit."""
        parts = [*args, *[f"{k}={py(v)}" for k, v in kw.items() if v is not None]]
        self.call(f"{var} = {ctor}", parts)

    def call(self, head: str, parts: list[str]) -> None:
        one = f"{head}({', '.join(parts)})"
        if len(one) + self.depth * 4 <= LINE:
            self.emit(one)
            return
        self.emit(f"{head}(")
        for part in parts:
            self.emit(f"    {part},")
        self.emit(")")

    def helper(self, name: str) -> None:
        if name in self.helpers:
            return
        imports, _src, deps = self.helper_table[name]
        self.helpers.add(name)
        self.imports.update(imports)
        for d in deps:
            self.helper(d)

    def want_image(self) -> None:
        self.helper("load_image")

    # --------------------------------------------------------------------- styling
    def res(self, node: Node) -> dict[str, object]:
        return resolve_style(self.theme, node.type, node.style)

    @property
    def surface(self) -> str:
        return self.theme.surface

    def style(self, hint: str, cls: str, options: dict[str, Any],
              mapping: dict[str, list[tuple[str, Any]]] | None = None) -> str:
        """Register (or reuse) a ttk style derived from ``cls`` and return its name."""
        mapping = mapping or {}
        key = json.dumps([cls, options, mapping], sort_keys=True, default=str)
        if key in self._style_keys:
            return self._style_keys[key]
        name = f"{hint}.{cls}"
        i = 2
        while name in self.styles:
            name = f"{hint}{i}.{cls}"
            i += 1
        self.styles[name] = StyleDef(name, cls, options, mapping)
        self._style_keys[key] = name
        return name

    def font_tuple(self, node: Node) -> tuple | None:
        """Font spec when the node overrides the theme font, else ``None``."""
        s = node.style
        if not any(s.get(k) for k in ("font_family", "font_size", "bold", "italic", "underline")):
            return None
        r = self.res(node)
        flags = " ".join(f for f in ("bold", "italic", "underline") if r[f])
        spec: list[Any] = [r["font_family"], int(r["font_size"])]  # type: ignore[call-overload]
        if flags:
            spec.append(flags)
        return tuple(spec)

    def cursor(self, node: Node) -> str | None:
        c = node.style.get("cursor", "")
        return CURSORS.get(c) if c else None

    def border_explicit(self, node: Node) -> tuple[int, str] | None:
        bw = node.style.get("border_width", -1)
        if bw in (-1, None) or int(bw) <= 0:
            return None
        return int(bw), str(self.res(node)["border_color"])

    # --------------------------------------------------------------------- events
    def handler_expr(self, name: str) -> str | None:
        if name not in self.project.handlers:
            self.emit(f"# py_vui: handler {name!r} is not defined in the project")
            return None
        return f"{self.prefix}{name}"

    def use(self, *events: str) -> str | None:
        """Claim ``events`` for native wiring; returns a zero-arg-safe handler expression."""
        exprs: list[str] = []
        for ev in events:
            name = self.cur.pop(ev, None)
            if name is None:
                continue
            expr = self.handler_expr(name)
            if expr and expr not in exprs:
                exprs.append(expr)
        if not exprs:
            return None
        if len(exprs) == 1:
            return exprs[0]
        return "lambda: (" + ", ".join(f"{e}()" for e in exprs) + ")"

    def sequence(self, widget_type: str, event_id: str) -> str | None:
        if event_id == "click":
            return "<Button-1>"
        if event_id == "paint":
            return "<Configure>"
        if event_id == "change":
            return "<KeyRelease>"
        if event_id in ("toggle", "select", "tab_change", "cell_change", "close"):
            return None
        return TK_SEQUENCES.get(event_id)

    def bind_remaining(self, node: Node, made: Made) -> None:
        plug = PLUGIN_SEQUENCES.get(node.type, {})
        for ev, name in list(self.cur.items()):
            expr = self.handler_expr(name)
            if expr is None:
                continue
            seq = plug.get(ev) or self.sequence(node.type, ev)
            if seq is None:
                self.emit(f"# py_vui: event {ev!r} is not supported on {node.type} "
                          f"({self.framework})")
                continue
            if node.type in ("window", "toplevel") and ev in _WINDOW_ONLY:
                # a toplevel is in the bindtags of every child: ignore events of descendants
                expr = f"lambda event: {expr}(event) if event.widget is {made.var} else None"
            self.emit(f"{made.var}.bind({py(seq)}, {expr}, add=\"+\")")
        self.cur.clear()

    # ----------------------------------------------------------------- geometry/layout
    def size_of(self, node: Node) -> tuple[float, float]:
        if node.type in ("window", "toplevel"):
            return num(node.props.get("width", node.box.w)), num(node.props.get("height", node.box.h))
        return node.box.w, node.box.h

    def layout_of(self, node: Node) -> ContainerLayout:
        return node.layout or ContainerLayout()

    def children_size(self, container: Node) -> tuple[float, float]:
        """Design-time size of the area children of ``container`` are positioned in."""
        return self.size_of(container)

    def plan_children(self, container: Node, kids: list[Node], target: str,
                      size: tuple[float, float]) -> tuple[list[str], dict[str, Place]]:
        if container.type == "paned_window":
            return [], {k.id: Place("add", {"weight": 1}) for k in kids}
        mode = self.layout_of(container).mode
        if mode == "flex":
            return self._plan_flex(container, kids, target, size)
        if mode == "grid":
            return self._plan_grid(container, kids, target, size)
        return [], {k.id: Place("place", box=(k.box.x, k.box.y, k.box.w, k.box.h),
                                anchors=k.anchors, size=size) for k in kids}

    def _propagate_line(self, container: Node, target: str) -> list[str]:
        if container.type in ("window", "toplevel", "scroll_frame"):
            return []
        return [f"{target}.grid_propagate(False)"]

    def _plan_flex(self, container: Node, kids: list[Node], target: str,
                   size: tuple[float, float]) -> tuple[list[str], dict[str, Place]]:
        lay = self.layout_of(container)
        row = lay.direction == "row"
        pad = lay.padding
        cfg_main = "grid_columnconfigure" if row else "grid_rowconfigure"
        cfg_cross = "grid_rowconfigure" if row else "grid_columnconfigure"
        vis = [k for k in kids if k.visible]
        out: dict[str, Place] = {k.id: Place("grid", {"row": 0, "column": 0})
                                 for k in kids if not k.visible}

        def margin(k: Node, main: bool) -> tuple[float, float]:
            m = k.flex.margin
            if row:
                return (m.left, m.right) if main else (m.top, m.bottom)
            return (m.top, m.bottom) if main else (m.left, m.right)

        def main_size(k: Node) -> float:
            lo, hi = margin(k, True)
            return (k.box.w if row else k.box.h) + lo + hi

        def cross_size(k: Node) -> float:
            lo, hi = margin(k, False)
            return (k.box.h if row else k.box.w) + lo + hi

        avail = (size[0] - pad.left - pad.right) if row else (size[1] - pad.top - pad.bottom)
        lines: list[list[Node]] = [[]]
        used = 0.0
        for k in vis:
            s = main_size(k)
            if lay.wrap and lines[-1] and used + s + lay.gap > avail:
                lines.append([])
                used = 0.0
            used += s + (lay.gap if lines[-1] else 0)
            lines[-1].append(k)
        lines = [ln for ln in lines if ln]
        wrapped = len(lines) > 1
        grow_any = any(k.flex.grow > 0 for k in vis)
        spacers = lay.justify in ("space_between", "space_around") and not grow_any and not wrapped
        around = spacers and lay.justify == "space_around"
        main_lo, main_hi = (pad.left, pad.right) if row else (pad.top, pad.bottom)
        cross_lo, cross_hi = (pad.top, pad.bottom) if row else (pad.left, pad.right)

        config = self._propagate_line(container, target)
        col_min: dict[int, float] = {}
        col_weight: dict[int, float] = {}
        row_min: dict[int, float] = {}
        for li, line in enumerate(lines):
            for i, k in enumerate(line):
                idx = i * (2 if spacers else 1) + (1 if around else 0)
                last = i == len(line) - 1
                m_lo, m_hi = margin(k, True)
                c_lo, c_hi = margin(k, False)
                lo = (main_lo if i == 0 else 0) + m_lo
                hi = m_hi + (lay.gap if not last else main_hi)
                clo = (cross_lo if li == 0 else 0) + c_lo
                chi = c_hi + (lay.gap if li < len(lines) - 1 else cross_hi)
                # grid's minsize includes the padding of the slot
                col_min[idx] = max(col_min.get(idx, 0), main_size(k) - m_lo - m_hi + lo + hi)
                col_weight[idx] = max(col_weight.get(idx, 0), k.flex.grow if not wrapped else 0)
                row_min[li] = max(row_min.get(li, 0), cross_size(k) - c_lo - c_hi + clo + chi)
                align = lay.align if k.flex.align_self == "auto" else k.flex.align_self
                cross_sticky = {"stretch": "ns" if row else "ew", "start": "n" if row else "w",
                                "end": "s" if row else "e", "center": ""}[align]
                sticky = ("ew" if row else "ns") + cross_sticky
                r_, c_ = (li, idx) if row else (idx, li)
                kw: dict[str, Any] = {"row": r_, "column": c_, "sticky": sticky}
                px_, py_ = (pad_value(lo, hi), pad_value(clo, chi)) if row else (
                    pad_value(clo, chi), pad_value(lo, hi))
                if px_:
                    kw["padx"] = px_
                if py_:
                    kw["pady"] = py_
                out[k.id] = Place("grid", kw)
        grow_cols = len([w for w in col_weight.values() if w > 0])
        n_items = max((len(ln) for ln in lines), default=0)
        n_slots = n_items if not spacers else (2 * n_items + 1 if around else 2 * n_items - 1)
        for idx in range(n_slots):
            if idx in col_min:
                kw = [f"weight={py(col_weight.get(idx, 0))}"]
                if col_weight.get(idx, 0) > 0 and grow_cols > 1:
                    kw.append("uniform=\"grow\"")  # free space split exactly by grow ratio
                if col_min[idx] > 0:
                    kw.append(f"minsize={px(col_min[idx])}")
            else:
                kw = ["weight=1"]  # spacer
            config.append(f"{target}.{cfg_main}({idx}, {', '.join(kw)})")
        for li in range(len(lines)):
            kw = ["weight=1"]
            if row_min.get(li, 0) > 0:
                kw.append(f"minsize={px(row_min[li])}")
            config.append(f"{target}.{cfg_cross}({li}, {', '.join(kw)})")
        if not grow_any and not spacers and not wrapped and lay.justify in ("center", "end"):
            anchor = ("center" if lay.justify == "center" else "e") if row else (
                "center" if lay.justify == "center" else "s")
            config.append(f"{target}.grid_anchor({py(anchor)})")
        return config, out

    def _plan_grid(self, container: Node, kids: list[Node], target: str,
                   size: tuple[float, float]) -> tuple[list[str], dict[str, Place]]:
        lay = self.layout_of(container)
        pad = lay.padding
        vis = [k for k in kids if k.visible]
        ncols = max([len(lay.column_weights), *[k.cell.column + k.cell.column_span for k in vis]])
        nrows = max([len(lay.row_weights), *[k.cell.row + k.cell.row_span for k in vis]])
        min_w = [0.0] * ncols
        min_h = [0.0] * nrows

        def cell_pads(k: Node) -> tuple[float, float, float, float]:
            last_c = k.cell.column + k.cell.column_span >= ncols
            last_r = k.cell.row + k.cell.row_span >= nrows
            return (pad.left if k.cell.column == 0 else lay.column_gap / 2,
                    pad.right if last_c else lay.column_gap / 2,
                    pad.top if k.cell.row == 0 else lay.row_gap / 2,
                    pad.bottom if last_r else lay.row_gap / 2)

        for k in vis:
            left, right, top, bottom = cell_pads(k)
            if k.cell.column_span == 1:
                min_w[k.cell.column] = max(min_w[k.cell.column], k.box.w + left + right)
            if k.cell.row_span == 1:
                min_h[k.cell.row] = max(min_h[k.cell.row], k.box.h + top + bottom)
        config = self._propagate_line(container, target)
        for c in range(ncols):
            w = lay.column_weights[c] if c < len(lay.column_weights) else 0
            extra = f", minsize={px(min_w[c])}" if min_w[c] > 0 else ""
            config.append(f"{target}.grid_columnconfigure({c}, weight={w}{extra})")
        for r in range(nrows):
            w = lay.row_weights[r] if r < len(lay.row_weights) else 0
            extra = f", minsize={px(min_h[r])}" if min_h[r] > 0 else ""
            config.append(f"{target}.grid_rowconfigure({r}, weight={w}{extra})")
        out: dict[str, Place] = {}
        for k in kids:
            if not k.visible:
                out[k.id] = Place("grid", {"row": 0, "column": 0})
                continue
            cell = k.cell
            left, right, top, bottom = cell_pads(k)
            padx, pady = pad_value(left, right), pad_value(top, bottom)
            kw: dict[str, Any] = {"row": cell.row, "column": cell.column}
            if cell.row_span > 1:
                kw["rowspan"] = cell.row_span
            if cell.column_span > 1:
                kw["columnspan"] = cell.column_span
            if cell.sticky:
                kw["sticky"] = "".join(c for c in "nsew" if c in cell.sticky.lower())
            if padx:
                kw["padx"] = padx
            if pady:
                kw["pady"] = pady
            out[k.id] = Place("grid", kw)
        return config, out

    def place_kwargs(self, place: Place,
                     sized: bool) -> tuple[dict[str, Any], tuple[int | None, int | None]]:
        """``place()`` options for an absolute child, plus (right, bottom) stretch margins.

        Right / bottom anchored widgets use relative placement so they follow window resizes;
        widgets pinned to both edges stretch (``relwidth`` + negative ``width``).  ``sized``
        widgets (customtkinter) take their size in the constructor, so a stretching one is
        reported back as a margin for the generated ``stretch()`` helper instead.
        """
        assert place.box is not None
        x, y, w, h = place.box
        a = place.anchors
        horiz, ax, sx = self._axis(x, w, place.size[0], a.left, a.right, sized, "x")
        vert, ay, sy = self._axis(y, h, place.size[1], a.top, a.bottom, sized, "y")
        kw = {**horiz, **vert}
        anchor = (ay + ax) or "center"
        if anchor != "nw":
            kw["anchor"] = anchor
        order = ["relx", "x", "rely", "y", "relwidth", "width", "relheight", "height", "anchor"]
        return {k: kw[k] for k in order if k in kw}, (sx, sy)

    @staticmethod
    def _axis(pos: float, length: float, whole: float, near: bool, far_pinned: bool,
              sized: bool, axis: str) -> tuple[dict[str, Any], str, int | None]:
        off, rel = ("x", "relx") if axis == "x" else ("y", "rely")
        size_key, rel_size = ("width", "relwidth") if axis == "x" else ("height", "relheight")
        lo_c, hi_c = ("w", "e") if axis == "x" else ("n", "s")
        far = whole - pos - length
        kw: dict[str, Any] = {}
        stretch = None
        if whole <= 0 or (near and not far_pinned):
            kw[off] = px(pos)
            anchor = lo_c
        elif near and far_pinned:
            kw[off] = px(pos)
            anchor = lo_c
            if sized:
                stretch = px(far)
            else:
                kw[rel_size], kw[size_key] = 1.0, -px(pos + far)
                return kw, anchor, None
        elif far_pinned:
            kw[rel], kw[off] = 1.0, -px(far)
            anchor = hi_c
        else:  # pinned to neither edge: keep the proportional centre
            kw[rel] = round((pos + length / 2) / whole, 4)
            anchor = ""
        if not sized:
            kw[size_key] = px(length)
        return kw, anchor, stretch

    def emit_geometry(self, node: Node, made: Made, place: Place | None, parent: str) -> None:
        if place is None:
            return
        outer = made.outer
        if place.manager == "place":
            kw, stretch = self.place_kwargs(place, made.sized)
            self.call(f"{outer}.place", [f"{k}={py(v)}" for k, v in kw.items()])
            if stretch != (None, None):
                self.helper_stretch()
                self.emit(f"stretch({outer}, {parent}, right={stretch[0]}, bottom={stretch[1]})")
            if not node.visible:
                self.emit(f"{outer}.place_forget()")
        elif place.manager == "grid":
            self.call(f"{outer}.grid", [f"{k}={py(v)}" for k, v in place.kwargs.items()])
            if not node.visible:
                self.emit(f"{outer}.grid_remove()")
        elif place.manager == "add" and node.visible:
            self.emit_pane_add(parent, outer, place)

    def helper_stretch(self) -> None:  # overridden by the customtkinter generator
        raise NotImplementedError

    def emit_pane_add(self, parent: str, outer: str, place: Place) -> None:
        self.emit(f"{parent}.add({outer}, weight=1)")

    # --------------------------------------------------------------------- node loop
    def emit_children(self, container: Node, made: Made, size: tuple[float, float] | None = None) -> None:
        # dialog windows are generated as their own ``open_<name>`` functions
        kids = [k for k in self.doc.children(container.id) if k.type != "toplevel"]
        if not kids:
            return
        paged = get_spec(container.type).paged
        groups: dict[int, list[Node]] = {}
        for k in kids:
            groups.setdefault(k.page if paged else 0, []).append(k)
        size = size or made.child_size or self.children_size(container)
        for page in sorted(groups):
            target = made.target(page) if made.target else made.var
            config, places = self.plan_children(container, groups[page], target, size)
            for line in config:
                self.emit(line)
            for k in groups[page]:
                self.emit_node(k, target, made.bg, places[k.id])

    def emit_node(self, node: Node, parent: str, pbg: str, place: Place | None) -> Made:
        var = self.names[node.id]
        spec = get_spec(node.type)
        saved_cur, saved_flow = self.cur, self.in_flow
        self.cur = dict(node.events)
        self.in_flow = place is not None and place.manager == "grid"
        made: Made
        outer_parent = parent
        box = None
        if self.needs_box(node, place):
            box = self.aux(var, "box")
            self.emit_box(box, parent, node, pbg)
            parent = box
        fn = plugin_emitter(node.type, self.framework)
        if not spec.supports(self.framework):
            made = self.w_unsupported(node, var, parent, pbg,
                                      f"{spec.label} is not available for {self.framework}")
        elif fn is not None:
            made = self.emit_plugin(node, var, parent, pbg, fn)
        else:
            method = getattr(self, f"w_{node.type}", None)
            if method is None:
                made = self.w_unsupported(node, var, parent, pbg,
                                          f"{spec.label} (no generator for {node.type})")
            else:
                made = method(node, var, parent, pbg)
        if box:
            self.emit(f"{made.var}.pack(fill=\"both\", expand=True)")
            made.outer = box
        self.scope_widgets.append((var, made.var))
        self.emit_geometry(node, made, place, outer_parent)
        self.bind_remaining(node, made)
        if node.tooltip and not made.placeholder:
            self.helper("Tooltip")
            self.emit(f"Tooltip({made.var}, {py(node.tooltip)})")
        if not node.enabled:
            self.emit_disabled(made)
        if node.tab_index is not None or node.id in self.project.tab_order:
            self.scope_tabs[node.id] = made.outer
        if spec.container and made.target is not None:
            self.emit_children(node, made)
        if made.post is not None:
            made.post()
        self.cur, self.in_flow = saved_cur, saved_flow
        return made

    #: leaf widget types that cannot be given a pixel size natively (see :meth:`needs_box`)
    box_types: frozenset[str] = frozenset()

    def needs_box(self, node: Node, place: Place | None) -> bool:
        """A leaf in a flex/grid cell that does not fill it keeps its designed size via a box."""
        if place is None or place.manager != "grid" or node.type not in self.box_types:
            return False
        sticky = str(place.kwargs.get("sticky", ""))
        return not (all(c in sticky for c in "ns") and all(c in sticky for c in "ew"))

    def emit_box(self, box: str, parent: str, node: Node, pbg: str) -> None:
        """Create the fixed-size frame (designed width x height) that wraps a leaf widget."""
        kw: dict[str, Any] = {"width": px(node.box.w), "height": px(node.box.h)}
        if pbg != self.surface:
            kw["style"] = self.style(box, "TFrame", {"background": pbg})
        self.assign(box, "ttk.Frame", [parent], kw)
        self.emit(f"{box}.pack_propagate(False)")

    def emit_disabled(self, made: Made) -> None:
        if made.state == "ttk":
            self.emit(f"{made.var}.state([\"disabled\"])")
        elif made.state in ("config", "ctk"):
            self.emit(f"{made.var}.configure(state=\"disabled\")")

    def emit_plugin(self, node: Node, var: str, parent: str, pbg: str, fn: Callable) -> Made:
        ctx = EmitContext(self.project, node, var, parent, self.framework)
        result = fn(ctx)
        self.imports.update(result.imports)
        self.requirements.update(result.requirements)
        for line in result.lines:
            self.emit(line)
        return Made(var=var, bg=pbg, sized=False, state="")

    def w_unsupported(self, node: Node, var: str, parent: str, pbg: str, text: str) -> Made:
        raise NotImplementedError

    # ------------------------------------------------------- default ttk theme / constants
    def constants(self) -> list[str]:
        t = self.theme
        return [f"FONT = ({py(t.font_family)}, {t.font_size})"]

    def style_function(self) -> list[str]:
        t = self.theme
        win = t.background
        lines = [
            "def configure_styles(root):",
            '    """Apply the project theme to the ttk widgets (the \"clam\" theme honours colours)."""',
            "    style = ttk.Style(root)",
            '    style.theme_use("clam")',
        ]

        def cfg(name: str, **opts: Any) -> None:
            self.call_into(lines, "style.configure", name, opts)

        def mp(name: str, **opts: Any) -> None:
            self.call_into(lines, "style.map", name, opts)

        cfg(".", background=win, foreground=t.text, font=Raw("FONT"), bordercolor=t.border,
            troughcolor=t.border, focuscolor=t.primary, selectbackground=t.primary,
            selectforeground=t.button_text)
        for cls in ("TFrame", "TLabel", "TLabelframe"):
            cfg(cls, background=t.surface)
        cfg("TLabelframe.Label", background=t.surface, foreground=t.text)
        for cls in ("TCheckbutton", "TRadiobutton"):
            cfg(cls, background=t.surface, indicatorbackground=t.surface,
                indicatorforeground=t.primary)
            mp(cls, background=[("active", t.surface)],
               indicatorbackground=[("pressed", t.border), ("active", t.surface)])
        cfg("TButton", background=t.primary, foreground=t.button_text, bordercolor=t.primary,
            padding=(10, 4), relief="flat")
        mp("TButton", background=[("disabled", t.border), ("active", t.primary_hover)],
           foreground=[("disabled", t.muted_text)])
        cfg("Toolbutton", background=t.surface, foreground=t.text, bordercolor=t.surface,
            padding=(8, 3))
        mp("Toolbutton", background=[("selected", t.border), ("active", t.border)])
        entry = dict(fieldbackground=t.surface, foreground=t.text, bordercolor=t.border,
                     lightcolor=t.surface, darkcolor=t.surface, insertcolor=t.text, padding=4)
        cfg("TEntry", **entry)
        cfg("TSpinbox", arrowcolor=t.text, background=t.surface, **entry)
        cfg("TCombobox", arrowcolor=t.text, background=t.surface, **entry)
        mp("TCombobox", fieldbackground=[("readonly", t.surface)],
           foreground=[("readonly", t.text)], selectbackground=[("readonly", t.surface)],
           selectforeground=[("readonly", t.text)])
        cfg("Treeview", background=t.surface, fieldbackground=t.surface, foreground=t.text,
            bordercolor=t.border, rowheight=24)
        mp("Treeview", background=[("selected", t.primary)],
           foreground=[("selected", t.button_text)])
        cfg("Treeview.Heading", background=win, foreground=t.text, relief="flat")
        cfg("TNotebook", background=win, bordercolor=t.border)
        cfg("TNotebook.Tab", background=win, foreground=t.muted_text, padding=(12, 4))
        mp("TNotebook.Tab", background=[("selected", t.surface)],
           foreground=[("selected", t.text)])
        cfg("TProgressbar", background=t.primary, troughcolor=t.border, bordercolor=t.border)
        cfg("TScrollbar", background=t.border, troughcolor=win, arrowcolor=t.text,
            bordercolor=win)
        cfg("TSeparator", background=t.border)
        cfg("TPanedwindow", background=win)
        for sd in self.styles.values():
            cfg(sd.name, **sd.options)
            if sd.mapping:
                mp(sd.name, **sd.mapping)
        return lines

    @staticmethod
    def call_into(lines: list[str], func: str, name: str, opts: dict[str, Any]) -> None:
        """Append ``func(name, key=value, ...)`` (indented once) wrapped at the line limit."""
        parts = [py(name), *[f"{k}={py(v)}" for k, v in opts.items()]]
        one = f"    {func}({', '.join(parts)})"
        if len(one) <= LINE:
            lines.append(one)
            return
        lines.append(f"    {func}(")
        lines.extend(f"        {part}," for part in parts)
        lines.append("    )")

    # ------------------------------------------------------------ dialect hooks (shared)
    #: wrapper frames (scrollbars) take their size in the constructor (customtkinter)
    wrapper_sized = False

    def wrapper_frame(self, var: str, parent: str, width: int, height: int) -> None:
        self.assign(var, "ttk.Frame", [parent], {"width": width, "height": height})

    scroll_orient_key = "orient"

    def scrollbar_ctor(self) -> str:
        return "ttk.Scrollbar"

    def classic_colors(self, node: Node, pbg: str) -> dict[str, Any]:
        """Colour options for classic tk widgets (Text, Listbox, Canvas) from theme + style."""
        t, st = self.theme, node.style
        bg = st.get("background") or t.surface
        fg = st.get("foreground") or t.text
        return {"background": bg, "foreground": fg}

    def text_kw(self, node: Node, pbg: str) -> dict[str, Any]:
        t = self.theme
        colors = self.classic_colors(node, pbg)
        kw: dict[str, Any] = {
            **colors, "insertbackground": colors["foreground"], "selectbackground": t.primary,
            "selectforeground": t.button_text, "relief": "flat", "borderwidth": 0,
            "highlightthickness": 1, "highlightbackground": t.border,
            "highlightcolor": t.primary, "font": self.font_tuple(node) or Raw("FONT"),
        }
        if self.cursor(node):
            kw["cursor"] = self.cursor(node)
        return kw

    # --------------------------------------------------------------- shared widgets
    def scrolled(self, node: Node, var: str, parent: str, build: Callable[[str], None],
                 *, scrollbar: bool = True, state: str = "config") -> Made:
        """Create the widget via ``build(parent)``; wrap it in a frame with a scrollbar."""
        if not scrollbar:
            build(parent)
            return Made(var=var, bg=self.surface, state=state)
        outer = self.aux(var, "frame")
        bar = self.aux(var, "scroll")
        self.wrapper_frame(outer, parent, px(node.box.w), px(node.box.h))
        self.emit(f"{outer}.pack_propagate(False)")
        build(outer)
        self.assign(bar, self.scrollbar_ctor(), [outer],
                    {self.scroll_orient_key: "vertical", "command": Raw(f"{var}.yview")})
        self.emit(f"{var}.configure(yscrollcommand={bar}.set)")
        self.emit(f"{bar}.pack(side=\"right\", fill=\"y\")")
        self.emit(f"{var}.pack(side=\"left\", fill=\"both\", expand=True)")
        return Made(var=var, outer=outer, sized=self.wrapper_sized, bg=self.surface,
                    state=state)

    def emit_sequence(self, head: str, items: list[Any], body: str | list[str]) -> None:
        """``for <head> in (<items>):`` with ``body``, wrapped when the tuple is long."""
        one = f"for {head} in {py(tuple(items))}:"
        if len(one) + self.depth * 4 <= LINE or not items:
            self.emit(one)
        else:
            self.emit(f"for {head} in (")
            for item in items:
                self.emit(f"    {py(item)},")
            self.emit("):")
        for line in [body] if isinstance(body, str) else body:
            self.emit(f"    {line}")

    def w_listbox(self, node: Node, var: str, parent: str, pbg: str) -> Made:
        p = node.props
        mode = {"single": "browse", "multiple": "multiple", "extended": "extended"}.get(
            p.get("selection_mode", "single"), "browse")

        def build(host: str) -> None:
            kw = {**self.text_kw(node, pbg), "exportselection": False, "selectmode": mode,
                  "activestyle": "none"}
            kw.pop("insertbackground")
            if self.in_flow:
                kw.update(width=chars(node.box.w), height=text_lines(node.box.h))
            self.assign(var, "tk.Listbox", [host], kw)
            self.emit_sequence("item", list(p.get("items", [])), f"{var}.insert(\"end\", item)")

        made = self.scrolled(node, var, parent, build)
        h = self.use("select")
        if h:
            self.emit(f"{var}.bind(\"<<ListboxSelect>>\", {h}, add=\"+\")")
        return made

    def w_table(self, node: Node, var: str, parent: str, pbg: str) -> Made:
        p = node.props
        columns = [str(c) for c in p.get("columns", [])] or ["Column"]
        ids = [f"c{i}" for i in range(len(columns))]
        mode = {"single": "browse", "multiple": "extended", "none": "none"}.get(
            p.get("selection_mode", "single"), "browse")
        header = bool(p.get("show_header", True))

        def build(host: str) -> None:
            kw: dict[str, Any] = {"columns": tuple(ids), "show": "headings" if header else "tree",
                                  "selectmode": mode}
            if self.in_flow:
                kw["height"] = text_lines(node.box.h)
            if self.cursor(node):
                kw["cursor"] = self.cursor(node)
            self.assign(var, "ttk.Treeview", [host], kw)
            width = max(40, px(node.box.w) // len(columns))
            if not header:
                self.emit(f"{var}.column(\"#0\", width=0, stretch=False)")
            for ident, title in zip(ids, columns, strict=True):
                self.emit(f"{var}.heading({py(ident)}, text={py(title)}, anchor=\"w\")")
                self.emit(f"{var}.column({py(ident)}, width={width}, minwidth=40, anchor=\"w\")")
            rows = [list(r) if isinstance(r, (list, tuple)) else [r] for r in p.get("rows", [])]
            if rows:
                self.emit_sequence("row", [tuple(str(c) for c in r) for r in rows],
                                   f"{var}.insert(\"\", \"end\", values=row)")

        made = self.scrolled(node, var, parent, build, state="")
        if p.get("editable"):
            self.helper("enable_cell_edit")
            cell = self.use("cell_change")
            self.emit(f"enable_cell_edit({var}{', ' + cell if cell else ''})")
        h = self.use("select")
        if h:
            self.emit(f"{var}.bind(\"<<TreeviewSelect>>\", {h}, add=\"+\")")
        return made

    def w_tree_view(self, node: Node, var: str, parent: str, pbg: str) -> Made:
        p = node.props
        header = bool(p.get("show_header", False))

        def build(host: str) -> None:
            kw: dict[str, Any] = {"show": "tree headings" if header else "tree",
                                  "selectmode": "browse"}
            if self.in_flow:
                kw["height"] = text_lines(node.box.h)
            if self.cursor(node):
                kw["cursor"] = self.cursor(node)
            self.assign(var, "ttk.Treeview", [host], kw)
            if header:
                self.emit(f"{var}.heading(\"#0\", text={py(p.get('header', 'Items'))}, anchor=\"w\")")

            def add(items: list, parent_iid: str, prefix: str) -> None:
                for i, item in enumerate(items):
                    if not isinstance(item, dict):
                        item = {"text": str(item)}
                    iid = f"{prefix}{i}"
                    kids = item.get("children") or []
                    opts = ", open=True" if kids else ""
                    self.emit(f"{var}.insert({py(parent_iid)}, \"end\", iid={py(iid)}, "
                              f"text={py(str(item.get('text', '')))}{opts})")
                    add(kids, iid, f"{iid}.")

            add(list(p.get("items", [])), "", "")

        made = self.scrolled(node, var, parent, build, state="")
        h = self.use("select")
        if h:
            self.emit(f"{var}.bind(\"<<TreeviewSelect>>\", {h}, add=\"+\")")
        return made

    def w_canvas(self, node: Node, var: str, parent: str, pbg: str) -> Made:
        p = node.props
        t = self.theme
        kw: dict[str, Any] = {"width": px(node.box.w), "height": px(node.box.h),
                              "background": node.style.get("background") or t.surface,
                              "highlightthickness": 0}
        border = self.border_explicit(node)
        if border:
            kw.update(highlightthickness=border[0], highlightbackground=border[1])
        if self.cursor(node):
            kw["cursor"] = self.cursor(node)
        if p.get("scrollable"):
            kw["scrollregion"] = (0, 0, px(node.box.w) * 2, px(node.box.h) * 2)
        self.assign(var, "tk.Canvas", [parent], kw)
        h = self.use("paint")
        if h:
            self.emit(f"{var}.bind(\"<Configure>\", {h}, add=\"+\")")
        return Made(var=var, bg=str(kw["background"]), state="")

    def w_dial(self, node: Node, var: str, parent: str, pbg: str) -> Made:
        p = node.props
        t = self.theme
        self.helper("Dial")
        kw: dict[str, Any] = {
            "minimum": int(num(p.get("minimum", 0))), "maximum": int(num(p.get("maximum", 100))),
            "value": int(num(p.get("value", 0))), "command": None,
            "background": node.style.get("background") or pbg,
            "foreground": t.primary, "track": t.border, "text": t.text,
            "width": px(node.box.w), "height": px(node.box.h),
        }
        h = self.use("change")
        if h:
            kw["command"] = Raw(h)
        self.assign(var, "Dial", [parent], kw)
        return Made(var=var, bg=pbg, state="")

    def w_date_entry(self, node: Node, var: str, parent: str, pbg: str) -> Made:
        p = node.props
        self.imports.add("from tkcalendar import DateEntry")
        kw: dict[str, Any] = {"date_pattern": p.get("pattern", "yyyy-mm-dd")}
        parts = str(p.get("date", "")).split("-")
        if len(parts) == 3 and all(x.isdigit() for x in parts):
            kw.update(year=int(parts[0]), month=int(parts[1]), day=int(parts[2]))
        if self.in_flow:
            kw["width"] = chars(node.box.w)
        self.assign(var, "DateEntry", [parent], kw)
        h = self.use("change")
        if h:
            self.emit(f"{var}.bind(\"<<DateEntrySelected>>\", {h}, add=\"+\")")
        return Made(var=var, bg=pbg)

    def w_time_entry(self, node: Node, var: str, parent: str, pbg: str) -> Made:
        p = node.props
        self.helper("TimeEntry")
        kw: dict[str, Any] = {"value": str(p.get("time", "12:00:00")),
                              "show_seconds": bool(p.get("show_seconds", True))}
        h = self.use("change")
        if h:
            kw["command"] = Raw(h)
        self.assign(var, "TimeEntry", [parent], kw)
        return Made(var=var, bg=pbg, state="")

    # ------------------------------------------------------------------------- windows
    def emit_window(self, node: Node, *, root: bool) -> list[str]:
        """Return the lines of ``build_ui`` (root) or ``open_<name>`` (dialog)."""
        self.out = []
        self.scope_widgets, self.scope_vars, self.scope_groups = [], [], {}
        self.scope_tabs = {}
        name = self.names[node.id]
        var = "root" if root else name
        self.cur = dict(node.events)
        made = self.begin_window(node, var, root=root)
        self.scope_widgets.append((name, var))
        self.emit_children(node, made)
        self.bind_remaining(node, made)
        if root:
            self.emit_menus(node, var)
        self.emit_tab_order()
        self.emit_registry(name, var)
        return self.out

    def begin_window(self, node: Node, var: str, *, root: bool) -> Made:
        raise NotImplementedError

    def window_options(self, node: Node, var: str, root: bool) -> None:
        """Lines shared by Tk and CTk windows: title, size, resize policy, icon, close ..."""
        p = node.props
        self.emit(f"{var}.title({py(p.get('title', node.name))})")
        w, h = px(p.get("width", node.box.w)), px(p.get("height", node.box.h))
        self.emit(f"{var}.geometry(\"{w}x{h}\")")
        rx, ry = bool(p.get("resizable_x", True)), bool(p.get("resizable_y", True))
        if not (rx and ry):
            self.emit(f"{var}.resizable({rx}, {ry})")
        mw, mh = px(p.get("min_width", 0)), px(p.get("min_height", 0))
        if mw or mh:
            self.emit(f"{var}.minsize({mw}, {mh})")
        if p.get("always_on_top"):
            self.emit(f"{var}.attributes(\"-topmost\", True)")
        if p.get("maximized"):
            self.emit("try:")
            self.emit(f"    {var}.state(\"zoomed\")")
            self.emit("except tk.TclError:")
            self.emit("    try:")
            self.emit(f"        {var}.attributes(\"-zoomed\", True)")
            self.emit("    except tk.TclError:")
            self.emit("        pass")
        if p.get("icon"):
            self.emit_window_icon(var, str(p["icon"]))
        h_close = self.use("close")
        if h_close:
            self.emit(f"{var}.protocol(\"WM_DELETE_WINDOW\", {h_close})")

    def emit_window_icon(self, var: str, icon: str) -> None:
        self.want_image()
        img = self.aux(var, "icon")
        self.emit(f"{img} = load_image({py(icon)})")
        self.emit(f"if {img} is not None:")
        self.emit(f"    {var}.iconphoto(True, {img})")
        self.emit(f"    {var}.icon_image = {img}")

    def emit_menus(self, node: Node, root_var: str) -> None:
        menus = node.props.get("menus") or []
        if not isinstance(menus, list) or not menus:
            return
        self.emit()
        bar = "menubar"
        self.emit(f"{bar} = tk.Menu({root_var})")
        seen: set[str] = {bar}

        def uniq(base: str) -> str:
            cand, i = base, 2
            while cand in seen or cand in self.used:
                cand = f"{base}_{i}"
                i += 1
            seen.add(cand)
            return cand

        def build(owner: str, items: list[dict], prefix: str) -> None:
            for item in items:
                if not isinstance(item, dict):
                    continue
                if item.get("separator"):
                    self.emit(f"{owner}.add_separator()")
                    continue
                label = str(item.get("label", ""))
                handler = item.get("handler")
                expr = self.handler_expr(handler) if handler else None
                if item.get("items"):
                    sub = uniq(f"{prefix}_{_slug(label)}")
                    self.emit(f"{sub} = tk.Menu({owner}, tearoff=False)")
                    build(sub, item["items"], sub)
                    self.emit(f"{owner}.add_cascade(label={py(label)}, menu={sub})")
                    continue
                kw: list[str] = [f"label={py(label)}"]
                seq = None
                if item.get("shortcut"):
                    kw.append(f"accelerator={py(item['shortcut'])}")
                    seq = shortcut_sequence(str(item["shortcut"]))
                if item.get("enabled") is False:
                    kw.append("state=\"disabled\"")
                if item.get("checkable"):
                    chk = uniq(f"{prefix}_{_slug(label)}_var")
                    self.emit(f"{chk} = tk.BooleanVar(value={bool(item.get('checked', False))})")
                    kw.insert(1, f"variable={chk}")
                    if expr:
                        kw.append(f"command={expr}")
                    self.call(f"{owner}.add_checkbutton", kw)
                else:
                    if expr:
                        kw.append(f"command={expr}")
                    self.call(f"{owner}.add_command", kw)
                if seq and expr:
                    self.emit(f"{root_var}.bind_all({py(seq)}, {expr})")

        for menu in menus:
            if not isinstance(menu, dict):
                continue
            title = str(menu.get("title", "Menu"))
            var = uniq(f"menu_{_slug(title)}")
            self.emit(f"{var} = tk.Menu({bar}, tearoff=False)")
            build(var, menu.get("items", []), var)
            self.emit(f"{bar}.add_cascade(label={py(title)}, menu={var})")
        self.emit(f"{root_var}.configure(menu={bar})")

    def emit_tab_order(self) -> None:
        wanted = [i for i in self.project.tab_order if i in self.scope_tabs]
        rest = sorted((i for i in self.scope_tabs if i not in wanted),
                      key=lambda i: (self.project.nodes[i].tab_index or 0, i))
        order = [self.scope_tabs[i] for i in (*wanted, *rest)]
        if len(order) > 1:
            self.emit()
            self.emit("# keyboard tab order (focus traversal follows stacking order)")
            one = f"for widget in ({', '.join(order)}{',' if len(order) == 1 else ''}):"
            if len(one) + self.depth * 4 <= LINE:
                self.emit(one)
            else:
                self.emit("for widget in (")
                for var in order:
                    self.emit(f"    {var},")
                self.emit("):")
            self.emit("    widget.lift()")

    def emit_registry(self, name: str, var: str) -> None:
        self.emit()
        items = list(self.scope_widgets)
        self.emit("WIDGETS.update({")
        for key, widget in items:
            self.emit(f"    {py(key)}: {widget},")
        self.emit("})")
        self.emit(f"WINDOWS[{py(name)}] = {var}")
        if self.scope_vars:
            self.emit("VARS.update({")
            for key, variable in self.scope_vars:
                self.emit(f"    {py(key)}: {variable},")
            self.emit("})")

    # ----------------------------------------------------------------- file assembly
    #: requirements known before generation (adapter + registry); the generator adds more
    base_reqs: tuple[str, ...] = ()
    #: helper sources available to this dialect (customtkinter overrides a few)
    helper_table = HELPERS
    #: first-party imports every module of this dialect needs
    base_imports: tuple[str, ...] = ("import os", "import tkinter as tk", "from tkinter import ttk")
    app_title = "tkinter"


    def build(self) -> list[GeneratedFile]:
        root = self.doc.get_node(self.project.root_id)
        functions: list[list[str]] = []
        main_lines = self.emit_window(root, root=True)
        tops = [n for n in self.doc.windows()[1:]]
        top_functions: list[list[str]] = []
        auto_open: list[str] = []
        for top in tops:
            fname = f"open_{self.names[top.id]}"
            auto = not top.props.get("start_hidden", False)
            lines = self.emit_window(top, root=False)
            top_functions.append(self.wrap_dialog(top, fname, lines))
            if auto:
                auto_open.append(fname)
        functions.append(self.wrap_root(root, main_lines, auto_open))
        functions.extend(top_functions)
        return self.assemble(functions)

    def wrap_root(self, root: Node, body: list[str], auto_open: list[str]) -> list[str]:
        lines = ["def build_ui():", f'    """Create the {root.name!r} window and return it."""']
        lines += body
        for fname in auto_open:
            lines.append(f"    {fname}()")
        lines += ["", "    return root", ""]
        # drop duplicate blank line
        return lines

    def wrap_dialog(self, top: Node, fname: str, body: list[str]) -> list[str]:
        name = self.names[top.id]
        head = [
            f"def {fname}():",
            f'    """Open (or raise) the {top.name!r} window and return it."""',
            f"    existing = WINDOWS.get({py(name)})",
            "    if existing is not None and existing.winfo_exists():",
            "        existing.deiconify()",
            "        existing.lift()",
            "        return existing",
        ]
        return [*head, *body, "", f"    return {name}", ""]

    # ------------------------------------------------------------------------ assembly
    def _import_block(self) -> list[str]:
        std, rest = [], []
        for line in {*self.base_imports, *self.imports}:
            mod = line.split()[1]
            (std if mod.split(".")[0] in _STDLIB else rest).append(line)

        def order(line: str) -> tuple[bool, bool, str]:
            return (line.split()[1] != "os", line.startswith("from"), line)

        std.sort(key=order)
        rest.sort(key=order)
        return [*std, *([""] if std and rest else []), *rest]

    def _handlers_inline(self) -> list[str]:
        out = ["# " + "-" * 76, "# Event handlers (edit freely)", "# " + "-" * 76, ""]
        custom = self.project.custom_code.strip("\n")
        if custom.strip():
            out += [custom, "", ""]
        for name in sorted(self.project.handlers):
            body = textwrap.dedent(self.project.handlers[name].body).rstrip() or "pass"
            out += [f"def {name}(event=None):", textwrap.indent(body, "    "), "", ""]
        return out

    def ui_module(self, functions: list[list[str]], docstring: str) -> str:
        lines = [HEADER, f'"""{docstring}"""', "", *self._import_block(), ""]
        lines += ["WIDGETS = {}  # widget name -> widget", "WINDOWS = {}  # window name -> window",
                  "VARS = {}  # widget name -> tkinter variable", ""]
        if not self.single:
            lines += ["import handlers  # noqa: E402,F401  (after the registries: no import cycle)", ""]
        lines += ["APP_DIR = os.path.dirname(os.path.abspath(__file__))", *self.constants(), "", ""]
        wanted = [n for n in _HELPER_ORDER if n in self.helpers]
        wanted += sorted(n for n in self.helpers if n not in _HELPER_ORDER)
        for name in wanted:
            lines += [self.helper_table[name][1], ""]
        if self.single:
            lines += self._handlers_inline()
        lines += [*self.style_function(), "", ""]
        for fn in functions:
            lines += [*fn, ""]
        return "\n".join(lines).rstrip() + "\n"

    def assemble(self, functions: list[list[str]]) -> list[GeneratedFile]:
        reqs = sorted({*self.base_reqs, *self.requirements}, key=str.lower)
        name = self.project.meta.name or "App"
        files: list[GeneratedFile] = []
        runner = ["if __name__ == \"__main__\":", "    build_ui().mainloop()"]
        if self.single:
            body = self.ui_module(functions, f"{name} - generated by py_vui.")
            files.append(GeneratedFile("main.py", body.rstrip("\n") + "\n\n\n" + "\n".join(runner) + "\n"))
        else:
            files.append(GeneratedFile("main.py", "\n".join([
                HEADER, f'"""Entry point of {name}. Run with: python main.py"""', "",
                "from ui import build_ui", "", "", "def main():", "    root = build_ui()",
                "    root.mainloop()", "", "", 'if __name__ == "__main__":', "    main()", ""])))
            files.append(GeneratedFile("ui.py", self.ui_module(
                functions, f"User interface of {name} (generated by py_vui: do not edit).")))
            files.append(handlers_file(self.project, self.options))
            files.append(GeneratedFile("custom.py", CUSTOM_PY, overwrite=False))
        files.append(GeneratedFile("requirements.txt", "\n".join(reqs) + ("\n" if reqs else "")))
        if self.options.readme:
            files.append(GeneratedFile("README.md", self.readme(reqs)))
        return files

    def readme(self, reqs: list[str]) -> str:
        meta = self.project.meta
        files = ("`main.py` (entry point), `ui.py` (generated UI, regenerated by py_vui), "
                 "`handlers.py` (your event handlers), `custom.py` (never overwritten)"
                 if not self.single else "`main.py` (everything in one file)")
        lines = [f"# {meta.name}", "", meta.description or "Generated with py_vui.", "",
                 f"Framework: **{self.app_title}**", "", "## Run", "", "```bash",
                 "pip install -r requirements.txt", "python main.py", "```", "",
                 f"Files: {files}.", "",
                 "Images and other resources are loaded from the `assets/` folder next to the "
                 "app.", "", *self.readme_notes()]
        return "\n".join(lines) + "\n"

    def readme_notes(self) -> list[str]:
        notes = [
            "## Optional features and what happens without them", "",
            "The app never crashes because an optional package is unusable; the affected "
            "widget degrades instead:", "",
            "* **Pillow `ImageTk`** (images): without Pillow, or when Pillow was built without "
            "Tk support, images fall back to Tk's own loader (PNG and GIF only). Other formats "
            "are not shown and the widget keeps its text / placeholder.",
            "* **matplotlib** (`chart` widget): needs the TkAgg backend, which requires a Python "
            "whose Tk is usable (some `uv`-managed Python builds lack it). If the import "
            "fails the chart shows a labelled placeholder with the error message.",
            "* **tkcalendar, tktimepicker, tkintermapview, tkvideoplayer, pandastable**: when "
            "missing, the matching widget shows `[Widget: pip install <package>]` instead of "
            "its content. Install the packages from `requirements.txt`.",
        ]
        if self.framework == "customtkinter":
            notes.append("* **customtkinter** renders every image through Pillow `ImageTk`; "
                         "where that is unavailable images and icons cannot be shown.")
        return notes


#: window events that must only fire for the window itself, not for its child widgets
_WINDOW_ONLY = frozenset({"resize", "show", "hide", "focus_in", "focus_out"})

CUSTOM_PY = (
    '"""Your own helper code. py_vui never overwrites this file.\n\n'
    'Import it from handlers.py with ``import custom``.\n"""\n'
)

_STDLIB = frozenset({"os", "sys", "math", "tkinter", "types", "datetime", "json", "re",
                     "pathlib", "csv", "io", "time", "random", "itertools", "collections"})


def _slug(text: str) -> str:
    s = re.sub(r"[^0-9a-zA-Z]+", "_", text.strip()).strip("_").lower()
    return s or "item"


#: tk virtual events plugin widgets expose, by widget type (adapters bind ``change`` etc.)
PLUGIN_SEQUENCES: dict[str, dict[str, str]] = {}
