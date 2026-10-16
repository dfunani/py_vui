"""Selection-level editing operations. Pure functions: they build Commands, never mutate."""

from __future__ import annotations

from PySide6.QtCore import QMimeData
from PySide6.QtWidgets import QApplication

from py_vui.app.editor.canvas_geometry import abs_rect, content_origin, current_page, is_paged
from py_vui.commands import (
    AddNodes,
    Batch,
    Command,
    RemoveSubtree,
    ReorderChildren,
    ReparentNode,
    SetAttr,
    build_paste,
    copy_nodes,
)
from py_vui.commands.clipboard import CLIPBOARD_MIME
from py_vui.core.document import ProjectDocument, make_node
from py_vui.core.model import Box
from py_vui.core.registry import get_spec

WRAP_TYPES = ("frame", "label_frame", "scroll_frame", "tabview", "paned_window")


def top_level_ids(doc: ProjectDocument, ids: list[str]) -> list[str]:
    """Selected ids without windows and without nodes whose ancestor is also selected."""
    sel = set(ids)
    out = []
    for i in ids:
        if i not in doc.project.nodes:
            continue
        if doc.get_node(i).type in ("window", "toplevel"):
            continue
        if any(a.id in sel for a in doc.ancestors(i)):
            continue
        out.append(i)
    return out


# ---------------------------------------------------------------------------- delete / copy
def delete_command(doc: ProjectDocument, ids: list[str]) -> Command | None:
    tops = [i for i in top_level_ids(doc, ids) if not _locked_chain(doc, i)]
    if not tops:
        return None
    label = (
        f"Delete {doc.get_node(tops[0]).name}" if len(tops) == 1 else f"Delete {len(tops)} widgets"
    )
    return Batch([RemoveSubtree(i, label=label) for i in tops], label=label)


def _locked_chain(doc: ProjectDocument, node_id: str) -> bool:
    return doc.get_node(node_id).locked


def copy_to_clipboard(doc: ProjectDocument, ids: list[str]) -> bool:
    tops = top_level_ids(doc, ids)
    if not tops:
        return False
    payload = copy_nodes(doc, tops)
    mime = QMimeData()
    mime.setData(CLIPBOARD_MIME, payload.encode())
    mime.setText(payload)
    QApplication.clipboard().setMimeData(mime)
    return True


def clipboard_payload() -> str | None:
    mime = QApplication.clipboard().mimeData()
    if mime is None:
        return None
    if mime.hasFormat(CLIPBOARD_MIME):
        return bytes(mime.data(CLIPBOARD_MIME)).decode()
    text = mime.text() if mime.hasText() else ""
    return text if text.startswith('{"py_vui"') else None


def paste_command(
    doc: ProjectDocument, target_parent_id: str, payload: str | None = None
) -> tuple[Command, list[str]] | None:
    payload = payload or clipboard_payload()
    if not payload:
        return None
    try:
        cmd, new_ids = build_paste(doc, payload, target_parent_id)
    except (ValueError, KeyError):
        return None
    # pasted nodes go to the current tab page of a paged container
    parent = doc.get_node(target_parent_id)
    if is_paged(parent):
        page = current_page(parent)
        cmd = Batch(
            [cmd, *[SetAttr(i, "page", page, label="Paste") for i in new_ids]], label="Paste"
        )
    return cmd, new_ids


def paste_target(doc: ProjectDocument, selection: list[str], window_id: str) -> str:
    """Container that receives a paste: the selected container, else the selection's parent."""
    for i in reversed(selection):
        if i not in doc.project.nodes:
            continue
        n = doc.get_node(i)
        if get_spec(n.type).container:
            return n.id
        if n.parent_id:
            return n.parent_id
    return window_id


def duplicate_command(doc: ProjectDocument, ids: list[str]) -> tuple[Command, list[str]] | None:
    tops = top_level_ids(doc, ids)
    if not tops:
        return None
    by_parent: dict[str, list[str]] = {}
    for i in tops:
        by_parent.setdefault(doc.get_node(i).parent_id or doc.project.root_id, []).append(i)
    cmds: list[Command] = []
    new_ids: list[str] = []
    for parent, group in by_parent.items():
        res = paste_command(doc, parent, copy_nodes(doc, group))
        if res is None:
            continue
        cmds.append(res[0])
        new_ids.extend(res[1])
        # keep the duplicate on the same tab page as the original
        if is_paged(doc.get_node(parent)):
            for src, dst in zip(group, res[1], strict=False):
                cmds.append(SetAttr(dst, "page", doc.get_node(src).page, label="Duplicate"))
    if not cmds:
        return None
    return Batch(cmds, label="Duplicate"), new_ids


# ------------------------------------------------------------------------------ grouping
def group_command(
    doc: ProjectDocument, ids: list[str], container_type: str = "frame"
) -> tuple[Command, str] | None:
    """Wrap sibling widgets in a new container (Group in frame / Wrap in…)."""
    tops = top_level_ids(doc, ids)
    if not tops or container_type not in WRAP_TYPES:
        return None
    parents = {doc.get_node(i).parent_id for i in tops}
    if len(parents) != 1:
        return None
    parent_id = next(iter(parents))
    assert parent_id is not None
    parent = doc.get_node(parent_id)
    rects = {i: abs_rect(doc, doc.get_node(i)) for i in tops}
    pox, poy = abs_rect(doc, parent)[:2]
    cox, coy = content_origin(parent)
    ox, oy = pox + cox, poy + coy
    x0 = min(r[0] for r in rects.values()) - ox
    y0 = min(r[1] for r in rects.values()) - oy
    x1 = max(r[0] + r[2] for r in rects.values()) - ox
    y1 = max(r[1] + r[3] for r in rects.values()) - oy
    pad = 8.0
    spec = get_spec(container_type)
    first = doc.get_node(tops[0])
    frame = make_node(container_type, parent_id=parent_id, name=doc.unique_name(spec.label))
    inner_ox, inner_oy = content_origin(frame)
    frame.box = Box(
        x=round(x0 - pad),
        y=round(y0 - pad - inner_oy),
        w=round(x1 - x0 + 2 * pad + inner_ox),
        h=round(y1 - y0 + 2 * pad + inner_oy),
    )
    frame.page = first.page
    frame.cell = first.cell.model_copy()
    frame.flex = first.flex.model_copy(deep=True)
    if container_type == "tabview":
        frame.props["tabs"] = ["Tab 1"]
    sibs = [k.id for k in doc.children(parent_id)]
    at = min(sibs.index(i) for i in tops)
    top_z = max((doc.get_node(k).z_index for k in sibs), default=-1) + 1
    frame.z_index = top_z
    cmds: list[Command] = [AddNodes([frame], label="Group")]
    for k, i in enumerate(tops):
        r = rects[i]
        box = Box(
            x=round(r[0] - ox - frame.box.x - inner_ox),
            y=round(r[1] - oy - frame.box.y - inner_oy),
            w=doc.get_node(i).box.w,
            h=doc.get_node(i).box.h,
        )
        cmds.append(ReparentNode(i, frame.id, new_z_index=k, new_box=box, label="Group"))
        if doc.get_node(i).page != 0:
            cmds.append(SetAttr(i, "page", 0, label="Group"))
    order = [s for s in sibs if s not in tops]
    order.insert(min(at, len(order)), frame.id)
    cmds.append(ReorderChildren(order, label="Group"))
    return Batch(cmds, label=f"Wrap in {spec.label}"), frame.id


def ungroup_command(doc: ProjectDocument, frame_id: str) -> tuple[Command, list[str]] | None:
    frame = doc.get_node(frame_id)
    if frame.type in ("window", "toplevel") or not get_spec(frame.type).container:
        return None
    kids = doc.children(frame_id)
    if not kids or frame.parent_id is None:
        return None
    parent = doc.get_node(frame.parent_id)
    ox, oy = content_origin(frame)
    cmds: list[Command] = []
    sibs = [k.id for k in doc.children(parent.id)]
    at = sibs.index(frame_id)
    top = max((doc.get_node(k).z_index for k in sibs), default=-1) + 1
    for k, kid in enumerate(kids):
        box = Box(
            x=kid.box.x + frame.box.x + ox, y=kid.box.y + frame.box.y + oy, w=kid.box.w, h=kid.box.h
        )
        cmds.append(
            ReparentNode(kid.id, parent.id, new_z_index=top + k, new_box=box, label="Ungroup")
        )
        if kid.page != frame.page:
            cmds.append(
                SetAttr(kid.id, "page", frame.page if is_paged(parent) else 0, label="Ungroup")
            )
    cmds.append(RemoveSubtree(frame_id, label="Ungroup"))
    order = [s for s in sibs if s != frame_id]
    order[at:at] = [k.id for k in kids]
    cmds.append(ReorderChildren(order, label="Ungroup"))
    return Batch(cmds, label="Ungroup"), [k.id for k in kids]


# -------------------------------------------------------------------------------- z-order
def z_order_command(doc: ProjectDocument, ids: list[str], mode: str) -> Command | None:
    """front / back / forward / backward for several siblings at once."""
    tops = top_level_ids(doc, ids)
    by_parent: dict[str, list[str]] = {}
    for i in tops:
        by_parent.setdefault(doc.get_node(i).parent_id or "", []).append(i)
    cmds: list[Command] = []
    for parent, group in by_parent.items():
        order = [k.id for k in doc.children(parent)]
        sel = set(group)
        new = list(order)
        if mode == "front":
            new = [i for i in order if i not in sel] + [i for i in order if i in sel]
        elif mode == "back":
            new = [i for i in order if i in sel] + [i for i in order if i not in sel]
        elif mode == "forward":
            for idx in range(len(new) - 2, -1, -1):
                if new[idx] in sel and new[idx + 1] not in sel:
                    new[idx], new[idx + 1] = new[idx + 1], new[idx]
        elif mode == "backward":
            for idx in range(1, len(new)):
                if new[idx] in sel and new[idx - 1] not in sel:
                    new[idx], new[idx - 1] = new[idx - 1], new[idx]
        if new != order:
            cmds.append(
                ReorderChildren(
                    new, label=f"Bring {mode}" if mode in ("front", "forward") else f"Send {mode}"
                )
            )
    if not cmds:
        return None
    label = {
        "front": "Bring to front",
        "back": "Send to back",
        "forward": "Bring forward",
        "backward": "Send backward",
    }[mode]
    return Batch(cmds, label=label)
