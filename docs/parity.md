# pyuibuilder.com parity

py_vui re-implements the pyuibuilder.com workflow as a free, local desktop app. The table is based on the
public pyuibuilder README, article page and site bundle (the site itself is a JavaScript app). Items that
pyuibuilder lists as paid, upcoming or work-in-progress are all included here, with no paywall.

| pyuibuilder feature | Tier there | py_vui |
|---|---|---|
| Tkinter code generation | Free | Yes |
| CustomTkinter code generation | Free | Yes |
| PySide / PyQt generation | Paid, upcoming | Yes (PySide6 and PyQt6) |
| Kivy generation | WIP | Yes |
| Absolute, flex and grid layout managers | Free | Yes, per container |
| Drag-and-drop canvas, resize, move | Free | Yes (zoom, rulers, guides, snapping, multi-select) |
| Widget toolbox | Free | 36 widgets in 6 categories, searchable |
| Premium widgets (tabs, scroll areas) | Paid | Yes (tabs, scroll area, splitter) |
| Properties / widget inspector | Free | Yes (Properties, Style, Layout, Events) |
| Event binding and built-in code editor | Free / roadmap | Yes (all events; syntax-highlighted editor) |
| 3rd-party widgets (time picker, maps, calendar, charts, pandas table, video) | Free | Yes, built in as plugin widgets |
| Load 3rd-party plugins locally | Paid | Yes (`py_vui plugins`, plugin manager) |
| Upload local assets | Free | Yes (asset manager, drag-and-drop) |
| `requirements.txt` generation | Free | Yes, computed per framework and widgets used |
| Save and load UI files | Paid | Yes (project folders, autosave, recovery) |
| Live preview | Paid, upcoming | Yes (run, and live restart on change) |
| Dark theme | Paid | Yes (editor light/dark, plus 7 project themes) |
| Templates | Free | 14 |
| Downloadable desktop app (Electron) | Paid, upcoming | Native desktop app, PyInstaller bundles |
| Responsive layouts | Free | Anchors, flex, grid |
| Multiple windows | Free | Dialog windows |
| Commercial use, priority support | Paid | Not applicable: MIT, no licensing tiers |

Beyond pyuibuilder: headless CLI, merge-safe regeneration of handlers, single-file export, v1 project
migration, and an extensible widget registry.
