from __future__ import annotations

import re

BEGIN = "# py_vui: begin custom"
END = "# py_vui: end custom"


def wrap_custom_block(body: str, *, indent: str = "") -> str:
    lines = [f"{indent}{BEGIN}", body.rstrip(), f"{indent}{END}"]
    return "\n".join(lines) + "\n"


def extract_custom_block(source: str, *, function_name: str | None = None) -> str | None:
    """Return text inside custom region for whole file or within a function."""
    if function_name:
        pattern = (
            rf"def {re.escape(function_name)}\([^)]*\)[^:]*:\n"
            rf"(?:.*?\n)*?"
            rf"(\s*{re.escape(BEGIN)}\n.*?\n\s*{re.escape(END)})"
        )
        match = re.search(pattern, source, re.DOTALL)
        if match:
            block = match.group(1)
            return _strip_markers(block)
        return None
    match = re.search(
        rf"{re.escape(BEGIN)}\n(.*?\n){re.escape(END)}",
        source,
        re.DOTALL,
    )
    if not match:
        return None
    return match.group(1).rstrip() + "\n"


def _strip_markers(block: str) -> str:
    lines = []
    for line in block.splitlines():
        stripped = line.strip()
        if stripped in (BEGIN, END):
            continue
        lines.append(line)
    return "\n".join(lines).rstrip() + "\n" if lines else ""


def merge_function_body(
    existing_source: str | None,
    function_name: str,
    new_body: str,
    *,
    default_body: str = "pass",
) -> str:
    preserved = None
    if existing_source:
        preserved = extract_custom_block(existing_source, function_name=function_name)
    body = preserved if preserved else new_body.strip() or default_body
    indented = "\n".join("    " + ln if ln.strip() else "    pass" for ln in body.splitlines())
    return (
        f"def {function_name}() -> None:\n"
        f"    {BEGIN}\n"
        f"{indented}\n"
        f"    {END}\n"
    )
