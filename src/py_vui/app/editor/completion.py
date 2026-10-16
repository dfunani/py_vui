"""Member / attribute completion data for the code editor (pure Python, no Qt).

Contexts understood on the text before the caret:

* ``WIDGETS["name"].<prefix>``  -> methods of that widget for the project's framework
* ``WIDGETS["<prefix>``         -> widget variable names of the project
* ``os.<prefix>`` / ``os.path.<prefix>`` -> public names of a few safe stdlib modules
* ``event.<prefix>``            -> attributes handlers receive (per framework)
"""

from __future__ import annotations

import importlib
import re
from dataclasses import dataclass

from py_vui.core.document import ProjectDocument

_WIDGET = re.compile(r"""(?:\bui\.)?\bWIDGETS\[\s*(['"])([^'"\]]+)\1\s*\]\.(\w*)$""")
_KEY = re.compile(r"""\bWIDGETS\[\s*(['"])(\w*)$""")
_DOTTED = re.compile(r"(?<![\w.])([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\.(\w*)$")


@dataclass(frozen=True)
class MemberContext:
    kind: str  # "widget" | "key" | "name"
    key: str  # widget variable name / dotted expression / ""
    prefix: str


def member_context(text_before_caret: str) -> MemberContext | None:
    m = _WIDGET.search(text_before_caret)
    if m:
        return MemberContext("widget", m.group(2), m.group(3))
    m = _KEY.search(text_before_caret)
    if m:
        return MemberContext("key", "", m.group(2))
    m = _DOTTED.search(text_before_caret)
    if m:
        return MemberContext("name", m.group(1), m.group(2))
    return None


# ----------------------------------------------------------------------------- widget tables
_TK_COMMON = (
    "configure", "config", "cget", "bind", "unbind", "after", "after_cancel", "focus_set",
    "focus_get", "destroy", "update", "update_idletasks", "winfo_width", "winfo_height",
    "winfo_x", "winfo_y", "winfo_exists", "winfo_children", "winfo_toplevel", "lift", "lower",
    "grid_remove", "event_generate", "keys",
)
_TTK_STATE = ("state", "instate")
_TK: dict[str, tuple[str, ...]] = {
    "window": ("title", "geometry", "resizable", "minsize", "maxsize", "attributes", "protocol",
               "withdraw", "deiconify", "iconify", "mainloop", "quit", "state", "iconbitmap"),
    "toplevel": ("title", "geometry", "resizable", "minsize", "attributes", "protocol",
                 "withdraw", "deiconify", "grab_set", "transient", "wait_window"),
    "button": ("invoke", *_TTK_STATE),
    "tool_button": ("invoke", *_TTK_STATE),
    "entry": ("get", "insert", "delete", "icursor", "selection_range", "selection_clear",
              "xview", *_TTK_STATE),
    "text": ("get", "insert", "delete", "see", "index", "mark_set", "tag_add", "tag_configure",
             "tag_remove", "edit_undo", "edit_redo", "search", "yview"),
    "checkbox": ("invoke", *_TTK_STATE),
    "radio": ("invoke", *_TTK_STATE),
    "switch": ("invoke", *_TTK_STATE),
    "slider": ("get", "set"),
    "dial": ("get", "set"),
    "spinbox": ("get", "set", "insert", "delete", *_TTK_STATE),
    "combobox": ("get", "set", "current", "delete", "insert", *_TTK_STATE),
    "listbox": ("insert", "delete", "get", "curselection", "size", "selection_set",
                "selection_clear", "see", "activate", "index", "itemconfigure", "nearest"),
    "progressbar": ("start", "stop", "step"),
    "tabview": ("add", "select", "tab", "tabs", "index", "forget", "hide", "insert"),
    "table": ("insert", "delete", "get_children", "item", "selection", "selection_set",
              "heading", "column", "set", "see", "exists", "focus"),
    "tree_view": ("insert", "delete", "get_children", "item", "selection", "selection_set",
                  "heading", "column", "set", "see", "exists", "focus", "move", "parent"),
    "canvas": ("create_line", "create_rectangle", "create_oval", "create_text",
               "create_polygon", "create_image", "delete", "coords", "move", "itemconfigure",
               "find_all", "bbox", "tag_bind"),
    "paned_window": ("add", "insert", "forget", "sashpos"),
}
_CTK_COMMON = ("configure", "cget", "bind", "unbind", "after", "after_cancel", "focus_set",
               "destroy", "update", "winfo_width", "winfo_height", "winfo_x", "winfo_y",
               "lift", "lower", "grid_remove")
_CTK: dict[str, tuple[str, ...]] = {
    "window": _TK["window"] + ("set_appearance_mode",),
    "toplevel": _TK["toplevel"],
    "button": ("invoke", "configure"),
    "entry": ("get", "insert", "delete", "focus", "configure"),
    "text": ("get", "insert", "delete", "see", "tag_config", "tag_add", "yview", "configure"),
    "checkbox": ("get", "select", "deselect", "toggle", "configure"),
    "switch": ("get", "select", "deselect", "toggle", "configure"),
    "radio": ("select", "deselect", "invoke", "configure"),
    "slider": ("get", "set", "configure"),
    "combobox": ("get", "set", "configure"),
    "progressbar": ("get", "set", "start", "stop", "step", "configure"),
    "tabview": ("add", "delete", "get", "set", "tab", "insert", "rename"),
    "segmented_button": ("get", "set", "configure"),
}
_QT_COMMON = (
    "setEnabled", "isEnabled", "setVisible", "isVisible", "show", "hide", "setToolTip",
    "setStyleSheet", "resize", "move", "setFocus", "update", "repaint", "width", "height", "x",
    "y", "geometry", "setGeometry", "parent", "close", "setMinimumSize", "setMaximumSize",
    "setFixedSize", "setObjectName", "objectName", "font", "setFont", "setCursor", "raise_",
    "lower", "deleteLater", "installEventFilter", "window",
)
_QT: dict[str, tuple[str, ...]] = {
    "window": ("setWindowTitle", "windowTitle", "showMaximized", "showMinimized", "showNormal",
               "showFullScreen", "statusBar", "menuBar", "setCentralWidget", "setWindowIcon"),
    "toplevel": ("setWindowTitle", "windowTitle", "exec", "open", "accept", "reject",
                 "setModal"),
    "label": ("text", "setText", "setPixmap", "setAlignment", "clear", "setWordWrap"),
    "button": ("text", "setText", "click", "setChecked", "isChecked", "setIcon", "setCheckable",
               "clicked"),
    "tool_button": ("text", "setText", "click", "setChecked", "isChecked", "setIcon", "clicked"),
    "entry": ("text", "setText", "clear", "setPlaceholderText", "setMaxLength", "selectAll",
              "setReadOnly", "setEchoMode", "textChanged", "returnPressed"),
    "text": ("toPlainText", "setPlainText", "appendPlainText", "insertPlainText", "clear",
             "setReadOnly", "textChanged", "moveCursor"),
    "checkbox": ("isChecked", "setChecked", "toggle", "setText", "text", "toggled"),
    "radio": ("isChecked", "setChecked", "toggle", "setText", "text", "toggled"),
    "switch": ("isChecked", "setChecked", "toggle", "setText", "text", "toggled"),
    "slider": ("value", "setValue", "setRange", "setMinimum", "setMaximum", "valueChanged"),
    "dial": ("value", "setValue", "setRange", "valueChanged"),
    "spinbox": ("value", "setValue", "setRange", "setSingleStep", "valueChanged"),
    "combobox": ("currentText", "currentIndex", "setCurrentIndex", "setCurrentText", "addItem",
                 "addItems", "clear", "count", "itemText", "removeItem", "currentIndexChanged"),
    "listbox": ("addItem", "addItems", "clear", "count", "currentItem", "currentRow",
                "setCurrentRow", "takeItem", "item", "selectedItems", "itemClicked"),
    "progressbar": ("value", "setValue", "setRange", "setFormat", "reset"),
    "table": ("rowCount", "columnCount", "setRowCount", "setColumnCount", "item", "setItem",
              "currentRow", "clear", "insertRow", "removeRow", "cellChanged"),
    "tree_view": ("addTopLevelItem", "clear", "currentItem", "topLevelItemCount", "expandAll",
                  "collapseAll"),
    "tabview": ("currentIndex", "setCurrentIndex", "count", "tabText", "setTabText",
                "currentChanged"),
    "date_entry": ("date", "setDate", "dateChanged"),
    "time_entry": ("time", "setTime", "timeChanged"),
    "calendar": ("selectedDate", "setSelectedDate"),
}
_KIVY_COMMON = (
    "text", "disabled", "opacity", "size", "pos", "x", "y", "width", "height", "size_hint",
    "parent", "bind", "unbind", "children", "add_widget", "remove_widget", "clear_widgets",
    "canvas", "id", "dispatch", "walk",
)
_KIVY: dict[str, tuple[str, ...]] = {
    "label": ("text", "color", "font_size", "halign", "valign", "markup"),
    "button": ("text", "state", "background_color", "color"),
    "entry": ("text", "hint_text", "readonly", "multiline", "focus", "select_all", "cursor"),
    "text": ("text", "readonly", "focus", "select_all", "cursor", "insert_text"),
    "checkbox": ("active", "group"),
    "radio": ("active", "group"),
    "switch": ("active",),
    "slider": ("value", "min", "max", "step", "orientation"),
    "progressbar": ("value", "max"),
    "combobox": ("text", "values", "is_open"),
    "tabview": ("tab_list", "current_tab", "switch_to"),
}

_EVENT_ATTRS = {
    "tkinter": ("widget", "x", "y", "x_root", "y_root", "char", "keysym", "keycode", "delta",
                "num", "width", "height"),
    "customtkinter": ("widget", "x", "y", "x_root", "y_root", "char", "keysym", "keycode",
                      "delta", "num", "width", "height"),
    "kivy": ("widget", "value", "pos", "key", "index"),
}

_QT_ALIASES = {"pyside6": _QT, "pyqt6": _QT}

#: dotted helper namespaces that are useful in handlers (offered regardless of imports)
_STATIC_MODULES: dict[str, tuple[str, ...]] = {
    "messagebox": ("showinfo", "showwarning", "showerror", "askyesno", "askokcancel",
                   "askretrycancel", "askquestion"),
    "filedialog": ("askopenfilename", "asksaveasfilename", "askdirectory", "askopenfilenames"),
    "simpledialog": ("askstring", "askinteger", "askfloat"),
    "QMessageBox": ("information", "warning", "critical", "question", "about"),
    "QFileDialog": ("getOpenFileName", "getSaveFileName", "getExistingDirectory",
                    "getOpenFileNames"),
    "QApplication": ("instance", "quit", "exec", "clipboard", "processEvents"),
}

#: stdlib modules whose public names may be listed (importing them is side-effect free)
SAFE_MODULES = frozenset({
    "os", "sys", "json", "math", "random", "time", "re", "datetime", "pathlib", "subprocess",
    "webbrowser", "threading", "csv", "shutil", "string", "itertools", "collections",
    "textwrap", "tempfile", "platform", "statistics", "functools", "typing", "logging",
})


def widget_members(framework: str, node_type: str) -> list[str]:
    """Method / attribute names worth offering for a widget of ``node_type``."""
    if framework == "tkinter":
        names = (*_TK_COMMON, *_TK.get(node_type, ()))
    elif framework == "customtkinter":
        names = (*_CTK_COMMON, *_CTK.get(node_type, _TK.get(node_type, ())))
    elif framework in _QT_ALIASES:
        names = (*_QT_COMMON, *_QT.get(node_type, ()))
    elif framework == "kivy":
        names = (*_KIVY_COMMON, *_KIVY.get(node_type, ()))
    else:
        names = ()
    return sorted(set(names))


def module_members(dotted: str, framework: str) -> list[str]:
    """Names reachable as ``<dotted>.`` for whitelisted modules and handler ``event``."""
    if dotted == "event":
        return list(_EVENT_ATTRS.get(framework, ()))
    if dotted in _STATIC_MODULES:
        return list(_STATIC_MODULES[dotted])
    root, *rest = dotted.split(".")
    if root not in SAFE_MODULES:
        return []
    try:
        obj = importlib.import_module(root)
        for part in rest:
            obj = getattr(obj, part)
    except (ImportError, AttributeError):
        return []
    if not (hasattr(obj, "__name__") and hasattr(obj, "__dict__")):
        return []
    return sorted(n for n in dir(obj) if not n.startswith("_"))


def members_for(ctx: MemberContext, doc: ProjectDocument | None) -> list[str]:
    """Candidate names for a completion context (unfiltered by prefix)."""
    framework = doc.project.framework if doc else "tkinter"
    if ctx.kind == "key":
        return sorted(doc.variable_names().values()) if doc else []
    if ctx.kind == "widget":
        if doc is None:
            return []
        for nid, var in doc.variable_names().items():
            if var == ctx.key:
                return widget_members(framework, doc.get_node(nid).type)
        return []
    return module_members(ctx.key, framework)
