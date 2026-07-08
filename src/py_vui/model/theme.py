from __future__ import annotations

import sys
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


def default_font_family() -> str:
    """Cross-platform UI font; empty string lets Qt pick the native default."""
    if sys.platform == "darwin":
        return "Helvetica Neue"
    if sys.platform == "win32":
        return "Segoe UI"
    return "sans-serif"


ThemePreset = Literal["light", "dark", "modern", "ocean"]


class WidgetStyle(BaseModel):
    """Per-widget visual overrides (merged on top of project theme)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    background: str | None = None
    foreground: str | None = None
    font_size: int | None = Field(default=None, ge=8, le=48)
    border_radius: int | None = Field(default=None, ge=0, le=32)


class ProjectTheme(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    preset: ThemePreset = "modern"
    font_family: str = Field(default_factory=default_font_family, alias="fontFamily")
    font_size: int = Field(default=13, ge=8, le=24, alias="fontSize")
    primary: str = "#2563eb"
    background: str = "#f1f5f9"
    surface: str = "#ffffff"
    text: str = "#0f172a"
    button_text: str = Field(default="#ffffff", alias="buttonText")
    button_radius: int = Field(default=8, ge=0, le=24, alias="buttonRadius")
    border: str = "#cbd5e1"


def _qss_font(theme: ProjectTheme, *, font_size: int) -> str:
    family = theme.font_family.strip()
    if sys.platform == "darwin" and family == "Segoe UI":
        family = default_font_family()
    if family:
        return f"font-family: {family}; font-size: {font_size}px; "
    return f"font-size: {font_size}px; "


_PRESET_DEFAULTS: dict[ThemePreset, dict[str, object]] = {
    "light": {
        "primary": "#2563eb",
        "background": "#f8fafc",
        "surface": "#ffffff",
        "text": "#0f172a",
        "button_text": "#ffffff",
        "button_radius": 6,
        "border": "#e2e8f0",
    },
    "dark": {
        "primary": "#3b82f6",
        "background": "#0f172a",
        "surface": "#1e293b",
        "text": "#f8fafc",
        "button_text": "#ffffff",
        "button_radius": 8,
        "border": "#334155",
    },
    "modern": {
        "primary": "#6366f1",
        "background": "#f4f4f5",
        "surface": "#ffffff",
        "text": "#18181b",
        "button_text": "#ffffff",
        "button_radius": 10,
        "border": "#d4d4d8",
    },
    "ocean": {
        "primary": "#0891b2",
        "background": "#ecfeff",
        "surface": "#ffffff",
        "text": "#164e63",
        "button_text": "#ffffff",
        "button_radius": 8,
        "border": "#a5f3fc",
    },
}


def theme_for_preset(preset: ThemePreset) -> ProjectTheme:
    base = ProjectTheme(preset=preset)
    data = base.model_dump(by_alias=False)
    data.update(_PRESET_DEFAULTS[preset])
    data["preset"] = preset
    return ProjectTheme.model_validate(data)


def resolve_widget_colors(
    *,
    theme: ProjectTheme,
    node_type: str,
    style: WidgetStyle | None,
) -> tuple[str, str, str]:
    """Return (fill, border, text) hex colors for canvas preview."""
    if node_type == "button":
        fill = style.background if style and style.background else theme.primary
        text = style.foreground if style and style.foreground else theme.button_text
        border = theme.primary
    elif node_type == "frame":
        fill = style.background if style and style.background else theme.surface
        text = style.foreground if style and style.foreground else theme.text
        border = theme.border
    elif node_type == "window":
        fill = style.background if style and style.background else theme.surface
        text = theme.text
        border = theme.primary
    else:
        fill = style.background if style and style.background else theme.surface
        text = style.foreground if style and style.foreground else theme.text
        border = theme.border
    return fill, border, text


def stylesheet_for_node(
    *,
    theme: ProjectTheme,
    node_type: str,
    style: WidgetStyle | None,
) -> str:
    fill, border, text = resolve_widget_colors(
        theme=theme, node_type=node_type, style=style
    )
    radius = (
        style.border_radius
        if style and style.border_radius is not None
        else theme.button_radius
        if node_type == "button"
        else 4
    )
    font_size = style.font_size if style and style.font_size else theme.font_size
    base = (
        f"{_qss_font(theme, font_size=font_size)}color: {text}; "
        f"background-color: {fill}; border: 1px solid {border}; "
        f"border-radius: {radius}px; padding: 4px 8px;"
    )
    if node_type == "button":
        hover_fill = style.background if style and style.background else theme.primary
        return (
            f"QPushButton {{ {base} }} "
            f"QPushButton:hover {{ {_qss_font(theme, font_size=font_size)}color: {text}; "
            f"background-color: {hover_fill}; border: 1px solid {border}; "
            f"border-radius: {radius}px; padding: 4px 8px; }} "
            f"QPushButton:pressed {{ background-color: {hover_fill}; }}"
        )
    if node_type == "window":
        return f"QWidget {{ {base} }}"
    if node_type in ("radio_button", "checkbox"):
        return f"QCheckBox {{ {base} }}"
    if node_type == "spin_box":
        return f"QSpinBox {{ {base} }}"
    if node_type == "slider":
        return f"QSlider {{ {base} }}"
    if node_type == "list_widget":
        return f"QListWidget {{ {base} }}"
    if node_type == "group_box":
        return f"QGroupBox {{ {base} }}"
    if node_type == "tab_widget":
        return f"QTabWidget {{ {base} }}"
    if node_type == "progress_bar":
        return f"QProgressBar {{ {base} border: none; }}"
    if node_type == "scroll_area":
        return f"QScrollArea {{ {base} }}"
    if node_type == "line_edit":
        return f"QLineEdit {{ {base} }}"
    if node_type == "combo_box":
        return f"QComboBox {{ {base} }}"
    if node_type == "text_edit":
        return f"QTextEdit {{ {base} }}"
    if node_type == "checkbox":
        return f"QCheckBox {{ {base} }}"
    if node_type == "label":
        if style and style.background:
            return f"QLabel {{ {base} }}"
        return f"QLabel {{ {base} border: none; background: transparent; }}"
    if node_type == "frame":
        return f"QFrame {{ {base} }}"
    return ""


def application_stylesheet(theme: ProjectTheme) -> str:
    return (
        f"QWidget {{ {_qss_font(theme, font_size=theme.font_size)}"
        f"color: {theme.text}; background-color: {theme.background}; }}"
    )
