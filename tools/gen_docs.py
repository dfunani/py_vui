"""Regenerate the registry-derived tables in docs/frameworks.md.

Usage::

    .venv/bin/python tools/gen_docs.py          # rewrite the generated blocks
    .venv/bin/python tools/gen_docs.py --check  # exit 1 when the doc is out of date

The blocks live between ``<!-- BEGIN name -->`` / ``<!-- END name -->`` markers; hand-written text
around them is never touched. Only the built-in catalog is used (no plugins are loaded).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

DOC = ROOT / "docs" / "frameworks.md"
FW_LABEL = {
    "tkinter": "Tk", "customtkinter": "CTk", "pyside6": "PySide6", "pyqt6": "PyQt6", "kivy": "Kivy",
}


def widget_matrix() -> str:
    from py_vui.core.registry import FRAMEWORKS, all_specs

    head = "| Widget | Type id | " + " | ".join(FW_LABEL[f] for f in FRAMEWORKS) + " | Extra packages |"
    lines = [head, "|" + "---|" * (len(FRAMEWORKS) + 3)]
    order = ["Window", "Layout", "Input", "Display", "Data", "Plugins"]
    specs = sorted(all_specs(), key=lambda s: (order.index(s.category), s.label.lower()))
    cat = None
    for s in specs:
        if s.category != cat:
            cat = s.category
            lines.append(f"| **{cat}** |" + " |" * (len(FRAMEWORKS) + 2))
        cells = ["yes" if s.supports(f) else "-" for f in FRAMEWORKS]
        pkgs = sorted({p for f in FRAMEWORKS for p in s.requires.get(f, ())})
        extra = ", ".join(f"`{p}`" for p in pkgs) or ""
        lines.append(f"| {s.label} | `{s.type}` | " + " | ".join(cells) + f" | {extra} |")
    return "\n".join(lines)


def widget_properties() -> str:
    from py_vui.core.registry import all_specs

    out = []
    for s in sorted(all_specs(), key=lambda s: s.type):
        props = ", ".join(f"`{p.name}`" for p in s.props) or "-"
        events = ", ".join(f"`{e}`" for e in s.events) or "-"
        out.append(f"- **`{s.type}`**: props {props}; events {events}")
    return "\n".join(out)


BLOCKS = {"widget-matrix": widget_matrix, "widget-properties": widget_properties}


def render(text: str) -> str:
    for name, fn in BLOCKS.items():
        pattern = re.compile(
            rf"(<!-- BEGIN {name} -->\n).*?(\n<!-- END {name} -->)", re.DOTALL
        )
        if not pattern.search(text):
            msg = f"docs/frameworks.md is missing the {name!r} markers"
            raise SystemExit(msg)
        body = fn()
        text = pattern.sub(lambda m, b=body: m.group(1) + b + m.group(2), text)
    return text


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="fail if the doc is out of date")
    args = ap.parse_args(argv)
    old = DOC.read_text(encoding="utf-8")
    new = render(old)
    if args.check:
        if new != old:
            print("docs/frameworks.md is out of date; run: python tools/gen_docs.py")
            return 1
        return 0
    if new != old:
        DOC.write_text(new, encoding="utf-8")
        print(f"updated {DOC}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
