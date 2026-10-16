# Frameworks

py_vui keeps one framework-agnostic document and generates code for five targets. Pick the target
in the toolbar (or `Project > Framework...`, or `py_vui gen -f NAME`). Changing it never edits the
design; widgets a target cannot render are generated as a visible placeholder and flagged as a
warning by `py_vui validate` and in the editor.

| Id | Toolkit | Install the generated app with |
|---|---|---|
| `tkinter` | Tk / ttk (`clam` theme), standard library | nothing (needs the OS `tkinter` package) |
| `customtkinter` | CustomTkinter | `customtkinter` |
| `pyside6` | Qt for Python (official) | `PySide6` |
| `pyqt6` | PyQt6 (same emitter as PySide6) | `PyQt6` |
| `kivy` | Kivy, pure Python (no `.kv` files) | `kivy` |

Every generated project contains `main.py`, `ui.py` (`build_ui()`, plus `WIDGETS` / `WINDOWS`
registries), `handlers.py`, `custom.py` (yours, never overwritten), `requirements.txt` and
`README.md`. The single-file layout produces one self-contained `main.py`.

## Widget support

Generated from the widget registry by `tools/gen_docs.py`; do not edit between the markers.
"yes" means a native or packaged implementation exists. "Extra packages" are added to
`requirements.txt` when the widget is used.

<!-- BEGIN widget-matrix -->
| Widget | Type id | Tk | CTk | PySide6 | PyQt6 | Kivy | Extra packages |
|---|---|---|---|---|---|---|---|
| **Window** | | | | | | | |
| Dialog Window | `toplevel` | yes | yes | yes | yes | yes |  |
| Main Window | `window` | yes | yes | yes | yes | yes |  |
| **Layout** | | | | | | | |
| Frame | `frame` | yes | yes | yes | yes | yes |  |
| Group Box | `label_frame` | yes | yes | yes | yes | yes |  |
| Scroll Area | `scroll_frame` | yes | yes | yes | yes | yes |  |
| Splitter | `paned_window` | yes | yes | yes | yes | yes |  |
| Tabs | `tabview` | yes | yes | yes | yes | yes |  |
| **Input** | | | | | | | |
| Button | `button` | yes | yes | yes | yes | yes |  |
| Checkbox | `checkbox` | yes | yes | yes | yes | yes |  |
| Date Input | `date_entry` | yes | yes | yes | yes | yes | `tkcalendar>=1.6` |
| Dial | `dial` | yes | yes | yes | yes | yes |  |
| Dropdown | `combobox` | yes | yes | yes | yes | yes |  |
| List Box | `listbox` | yes | yes | yes | yes | yes |  |
| Radio Button | `radio` | yes | yes | yes | yes | yes |  |
| Segmented Button | `segmented_button` | yes | yes | yes | yes | yes |  |
| Slider | `slider` | yes | yes | yes | yes | yes |  |
| Spin Box | `spinbox` | yes | yes | yes | yes | yes |  |
| Switch | `switch` | yes | yes | yes | yes | yes |  |
| Text Area | `text` | yes | yes | yes | yes | yes |  |
| Text Input | `entry` | yes | yes | yes | yes | yes |  |
| Time Input | `time_entry` | yes | yes | yes | yes | yes |  |
| Tool Button | `tool_button` | yes | yes | yes | yes | yes |  |
| **Display** | | | | | | | |
| Canvas | `canvas` | yes | yes | yes | yes | yes |  |
| Image | `image` | yes | yes | yes | yes | yes |  |
| Label | `label` | yes | yes | yes | yes | yes |  |
| Progress Bar | `progressbar` | yes | yes | yes | yes | yes |  |
| Separator | `separator` | yes | yes | yes | yes | yes |  |
| **Data** | | | | | | | |
| Table | `table` | yes | yes | yes | yes | yes |  |
| Tree View | `tree_view` | yes | yes | yes | yes | yes |  |
| **Plugins** | | | | | | | |
| Calendar | `calendar` | yes | yes | yes | yes | yes | `tkcalendar>=1.6` |
| Chart | `chart` | yes | yes | yes | yes | - | `matplotlib>=3.8` |
| Color Picker | `color_picker` | yes | yes | yes | yes | - |  |
| Map Viewer | `map_view` | yes | yes | - | - | - | `tkintermapview>=1.29` |
| Pandas Table | `pandas_table` | yes | yes | - | - | - | `pandas>=2.0`, `pandastable>=0.13` |
| Time Picker | `time_picker` | yes | yes | - | - | - | `tktimepicker>=2.0` |
| Video Player | `video_player` | yes | yes | - | - | - | `pillow>=10`, `tkvideoplayer>=2.3` |
<!-- END widget-matrix -->

Notes:

* `dial` is native on Qt and drawn on a canvas on Tk and Kivy.
* `calendar`, `time_picker`, `map_view`, `video_player`, `pandas_table` and `color_picker` are
  "plugin-style" built-ins: they need an optional third-party package. The generated code imports
  it inside a `try` block and shows a placeholder label when it is missing, so the app still starts.
* Plugin widgets you add yourself appear under category *Plugins* and only support the frameworks
  their plugin registered emitters for (see [plugins.md](./plugins.md)).

## Layout mapping

| Layout mode | tkinter / customtkinter | PySide6 / PyQt6 | Kivy |
|---|---|---|---|
| `absolute` | `place(x, y, width, height)`; anchors that stretch are re-applied on resize | children positioned with `setGeometry` | `FloatLayout` + pinned top-left coordinates |
| `flex` | `pack` / `grid` based row or column with weights for `grow` | `QHBoxLayout` / `QVBoxLayout` with stretch factors | `BoxLayout` (+ `AnchorLayout` cells and spacers for align / margin / justify) |
| `grid` | `grid` with `columnconfigure` / `rowconfigure` weights, spans and `sticky` | `QGridLayout` with stretch factors and spans | `FloatLayout` + a small `_grid()` helper (weights, spans, sticky) |

The editor canvas uses the same rules (`py_vui.core.layout_engine`), so what you see is close to
what runs, but native toolkits round and style differently: expect differences of a few pixels.

Other mappings:

* `tabview` pages: `ttk.Notebook` / `CTkTabview` / `QTabWidget` / `TabbedPanel`.
* Dialog windows (`toplevel`): a function in `ui.py` that opens the window on demand (Kivy:
  `open_<name>()`, shown in a `Popup`); modal dialogs block their parent where the toolkit
  supports it.
* Menus (`window.props["menus"]`): native menu bars on Tk, CTk and Qt; Kivy uses an `ActionBar`.
* Themes: the project theme tokens are translated to ttk styles, CTk colours, a Qt stylesheet plus
  palette (`theme.py`), or Kivy canvas instructions.

## Limitations

* **Kivy**: widgets marked `-` in the matrix (for example `chart`, `map_view`, `video_player`)
  are generated as placeholders. Menus are an `ActionBar`, not a native menu bar. Window icons
  and `always_on_top` depend on the platform.
* **CustomTkinter**: widgets are sized in their constructors, so style changes such as border
  radius apply at creation only; `ttk`-only options (for example `relief`) are ignored.
* **Tkinter**: rounded corners (`corner_radius`) and hover colours are not supported by plain
  ttk widgets and are ignored.
* **Qt**: styling goes through a generated stylesheet; very custom per-widget fonts and borders may
  be limited by Qt's stylesheet model. `PyQt6` and `PySide6` differ in licence, not API.
* **All**: handlers have the shape `def name(event=None)`. Event payloads are framework specific;
  use `ui.WIDGETS` to read widget state. Absolute layouts do not reflow on DPI changes.

## Widget reference (generated)

<!-- BEGIN widget-properties -->
- **`button`**: props `text`, `image`, `compound`, `default`; events `click`, `double_click`, `right_click`, `middle_click`, `mouse_press`, `mouse_release`, `mouse_move`, `mouse_enter`, `mouse_leave`, `mouse_wheel`, `key_press`, `key_release`, `focus_in`, `focus_out`, `resize`
- **`calendar`**: props `date`, `first_weekday`, `show_week_numbers`; events `change`
- **`canvas`**: props `scrollable`; events `paint`, `double_click`, `right_click`, `middle_click`, `mouse_press`, `mouse_release`, `mouse_move`, `mouse_enter`, `mouse_leave`, `mouse_wheel`, `key_press`, `key_release`, `focus_in`, `focus_out`, `resize`
- **`chart`**: props `kind`, `title`, `x`, `y`, `x_label`, `y_label`; events -
- **`checkbox`**: props `text`, `checked`; events `toggle`, `click`, `double_click`, `right_click`, `middle_click`, `mouse_press`, `mouse_release`, `mouse_move`, `mouse_enter`, `mouse_leave`, `mouse_wheel`, `key_press`, `key_release`, `focus_in`, `focus_out`, `resize`
- **`color_picker`**: props `text`, `color`; events `change`
- **`combobox`**: props `items`, `current`, `editable`; events `change`, `double_click`, `right_click`, `middle_click`, `mouse_press`, `mouse_release`, `mouse_move`, `mouse_enter`, `mouse_leave`, `mouse_wheel`, `key_press`, `key_release`, `focus_in`, `focus_out`, `resize`
- **`date_entry`**: props `date`, `pattern`; events `change`
- **`dial`**: props `minimum`, `maximum`, `value`; events `change`
- **`entry`**: props `text`, `placeholder`, `show`, `readonly`, `justify`, `max_length`; events `change`, `submit`, `double_click`, `right_click`, `middle_click`, `mouse_press`, `mouse_release`, `mouse_move`, `mouse_enter`, `mouse_leave`, `mouse_wheel`, `key_press`, `key_release`, `focus_in`, `focus_out`, `resize`
- **`frame`**: props -; events `click`, `double_click`, `right_click`, `middle_click`, `mouse_press`, `mouse_release`, `mouse_move`, `mouse_enter`, `mouse_leave`, `mouse_wheel`, `key_press`, `key_release`, `focus_in`, `focus_out`, `resize`
- **`image`**: props `source`, `fit`, `alt_text`; events `click`, `double_click`, `right_click`, `middle_click`, `mouse_press`, `mouse_release`, `mouse_move`, `mouse_enter`, `mouse_leave`, `mouse_wheel`, `key_press`, `key_release`, `focus_in`, `focus_out`, `resize`
- **`label`**: props `text`, `anchor`, `justify`, `wrap_length`, `image`; events `click`, `double_click`, `right_click`, `middle_click`, `mouse_press`, `mouse_release`, `mouse_move`, `mouse_enter`, `mouse_leave`, `mouse_wheel`, `key_press`, `key_release`, `focus_in`, `focus_out`, `resize`
- **`label_frame`**: props `title`, `title_align`; events `double_click`, `right_click`, `middle_click`, `mouse_press`, `mouse_release`, `mouse_move`, `mouse_enter`, `mouse_leave`, `mouse_wheel`, `key_press`, `key_release`, `focus_in`, `focus_out`, `resize`
- **`listbox`**: props `items`, `selection_mode`; events `select`, `double_click`, `right_click`, `middle_click`, `mouse_press`, `mouse_release`, `mouse_move`, `mouse_enter`, `mouse_leave`, `mouse_wheel`, `key_press`, `key_release`, `focus_in`, `focus_out`, `resize`
- **`map_view`**: props `latitude`, `longitude`, `zoom`, `marker_text`; events `click`
- **`pandas_table`**: props `csv_path`, `editable`, `show_toolbar`; events -
- **`paned_window`**: props `orientation`, `sizes`; events -
- **`progressbar`**: props `value`, `maximum`, `mode`, `orientation`, `show_text`; events -
- **`radio`**: props `text`, `checked`, `group`, `value`; events `toggle`, `click`, `double_click`, `right_click`, `middle_click`, `mouse_press`, `mouse_release`, `mouse_move`, `mouse_enter`, `mouse_leave`, `mouse_wheel`, `key_press`, `key_release`, `focus_in`, `focus_out`, `resize`
- **`scroll_frame`**: props `orientation`, `content_width`, `content_height`; events `mouse_wheel`
- **`segmented_button`**: props `items`, `current`; events `change`
- **`separator`**: props `orientation`; events -
- **`slider`**: props `minimum`, `maximum`, `value`, `step`, `orientation`, `show_value`; events `change`, `double_click`, `right_click`, `middle_click`, `mouse_press`, `mouse_release`, `mouse_move`, `mouse_enter`, `mouse_leave`, `mouse_wheel`, `key_press`, `key_release`, `focus_in`, `focus_out`, `resize`
- **`spinbox`**: props `minimum`, `maximum`, `value`, `step`, `decimals`, `wrap`; events `change`, `double_click`, `right_click`, `middle_click`, `mouse_press`, `mouse_release`, `mouse_move`, `mouse_enter`, `mouse_leave`, `mouse_wheel`, `key_press`, `key_release`, `focus_in`, `focus_out`, `resize`
- **`switch`**: props `text`, `checked`; events `toggle`, `click`, `double_click`, `right_click`, `middle_click`, `mouse_press`, `mouse_release`, `mouse_move`, `mouse_enter`, `mouse_leave`, `mouse_wheel`, `key_press`, `key_release`, `focus_in`, `focus_out`, `resize`
- **`table`**: props `columns`, `rows`, `show_header`, `editable`, `selection_mode`; events `select`, `cell_change`, `double_click`, `right_click`, `middle_click`, `mouse_press`, `mouse_release`, `mouse_move`, `mouse_enter`, `mouse_leave`, `mouse_wheel`, `key_press`, `key_release`, `focus_in`, `focus_out`, `resize`
- **`tabview`**: props `tabs`, `current`; events `tab_change`, `double_click`, `right_click`, `middle_click`, `mouse_press`, `mouse_release`, `mouse_move`, `mouse_enter`, `mouse_leave`, `mouse_wheel`, `key_press`, `key_release`, `focus_in`, `focus_out`, `resize`
- **`text`**: props `text`, `placeholder`, `readonly`, `wrap`, `scrollbar`; events `change`, `double_click`, `right_click`, `middle_click`, `mouse_press`, `mouse_release`, `mouse_move`, `mouse_enter`, `mouse_leave`, `mouse_wheel`, `key_press`, `key_release`, `focus_in`, `focus_out`, `resize`
- **`time_entry`**: props `time`, `show_seconds`; events `change`
- **`time_picker`**: props `hours24`, `theme`; events `change`
- **`tool_button`**: props `text`, `image`, `checkable`; events `click`, `double_click`, `right_click`, `middle_click`, `mouse_press`, `mouse_release`, `mouse_move`, `mouse_enter`, `mouse_leave`, `mouse_wheel`, `key_press`, `key_release`, `focus_in`, `focus_out`, `resize`
- **`toplevel`**: props `title`, `width`, `height`, `modal`, `resizable_x`, `resizable_y`, `always_on_top`, `start_hidden`, `icon`; events `close`, `resize`, `key_press`, `key_release`, `focus_in`, `focus_out`, `show`, `hide`
- **`tree_view`**: props `items`, `show_header`, `header`; events `select`, `double_click`, `right_click`, `middle_click`, `mouse_press`, `mouse_release`, `mouse_move`, `mouse_enter`, `mouse_leave`, `mouse_wheel`, `key_press`, `key_release`, `focus_in`, `focus_out`, `resize`
- **`video_player`**: props `source`, `autoplay`, `loop`, `controls`; events -
- **`window`**: props `title`, `width`, `height`, `resizable_x`, `resizable_y`, `min_width`, `min_height`, `maximized`, `always_on_top`, `icon`, `menus`; events `close`, `resize`, `key_press`, `key_release`, `focus_in`, `focus_out`, `show`, `hide`, `mouse_move`, `mouse_press`, `mouse_release`, `mouse_wheel`
<!-- END widget-properties -->
