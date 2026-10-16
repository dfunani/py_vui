"""``tkinter`` code generator (ttk widgets on the ``clam`` theme).

Output follows docs/architecture.md: ``main.py`` + ``ui.py`` (``build_ui()``, ``WIDGETS``,
``WINDOWS``) + ``handlers.py`` + ``custom.py`` + ``requirements.txt`` + ``README.md``, or one
self-contained ``main.py`` when ``GenOptions.layout == "single"``.
"""

from __future__ import annotations

import re
from typing import Any

from py_vui.codegen import tk_plugins  # noqa: F401  (registers the built-in plugin emitters)
from py_vui.codegen.base import Adapter, GeneratedFile, GenOptions, register_adapter
from py_vui.codegen.tk_common import (
    Made,
    Raw,
    StyleDef,
    TkGenerator,
    chars,
    num,
    px,
    py,
    text_lines,
)
from py_vui.core.model import Node, Project

_NON_ALNUM = re.compile(r"[^0-9a-zA-Z]+")


class TkGen(TkGenerator):
    framework = "tkinter"
    app_title = "tkinter (ttk)"
    box_types = frozenset({"label", "image", "button", "tool_button", "entry", "checkbox",
                           "radio", "combobox", "spinbox", "separator", "date_entry", "switch",
                           "slider"})

    # ------------------------------------------------------------------ style helpers
    def widget_style(self, node: Node, var: str, cls: str, pbg: str, *, fill: bool = True,
                     extra: dict[str, Any] | None = None,
                     mapping: dict[str, list[tuple[str, Any]]] | None = None) -> str | None:
        """A per-widget ttk style when the node (or its parent's colour) needs one."""
        opts = dict(extra or {})
        mp = {k: list(v) for k, v in (mapping or {}).items()}
        bg = node.style.get("background") or pbg
        if fill and bg != self.surface:
            opts["background"] = bg
            mp.setdefault("background", []).insert(0, ("active", bg))
        if node.style.get("foreground"):
            opts["foreground"] = node.style["foreground"]
        font = self.font_tuple(node)
        if font:
            opts["font"] = font
        border = self.border_explicit(node)
        if border:
            opts.update(borderwidth=border[0], bordercolor=border[1])
        if not opts:
            return None
        return self.style(var, cls, opts, mp)

    def common_kw(self, node: Node, *, font: bool = False, cursor: bool = True,
                  relief: bool = False) -> dict[str, Any]:
        kw: dict[str, Any] = {}
        if font and self.font_tuple(node):
            kw["font"] = self.font_tuple(node)
        if cursor and self.cursor(node):
            kw["cursor"] = self.cursor(node)
        if relief and node.style.get("relief"):
            kw["relief"] = node.style["relief"]
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

    def keep_image(self, var: str, img: str | None) -> None:
        if img:
            self.emit(f"{var}.image = {img}  # keep a reference")

    # ------------------------------------------------------------------------ windows
    def begin_window(self, node: Node, var: str, *, root: bool) -> Made:
        bg = node.style.get("background") or self.theme.background
        if root:
            self.emit(f"{var} = tk.Tk()")
            self.emit(f"configure_styles({var})")
        else:
            main = self.names[self.project.root_id]
            self.emit(f"parent = WINDOWS[{py(main)}]")
            self.emit(f"{var} = tk.Toplevel(parent)")
        self.window_options(node, var, root)
        self.emit(f"{var}.configure(background={py(bg)})")
        if not root and node.props.get("modal"):
            self.helper("grab_when_visible")
            self.emit(f"{var}.transient(parent)")
            self.emit(f"grab_when_visible({var})")
        elif not root:
            self.emit(f"{var}.transient(parent)")
        return Made(var=var, bg=bg, target=lambda page: var, state="")

    def w_unsupported(self, node: Node, var: str, parent: str, pbg: str, text: str) -> Made:
        self.assign(var, "ttk.Label", [parent], {
            "text": f"[{text}]", "anchor": "center", "relief": "solid", "borderwidth": 1,
            "wraplength": max(40, px(node.box.w) - 8)})
        return Made(var=var, bg=pbg, placeholder=True, state="")

    # --------------------------------------------------------------------- containers
    def w_frame(self, node: Node, var: str, parent: str, pbg: str) -> Made:
        kw: dict[str, Any] = {"width": px(node.box.w), "height": px(node.box.h)}
        bg = node.style.get("background") or self.surface
        sty = None
        border = self.border_explicit(node)
        if node.style.get("background") or border:
            opts: dict[str, Any] = {"background": bg}
            if border:
                opts["bordercolor"] = border[1]
            sty = self.style(var, "TFrame", opts)
        if sty:
            kw["style"] = sty
        if border or node.style.get("relief"):
            kw["relief"] = node.style.get("relief") or "solid"
            kw["borderwidth"] = border[0] if border else 1
        kw.update(self.common_kw(node))
        self.assign(var, "ttk.Frame", [parent], kw)
        return Made(var=var, bg=bg, target=lambda page: var, state="")

    def w_label_frame(self, node: Node, var: str, parent: str, pbg: str) -> Made:
        p = node.props
        bg = node.style.get("background") or self.surface
        anchor = {"left": "nw", "center": "n", "right": "ne"}.get(p.get("title_align", "left"), "nw")
        kw: dict[str, Any] = {"text": p.get("title", ""), "labelanchor": anchor,
                              "width": px(node.box.w), "height": px(node.box.h)}
        opts: dict[str, Any] = {}
        if node.style.get("background"):
            opts["background"] = bg
        border = self.border_explicit(node)
        if border:
            opts["bordercolor"] = border[1]
        label_opts = {k: v for k, v in {"background": opts.get("background"),
                                        "foreground": node.style.get("foreground"),
                                        "font": self.font_tuple(node)}.items() if v}
        if opts or label_opts:
            name = self.style(var, "TLabelframe", opts)
            if label_opts:
                self.styles[f"{name}.Label"] = StyleDef(f"{name}.Label", "TLabelframe.Label",
                                                        label_opts, {})
            kw["style"] = name
        kw.update(self.common_kw(node))
        self.assign(var, "ttk.LabelFrame", [parent], kw)
        return Made(var=var, bg=bg, target=lambda page: var, state="")

    def w_tabview(self, node: Node, var: str, parent: str, pbg: str) -> Made:
        p = node.props
        tabs = [str(t) for t in p.get("tabs", [])] or ["Tab 1"]
        bg = node.style.get("background") or self.surface
        kw: dict[str, Any] = {"width": px(node.box.w), "height": px(node.box.h)}
        kw.update(self.common_kw(node))
        self.assign(var, "ttk.Notebook", [parent], kw)
        pages: list[str] = []
        page_kw: dict[str, Any] = {}
        if node.style.get("background"):
            page_kw["style"] = self.style(var, "TFrame", {"background": bg})
        for i, title in enumerate(tabs):
            page = self.aux(var, f"tab{i + 1}")
            pages.append(page)
            self.assign(page, "ttk.Frame", [var], page_kw)
            self.emit(f"{var}.add({page}, text={py(title)})")
        current = int(num(p.get("current", 0)))
        if 0 < current < len(pages):
            self.emit(f"{var}.select({pages[current]})")
        h = self.use("tab_change")
        if h:
            self.emit(f"{var}.bind(\"<<NotebookTabChanged>>\", {h}, add=\"+\")")
        return Made(var=var, bg=bg, state="",
                    target=lambda page: pages[min(page, len(pages) - 1)])

    def w_scroll_frame(self, node: Node, var: str, parent: str, pbg: str) -> Made:
        p = node.props
        orient = p.get("orientation", "vertical")
        bg = node.style.get("background") or self.surface
        kw: dict[str, Any] = {"orient": orient}
        size = (node.box.w, node.box.h)
        if self.layout_of(node).mode == "absolute":
            kids = self.doc.children(node.id)
            bar = 16
            cw = int(num(p.get("content_width", 0))) or (
                px(node.box.w) - (bar if orient in ("vertical", "both") else 0))
            reach = max([k.box.y + k.box.h for k in kids] or [0]) + 8
            ch = int(num(p.get("content_height", 0))) or max(px(node.box.h), px(reach))
            if orient == "horizontal":
                reach_x = max([k.box.x + k.box.w for k in kids] or [0]) + 8
                cw = int(num(p.get("content_width", 0))) or max(px(node.box.w), px(reach_x))
                ch = int(num(p.get("content_height", 0))) or px(node.box.h) - bar
            kw["content_width"], kw["content_height"] = cw, ch
            size = (cw, ch)
        else:
            if p.get("content_width"):
                kw["content_width"] = int(p["content_width"])
            if p.get("content_height"):
                kw["content_height"] = int(p["content_height"])
        kw["background"] = bg
        if node.style.get("background"):
            kw["content_style"] = self.style(var, "TFrame", {"background": bg})
        kw.update(width=px(node.box.w), height=px(node.box.h))
        self.helper("ScrollFrame")
        self.assign(var, "ScrollFrame", [parent], kw)
        return Made(var=var, bg=bg, state="", target=lambda page: f"{var}.content",
                    child_size=size)

    def w_paned_window(self, node: Node, var: str, parent: str, pbg: str) -> Made:
        p = node.props
        orient = p.get("orientation", "horizontal")
        self.assign(var, "ttk.PanedWindow", [parent], {
            "orient": orient, "width": px(node.box.w), "height": px(node.box.h)})
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

    # --------------------------------------------------------------------- display
    def w_label(self, node: Node, var: str, parent: str, pbg: str) -> Made:
        p = node.props
        bg = node.style.get("background") or pbg
        kw: dict[str, Any] = {"text": p.get("text", ""), "anchor": p.get("anchor", "w"),
                              "justify": p.get("justify", "left")}
        if num(p.get("wrap_length")):
            kw["wraplength"] = int(p["wrap_length"])
        if bg != self.surface:
            kw["background"] = bg
        if node.style.get("foreground"):
            kw["foreground"] = node.style["foreground"]
        img = self.image_kw(node, var, kw)
        if img and p.get("text"):
            kw["compound"] = "left"
        kw.update(self.common_kw(node, font=True, relief=True))
        border = self.border_explicit(node)
        if border:
            kw.setdefault("relief", "solid")
            kw["borderwidth"] = border[0]
        self.assign(var, "ttk.Label", [parent], kw)
        self.keep_image(var, img)
        h = self.use("click")
        if h:
            self.emit(f"{var}.bind(\"<Button-1>\", {h}, add=\"+\")")
        return Made(var=var, bg=bg, state="")

    def w_image(self, node: Node, var: str, parent: str, pbg: str) -> Made:
        p = node.props
        src = p.get("source")
        kw: dict[str, Any] = {"anchor": "center"}
        bg = node.style.get("background") or pbg
        if bg != self.surface:
            kw["background"] = bg
        img = None
        if src:
            self.want_image()
            img = self.aux(var, "image")
            fit = p.get("fit", "contain")
            size = f", size=({px(node.box.w)}, {px(node.box.h)}), fit={py(fit)}" if fit != "none" else ""
            self.emit(f"{img} = load_image({py(src)}{size})")
            kw["image"] = Raw(img)
        if not src:
            kw.update(text=p.get("alt_text", "Image"), relief="solid", borderwidth=1)
        kw.update(self.common_kw(node))
        self.assign(var, "ttk.Label", [parent], kw)
        if img:
            self.emit(f"if {img} is None:  # the file is missing: show the placeholder text")
            self.emit(f"    {var}.configure(text={py(p.get('alt_text', 'Image'))})")
        self.keep_image(var, img)
        h = self.use("click")
        if h:
            self.emit(f"{var}.bind(\"<Button-1>\", {h}, add=\"+\")")
        return Made(var=var, bg=bg, state="")

    def w_separator(self, node: Node, var: str, parent: str, pbg: str) -> Made:
        self.assign(var, "ttk.Separator", [parent], {"orient": node.props.get("orientation", "horizontal")})
        return Made(var=var, bg=pbg, state="")

    def w_progressbar(self, node: Node, var: str, parent: str, pbg: str) -> Made:
        p = node.props
        orient = p.get("orientation", "horizontal")
        indeterminate = p.get("mode") == "indeterminate"
        maximum = num(p.get("maximum", 100)) or 100
        text = bool(p.get("show_text")) and not indeterminate
        host = parent
        outer = ""
        if text:  # the percentage label sits beside the bar, inside a box of the designed size
            outer = self.aux(var, "box")
            self.assign(outer, "ttk.Frame", [parent],
                        {"width": px(node.box.w), "height": px(node.box.h)})
            self.emit(f"{outer}.pack_propagate(False)")
            host = outer
        kw: dict[str, Any] = {"orient": orient, "mode": p.get("mode", "determinate"),
                              "maximum": maximum}
        vv = None
        if text:
            vv = self.aux(var, "var")
            self.emit(f"{vv} = tk.DoubleVar(value={py(p.get('value', 0))})")
            self.scope_vars.append((var, vv))
            kw["variable"] = Raw(vv)
        elif not indeterminate:
            kw["value"] = p.get("value", 0)
        if self.in_flow and not text:
            kw["length"] = px(node.box.w if orient == "horizontal" else node.box.h)
        self.assign(var, "ttk.Progressbar", [host], kw)
        if indeterminate:
            self.emit(f"{var}.start()")
        if text:
            label = self.aux(var, "text")
            self.assign(label, "ttk.Label", [host], {"width": 5, "anchor": "e"})
            side = "right" if orient == "horizontal" else "bottom"
            self.emit(f"{label}.pack(side=\"{side}\")")
            self.emit(f"{var}.pack(side=\"{'left' if side == 'right' else 'top'}\", "
                      "fill=\"both\", expand=True)")
            self.emit(f"{vv}.trace_add(\"write\", lambda *_: {label}.configure("
                      f"text=f\"{{{vv}.get() / {py(maximum)}:.0%}}\"))")
            self.emit(f"{vv}.set({vv}.get())  # show the initial percentage")
        return Made(var=var, outer=outer, bg=pbg, state="")

    # ----------------------------------------------------------------------- inputs
    def w_button(self, node: Node, var: str, parent: str, pbg: str) -> Made:
        p = node.props
        r = self.res(node)
        kw: dict[str, Any] = {"text": p.get("text", "")}
        img = self.image_kw(node, var, kw)
        if img:
            kw["compound"] = p.get("compound", "left")
        h = self.use("click")
        if h:
            kw["command"] = Raw(h)
        if p.get("default"):
            kw["default"] = "active"
        extra: dict[str, Any] = {}
        mapping: dict[str, list[tuple[str, Any]]] = {}
        if node.style.get("background"):
            extra.update(background=r["background"], bordercolor=r["background"])
            mapping["background"] = [("active", node.style.get("hover_color") or r["background"])]
        elif node.style.get("hover_color"):
            mapping["background"] = [("active", node.style["hover_color"])]
        sty = self.widget_style(node, var, "TButton", pbg, fill=False, extra=extra, mapping=mapping)
        if sty:
            kw["style"] = sty
        kw.update(self.common_kw(node))
        self.assign(var, "ttk.Button", [parent], kw)
        self.keep_image(var, img)
        return Made(var=var, bg=pbg)

    def w_tool_button(self, node: Node, var: str, parent: str, pbg: str) -> Made:
        p = node.props
        kw: dict[str, Any] = {"text": p.get("text", "")}
        img = self.image_kw(node, var, kw)
        if img:
            kw["compound"] = "left"
        h = self.use("click")
        sty = self.widget_style(node, var, "Toolbutton", pbg, fill=False) or "Toolbutton"
        kw["style"] = sty
        if p.get("checkable"):
            vv = self.aux(var, "var")
            self.emit(f"{vv} = tk.BooleanVar(value=False)")
            self.scope_vars.append((var, vv))
            kw["variable"] = Raw(vv)
            if h:
                kw["command"] = Raw(h)
            kw.update(self.common_kw(node))
            self.assign(var, "ttk.Checkbutton", [parent], kw)
        else:
            if h:
                kw["command"] = Raw(h)
            kw.update(self.common_kw(node))
            self.assign(var, "ttk.Button", [parent], kw)
        self.keep_image(var, img)
        return Made(var=var, bg=pbg)

    def w_entry(self, node: Node, var: str, parent: str, pbg: str) -> Made:
        p = node.props
        t = self.theme
        vv = self.aux(var, "var")
        self.emit(f"{vv} = tk.StringVar(value={py(p.get('text', ''))})")
        self.scope_vars.append((var, vv))
        kw: dict[str, Any] = {"textvariable": Raw(vv)}
        if p.get("justify", "left") != "left":
            kw["justify"] = p["justify"]
        if p.get("show"):
            kw["show"] = p["show"]
        if p.get("readonly"):
            kw["state"] = "readonly"
        if self.in_flow:
            kw["width"] = chars(node.box.w)
        field_bg = node.style.get("background") or t.surface
        opts: dict[str, Any] = {}
        if node.style.get("background"):
            opts["fieldbackground"] = field_bg
        border = self.border_explicit(node)
        if border:
            opts.update(bordercolor=border[1], borderwidth=border[0])
        if opts:
            kw["style"] = self.style(var, "TEntry", opts)
        if node.style.get("foreground"):
            kw["foreground"] = node.style["foreground"]
        kw.update(self.common_kw(node, font=True))
        self.assign(var, "ttk.Entry", [parent], kw)
        if int(num(p.get("max_length", 0))) > 0:
            limit = int(p["max_length"])
            self.emit(f"{var}.configure(validate=\"key\", "
                      f"validatecommand=({var}.register(lambda value: len(value) <= {limit}), \"%P\"))")
        if p.get("placeholder"):
            self.helper("add_placeholder")
            color = self.theme.muted_text
            self.emit(f"add_placeholder({var}, {vv}, {py(p['placeholder'])}, "
                      f"color={py(color)}, background={py(field_bg)})")
        h = self.use("change")
        if h:
            self.emit(f"{vv}.trace_add(\"write\", lambda *_: {h}())")
        return Made(var=var, bg=pbg)

    def w_text(self, node: Node, var: str, parent: str, pbg: str) -> Made:
        p = node.props

        def build(host: str) -> None:
            kw = {**self.text_kw(node, pbg), "wrap": p.get("wrap", "word"), "undo": True,
                  "padx": 4, "pady": 4}
            if self.in_flow:
                kw.update(width=chars(node.box.w), height=text_lines(node.box.h))
            self.assign(var, "tk.Text", [host], kw)
            if p.get("text"):
                self.emit(f"{var}.insert(\"1.0\", {py(p['text'])})")
            if p.get("readonly"):
                self.emit(f"{var}.configure(state=\"disabled\")")
            if p.get("placeholder"):
                self.helper("add_text_placeholder")
                self.emit(f"add_text_placeholder({var}, {py(p['placeholder'])}, "
                          f"color={py(self.theme.muted_text)}, "
                          f"background={py(self.classic_colors(node, pbg)['background'])})")

        made = self.scrolled(node, var, parent, build, scrollbar=bool(p.get("scrollbar", True)))
        h = self.use("change")
        if h:
            self.helper("bind_text_change")
            self.emit(f"bind_text_change({var}, {h})")
        if h or p.get("placeholder"):
            self.emit(f"{var}.edit_modified(False)")
        return made

    def _toggle_widget(self, node: Node, var: str, parent: str, pbg: str, cls: str,
                       kw: dict[str, Any]) -> Made:
        h = self.use("toggle", "click")
        if h:
            kw["command"] = Raw(h)
        sty = self.widget_style(node, var, cls, pbg)
        if sty:
            kw["style"] = sty
        kw.update(self.common_kw(node))
        self.assign(var, f"ttk.{cls[1:]}", [parent], kw)
        return Made(var=var, bg=pbg)

    def w_checkbox(self, node: Node, var: str, parent: str, pbg: str) -> Made:
        vv = self.aux(var, "var")
        self.emit(f"{vv} = tk.BooleanVar(value={bool(node.props.get('checked'))})")
        self.scope_vars.append((var, vv))
        return self._toggle_widget(node, var, parent, pbg, "TCheckbutton",
                                   {"text": node.props.get("text", ""), "variable": Raw(vv)})

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
        return self._toggle_widget(node, var, parent, pbg, "TRadiobutton",
                                   {"text": p.get("text", ""), "value": value,
                                    "variable": Raw(gv)})

    def w_switch(self, node: Node, var: str, parent: str, pbg: str) -> Made:
        p = node.props
        t = self.theme
        self.helper("Switch")
        bg = node.style.get("background") or pbg
        kw: dict[str, Any] = {
            "text": p.get("text", ""), "value": bool(p.get("checked")), "command": None,
            "background": bg, "foreground": node.style.get("foreground") or t.text,
            "on": t.primary, "off": t.border, "font": self.font_tuple(node) or Raw("FONT"),
        }
        h = self.use("toggle", "click")
        if h:
            kw["command"] = Raw(h)
        self.assign(var, "Switch", [parent], kw)
        self.scope_vars.append((var, f"{var}.variable"))
        return Made(var=var, bg=bg, state="config")

    def w_slider(self, node: Node, var: str, parent: str, pbg: str) -> Made:
        p = node.props
        t = self.theme
        vv = self.aux(var, "var")
        self.emit(f"{vv} = tk.DoubleVar(value={py(p.get('value', 0))})")
        self.scope_vars.append((var, vv))
        bg = node.style.get("background") or pbg
        kw: dict[str, Any] = {
            "from_": p.get("minimum", 0), "to": p.get("maximum", 100),
            "orient": p.get("orientation", "horizontal"), "variable": Raw(vv),
            "resolution": p.get("step", 1) or 1, "showvalue": bool(p.get("show_value")),
            "background": bg, "foreground": node.style.get("foreground") or t.text,
            "troughcolor": t.border, "activebackground": t.primary_hover,
            "highlightthickness": 0, "borderwidth": 0, "sliderrelief": "flat",
            "font": self.font_tuple(node) or Raw("FONT"),
        }
        kw.update(self.common_kw(node))
        self.assign(var, "tk.Scale", [parent], kw)
        h = self.use("change")
        if h:
            self.emit(f"{vv}.trace_add(\"write\", lambda *_: {h}())")
        return Made(var=var, bg=bg, state="config")

    def w_spinbox(self, node: Node, var: str, parent: str, pbg: str) -> Made:
        p = node.props
        dec = int(num(p.get("decimals", 0)))
        vv = self.aux(var, "var")
        value = num(p.get("value", 0))
        self.emit(f"{vv} = tk.StringVar(value={py(f'{value:.{dec}f}')})")
        self.scope_vars.append((var, vv))
        kw: dict[str, Any] = {
            "from_": p.get("minimum", 0), "to": p.get("maximum", 100),
            "increment": p.get("step", 1), "wrap": bool(p.get("wrap")), "textvariable": Raw(vv),
            "format": f"%.{dec}f",
        }
        if self.in_flow:
            kw["width"] = chars(node.box.w)
        kw.update(self.common_kw(node, font=True))
        self.assign(var, "ttk.Spinbox", [parent], kw)
        h = self.use("change")
        if h:
            self.emit(f"{vv}.trace_add(\"write\", lambda *_: {h}())")
        return Made(var=var, bg=pbg)

    def w_combobox(self, node: Node, var: str, parent: str, pbg: str) -> Made:
        p = node.props
        items = [str(i) for i in p.get("items", [])]
        kw: dict[str, Any] = {"values": items,
                              "state": "normal" if p.get("editable") else "readonly"}
        h = self.use("change")
        vv = None
        if h:
            vv = self.aux(var, "var")
            self.emit(f"{vv} = tk.StringVar()")
            self.scope_vars.append((var, vv))
            kw["textvariable"] = Raw(vv)
        if self.in_flow:
            kw["width"] = chars(node.box.w)
        kw.update(self.common_kw(node, font=True))
        self.assign(var, "ttk.Combobox", [parent], kw)
        current = int(num(p.get("current", 0)))
        if 0 <= current < len(items):
            self.emit(f"{var}.current({current})")
        if h:
            self.emit(f"{vv}.trace_add(\"write\", lambda *_: {h}())")
        return Made(var=var, bg=pbg)

    def w_segmented_button(self, node: Node, var: str, parent: str, pbg: str) -> Made:
        p = node.props
        items = [str(i) for i in p.get("items", [])]
        current = int(num(p.get("current", 0)))
        vv = self.aux(var, "var")
        self.assign(var, "ttk.Frame", [parent], {"width": px(node.box.w), "height": px(node.box.h)})
        self.emit(f"{vv} = tk.StringVar(value={py(items[current] if 0 <= current < len(items) else '')})")
        self.scope_vars.append((var, vv))
        style = self.widget_style(node, var, "Toolbutton", pbg, fill=False) or "Toolbutton"
        self.emit_sequence("item", items, [
            f"segment = ttk.Radiobutton({var}, text=item, value=item, variable={vv}, "
            f"style={py(style)})",
            "segment.pack(side=\"left\", fill=\"both\", expand=True)"])
        h = self.use("change")
        if h:
            self.emit(f"{vv}.trace_add(\"write\", lambda *_: {h}())")
        return Made(var=var, bg=pbg, state="")


class TkAdapter(Adapter):
    framework = "tkinter"
    label = "Tkinter (ttk)"

    def image_requirements(self) -> list[str]:
        return ["pillow>=10"]

    def generate(self, project: Project, options: GenOptions) -> list[GeneratedFile]:
        gen = TkGen(project, options)
        gen.base_reqs = tuple(self.requirements(project))
        return gen.build()


ADAPTER = register_adapter(TkAdapter())
