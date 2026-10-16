"""Built-in widget catalog (every widget is free; there are no paid tiers)."""

from __future__ import annotations

from py_vui.core.events import GENERIC_EVENTS
from py_vui.core.registry import FRAMEWORKS, PropSpec, WidgetSpec, has_spec, register

_P = PropSpec
_ALL = frozenset(FRAMEWORKS)
_TK = frozenset({"tkinter", "customtkinter"})
_QT = frozenset({"pyside6", "pyqt6"})
_NOT_KIVY = frozenset({"tkinter", "customtkinter", "pyside6", "pyqt6"})
_CTK_QT = frozenset({"customtkinter", "pyside6", "pyqt6", "kivy"})

ORIENT = ("horizontal", "vertical")

#: Universal visual properties stored in ``node.style`` (empty / None = inherit theme).
STYLE_PROPS: tuple[PropSpec, ...] = (
    _P("background", "color", "", "Background", "Style"),
    _P("foreground", "color", "", "Text color", "Style"),
    _P("font_family", "str", "", "Font family", "Style"),
    _P("font_size", "int", 0, "Font size", "Style", minimum=0, maximum=96, help="0 = theme"),
    _P("bold", "bool", False, "Bold", "Style"),
    _P("italic", "bool", False, "Italic", "Style"),
    _P("underline", "bool", False, "Underline", "Style"),
    _P("border_width", "int", -1, "Border width", "Style", minimum=-1, maximum=32, help="-1 = theme"),
    _P("border_color", "color", "", "Border color", "Style"),
    _P("corner_radius", "int", -1, "Corner radius", "Style", minimum=-1, maximum=64, help="-1 = theme"),
    _P("hover_color", "color", "", "Hover color", "Style"),
    _P("cursor", "choice", "", "Cursor", "Style",
       choices=("", "arrow", "hand", "ibeam", "cross", "wait", "forbidden", "size_all")),
    _P("relief", "choice", "", "Relief", "Style",
       choices=("", "flat", "raised", "sunken", "groove", "ridge", "solid")),
)
STYLE_KEYS = frozenset(p.name for p in STYLE_PROPS)

_CLICK = ("click",) + GENERIC_EVENTS


def _reg(**kw) -> WidgetSpec:
    return register(WidgetSpec(**kw))


def register_builtin_widgets() -> None:
    if has_spec("window"):
        return

    # ---------------------------------------------------------------- windows
    _reg(
        type="window", label="Main Window", category="Window", icon="🪟",
        default_size=(640, 480), container=True,
        props=(
            _P("title", "str", "Window", "Title"),
            _P("width", "int", 640, "Width", minimum=100, maximum=8192),
            _P("height", "int", 480, "Height", minimum=100, maximum=8192),
            _P("resizable_x", "bool", True, "Resizable width"),
            _P("resizable_y", "bool", True, "Resizable height"),
            _P("min_width", "int", 0, "Min width", minimum=0),
            _P("min_height", "int", 0, "Min height", minimum=0),
            _P("maximized", "bool", False, "Start maximized"),
            _P("always_on_top", "bool", False, "Always on top"),
            _P("icon", "image", "", "Window icon"),
            _P("menus", "json", [], "Menu bar", "Menus"),
        ),
        events=("close", "resize", "key_press", "key_release", "focus_in", "focus_out",
                "show", "hide", "mouse_move", "mouse_press", "mouse_release", "mouse_wheel"),
    )
    _reg(
        type="toplevel", label="Dialog Window", category="Window", icon="🗔",
        default_size=(420, 300), container=True,
        props=(
            _P("title", "str", "Dialog", "Title"),
            _P("width", "int", 420, "Width", minimum=100, maximum=8192),
            _P("height", "int", 300, "Height", minimum=100, maximum=8192),
            _P("modal", "bool", False, "Modal"),
            _P("resizable_x", "bool", True, "Resizable width"),
            _P("resizable_y", "bool", True, "Resizable height"),
            _P("always_on_top", "bool", False, "Always on top"),
            _P("start_hidden", "bool", False, "Start hidden"),
            _P("icon", "image", "", "Window icon"),
        ),
        events=("close", "resize", "key_press", "key_release", "focus_in", "focus_out",
                "show", "hide"),
        description="Secondary window. Generated as a function that opens it on demand.",
    )

    # ------------------------------------------------------------- containers
    _reg(
        type="frame", label="Frame", category="Layout", icon="▭", default_size=(240, 160),
        container=True, props=(), events=("click",) + GENERIC_EVENTS,
    )
    _reg(
        type="label_frame", label="Group Box", category="Layout", icon="▣",
        default_size=(260, 180), container=True,
        props=(_P("title", "str", "Group", "Title"),
               _P("title_align", "choice", "left", "Title alignment",
                  choices=("left", "center", "right"))),
        events=GENERIC_EVENTS,
    )
    _reg(
        type="tabview", label="Tabs", category="Layout", icon="🗂", default_size=(320, 220),
        container=True, paged=True,
        props=(_P("tabs", "list", ["Tab 1", "Tab 2"], "Tab titles"),
               _P("current", "int", 0, "Current tab", minimum=0)),
        events=("tab_change",) + GENERIC_EVENTS,
    )
    _reg(
        type="scroll_frame", label="Scroll Area", category="Layout", icon="↕",
        default_size=(260, 180), container=True,
        props=(_P("orientation", "choice", "vertical", "Scroll direction",
                  choices=("vertical", "horizontal", "both")),
               _P("content_width", "int", 0, "Content width", minimum=0),
               _P("content_height", "int", 0, "Content height", minimum=0)),
        events=("mouse_wheel",),
    )
    _reg(
        type="paned_window", label="Splitter", category="Layout", icon="◫",
        default_size=(320, 200), container=True,
        props=(_P("orientation", "choice", "horizontal", "Orientation", choices=ORIENT),
               _P("sizes", "list", [], "Pane sizes (px)")),
        events=(),
        description="Children become resizable panes, in z-order.",
    )

    # --------------------------------------------------------------- display
    _reg(
        type="label", label="Label", category="Display", icon="T", default_size=(120, 28),
        props=(_P("text", "str", "Label", "Text"),
               _P("anchor", "choice", "w", "Text anchor", choices=("w", "center", "e")),
               _P("justify", "choice", "left", "Justify", choices=("left", "center", "right")),
               _P("wrap_length", "int", 0, "Wrap length (px)", minimum=0),
               _P("image", "image", "", "Image")),
        events=("click",) + GENERIC_EVENTS,
    )
    _reg(
        type="image", label="Image", category="Display", icon="🖼", default_size=(160, 120),
        props=(_P("source", "image", "", "Image file"),
               _P("fit", "choice", "contain", "Fit", choices=("contain", "stretch", "none")),
               _P("alt_text", "str", "Image", "Placeholder text")),
        events=("click",) + GENERIC_EVENTS,
    )
    _reg(
        type="separator", label="Separator", category="Display", icon="―", default_size=(200, 4),
        min_size=(1, 1),
        props=(_P("orientation", "choice", "horizontal", "Orientation", choices=ORIENT),),
        events=(),
    )
    _reg(
        type="progressbar", label="Progress Bar", category="Display", icon="▰",
        default_size=(200, 20),
        props=(_P("value", "float", 30, "Value", minimum=0),
               _P("maximum", "float", 100, "Maximum", minimum=1),
               _P("mode", "choice", "determinate", "Mode",
                  choices=("determinate", "indeterminate")),
               _P("orientation", "choice", "horizontal", "Orientation", choices=ORIENT),
               _P("show_text", "bool", False, "Show percentage")),
        events=(),
    )
    _reg(
        type="canvas", label="Canvas", category="Display", icon="✎", default_size=(240, 160),
        props=(_P("scrollable", "bool", False, "Scrollable"),),
        events=("paint",) + _CLICK[1:],
        description="Free-drawing surface. Draw in the `paint` handler.",
    )

    # ----------------------------------------------------------------- input
    _reg(
        type="button", label="Button", category="Input", icon="⬜", default_size=(110, 34),
        props=(_P("text", "str", "Button", "Text"),
               _P("image", "image", "", "Image"),
               _P("compound", "choice", "left", "Image position",
                  choices=("left", "right", "top", "bottom", "center")),
               _P("default", "bool", False, "Default button")),
        events=_CLICK,
    )
    _reg(
        type="tool_button", label="Tool Button", category="Input", icon="🔧",
        default_size=(90, 30), frameworks=_NOT_KIVY | frozenset({"kivy"}),
        props=(_P("text", "str", "Tool", "Text"), _P("image", "image", "", "Image"),
               _P("checkable", "bool", False, "Checkable")),
        events=_CLICK,
    )
    _reg(
        type="entry", label="Text Input", category="Input", icon="⌶", default_size=(180, 32),
        props=(_P("text", "str", "", "Text"),
               _P("placeholder", "str", "", "Placeholder"),
               _P("show", "str", "", "Mask character", help="e.g. * for passwords"),
               _P("readonly", "bool", False, "Read only"),
               _P("justify", "choice", "left", "Justify", choices=("left", "center", "right")),
               _P("max_length", "int", 0, "Max length", minimum=0)),
        events=("change", "submit") + GENERIC_EVENTS,
    )
    _reg(
        type="text", label="Text Area", category="Input", icon="¶", default_size=(240, 120),
        props=(_P("text", "text", "", "Text"),
               _P("placeholder", "str", "", "Placeholder"),
               _P("readonly", "bool", False, "Read only"),
               _P("wrap", "choice", "word", "Wrap", choices=("none", "char", "word")),
               _P("scrollbar", "bool", True, "Show scrollbar")),
        events=("change",) + GENERIC_EVENTS,
    )
    _reg(
        type="checkbox", label="Checkbox", category="Input", icon="☑", default_size=(140, 28),
        props=(_P("text", "str", "Checkbox", "Text"), _P("checked", "bool", False, "Checked")),
        events=("toggle", "click") + GENERIC_EVENTS,
    )
    _reg(
        type="radio", label="Radio Button", category="Input", icon="◉", default_size=(140, 28),
        props=(_P("text", "str", "Option", "Text"),
               _P("checked", "bool", False, "Selected"),
               _P("group", "str", "group1", "Group", help="Radios sharing a group are exclusive"),
               _P("value", "str", "", "Value", help="defaults to the text")),
        events=("toggle", "click") + GENERIC_EVENTS,
    )
    _reg(
        type="switch", label="Switch", category="Input", icon="◐", default_size=(120, 28),
        props=(_P("text", "str", "Switch", "Text"), _P("checked", "bool", False, "On")),
        events=("toggle", "click") + GENERIC_EVENTS,
    )
    _reg(
        type="slider", label="Slider", category="Input", icon="⎯", default_size=(200, 28),
        props=(_P("minimum", "float", 0, "Minimum"),
               _P("maximum", "float", 100, "Maximum"),
               _P("value", "float", 50, "Value"),
               _P("step", "float", 1, "Step", minimum=0),
               _P("orientation", "choice", "horizontal", "Orientation", choices=ORIENT),
               _P("show_value", "bool", False, "Show value")),
        events=("change",) + GENERIC_EVENTS,
    )
    _reg(
        type="dial", label="Dial", category="Input", icon="◔", default_size=(80, 80),
        frameworks=_QT | frozenset({"customtkinter", "tkinter", "kivy"}),
        props=(_P("minimum", "int", 0, "Minimum"), _P("maximum", "int", 100, "Maximum"),
               _P("value", "int", 0, "Value")),
        events=("change",),
        description="Rotary control (native on Qt; canvas-drawn on Tk and Kivy).",
    )
    _reg(
        type="spinbox", label="Spin Box", category="Input", icon="⇅", default_size=(100, 32),
        props=(_P("minimum", "float", 0, "Minimum"), _P("maximum", "float", 100, "Maximum"),
               _P("value", "float", 0, "Value"), _P("step", "float", 1, "Step", minimum=0),
               _P("decimals", "int", 0, "Decimals", minimum=0, maximum=6),
               _P("wrap", "bool", False, "Wrap around")),
        events=("change",) + GENERIC_EVENTS,
    )
    _reg(
        type="combobox", label="Dropdown", category="Input", icon="▾", default_size=(160, 32),
        props=(_P("items", "list", ["Option 1", "Option 2"], "Items"),
               _P("current", "int", 0, "Current index", minimum=-1),
               _P("editable", "bool", False, "Editable")),
        events=("change",) + GENERIC_EVENTS,
    )
    _reg(
        type="listbox", label="List Box", category="Input", icon="☰", default_size=(160, 120),
        props=(_P("items", "list", ["Item 1", "Item 2", "Item 3"], "Items"),
               _P("selection_mode", "choice", "single", "Selection",
                  choices=("single", "multiple", "extended"))),
        events=("select",) + GENERIC_EVENTS,
    )
    _reg(
        type="segmented_button", label="Segmented Button", category="Input", icon="▤",
        default_size=(240, 32),
        props=(_P("items", "list", ["One", "Two", "Three"], "Segments"),
               _P("current", "int", 0, "Current", minimum=-1)),
        events=("change",),
    )
    _reg(
        type="date_entry", label="Date Input", category="Input", icon="📅", default_size=(140, 32),
        props=(_P("date", "str", "2025-01-01", "Date (YYYY-MM-DD)"),
               _P("pattern", "str", "yyyy-mm-dd", "Display pattern")),
        events=("change",),
        requires={"tkinter": ("tkcalendar>=1.6",), "customtkinter": ("tkcalendar>=1.6",)},
    )
    _reg(
        type="time_entry", label="Time Input", category="Input", icon="⏰", default_size=(120, 32),
        props=(_P("time", "str", "12:00:00", "Time (HH:MM:SS)"),
               _P("show_seconds", "bool", True, "Show seconds")),
        events=("change",),
    )

    # ------------------------------------------------------------------ data
    _reg(
        type="table", label="Table", category="Data", icon="▦", default_size=(320, 160),
        props=(_P("columns", "list", ["Name", "Value"], "Columns"),
               _P("rows", "json", [["Alpha", "1"], ["Beta", "2"]], "Rows"),
               _P("show_header", "bool", True, "Show header"),
               _P("editable", "bool", False, "Editable cells"),
               _P("selection_mode", "choice", "single", "Selection",
                  choices=("single", "multiple", "none"))),
        events=("select", "cell_change") + GENERIC_EVENTS,
    )
    _reg(
        type="tree_view", label="Tree View", category="Data", icon="🌲", default_size=(220, 200),
        props=(_P("items", "json",
                  [{"text": "Root", "children": [{"text": "Child A"}, {"text": "Child B"}]}],
                  "Items"),
               _P("show_header", "bool", False, "Show header"),
               _P("header", "str", "Items", "Header text")),
        events=("select",) + GENERIC_EVENTS,
    )

    # --------------------------------------------- plugin-style 3rd-party widgets
    _reg(
        type="calendar", label="Calendar", category="Plugins", icon="🗓", default_size=(260, 220),
        frameworks=_ALL, plugin=True,
        props=(_P("date", "str", "2025-01-01", "Selected date"),
               _P("first_weekday", "choice", "monday", "First weekday",
                  choices=("monday", "sunday")),
               _P("show_week_numbers", "bool", True, "Week numbers")),
        events=("change",),
        requires={"tkinter": ("tkcalendar>=1.6",), "customtkinter": ("tkcalendar>=1.6",)},
    )
    _reg(
        type="time_picker", label="Time Picker", category="Plugins", icon="🕒",
        default_size=(250, 350), plugin=True, frameworks=_TK,
        props=(_P("hours24", "bool", False, "24-hour clock"),
               _P("theme", "choice", "navy_blue", "Theme",
                  choices=("navy_blue", "dracula", "purple"))),
        events=("change",),
        requires={"tkinter": ("tktimepicker>=2.0",), "customtkinter": ("tktimepicker>=2.0",)},
    )
    _reg(
        type="map_view", label="Map Viewer", category="Plugins", icon="🗺",
        default_size=(400, 250), plugin=True, frameworks=_TK,
        props=(_P("latitude", "float", 51.5074, "Latitude", minimum=-90, maximum=90),
               _P("longitude", "float", -0.1278, "Longitude", minimum=-180, maximum=180),
               _P("zoom", "int", 10, "Zoom", minimum=1, maximum=19),
               _P("marker_text", "str", "", "Marker label")),
        events=("click",),
        requires={"tkinter": ("tkintermapview>=1.29",),
                  "customtkinter": ("tkintermapview>=1.29",)},
    )
    _reg(
        type="chart", label="Chart", category="Plugins", icon="📈", default_size=(360, 240),
        plugin=True, frameworks=_NOT_KIVY,
        props=(_P("kind", "choice", "line", "Chart type",
                  choices=("line", "bar", "scatter", "pie", "hist")),
               _P("title", "str", "Chart", "Title"),
               _P("x", "list", ["1", "2", "3", "4"], "X values"),
               _P("y", "list", ["3", "7", "4", "9"], "Y values"),
               _P("x_label", "str", "", "X label"), _P("y_label", "str", "", "Y label")),
        events=(),
        requires={"tkinter": ("matplotlib>=3.8",), "customtkinter": ("matplotlib>=3.8",),
                  "pyside6": ("matplotlib>=3.8",), "pyqt6": ("matplotlib>=3.8",)},
    )
    _reg(
        type="video_player", label="Video Player", category="Plugins", icon="🎬",
        default_size=(360, 240), plugin=True, frameworks=_TK,
        props=(_P("source", "file", "", "Video file"), _P("autoplay", "bool", False, "Autoplay"),
               _P("loop", "bool", False, "Loop"), _P("controls", "bool", True, "Controls")),
        events=(),
        requires={"tkinter": ("tkvideoplayer>=2.3", "pillow>=10"),
                  "customtkinter": ("tkvideoplayer>=2.3", "pillow>=10")},
    )
    _reg(
        type="pandas_table", label="Pandas Table", category="Plugins", icon="🐼",
        default_size=(380, 220), plugin=True, frameworks=_TK,
        props=(_P("csv_path", "file", "", "CSV file"),
               _P("editable", "bool", False, "Editable"),
               _P("show_toolbar", "bool", False, "Toolbar")),
        events=(),
        requires={"tkinter": ("pandastable>=0.13", "pandas>=2.0"),
                  "customtkinter": ("pandastable>=0.13", "pandas>=2.0")},
    )
    _reg(
        type="color_picker", label="Color Picker", category="Plugins", icon="🎨",
        default_size=(140, 34), plugin=True, frameworks=_NOT_KIVY,
        props=(_P("text", "str", "Pick color", "Button text"), _P("color", "color", "#ff0000", "Color")),
        events=("change",),
    )


register_builtin_widgets()
