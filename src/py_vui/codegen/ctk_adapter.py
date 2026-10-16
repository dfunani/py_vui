"""``customtkinter`` code generator.

Shares layout, event, menu, theme and file-assembly logic with the plain ``tkinter`` adapter
(:mod:`py_vui.codegen.tk_common`); only widget construction differs here.  customtkinter
widgets take their size in the constructor, so they are placed with ``place(x=, y=)`` and
anchored widgets that stretch use the small generated ``stretch()`` helper.
"""

from __future__ import annotations

import re
import textwrap
from typing import Any

from py_vui.codegen import tk_plugins  # noqa: F401  (registers the built-in plugin emitters)
from py_vui.codegen.base import Adapter, GeneratedFile, GenOptions, register_adapter
from py_vui.codegen.tk_adapter import TkGen
from py_vui.codegen.tk_common import (
    HELPERS,
    Made,
    Place,
    Raw,
    TkGenerator,
    num,
    px,
    py,
)
from py_vui.core.model import Node, Project

_NON_ALNUM = re.compile(r"[^0-9a-zA-Z]+")

#: helpers whose customtkinter flavour differs from the tkinter one
CTK_HELPERS: dict[str, tuple[tuple[str, ...], str, tuple[str, ...]]] = {}


def _ctk_helper(name: str, source: str, deps: tuple[str, ...] = ()) -> None:
    CTK_HELPERS[name] = ((), textwrap.dedent(source).strip("\n") + "\n", deps)


_ctk_helper("load_image", '''
    def load_image(path, size=None, fit="contain"):
        """Load ``path`` as a CTkImage (``None`` if the file is missing)."""
        full = asset(path)
        if not os.path.exists(full):
            return None
        from PIL import Image

        picture = Image.open(full)
        shown = picture.size
        if size and fit == "stretch":
            shown = tuple(size)
        elif size and fit == "contain":
            ratio = min(size[0] / picture.width, size[1] / picture.height)
            shown = (max(1, int(picture.width * ratio)), max(1, int(picture.height * ratio)))
        return ctk.CTkImage(light_image=picture, dark_image=picture, size=shown)
''', deps=("asset",))

_ctk_helper("stretch", '''
    def stretch(widget, parent, right=None, bottom=None):
        """Keep ``widget`` ``right`` / ``bottom`` pixels away from the edges of ``parent``."""

        def on_resize(_event=None):
            scale = widget._get_widget_scaling()  # customtkinter's DPI factor
            if right is not None:
                width = (parent.winfo_width() - widget.winfo_x() - right) / scale
                widget.configure(width=max(1, int(width)))
            if bottom is not None:
                height = (parent.winfo_height() - widget.winfo_y() - bottom) / scale
                widget.configure(height=max(1, int(height)))

        parent.bind("<Configure>", on_resize, add="+")
        on_resize()
''')

_ctk_helper("Spinbox", '''
    class Spinbox(ctk.CTkFrame):
        """Number entry with - / + buttons (customtkinter has no native spin box)."""

        def __init__(self, master, minimum=0, maximum=100, value=0, step=1, decimals=0,
                     wrap=False, command=None, width=110, height=32, accent="#6366f1",
                     text_color="#18181b", **kw):
            super().__init__(master, width=width, height=height, **kw)
            self.minimum, self.maximum, self.step = minimum, maximum, step
            self.decimals, self.wrap = decimals, wrap
            self.variable = tk.StringVar(value=self._format(value))
            self.grid_propagate(False)
            self.grid_columnconfigure(1, weight=1)
            self.grid_rowconfigure(0, weight=1)
            side = max(8, height - 4)
            ctk.CTkButton(self, text="-", width=side, height=side, fg_color=accent,
                          command=lambda: self.step_by(-1)).grid(row=0, column=0, padx=2)
            self.entry = ctk.CTkEntry(self, textvariable=self.variable, justify="center",
                                      height=side, text_color=text_color)
            self.entry.grid(row=0, column=1, sticky="ew")
            ctk.CTkButton(self, text="+", width=side, height=side, fg_color=accent,
                          command=lambda: self.step_by(1)).grid(row=0, column=2, padx=2)
            if command:
                self.variable.trace_add("write", lambda *_: command())

        def _format(self, value):
            return f"{value:.{self.decimals}f}"

        def get(self):
            try:
                value = float(self.variable.get())
            except ValueError:
                value = self.minimum
            return round(value) if self.decimals == 0 else value

        def set(self, value):
            self.variable.set(self._format(max(self.minimum, min(self.maximum, value))))

        def step_by(self, direction):
            value = self.get() + direction * self.step
            if value > self.maximum:
                value = self.minimum if self.wrap else self.maximum
            elif value < self.minimum:
                value = self.maximum if self.wrap else self.minimum
            self.set(value)
''')


class CtkGen(TkGenerator):
    framework = "customtkinter"
    app_title = "customtkinter"
    base_imports = ("import os", "import tkinter as tk", "from tkinter import ttk",
                    "import customtkinter as ctk")
    helper_table = {**HELPERS, **CTK_HELPERS}

    wrapper_sized = True

    # --------------------------------------------------------------------- helpers
    def helper_stretch(self) -> None:
        self.helper("stretch")

    def wrapper_frame(self, var: str, parent: str, width: int, height: int) -> None:
        self.assign(var, "ctk.CTkFrame", [parent], {
            "width": width, "height": height, "fg_color": "transparent", "corner_radius": 0})

    scroll_orient_key = "orientation"

    def scrollbar_ctor(self) -> str:
        return "ctk.CTkScrollbar"

    def ctk_font(self, node: Node) -> Raw | None:
        s = node.style
        if not any(s.get(k) for k in ("font_family", "font_size", "bold", "italic", "underline")):
            return None
        r = self.res(node)
        kw: dict[str, Any] = {"family": r["font_family"], "size": int(r["font_size"])}  # type: ignore[call-overload]
        if r["bold"]:
            kw["weight"] = "bold"
        if r["italic"]:
            kw["slant"] = "italic"
        if r["underline"]:
            kw["underline"] = True
        return Raw("ctk.CTkFont(" + ", ".join(f"{k}={py(v)}" for k, v in kw.items()) + ")")

    def radius(self, node: Node, *, button: bool = False) -> int | None:
        explicit = node.style.get("corner_radius", -1)
        if explicit not in (-1, None):
            return int(explicit)
        return self.theme.button_radius if button else None

    def size_kw(self, node: Node) -> dict[str, Any]:
        return {"width": px(node.box.w), "height": px(node.box.h)}

    def visuals(self, node: Node, *, fg: str | None = None, text: bool = False,
                button: bool = False, border: bool = True, radius: bool = True,
                font: bool = True, hover: bool = False) -> dict[str, Any]:
        """Common customtkinter styling options derived from the node style and theme."""
        t = self.theme
        kw: dict[str, Any] = {}
        if fg is not None or node.style.get("background"):
            kw["fg_color"] = node.style.get("background") or fg
        if text:
            kw["text_color"] = node.style.get("foreground") or (t.button_text if button else t.text)
        if hover:
            kw["hover_color"] = node.style.get("hover_color") or t.primary_hover
        if radius and self.radius(node, button=button) is not None:
            kw["corner_radius"] = self.radius(node, button=button)
        bw = self.border_explicit(node)
        if border and bw:
            kw.update(border_width=bw[0], border_color=bw[1])
        if font and self.ctk_font(node):
            kw["font"] = self.ctk_font(node)
        if self.cursor(node):
            kw["cursor"] = self.cursor(node)
        return kw

    def image_kw(self, node: Node, var: str, kw: dict[str, Any], key: str = "image") -> str | None:
        path = node.props.get(key)
        if not path:
            return None
        self.want_image()
        img = self.aux(var, "image")
        self.emit(f"{img} = load_image({py(path)})")
        kw["image"] = Raw(img)
        return img

    def emit_window_icon(self, var: str, icon: str) -> None:
        self.helper("asset")
        self.emit("try:")
        self.emit(f"    {var}.iconphoto(True, tk.PhotoImage(file=asset({py(icon)})))")
        self.emit("except tk.TclError:")
        self.emit("    pass  # missing / unsupported icon file")

    def emit_pane_add(self, parent: str, outer: str, place: Place) -> None:
        self.emit(f"{parent}.add({outer}, stretch=\"always\")")

    # ---------------------------------------------------------------------- windows
    def constants(self) -> list[str]:
        t = self.theme
        return [f"FONT = ({py(t.font_family)}, {t.font_size})"]

    def begin_window(self, node: Node, var: str, *, root: bool) -> Made:
        t = self.theme
        bg = node.style.get("background") or t.background
        if root:
            self.emit(f"ctk.set_appearance_mode({py(t.appearance)})")
            self.emit("ctk.ThemeManager.theme[\"CTkFont\"].update(family=FONT[0], size=FONT[1])")
            self.emit(f"{var} = ctk.CTk()")
            self.emit(f"configure_styles({var})")
        else:
            main = self.names[self.project.root_id]
            self.emit(f"parent = WINDOWS[{py(main)}]")
            self.emit(f"{var} = ctk.CTkToplevel(parent)")
        self.window_options(node, var, root)
        self.emit(f"{var}.configure(fg_color={py(bg)})")
        if not root:
            self.emit(f"{var}.transient(parent)")
            if node.props.get("modal"):
                self.helper("grab_when_visible")
                self.emit(f"grab_when_visible({var})")
        return Made(var=var, bg=bg, target=lambda page: var, state="")

    def w_unsupported(self, node: Node, var: str, parent: str, pbg: str, text: str) -> Made:
        self.assign(var, "ctk.CTkLabel", [parent], {
            **self.size_kw(node), "text": f"[{text}]", "fg_color": self.theme.border,
            "text_color": self.theme.text, "wraplength": max(40, px(node.box.w) - 8)})
        return Made(var=var, sized=True, bg=pbg, placeholder=True, state="")

    # ------------------------------------------------------------------- containers
    def w_frame(self, node: Node, var: str, parent: str, pbg: str) -> Made:
        bg = node.style.get("background") or self.surface
        kw = {**self.size_kw(node), **self.visuals(node, fg=bg, font=False)}
        self.assign(var, "ctk.CTkFrame", [parent], kw)
        return Made(var=var, sized=True, bg=bg, target=lambda page: var, state="")

    def w_label_frame(self, node: Node, var: str, parent: str, pbg: str) -> Made:
        p = node.props
        t = self.theme
        bg = node.style.get("background") or self.surface
        bw = self.border_explicit(node)
        kw = {**self.size_kw(node), **self.visuals(node, fg=bg, font=False)}
        kw.setdefault("border_width", bw[0] if bw else 1)
        kw.setdefault("border_color", t.border)
        self.assign(var, "ctk.CTkFrame", [parent], kw)
        title = self.aux(var, "title")
        lab: dict[str, Any] = {"text": p.get("title", ""), "fg_color": bg,
                               "text_color": node.style.get("foreground") or t.text,
                               "height": 18, "corner_radius": 0}
        if self.ctk_font(node):
            lab["font"] = self.ctk_font(node)
        self.assign(title, "ctk.CTkLabel", [var], lab)
        align = p.get("title_align", "left")
        place = {"left": "x=10, y=-2", "center": "relx=0.5, y=-2, anchor=\"n\"",
                 "right": "relx=1.0, x=-10, y=-2, anchor=\"ne\""}.get(align, "x=10, y=-2")
        self.emit(f"{title}.place({place})")
        return Made(var=var, sized=True, bg=bg, target=lambda page: var, state="")

    def w_tabview(self, node: Node, var: str, parent: str, pbg: str) -> Made:
        p = node.props
        t = self.theme
        bg = node.style.get("background") or self.surface
        titles: list[str] = []
        for raw in [str(x) for x in p.get("tabs", [])] or ["Tab 1"]:
            title, i = raw, 2
            while title in titles:  # CTkTabview needs unique names
                title, i = f"{raw} ({i})", i + 1
            titles.append(title)
        kw: dict[str, Any] = {**self.size_kw(node), "fg_color": bg,
                              "segmented_button_selected_color": t.primary,
                              "segmented_button_selected_hover_color": t.primary_hover,
                              "segmented_button_unselected_color": t.border,
                              "segmented_button_unselected_hover_color": t.border,
                              "text_color": t.button_text}
        if self.radius(node) is not None:
            kw["corner_radius"] = self.radius(node)
        h = self.use("tab_change")
        if h:
            kw["command"] = Raw(h)
        self.assign(var, "ctk.CTkTabview", [parent], kw)
        for title in titles:
            self.emit(f"{var}.add({py(title)})")
        current = int(num(p.get("current", 0)))
        if 0 < current < len(titles):
            self.emit(f"{var}.set({py(titles[current])})")
        return Made(var=var, sized=True, bg=bg, state="",
                    target=lambda page: f"{var}.tab({py(titles[min(page, len(titles) - 1)])})")

    def w_scroll_frame(self, node: Node, var: str, parent: str, pbg: str) -> Made:
        if node.props.get("orientation") == "both":
            # CTkScrollableFrame scrolls one way only: use the generated two-way ScrollFrame
            return TkGen.w_scroll_frame(self, node, var, parent, pbg)  # type: ignore[arg-type]
        p = node.props
        bg = node.style.get("background") or self.surface
        orient = "horizontal" if p.get("orientation") == "horizontal" else "vertical"
        # customtkinter sizes the scrollable frame by its *inner* area (plus bars and padding),
        # so it fills a wrapper frame that has exactly the designed size
        outer = self.aux(var, "frame")
        self.wrapper_frame(outer, parent, px(node.box.w), px(node.box.h))
        self.emit(f"{outer}.pack_propagate(False)")
        kw = {**self.visuals(node, fg=bg, font=False), "orientation": orient}
        self.assign(var, "ctk.CTkScrollableFrame", [outer], kw)
        self.emit(f"{var}.pack(fill=\"both\", expand=True)")
        target, size = var, (node.box.w, node.box.h)
        if self.layout_of(node).mode == "absolute":
            kids = self.doc.children(node.id)
            cw = int(num(p.get("content_width", 0))) or px(node.box.w) - (
                16 if orient == "vertical" else 0)
            ch = int(num(p.get("content_height", 0))) or max(
                px(node.box.h), px(max([k.box.y + k.box.h for k in kids] or [0]) + 8))
            if orient == "horizontal":
                cw = int(num(p.get("content_width", 0))) or max(
                    px(node.box.w), px(max([k.box.x + k.box.w for k in kids] or [0]) + 8))
                ch = int(num(p.get("content_height", 0))) or px(node.box.h) - 16
            content = self.aux(var, "content")
            self.assign(content, "ctk.CTkFrame", [var], {
                "width": cw, "height": ch, "fg_color": "transparent", "corner_radius": 0})
            self.emit(f"{content}.pack(anchor=\"nw\")")
            target, size = content, (cw, ch)
        return Made(var=var, outer=outer, sized=True, bg=bg, state="",
                    target=lambda page: target, child_size=size)

    def w_paned_window(self, node: Node, var: str, parent: str, pbg: str) -> Made:
        p = node.props
        orient = p.get("orientation", "horizontal")
        self.assign(var, "tk.PanedWindow", [parent], {
            "orient": orient, "sashwidth": 6, "background": self.theme.border,
            "borderwidth": 0, "width": px(node.box.w), "height": px(node.box.h)})
        sizes = [px(s) for s in p.get("sizes", []) if num(s) > 0]
        n_kids = len([k for k in self.doc.children(node.id) if k.visible])

        def post() -> None:
            sashes = min(len(sizes), n_kids - 1)
            if sashes < 1:
                return
            cumulative, total = [], 0
            for s in sizes[:sashes]:
                total += s
                cumulative.append(total)
            self.helper("set_sashes")
            self.emit(f"set_sashes({var}, {py(tuple(cumulative))})")

        return Made(var=var, bg=self.theme.background, state="", target=lambda page: var, post=post)

    # ---------------------------------------------------------------------- display
    def w_label(self, node: Node, var: str, parent: str, pbg: str) -> Made:
        p = node.props
        kw: dict[str, Any] = {**self.size_kw(node), "text": p.get("text", ""),
                              "anchor": p.get("anchor", "w"), "justify": p.get("justify", "left"),
                              **self.visuals(node, text=True)}
        if num(p.get("wrap_length")):
            kw["wraplength"] = int(p["wrap_length"])
        img = self.image_kw(node, var, kw)
        if img:
            kw["compound"] = "left"
        self.assign(var, "ctk.CTkLabel", [parent], kw)
        return Made(var=var, sized=True, bg=pbg, state="")

    def w_image(self, node: Node, var: str, parent: str, pbg: str) -> Made:
        p = node.props
        src = p.get("source")
        kw: dict[str, Any] = {**self.size_kw(node), "text": "", **self.visuals(node, text=True)}
        img = None
        if src:
            self.want_image()
            img = self.aux(var, "image")
            fit = p.get("fit", "contain")
            size = f", size=({px(node.box.w)}, {px(node.box.h)}), fit={py(fit)}" if fit != "none" else ""
            self.emit(f"{img} = load_image({py(src)}{size})")
            kw["image"] = Raw(img)
        else:
            kw["text"] = p.get("alt_text", "Image")
            kw["fg_color"] = self.theme.border
        self.assign(var, "ctk.CTkLabel", [parent], kw)
        if img:
            self.emit(f"if {img} is None:  # the file is missing: show the placeholder text")
            self.emit(f"    {var}.configure(text={py(p.get('alt_text', 'Image'))})")
        h = self.use("click")
        if h:
            self.emit(f"{var}.bind(\"<Button-1>\", {h}, add=\"+\")")
        return Made(var=var, sized=True, bg=pbg, state="")

    def w_separator(self, node: Node, var: str, parent: str, pbg: str) -> Made:
        kw = {**self.size_kw(node),
              "fg_color": node.style.get("background") or self.theme.border, "corner_radius": 0}
        self.assign(var, "ctk.CTkFrame", [parent], kw)
        return Made(var=var, sized=True, bg=pbg, state="")

    def labelled(self, node: Node, var: str, parent: str, vertical: bool) -> tuple[str, str, str]:
        """A transparent box of the designed size holding a widget and its value label."""
        outer, label = self.aux(var, "box"), self.aux(var, "text")
        self.wrapper_frame(outer, parent, px(node.box.w), px(node.box.h))
        self.emit(f"{outer}.pack_propagate(False)")
        return outer, label, "bottom" if vertical else "right"

    def pack_labelled(self, var: str, label: str, side: str, text_expr: str, vv: str,
                      host: str) -> None:
        self.assign(label, "ctk.CTkLabel", [host], {
            "text": "", "width": 40, "text_color": self.theme.text})
        self.emit(f"{label}.pack(side=\"{side}\")")
        self.emit(f"{var}.pack(side=\"{'left' if side == 'right' else 'top'}\", "
                  "fill=\"both\", expand=True)")
        self.emit(f"{vv}.trace_add(\"write\", lambda *_: {label}.configure(text={text_expr}))")
        self.emit(f"{vv}.set({vv}.get())  # show the initial value")

    def w_progressbar(self, node: Node, var: str, parent: str, pbg: str) -> Made:
        p = node.props
        t = self.theme
        orient = p.get("orientation", "horizontal")
        indeterminate = p.get("mode") == "indeterminate"
        maximum = num(p.get("maximum", 100)) or 100
        text = bool(p.get("show_text")) and not indeterminate
        host, outer, label, side = parent, "", "", ""
        if text:
            outer, label, side = self.labelled(node, var, parent, orient == "vertical")
            host = outer
        kw: dict[str, Any] = {**self.size_kw(node), "orientation": orient,
                              "progress_color": t.primary, "fg_color": t.border}
        if indeterminate:
            kw["mode"] = "indeterminate"
        if text:
            vv = self.aux(var, "var")
            self.emit(f"{vv} = tk.DoubleVar(value={py(round(min(1.0, num(p.get('value', 0)) / maximum), 4))})")
            self.scope_vars.append((var, vv))
            kw["variable"] = Raw(vv)
            kw["width"], kw["height"] = (px(node.box.w) - 44, px(node.box.h)) if side == "right" \
                else (px(node.box.w), px(node.box.h) - 24)
        if self.radius(node) is not None:
            kw["corner_radius"] = self.radius(node)
        self.assign(var, "ctk.CTkProgressBar", [host], kw)
        if indeterminate:
            self.emit(f"{var}.start()")
        elif text:
            self.pack_labelled(var, label, side, f"f\"{{{vv}.get():.0%}}\"", vv, host)
        else:
            self.emit(f"{var}.set({py(round(min(1.0, num(p.get('value', 0)) / maximum), 4))})")
        return Made(var=var, outer=outer, sized=True, bg=pbg, state="")

    # ----------------------------------------------------------------------- inputs
    def w_button(self, node: Node, var: str, parent: str, pbg: str) -> Made:
        p = node.props
        r = self.res(node)
        kw: dict[str, Any] = {**self.size_kw(node), "text": p.get("text", ""),
                              "fg_color": r["background"], "hover_color": r["hover_color"],
                              "text_color": r["foreground"],
                              "corner_radius": self.radius(node, button=True)}
        kw.update({k: v for k, v in self.visuals(node, radius=False).items() if k not in kw})
        if self.border_explicit(node) is None and "border_width" in kw:
            kw.pop("border_width")
        img = self.image_kw(node, var, kw)
        if img:
            kw["compound"] = {"center": "top"}.get(p.get("compound", "left"), p.get("compound", "left"))
        h = self.use("click")
        if h:
            kw["command"] = Raw(h)
        self.assign(var, "ctk.CTkButton", [parent], kw)
        return Made(var=var, sized=True, bg=pbg, state="ctk")

    def w_tool_button(self, node: Node, var: str, parent: str, pbg: str) -> Made:
        p = node.props
        t = self.theme
        h = self.use("click")
        kw = {**self.size_kw(node), "text": p.get("text", ""), "fg_color": "transparent",
              "border_width": 1, "border_color": t.border, "hover_color": t.border,
              "text_color": t.text, **self.visuals(node, radius=True)}
        img = self.image_kw(node, var, kw)
        if img:
            kw["compound"] = "left"
        if p.get("checkable"):
            # a real toggle: the button keeps its state in a variable and shows it as colours
            vv = self.aux(var, "var")
            self.emit(f"{vv} = tk.BooleanVar(value=False)")
            self.scope_vars.append((var, vv))
            self.assign(var, "ctk.CTkButton", [parent], kw)
            self.emit(f"{var}.configure(command=lambda: {vv}.set(not {vv}.get()))")
            self.emit(f"{vv}.trace_add(\"write\", lambda *_: {var}.configure(")
            self.emit(f"    fg_color={py(t.primary)} if {vv}.get() else \"transparent\",")
            self.emit(f"    text_color={py(t.button_text)} if {vv}.get() else {py(t.text)}))")
            if h:
                self.emit(f"{vv}.trace_add(\"write\", lambda *_: {h}())")
            return Made(var=var, sized=True, bg=pbg, state="ctk")
        if h:
            kw["command"] = Raw(h)
        self.assign(var, "ctk.CTkButton", [parent], kw)
        return Made(var=var, sized=True, bg=pbg, state="ctk")

    def w_entry(self, node: Node, var: str, parent: str, pbg: str) -> Made:
        p = node.props
        t = self.theme
        kw: dict[str, Any] = {**self.size_kw(node), **self.visuals(node, fg=t.surface, text=True)}
        kw.setdefault("border_color", t.border)
        vv = self.aux(var, "var")
        self.emit(f"{vv} = tk.StringVar(value={py(p.get('text', ''))})")
        self.scope_vars.append((var, vv))
        kw["textvariable"] = Raw(vv)
        if p.get("justify", "left") != "left":
            kw["justify"] = p["justify"]
        if p.get("show"):
            kw["show"] = p["show"]
        if p.get("readonly"):
            kw["state"] = "readonly"
        self.assign(var, "ctk.CTkEntry", [parent], kw)
        if p.get("placeholder"):
            # an overlay label instead of CTkEntry's placeholder_text, which is disabled by a
            # textvariable; with the variable, programmatic edits are observable too
            self.helper("add_placeholder")
            self.emit(f"add_placeholder({var}, {vv}, {py(p['placeholder'])}, "
                      f"color={py(t.muted_text)}, background={py(kw['fg_color'])}, x=10)")
        if int(num(p.get("max_length", 0))) > 0:
            limit = int(p["max_length"])
            self.emit(f"{var}.configure(validate=\"key\", "
                      f"validatecommand=({var}.register(lambda value: len(value) <= {limit}), \"%P\"))")
        h = self.use("change")
        if h:
            self.emit(f"{vv}.trace_add(\"write\", lambda *_: {h}())")
        return Made(var=var, sized=True, bg=pbg, state="ctk")

    def w_text(self, node: Node, var: str, parent: str, pbg: str) -> Made:
        p = node.props
        t = self.theme
        kw: dict[str, Any] = {**self.size_kw(node), "wrap": p.get("wrap", "word"),
                              "border_color": t.border, "border_width": 1,
                              "activate_scrollbars": bool(p.get("scrollbar", True)),
                              **self.visuals(node, fg=t.surface, text=True)}
        self.assign(var, "ctk.CTkTextbox", [parent], kw)
        if p.get("text"):
            self.emit(f"{var}.insert(\"1.0\", {py(p['text'])})")
        if p.get("placeholder"):
            self.helper("add_text_placeholder")
            self.emit(f"add_text_placeholder({var}, {py(p['placeholder'])}, "
                      f"color={py(t.muted_text)}, background={py(kw['fg_color'])})")
        h = self.use("change")
        if h:
            self.helper("bind_text_change")
            self.emit(f"bind_text_change({var}, {h})")
        if h or p.get("placeholder"):
            self.emit(f"{var}.edit_modified(False)")
        if p.get("readonly"):
            self.emit(f"{var}.configure(state=\"disabled\")")
        return Made(var=var, sized=True, bg=pbg, state="ctk")

    def _check_like(self, node: Node, var: str, ctor: str, kw: dict[str, Any]) -> Made:
        t = self.theme
        h = self.use("toggle", "click")
        if h:
            kw["command"] = Raw(h)
        kw.update(self.size_kw(node))
        kw.update(self.visuals(node, text=True, fg=t.primary, hover=True))
        self.assign(var, ctor, [kw.pop("_parent")], kw)
        return Made(var=var, sized=True, state="ctk")

    def w_checkbox(self, node: Node, var: str, parent: str, pbg: str) -> Made:
        vv = self.aux(var, "var")
        self.emit(f"{vv} = tk.BooleanVar(value={bool(node.props.get('checked'))})")
        self.scope_vars.append((var, vv))
        made = self._check_like(node, var, "ctk.CTkCheckBox", {
            "_parent": parent, "text": node.props.get("text", ""), "variable": Raw(vv),
            "onvalue": True, "offvalue": False})
        made.bg = pbg
        return made

    def w_radio(self, node: Node, var: str, parent: str, pbg: str) -> Made:
        p = node.props
        group = str(p.get("group") or "group1")
        value = str(p.get("value") or p.get("text", ""))
        gv = self.scope_groups.get(group)
        if gv is None:
            initial = ""
            for other in self.doc.walk():
                if other.type == "radio" and str(other.props.get("group") or "group1") == group \
                        and other.props.get("checked"):
                    initial = str(other.props.get("value") or other.props.get("text", ""))
                    break
            slug = _NON_ALNUM.sub("_", group).strip("_").lower() or "group"
            gv = self.aux(f"group_{slug}", "var")
            self.emit(f"{gv} = tk.StringVar(value={py(initial)})")
            self.scope_groups[group] = gv
            self.scope_vars.append((f"group_{slug}", gv))
        made = self._check_like(node, var, "ctk.CTkRadioButton", {
            "_parent": parent, "text": p.get("text", ""), "value": value, "variable": Raw(gv)})
        made.bg = pbg
        return made

    def w_switch(self, node: Node, var: str, parent: str, pbg: str) -> Made:
        p = node.props
        t = self.theme
        vv = self.aux(var, "var")
        self.emit(f"{vv} = tk.BooleanVar(value={bool(p.get('checked'))})")
        self.scope_vars.append((var, vv))
        kw: dict[str, Any] = {**self.size_kw(node), "text": p.get("text", ""), "variable": Raw(vv),
                              "onvalue": True, "offvalue": False, "progress_color": t.primary,
                              **self.visuals(node, text=True, radius=False)}
        h = self.use("toggle", "click")
        if h:
            kw["command"] = Raw(h)
        self.assign(var, "ctk.CTkSwitch", [parent], kw)
        return Made(var=var, sized=True, bg=pbg, state="ctk")

    def w_slider(self, node: Node, var: str, parent: str, pbg: str) -> Made:
        p = node.props
        t = self.theme
        lo, hi, step = num(p.get("minimum", 0)), num(p.get("maximum", 100)), num(p.get("step", 1))
        vv = self.aux(var, "var")
        self.emit(f"{vv} = tk.DoubleVar(value={py(p.get('value', 0))})")
        self.scope_vars.append((var, vv))
        vertical = p.get("orientation", "horizontal") == "vertical"
        show = bool(p.get("show_value"))
        host, outer, label, side = parent, "", "", ""
        size = self.size_kw(node)
        if show:  # customtkinter has no value read-out: add a label next to the slider
            outer, label, side = self.labelled(node, var, parent, vertical)
            host = outer
            size = ({"width": px(node.box.w), "height": max(10, px(node.box.h) - 24)} if vertical
                    else {"width": max(10, px(node.box.w) - 44), "height": px(node.box.h)})
        kw: dict[str, Any] = {**size, "from_": p.get("minimum", 0),
                              "to": p.get("maximum", 100), "variable": Raw(vv),
                              "orientation": p.get("orientation", "horizontal"),
                              "progress_color": t.primary, "button_color": t.primary,
                              "button_hover_color": t.primary_hover, "fg_color": t.border}
        if step > 0 and hi > lo:
            kw["number_of_steps"] = max(1, round((hi - lo) / step))
        self.assign(var, "ctk.CTkSlider", [host], kw)
        if show:
            self.pack_labelled(var, label, side, f"f\"{{{vv}.get():g}}\"", vv, host)
        h = self.use("change")
        if h:
            self.emit(f"{vv}.trace_add(\"write\", lambda *_: {h}())")
        return Made(var=var, outer=outer, sized=True, bg=pbg, state="ctk")

    def w_spinbox(self, node: Node, var: str, parent: str, pbg: str) -> Made:
        p = node.props
        t = self.theme
        self.helper("Spinbox")
        dec = int(num(p.get("decimals", 0)))
        kw: dict[str, Any] = {
            "minimum": p.get("minimum", 0), "maximum": p.get("maximum", 100),
            "value": p.get("value", 0), "step": p.get("step", 1), "decimals": dec,
            "wrap": bool(p.get("wrap")), "command": None, **self.size_kw(node),
            "accent": t.primary, "text_color": t.text,
            "fg_color": node.style.get("background") or "transparent",
        }
        h = self.use("change")
        if h:
            kw["command"] = Raw(h)
        self.assign(var, "Spinbox", [parent], kw)
        self.scope_vars.append((var, f"{var}.variable"))
        return Made(var=var, sized=True, bg=pbg, state="")

    def w_combobox(self, node: Node, var: str, parent: str, pbg: str) -> Made:
        p = node.props
        t = self.theme
        items = [str(i) for i in p.get("items", [])]
        kw: dict[str, Any] = {**self.size_kw(node), "values": items,
                              "state": "normal" if p.get("editable") else "readonly",
                              "fg_color": node.style.get("background") or t.surface,
                              "border_color": t.border, "button_color": t.primary,
                              "button_hover_color": t.primary_hover,
                              "dropdown_fg_color": t.surface, "dropdown_text_color": t.text,
                              "dropdown_hover_color": t.border,
                              "text_color": node.style.get("foreground") or t.text}
        if self.radius(node) is not None:
            kw["corner_radius"] = self.radius(node)
        if self.ctk_font(node):
            kw["font"] = self.ctk_font(node)
        h = self.use("change")
        vv = None
        if h:
            vv = self.aux(var, "var")
            self.emit(f"{vv} = tk.StringVar()")
            self.scope_vars.append((var, vv))
            kw["variable"] = Raw(vv)
        self.assign(var, "ctk.CTkComboBox", [parent], kw)
        current = int(num(p.get("current", 0)))
        if 0 <= current < len(items):
            self.emit(f"{var}.set({py(items[current])})")
        if h:
            self.emit(f"{vv}.trace_add(\"write\", lambda *_: {h}())")
        return Made(var=var, sized=True, bg=pbg, state="ctk")

    def w_segmented_button(self, node: Node, var: str, parent: str, pbg: str) -> Made:
        p = node.props
        t = self.theme
        items = [str(i) for i in p.get("items", [])]
        current = int(num(p.get("current", 0)))
        vv = self.aux(var, "var")
        self.emit(f"{vv} = tk.StringVar(value={py(items[current] if 0 <= current < len(items) else '')})")
        self.scope_vars.append((var, vv))
        kw: dict[str, Any] = {**self.size_kw(node), "values": items, "variable": Raw(vv),
                              "dynamic_resizing": False,
                              "selected_color": t.primary, "selected_hover_color": t.primary_hover,
                              "unselected_color": t.border, "unselected_hover_color": t.border,
                              "text_color": t.button_text}
        if self.radius(node) is not None:
            kw["corner_radius"] = self.radius(node)
        self.assign(var, "ctk.CTkSegmentedButton", [parent], kw)
        if 0 <= current < len(items):
            self.emit(f"{var}.set({py(items[current])})")
        h = self.use("change")
        if h:
            self.emit(f"{vv}.trace_add(\"write\", lambda *_: {h}())")
        return Made(var=var, sized=True, bg=pbg, state="ctk")


class CtkAdapter(Adapter):
    framework = "customtkinter"
    label = "CustomTkinter"

    def base_requirements(self) -> list[str]:
        return ["customtkinter>=5.2", "pillow>=10"]

    def image_requirements(self) -> list[str]:
        return ["pillow>=10"]

    def generate(self, project: Project, options: GenOptions) -> list[GeneratedFile]:
        gen = CtkGen(project, options)
        gen.base_reqs = tuple(self.requirements(project))
        return gen.build()


ADAPTER = register_adapter(CtkAdapter())
