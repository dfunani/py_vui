"""Facts about what each code generator does, derived from the adapters' source.

Each entry names the adapter module (and a phrase from it) it was verified against;
``src/tests/test_panels_dialogs.py`` re-checks those phrases so this table cannot drift
silently when an adapter changes.
"""

from __future__ import annotations

from dataclasses import dataclass

from py_vui.core.document import ProjectDocument
from py_vui.core.registry import get_spec


@dataclass(frozen=True)
class Fact:
    text: str
    #: adapter module (under py_vui/codegen) and a literal phrase that proves the fact
    module: str
    phrase: str


_TK_FACTS = (
    Fact("Widgets with no Tk equivalent are generated as a bordered label placeholder.",
         "tk_common.py", "is not available for"),
    Fact("Flex containers use grid() with row/column weights; wrap, grow, gap and justify "
         "are supported.", "tk_common.py", "_plan_flex"),
    Fact("Window menus are built with tk.Menu.", "tk_common.py", "tk.Menu("),
)
_FACTS: dict[str, tuple[Fact, ...]] = {
    "tkinter": _TK_FACTS,
    "customtkinter": (
        Fact("Widgets with no CustomTkinter equivalent are generated as a placeholder label.",
             "ctk_adapter.py", "def w_unsupported"),
        _TK_FACTS[1],
        Fact("Window menus are built with tk.Menu (shared with the Tk generator).",
             "ctk_adapter.py", "menu"),
    ),
    "pyside6": (
        Fact("Widgets that Qt cannot render are generated as a QLabel placeholder.",
             "qt_adapter.py", '_PLACEHOLDER = "QLabel"'),
        Fact("Flex containers use QHBoxLayout / QVBoxLayout; wrap uses a custom flow layout "
             "for both directions.", "qt_adapter.py", "_FlowLayout("),
    ),
    "kivy": (
        Fact("Kivy has no menu bar: window menus are rendered as an ActionBar above the "
             "content.", "kivy_adapter.py", "Kivy has no menu bar"),
        Fact("Fonts: .ttf / .otf files are used as given; system font names are mapped to "
             "Kivy's bundled fonts (Roboto, Roboto Mono, DejaVu Sans).", "kivy_adapter.py",
             "system font names are mapped to"),
        Fact("Kivy has no per-axis resizable flag: a window locked in one direction is "
             "snapped back to its size on resize, which can flicker.", "kivy_adapter.py",
             "no per-axis resizable flag"),
        Fact("Dialog windows are Popups and always block the window beneath them.",
             "kivy_adapter.py", "Dialog windows are `Popup`s"),
        Fact("Grid containers are positioned by a helper (spans, sticky and weights match the "
             "editor); flex containers that wrap or use grow are re-laid out on resize.",
             "kivy_adapter.py", "are re-laid out"),
        Fact("Widgets with no Kivy equivalent are generated as a red placeholder label.",
             "kivy_adapter.py", "generated as a red placeholder"),
    ),
}
_FACTS["pyqt6"] = _FACTS["pyside6"]


def facts_for(framework: str) -> tuple[Fact, ...]:
    return _FACTS.get(framework, ())


def project_caveats(doc: ProjectDocument, framework: str) -> list[str]:
    """Caveats that actually apply to *this* project when generated for ``framework``."""
    nodes = list(doc.project.nodes.values())
    out: list[str] = []
    for n in nodes:
        spec = get_spec(n.type)
        if not spec.supports(framework):
            out.append(f"Unsupported widget: {n.name} ({spec.label}) becomes a placeholder.")
    if framework == "kivy":
        if any(n.type == "window" and n.props.get("menus") for n in nodes):
            out.append("Window menus are rendered as an ActionBar (Kivy has no menu bar).")
        if any(n.type in ("window", "toplevel")
               and bool(n.props.get("resizable_x", True)) != bool(n.props.get("resizable_y", True))
               for n in nodes):
            out.append("A window locked on one axis only is snapped back on resize and can "
                       "flicker (Kivy has one resizable flag).")
        if any(n.type == "toplevel" for n in nodes):
            out.append("Dialog windows become blocking Popups.")
    return out
