"""All editor QActions in one table (text, shortcut, glyph, slot name)."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QWidget

from py_vui.app.editor.icons import glyph_icon


@dataclass(frozen=True)
class A:
    key: str
    text: str
    keys: tuple[str, ...] = ()
    glyph: str = ""
    tip: str = ""
    checkable: bool = False
    checked: bool = False
    #: needs a selection / specific selection size to be enabled (handled by MainWindow)
    needs: str = ""


ACTIONS: tuple[A, ...] = (
    # ---- file
    A("new", "&New Project…", ("Ctrl+N",), "🗋", "Create a new project"),
    A("new_template", "New from &Template…", ("Ctrl+Shift+N",), "🗐", "Start from a template"),
    A("open", "&Open…", ("Ctrl+O",), "📂", "Open a project folder or .json file"),
    A("save", "&Save", ("Ctrl+S",), "💾", "Save the project"),
    A("save_as", "Save &As…", ("Ctrl+Shift+S",), "", "Save to a new location"),
    A("import_json", "&Import Project JSON…", (), "", "Import a project .json file"),
    A("export", "&Export…", ("Ctrl+E",), "⇪", "Export code (project folder, single file or zip)"),
    A("preferences", "&Preferences…", ("Ctrl+,",), "⚙", "Editor preferences"),
    A("quit", "&Quit", ("Ctrl+Q",), "", "Quit"),
    # ---- edit
    A("undo", "&Undo", ("Ctrl+Z",), "↶", "Undo"),
    A("redo", "&Redo", ("Ctrl+Shift+Z", "Ctrl+Y"), "↷", "Redo"),
    A("cut", "Cu&t", ("Ctrl+X",), "✂", "Cut", needs="sel"),
    A("copy", "&Copy", ("Ctrl+C",), "⧉", "Copy", needs="sel"),
    A("paste", "&Paste", ("Ctrl+V",), "📋", "Paste"),
    A("duplicate", "&Duplicate", ("Ctrl+D",), "❏", "Duplicate selection", needs="sel"),
    A("delete", "De&lete", ("Del", "Backspace"), "🗑", "Delete selection", needs="sel"),
    A("select_all", "Select &All", ("Ctrl+A",), "", "Select all widgets in the container"),
    A("rename", "Re&name", ("F2",), "", "Rename the selected widget", needs="one"),
    A("align_left", "Align &Left", (), "⇤", "Align left edges", needs="sel"),
    A("align_center", "Align Center (&H)", (), "⇹", "Align horizontal centres", needs="sel"),
    A("align_right", "Align &Right", (), "⇥", "Align right edges", needs="sel"),
    A("align_top", "Align &Top", (), "⤒", "Align top edges", needs="sel"),
    A("align_middle", "Align Middle (&V)", (), "⇕", "Align vertical centres", needs="sel"),
    A("align_bottom", "Align &Bottom", (), "⤓", "Align bottom edges", needs="sel"),
    A(
        "distribute_h",
        "Distribute Hori&zontally",
        (),
        "⇿",
        "Even horizontal spacing",
        needs="three",
    ),
    A("distribute_v", "Distribute &Vertically", (), "⇳", "Even vertical spacing", needs="three"),
    A("same_width", "Same &Width", (), "↔", "Match width of the first selected", needs="two"),
    A("same_height", "Same &Height", (), "↕", "Match height of the first selected", needs="two"),
    A("same_size", "Same &Size", (), "⤢", "Match size of the first selected", needs="two"),
    A("z_front", "Bring to &Front", ("Ctrl+Shift+]",), "⤒", "Bring to front", needs="sel"),
    A("z_forward", "Bring &Forward", ("Ctrl+]",), "↑", "Bring forward", needs="sel"),
    A("z_backward", "Send Back&ward", ("Ctrl+[",), "↓", "Send backward", needs="sel"),
    A("z_back", "Send to &Back", ("Ctrl+Shift+[",), "⤓", "Send to back", needs="sel"),
    A("group", "&Group in Frame", ("Ctrl+G",), "▣", "Wrap the selection in a frame", needs="sel"),
    A(
        "ungroup",
        "&Ungroup",
        ("Ctrl+Shift+G",),
        "▢",
        "Dissolve the selected container",
        needs="one",
    ),
    # ---- view
    A("zoom_in", "Zoom &In", ("Ctrl+=", "Ctrl++"), "＋", "Zoom in"),
    A("zoom_out", "Zoom &Out", ("Ctrl+-",), "－", "Zoom out"),
    A("zoom_fit", "&Fit Window", ("Ctrl+0",), "⛶", "Fit the window in view"),
    A("zoom_100", "&Actual Size", ("Ctrl+1",), "1:1", "100 %"),
    A("toggle_grid", "Show &Grid", ("Ctrl+'",), "▦", "Show the dot grid", True, True),
    A("toggle_snap", "&Snap to Grid", ("Ctrl+;",), "🧲", "Snap to the grid", True, True),
    A("toggle_guides", "Smart &Guides", ("Ctrl+Shift+;",), "┼", "Alignment guides", True, True),
    A("toggle_rulers", "&Rulers", ("Ctrl+R",), "📏", "Show rulers", True, True),
    A("theme_dark", "&Dark", (), "", "Dark editor theme", True),
    A("theme_light", "&Light", (), "", "Light editor theme", True),
    A("theme_auto", "&Follow System", (), "", "Follow the OS appearance", True),
    # ---- build
    A("generate", "&Generate Code", ("Ctrl+B",), "⚙", "Generate the app into the project folder"),
    A("run", "&Run / Preview", ("F5",), "▶", "Generate and run the app"),
    A("stop", "S&top", ("Shift+F5",), "■", "Stop the running preview"),
    A("restart", "Re&start", ("Ctrl+F5",), "⟳", "Restart the preview"),
    A(
        "live_preview",
        "&Live Preview",
        ("Ctrl+L",),
        "⚡",
        "Restart the preview after every edit",
        True,
    ),
    A("build_exe", "Build E&xecutable (PyInstaller)…", (), "📦", "Build a standalone executable"),
    A("requirements", "Re&quirements…", (), "", "Edit requirements.txt entries"),
    A("sync_handlers", "&Sync Handlers from Disk", (), "⇅", "Import edits made to handlers.py"),
    # ---- project
    A("framework", "&Framework…", (), "🧩", "Change the target framework"),
    A("theme", "&Theme…", (), "🎨", "Edit the app theme"),
    A("assets", "&Assets…", (), "🖼", "Manage images and files"),
    A("menus", "&Menus…", (), "☰", "Design the window's menu bar"),
    A("plugins", "&Plugins…", (), "🔌", "Enable local widget plugins"),
    A("add_dialog", "Add &Dialog Window", (), "🗔", "Add a dialog window"),
    # ---- help
    A("shortcuts", "&Keyboard Shortcuts", ("Ctrl+/",), "⌨", "Show all shortcuts"),
    A("about", "&About py_vui", (), "", "About"),
)


def build_actions(window: QWidget) -> dict[str, QAction]:
    """Create every action, wire ``triggered`` to ``window.do_<key>`` when it exists."""
    out: dict[str, QAction] = {}
    for spec in ACTIONS:
        act = QAction(spec.text, window)
        if spec.glyph:
            act.setIcon(glyph_icon(spec.glyph))
        if spec.keys:
            act.setShortcuts([QKeySequence(k) for k in spec.keys])
        tip = spec.tip + (f"  ({spec.keys[0]})" if spec.keys else "")
        act.setToolTip(tip)
        act.setStatusTip(spec.tip)
        act.setCheckable(spec.checkable)
        if spec.checkable:
            act.setChecked(spec.checked)
        act.setProperty("needs", spec.needs)
        slot = getattr(window, f"do_{spec.key}", None)
        if slot is not None:
            if spec.checkable:
                act.toggled.connect(slot)
            else:
                act.triggered.connect(lambda _checked=False, s=slot: s())
        out[spec.key] = act
    return out


def refresh_icons(actions: dict[str, QAction]) -> None:
    """Re-tint glyph icons after a theme switch."""
    glyphs = {a.key: a.glyph for a in ACTIONS}
    for key, act in actions.items():
        if glyphs.get(key):
            act.setIcon(glyph_icon(glyphs[key]))
