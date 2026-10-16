"""handlers.py rendering with user-code regions that survive regeneration."""

from __future__ import annotations

import re
import textwrap

from py_vui.core.model import Project

BEGIN = "# py_vui: begin custom"
END = "# py_vui: end custom"
MODULE_BEGIN = "# py_vui: begin module"
MODULE_END = "# py_vui: end module"

_DEF_RE = re.compile(r"^def (\w+)\(event=None\):\n", re.MULTILINE)


def _region(source: str, begin: str, end: str, start: int = 0, stop: int | None = None) -> str | None:
    seg = source[start:stop]
    m = re.search(rf"^[ \t]*{re.escape(begin)}\n(.*?)^[ \t]*{re.escape(end)}", seg, re.S | re.M)
    return m.group(1) if m else None


def parse_handler_bodies(source: str) -> dict[str, str]:
    """Extract ``{handler_name: body}`` from a previously generated handlers.py."""
    out: dict[str, str] = {}
    matches = list(_DEF_RE.finditer(source))
    for i, m in enumerate(matches):
        stop = matches[i + 1].start() if i + 1 < len(matches) else None
        body = _region(source, BEGIN, END, m.end(), stop)
        if body is not None:
            out[m.group(1)] = textwrap.dedent(body).rstrip() or "pass"
    return out


def parse_module_code(source: str) -> str | None:
    body = _region(source, MODULE_BEGIN, MODULE_END)
    return textwrap.dedent(body).rstrip() if body is not None else None


def render_handler(name: str, body: str) -> str:
    body = textwrap.dedent(body).rstrip() or "pass"
    indented = textwrap.indent(body, "    ")
    return f"def {name}(event=None):\n    {BEGIN}\n{indented}\n    {END}\n"


def render_handlers_module(project: Project, existing: str | None = None) -> str:
    bodies = parse_handler_bodies(existing) if existing else {}
    module = (parse_module_code(existing) if existing else None) or project.custom_code
    parts = [
        '"""Event handlers. Edit between the py_vui markers; they are kept on regeneration."""',
        "",
        MODULE_BEGIN,
        module.rstrip(),
        MODULE_END,
        "",
    ]
    for name in sorted(project.handlers):
        h = project.handlers[name]
        parts.append("")
        parts.append(render_handler(name, bodies.get(name, h.body)))
    return "\n".join(parts).rstrip() + "\n"


def sync_handlers_from_source(project: Project, source: str) -> int:
    """Pull edited handler bodies / module code from handlers.py into the project."""
    changed = 0
    for name, body in parse_handler_bodies(source).items():
        h = project.handlers.get(name)
        if h is not None and h.body.strip() != body.strip():
            h.body = body
            changed += 1
    module = parse_module_code(source)
    if module is not None and module.strip() != project.custom_code.strip():
        project.custom_code = module
        changed += 1
    return changed
