"""Menu bar and toolbars, assembled from the shared action table."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QSize
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QComboBox, QLabel, QMenu, QSizePolicy, QToolBar, QWidget

from py_vui.app.editor.edit_ops import WRAP_TYPES
from py_vui.core.registry import FRAMEWORKS, get_spec

if TYPE_CHECKING:
    from py_vui.app.editor.main_window import MainWindow

DEVICE_PRESETS: tuple[tuple[str, tuple[int, int] | None], ...] = (
    ("Window size…", None),
    ("Phone  390 × 844", (390, 844)),
    ("Tablet  820 × 1180", (820, 1180)),
    ("Laptop  1280 × 800", (1280, 800)),
    ("Desktop  1920 × 1080", (1920, 1080)),
    ("Small  640 × 480", (640, 480)),
    ("Custom…", None),
)
ZOOM_PRESETS = (10, 25, 50, 75, 100, 150, 200, 300, 400)


def build_menus(mw: MainWindow) -> None:
    a = mw.act
    bar = mw.menuBar()

    m = bar.addMenu("&File")
    for k in ("new", "new_template", "open"):
        m.addAction(a[k])
    mw.recent_menu = m.addMenu("Open &Recent")
    mw.recent_menu.aboutToShow.connect(mw.fill_recent_menu)
    for k in ("save", "save_as"):
        m.addAction(a[k])
    m.addSeparator()
    m.addAction(a["import_json"])
    m.addAction(a["export"])
    m.addSeparator()
    m.addAction(a["preferences"])
    m.addSeparator()
    m.addAction(a["quit"])

    m = bar.addMenu("&Edit")
    mw.edit_menu = m
    for k in ("undo", "redo"):
        m.addAction(a[k])
    m.addSeparator()
    for k in ("cut", "copy", "paste", "duplicate", "select_all", "delete", "rename"):
        m.addAction(a[k])
    m.addSeparator()
    sub = m.addMenu("&Align")
    for k in (
        "align_left",
        "align_center",
        "align_right",
        "align_top",
        "align_middle",
        "align_bottom",
    ):
        sub.addAction(a[k])
    sub = m.addMenu("Distri&bute")
    for k in ("distribute_h", "distribute_v"):
        sub.addAction(a[k])
    sub = m.addMenu("&Size")
    for k in ("same_width", "same_height", "same_size"):
        sub.addAction(a[k])
    sub = m.addMenu("&Order")
    for k in ("z_front", "z_forward", "z_backward", "z_back"):
        sub.addAction(a[k])
    m.addSeparator()
    m.addAction(a["group"])
    m.addAction(a["ungroup"])
    wrap = m.addMenu("&Wrap in…")
    for t in WRAP_TYPES:
        act = QAction(get_spec(t).label, wrap)
        act.triggered.connect(lambda _=False, tt=t: mw.wrap_selection(tt))
        wrap.addAction(act)

    m = bar.addMenu("&View")
    for k in ("zoom_in", "zoom_out", "zoom_fit", "zoom_100"):
        m.addAction(a[k])
    m.addSeparator()
    for k in ("toggle_grid", "toggle_snap", "toggle_guides", "toggle_rulers"):
        m.addAction(a[k])
    m.addSeparator()
    mw.docks_menu = m.addMenu("&Panels")
    theme = m.addMenu("Editor &Theme")
    group = QActionGroup(mw)
    group.setExclusive(True)
    for k in ("theme_dark", "theme_light", "theme_auto"):
        group.addAction(a[k])
        theme.addAction(a[k])

    m = bar.addMenu("&Build")
    for k in ("generate", "run", "stop", "restart", "live_preview"):
        m.addAction(a[k])
    m.addSeparator()
    for k in ("export", "build_exe"):
        m.addAction(a[k])
    m.addSeparator()
    for k in ("requirements", "sync_handlers"):
        m.addAction(a[k])

    m = bar.addMenu("&Project")
    for k in ("framework", "theme", "assets", "menus", "plugins"):
        m.addAction(a[k])
    m.addSeparator()
    m.addAction(a["add_dialog"])

    m = bar.addMenu("&Help")
    for k in ("shortcuts", "about"):
        m.addAction(a[k])


def _combo(items: list[str], width: int, tip: str) -> QComboBox:
    c = QComboBox()
    c.addItems(items)
    c.setToolTip(tip)
    c.setMinimumWidth(width)
    return c


def _add(bar: QToolBar, mw: MainWindow, keys: tuple[str, ...]) -> None:
    for k in keys:
        bar.addAction(mw.act[k])


def build_toolbars(mw: MainWindow) -> None:
    top = QToolBar("Main", mw)
    top.setObjectName("toolbar_main")
    top.setMovable(False)
    top.setIconSize(QSize(20, 20))
    mw.addToolBar(top)
    _add(top, mw, ("new", "open", "save"))
    top.addSeparator()
    _add(top, mw, ("undo", "redo"))
    top.addSeparator()
    _add(top, mw, ("cut", "copy", "paste", "duplicate", "delete"))
    top.addSeparator()
    top.addWidget(QLabel(" Framework "))
    mw.fw_combo = _combo(list(FRAMEWORKS), 120, "Target framework (click to change)")
    mw.fw_combo.setCurrentText(mw.doc.project.framework)
    mw.fw_combo.activated.connect(mw.on_framework_combo)
    top.addWidget(mw.fw_combo)
    top.addSeparator()
    _add(top, mw, ("generate", "run", "stop", "live_preview"))
    top.addSeparator()
    _add(top, mw, ("export", "theme"))
    spacer = QWidget()
    spacer.setObjectName("toolbarSpacer")
    spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    top.addWidget(spacer)
    _add(top, mw, ("preferences",))

    mw.addToolBarBreak()
    lay = QToolBar("Layout", mw)
    lay.setObjectName("toolbar_layout")
    lay.setMovable(False)
    lay.setIconSize(QSize(20, 20))
    mw.addToolBar(lay)
    _add(
        lay,
        mw,
        ("align_left", "align_center", "align_right", "align_top", "align_middle", "align_bottom"),
    )
    lay.addSeparator()
    _add(lay, mw, ("distribute_h", "distribute_v", "same_width", "same_height", "same_size"))
    lay.addSeparator()
    _add(lay, mw, ("z_front", "z_forward", "z_backward", "z_back"))
    lay.addSeparator()
    _add(lay, mw, ("group", "ungroup"))
    lay.addSeparator()
    _add(lay, mw, ("zoom_out",))
    mw.zoom_combo = _combo([f"{z}%" for z in ZOOM_PRESETS], 78, "Zoom")
    mw.zoom_combo.setEditable(True)
    mw.zoom_combo.setCurrentText("100%")
    mw.zoom_combo.activated.connect(lambda _i: mw.apply_zoom_text(mw.zoom_combo.currentText()))
    mw.zoom_combo.lineEdit().editingFinished.connect(
        lambda: mw.apply_zoom_text(mw.zoom_combo.currentText())
    )
    lay.addWidget(mw.zoom_combo)
    _add(lay, mw, ("zoom_in", "zoom_fit"))
    lay.addSeparator()
    _add(lay, mw, ("toggle_grid", "toggle_snap", "toggle_guides", "toggle_rulers"))
    lay.addSeparator()
    lay.addWidget(QLabel(" Device "))
    mw.device_combo = _combo([n for n, _s in DEVICE_PRESETS], 150, "Window size presets")
    mw.device_combo.activated.connect(mw.on_device_combo)
    lay.addWidget(mw.device_combo)
    mw.toolbars = [top, lay]


def fill_docks_menu(mw: MainWindow, menu: QMenu, docks: list) -> None:
    for d in docks:
        menu.addAction(d.toggleViewAction())
