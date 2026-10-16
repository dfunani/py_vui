"""Framework-agnostic design tokens. Adapters translate them to native styling."""

from __future__ import annotations

import sys
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ThemePreset = Literal["light", "dark", "modern", "ocean", "forest", "sunset", "midnight"]
PRESETS: tuple[str, ...] = ("light", "dark", "modern", "ocean", "forest", "sunset", "midnight")


def default_font_family() -> str:
    if sys.platform == "darwin":
        return "Helvetica Neue"
    if sys.platform == "win32":
        return "Segoe UI"
    return "DejaVu Sans"


class ProjectTheme(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    preset: ThemePreset = "modern"
    font_family: str = Field(default_factory=default_font_family, alias="fontFamily")
    font_size: int = Field(default=13, ge=6, le=48, alias="fontSize")
    primary: str = "#6366f1"
    primary_hover: str = Field(default="#4f46e5", alias="primaryHover")
    background: str = "#f4f4f5"
    surface: str = "#ffffff"
    text: str = "#18181b"
    muted_text: str = Field(default="#71717a", alias="mutedText")
    button_text: str = Field(default="#ffffff", alias="buttonText")
    button_radius: int = Field(default=10, ge=0, le=64, alias="buttonRadius")
    border: str = "#d4d4d8"
    border_width: int = Field(default=1, ge=0, le=16, alias="borderWidth")
    #: ctk appearance mode hint: system | light | dark
    appearance: Literal["system", "light", "dark"] = "light"


_TOKENS: dict[str, dict[str, object]] = {
    "light": dict(primary="#2563eb", primary_hover="#1d4ed8", background="#f8fafc",
                  surface="#ffffff", text="#0f172a", muted_text="#64748b",
                  button_radius=6, border="#e2e8f0", appearance="light"),
    "dark": dict(primary="#3b82f6", primary_hover="#2563eb", background="#0f172a",
                 surface="#1e293b", text="#f8fafc", muted_text="#94a3b8",
                 button_radius=8, border="#334155", appearance="dark"),
    "modern": dict(primary="#6366f1", primary_hover="#4f46e5", background="#f4f4f5",
                   surface="#ffffff", text="#18181b", muted_text="#71717a",
                   button_radius=10, border="#d4d4d8", appearance="light"),
    "ocean": dict(primary="#0891b2", primary_hover="#0e7490", background="#ecfeff",
                  surface="#ffffff", text="#164e63", muted_text="#0e7490",
                  button_radius=8, border="#a5f3fc", appearance="light"),
    "forest": dict(primary="#16a34a", primary_hover="#15803d", background="#f0fdf4",
                   surface="#ffffff", text="#14532d", muted_text="#4d7c0f",
                   button_radius=8, border="#bbf7d0", appearance="light"),
    "sunset": dict(primary="#ea580c", primary_hover="#c2410c", background="#fff7ed",
                   surface="#ffffff", text="#431407", muted_text="#9a3412",
                   button_radius=12, border="#fed7aa", appearance="light"),
    "midnight": dict(primary="#8b5cf6", primary_hover="#7c3aed", background="#09090b",
                     surface="#18181b", text="#fafafa", muted_text="#a1a1aa",
                     button_radius=8, border="#3f3f46", appearance="dark"),
}


def theme_for_preset(preset: str) -> ProjectTheme:
    data = ProjectTheme(preset=preset).model_dump()  # type: ignore[arg-type]
    data.update(_TOKENS[preset])
    data["preset"] = preset
    return ProjectTheme.model_validate(data)


def resolve_style(theme: ProjectTheme, node_type: str, style: dict) -> dict[str, object]:
    """Return fully-resolved visual tokens for one widget (shared by canvas + adapters)."""
    is_button = node_type in {"button", "tool_button", "segmented_button"}
    is_surface = node_type in {"frame", "label_frame", "tabview", "scroll_frame", "window",
                               "toplevel", "paned_window"}
    bg = style.get("background") or (
        theme.primary if is_button else theme.background if node_type in {"window", "toplevel"}
        else theme.surface if is_surface else theme.surface
    )
    fg = style.get("foreground") or (theme.button_text if is_button else theme.text)
    bw = style.get("border_width", -1)
    radius = style.get("corner_radius", -1)
    return {
        "background": bg,
        "foreground": fg,
        "font_family": style.get("font_family") or theme.font_family,
        "font_size": style.get("font_size") or theme.font_size,
        "bold": bool(style.get("bold")),
        "italic": bool(style.get("italic")),
        "underline": bool(style.get("underline")),
        "border_width": theme.border_width if bw in (-1, None) else bw,
        "border_color": style.get("border_color") or theme.border,
        "corner_radius": (theme.button_radius if is_button else 4) if radius in (-1, None) else radius,
        "hover_color": style.get("hover_color") or theme.primary_hover,
        "cursor": style.get("cursor", ""),
        "relief": style.get("relief", ""),
    }
