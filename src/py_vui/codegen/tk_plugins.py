"""Emitters for the built-in plugin widgets on ``tkinter`` and ``customtkinter``.

Each emitter returns :class:`EmitResult` statements that create ``ctx.var`` as a child of
``ctx.parent``.  The optional third-party library is imported inside a ``try`` block, so a
missing package produces a visible placeholder label instead of crashing the app.
"""

from __future__ import annotations

from py_vui.codegen.base import EmitContext, EmitResult, register_plugin_emitter
from py_vui.codegen.tk_common import PLUGIN_SEQUENCES, py

FRAMEWORKS = ("tkinter", "customtkinter")

#: virtual events a plugin widget generates, so ``events: {"change": ...}`` can bind them
PLUGIN_SEQUENCES.update({
    "calendar": {"change": "<<CalendarSelected>>"},
    "time_picker": {"change": "<<TimeChanged>>"},
    "color_picker": {"change": "<<ColorChanged>>"},
})


def _guarded(ctx: EmitContext, label: str, package: str, import_line: str,
             body: list[str]) -> list[str]:
    """``try: import; body`` with a visible placeholder label when the library is unusable."""
    missing = f"[{label}: pip install {package}]"
    lines = ["try:", f"    {import_line}", ""]
    lines += [f"    {ln}" if ln else "" for ln in body]
    lines += ["except ModuleNotFoundError:",
              f"    {ctx.var} = ttk.Label({ctx.parent}, text={py(missing)}, anchor=\"center\", "
              "relief=\"solid\")",
              "except Exception as error:  # installed, but unusable on this system",
              f"    {ctx.var} = ttk.Label({ctx.parent}, text=f\"[{label}: {{error}}]\", "
              "anchor=\"center\", relief=\"solid\")"]
    return lines


def _num_list(values: list) -> list:
    out: list = []
    for v in values:
        try:
            f = float(v)
            out.append(int(f) if f == int(f) else f)
        except (TypeError, ValueError):
            out.append(str(v))
    return out


def _asset_expr(path: str) -> str:
    return f"os.path.join(APP_DIR, *{py(path)}.split(\"/\"))"


def emit_calendar(ctx: EmitContext) -> EmitResult:
    p = ctx.node.props
    kw = ["selectmode=\"day\"", f"firstweekday={py(p.get('first_weekday', 'monday'))}",
          f"showweeknumbers={bool(p.get('show_week_numbers', True))}",
          "date_pattern=\"yyyy-mm-dd\""]
    parts = str(p.get("date", "")).split("-")
    if len(parts) == 3 and all(x.isdigit() for x in parts):
        kw[1:1] = [f"year={int(parts[0])}", f"month={int(parts[1])}", f"day={int(parts[2])}"]
    body = [f"{ctx.var} = Calendar({ctx.parent}, {', '.join(kw)})"]
    lines = _guarded(ctx, "Calendar", "tkcalendar", "from tkcalendar import Calendar", body)
    return EmitResult(lines=lines, requirements=["tkcalendar>=1.6"])


def emit_time_picker(ctx: EmitContext) -> EmitResult:
    p = ctx.node.props
    theme = {"navy_blue": "setNavyBlue", "dracula": "setDracula", "purple": "setPurple"}.get(
        p.get("theme", "navy_blue"), "setNavyBlue")
    clock = "HOURS24" if p.get("hours24") else "HOURS12"
    v = ctx.var
    body = [
        f"{v} = AnalogPicker({ctx.parent}, type=constants.{clock})",
        f"AnalogThemes({v}).{theme}()",
        f"for picker in ({v}.hours_picker, {v}.minutes_picker):",
        f"    picker.bind(\"<<HoursChanged>>\", lambda _e: {v}.event_generate(\"<<TimeChanged>>\"),"
        " add=\"+\")",
        f"    picker.bind(\"<<MinChanged>>\", lambda _e: {v}.event_generate(\"<<TimeChanged>>\"),"
        " add=\"+\")",
    ]
    lines = _guarded(ctx, "Time picker", "tktimepicker",
                     "from tktimepicker import AnalogPicker, AnalogThemes, constants", body)
    return EmitResult(lines=lines, requirements=["tktimepicker>=2.0"])


def emit_map_view(ctx: EmitContext) -> EmitResult:
    p, n, v = ctx.node.props, ctx.node, ctx.var
    lat, lon = float(p.get("latitude", 0)), float(p.get("longitude", 0))
    body = [
        f"{v} = TkinterMapView({ctx.parent}, width={int(n.box.w)}, height={int(n.box.h)}, "
        "corner_radius=0)",
        f"{v}.set_position({py(lat)}, {py(lon)})",
        f"{v}.set_zoom({int(p.get('zoom', 10))})",
    ]
    if p.get("marker_text"):
        body.append(f"{v}.set_marker({py(lat)}, {py(lon)}, text={py(p['marker_text'])})")
    lines = _guarded(ctx, "Map", "tkintermapview", "from tkintermapview import TkinterMapView",
                     body)
    return EmitResult(lines=lines, requirements=["tkintermapview>=1.29"])


def emit_chart(ctx: EmitContext) -> EmitResult:
    p, n, v = ctx.node.props, ctx.node, ctx.var
    theme = ctx.project.theme
    kind = p.get("kind", "line")
    xs, ys = _num_list(list(p.get("x", []))), _num_list(list(p.get("y", [])))
    ys = [y if isinstance(y, (int, float)) else 0 for y in ys]
    fig, ax = f"{v}_fig", f"{v}_ax"
    body = [
        f"{fig} = Figure(figsize=({n.box.w / 100:.2f}, {n.box.h / 100:.2f}), dpi=100)",
        f"{fig}.patch.set_facecolor({py(theme.surface)})",
        f"{ax} = {fig}.add_subplot(111)",
    ]
    if kind == "pie":
        body.append(f"{ax}.pie({py(ys)}, labels={py([str(x) for x in xs])}, autopct=\"%1.0f%%\")")
    elif kind == "hist":
        body.append(f"{ax}.hist({py(ys)})")
    elif kind == "bar":
        body.append(f"{ax}.bar({py(xs if all(isinstance(x, str) for x in xs) else [str(x) for x in xs])}"
                    f", {py(ys)}, color={py(theme.primary)})")
    elif kind == "scatter":
        xnum = [x if isinstance(x, (int, float)) else i for i, x in enumerate(xs)]
        body.append(f"{ax}.scatter({py(xnum)}, {py(ys)}, color={py(theme.primary)})")
    else:
        xnum = [x if isinstance(x, (int, float)) else i for i, x in enumerate(xs)]
        body.append(f"{ax}.plot({py(xnum)}, {py(ys)}, color={py(theme.primary)})")
    if p.get("title"):
        body.append(f"{ax}.set_title({py(p['title'])})")
    if p.get("x_label") and kind not in ("pie",):
        body.append(f"{ax}.set_xlabel({py(p['x_label'])})")
    if p.get("y_label") and kind not in ("pie",):
        body.append(f"{ax}.set_ylabel({py(p['y_label'])})")
    body += [f"{fig}.tight_layout()",
             f"{v} = FigureCanvasTkAgg({fig}, master={ctx.parent}).get_tk_widget()"]
    lines = _guarded(ctx, "Chart", "matplotlib",
                     "from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg", body)
    lines.insert(2, "    from matplotlib.figure import Figure")
    return EmitResult(lines=lines, requirements=["matplotlib>=3.8"])


def emit_video_player(ctx: EmitContext) -> EmitResult:
    p, v = ctx.node.props, ctx.var
    player = f"{v}_player"
    body = [
        f"{v} = ttk.Frame({ctx.parent})",
        f"{player} = TkinterVideo(master={v}, scaled=True)",
        f"{player}.pack(fill=\"both\", expand=True)",
        f"{v}.player = {player}",
    ]
    if p.get("source"):
        body.append(f"{player}.load({_asset_expr(str(p['source']))})")
    if p.get("loop"):
        body.append(f"{player}.bind(\"<<Ended>>\", lambda _e: {player}.play())")
    if p.get("controls", True):
        body += [
            f"{v}_bar = ttk.Button({v}, text=\"Play / Pause\", command=lambda: "
            f"{player}.pause() if not {player}.is_paused() else {player}.play())",
            f"{v}_bar.pack(side=\"bottom\", fill=\"x\")",
        ]
    if p.get("autoplay") and p.get("source"):
        body.append(f"{player}.play()")
    lines = _guarded(ctx, "Video player", "tkvideoplayer",
                     "from tkVideoPlayer import TkinterVideo", body)
    return EmitResult(lines=lines, requirements=["tkvideoplayer>=2.3", "pillow>=10"])


def emit_pandas_table(ctx: EmitContext) -> EmitResult:
    p, v = ctx.node.props, ctx.var
    table, frame = f"{v}_table", v
    if p.get("csv_path"):
        data = f"pd.read_csv({_asset_expr(str(p['csv_path']))})"
    else:
        data = "pd.DataFrame({\"A\": [1, 2, 3], \"B\": [\"x\", \"y\", \"z\"]})"
    body = [
        f"{frame} = ttk.Frame({ctx.parent})",
        f"{table} = Table({frame}, dataframe={data}, showtoolbar={bool(p.get('show_toolbar'))}, "
        f"showstatusbar=False, editable={bool(p.get('editable'))})",
        f"{table}.show()",
        f"{frame}.table = {table}",
    ]
    lines = _guarded(ctx, "Pandas table", "pandastable pandas",
                     "import pandas as pd\n    from pandastable import Table", body)
    # the guarded import line above contains a newline; split so every element is one line
    flat: list[str] = []
    for ln in lines:
        flat.extend(ln.split("\n"))
    return EmitResult(lines=flat, requirements=["pandas>=2.0", "pandastable>=0.13"])


def emit_color_picker(ctx: EmitContext) -> EmitResult:
    p, v = ctx.node.props, ctx.var
    color = str(p.get("color", "#ff0000"))
    swatch, pick = f"{v}_swatch", f"_pick_{v}"
    lines = [
        f"{swatch} = tk.PhotoImage(width=14, height=14)",
        f"{swatch}.put({py(color)}, to=(0, 0, 14, 14))",
        f"{v} = ttk.Button({ctx.parent}, text={py(p.get('text', 'Pick color'))}, image={swatch}, "
        "compound=\"left\")",
        f"{v}.color = {py(color)}",
        f"{v}.swatch = {swatch}",
        "",
        f"def {pick}():",
        f"    chosen = colorchooser.askcolor(color={v}.color, title={py(p.get('text', 'Color'))})[1]",
        "    if chosen:",
        f"        {v}.color = chosen",
        f"        {swatch}.put(chosen, to=(0, 0, 14, 14))",
        f"        {v}.event_generate(\"<<ColorChanged>>\")",
        "",
        "",
        f"{v}.configure(command={pick})",
    ]
    return EmitResult(imports=["from tkinter import colorchooser"], lines=lines)


for _fw in FRAMEWORKS:
    register_plugin_emitter("calendar", _fw, emit_calendar)
    register_plugin_emitter("time_picker", _fw, emit_time_picker)
    register_plugin_emitter("map_view", _fw, emit_map_view)
    register_plugin_emitter("chart", _fw, emit_chart)
    register_plugin_emitter("video_player", _fw, emit_video_player)
    register_plugin_emitter("pandas_table", _fw, emit_pandas_table)
    register_plugin_emitter("color_picker", _fw, emit_color_picker)
