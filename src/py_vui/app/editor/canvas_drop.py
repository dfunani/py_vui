"""Drop planning: where a widget lands inside a container (absolute / flex / grid / tab page)
and the commands that perform an add or a move. Used by palette drops, drags and paste."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF

from py_vui.app.editor.canvas_commands import MergeableBoxes, new_drag_key
from py_vui.app.editor.canvas_geometry import (
    abs_origin,
    content_origin,
    content_size,
    current_page,
    grid_geometry,
    is_paged,
    tab_at,
)
from py_vui.commands import (
    AddNodes,
    Batch,
    Command,
    ReorderChildren,
    ReparentNode,
    SetAttr,
    SetField,
)
from py_vui.core.document import ProjectDocument
from py_vui.core.layout_engine import resolve_children
from py_vui.core.model import Box, GridCell, Node


@dataclass
class DropPlan:
    container_id: str
    mode: str = "absolute"  # absolute | flex | grid
    #: container-content relative top-left for absolute placement
    box: Box | None = None
    index: int | None = None
    cell: GridCell | None = None
    page: int = 0
    #: tab header hovered while dragging: switch the editing page to this tab on commit
    switch_page: int | None = None
    # --- overlay hints (scene coordinates)
    target_rect: QRectF | None = None
    insertion: tuple[QPointF, QPointF] | None = None
    cell_rect: QRectF | None = None


def container_mode(container: Node) -> str:
    if container.layout is None or is_paged(container):
        return "absolute"
    return container.layout.mode


def content_origin_abs(doc: ProjectDocument, container: Node) -> tuple[float, float]:
    ax, ay = abs_origin(doc, container)
    ox, oy = content_origin(container)
    return ax + ox, ay + oy


def plan_in_container(
    doc: ProjectDocument,
    container: Node,
    scene_pt: QPointF,
    size: tuple[float, float],
    grab: tuple[float, float] | None = None,
    exclude: set[str] | None = None,
) -> DropPlan:
    """Plan a drop at ``scene_pt``. ``grab`` is the cursor offset inside the dragged box
    (defaults to its centre)."""
    exclude = exclude or set()
    ox, oy = content_origin_abs(doc, container)
    cw, ch = content_size(doc, container)
    lx, ly = scene_pt.x() - ox, scene_pt.y() - oy
    mode = container_mode(container)
    plan = DropPlan(container.id, mode, target_rect=QRectF(ox, oy, cw, ch))

    if is_paged(container):
        ax, ay = abs_origin(doc, container)
        cur = current_page(container)
        hit = tab_at(container, scene_pt.x() - ax, scene_pt.y() - ay)
        plan.page = cur if hit is None else hit
        if hit is not None and hit != cur:
            plan.switch_page = hit
    gx, gy = grab if grab is not None else (size[0] / 2, size[1] / 2)

    if mode == "absolute":
        plan.box = Box(x=lx - gx, y=ly - gy, w=size[0], h=size[1])
    elif mode == "flex":
        _plan_flex(doc, container, plan, lx, ly, ox, oy, exclude)
    else:
        gg = grid_geometry(doc, container, extra_cells=1)
        row, col = gg.cell_at(lx, ly)
        plan.cell = GridCell(row=row, column=col)
        cx, cy, cwid, chei = gg.cell_rect(row, col)
        plan.cell_rect = QRectF(ox + cx, oy + cy, cwid, chei)
    return plan


def _plan_flex(
    doc: ProjectDocument,
    container: Node,
    plan: DropPlan,
    lx: float,
    ly: float,
    ox: float,
    oy: float,
    exclude: set[str],
) -> None:
    layout = container.layout
    assert layout is not None
    row = layout.direction == "row"
    boxes = resolve_children(doc, container.id)
    sibs = [k for k in doc.children(container.id) if k.visible and k.id not in exclude]

    def precedes(b: Box) -> bool:
        if layout.wrap:
            if (b.y + b.h) < ly if row else (b.x + b.w) < lx:
                return True
            if (b.y <= ly <= b.y + b.h) if row else (b.x <= lx <= b.x + b.w):
                return (b.x + b.w / 2 < lx) if row else (b.y + b.h / 2 < ly)
            return False
        return (b.x + b.w / 2 < lx) if row else (b.y + b.h / 2 < ly)

    index = sum(1 for s in sibs if precedes(boxes.get(s.id, s.box)))
    plan.index = index
    cw, ch = content_size(doc, container)
    gap = layout.gap / 2
    if sibs:
        if index < len(sibs):
            b = boxes.get(sibs[index].id, sibs[index].box)
            pos = (b.x - gap) if row else (b.y - gap)
            span = (b.y, b.y + b.h) if row else (b.x, b.x + b.w)
        else:
            b = boxes.get(sibs[-1].id, sibs[-1].box)
            pos = (b.x + b.w + gap) if row else (b.y + b.h + gap)
            span = (b.y, b.y + b.h) if row else (b.x, b.x + b.w)
    else:
        pad = layout.padding
        pos = pad.left if row else pad.top
        span = (pad.top, ch - pad.bottom) if row else (pad.left, cw - pad.right)
    if row:
        plan.insertion = (QPointF(ox + pos, oy + span[0]), QPointF(ox + pos, oy + span[1]))
    else:
        plan.insertion = (QPointF(ox + span[0], oy + pos), QPointF(ox + span[1], oy + pos))


def _top_z(doc: ProjectDocument, container_id: str) -> int:
    kids = doc.children(container_id)
    return (max((k.z_index for k in kids), default=-1)) + 1


def add_command(doc: ProjectDocument, node: Node, plan: DropPlan, label: str = "") -> Command:
    """Command that inserts ``node`` (parent/box/page/cell are filled in from the plan)."""
    container = doc.get_node(plan.container_id)
    node.parent_id = container.id
    node.page = plan.page if is_paged(container) else 0
    node.z_index = _top_z(doc, container.id)
    if plan.mode == "absolute" and plan.box is not None:
        node.box = Box(x=round(plan.box.x), y=round(plan.box.y), w=node.box.w, h=node.box.h)
    if plan.mode == "grid" and plan.cell is not None:
        node.cell = plan.cell.model_copy()
    cmds: list[Command] = [AddNodes([node], label=label or f"Add {node.name}")]
    if plan.switch_page is not None:
        cmds.append(
            SetField(
                container.id,
                "props",
                "current",
                plan.switch_page,
                label="Switch tab",
                merge_key=new_drag_key("tab"),
            )
        )
    if plan.index is not None:
        order = [k.id for k in doc.children(container.id)]
        order.insert(min(plan.index, len(order)), node.id)
        cmds.append(ReorderChildren(order, label="Reorder"))
    return Batch(cmds, label=label or f"Add {node.name}")


def move_command(
    doc: ProjectDocument,
    ids: list[str],
    plan: DropPlan,
    new_boxes: dict[str, Box] | None = None,
    label: str = "Move",
) -> Command | None:
    """Command moving ``ids`` into ``plan``'s container (None when nothing would change)."""
    container = doc.get_node(plan.container_id)
    paged = is_paged(container)
    same_parent = all(doc.get_node(i).parent_id == container.id for i in ids)
    new_boxes = new_boxes or {}

    if same_parent and plan.mode == "absolute" and not paged and plan.switch_page is None:
        updates = [(i, new_boxes[i]) for i in ids if i in new_boxes]
        return MergeableBoxes(updates, label=label, merge_key=new_drag_key()) if updates else None

    cmds: list[Command] = []
    z = _top_z(doc, container.id)
    for k, i in enumerate(ids):
        node = doc.get_node(i)
        if node.parent_id != container.id:
            cmds.append(
                ReparentNode(
                    i,
                    container.id,
                    new_z_index=z + k,
                    new_box=new_boxes.get(i) if plan.mode == "absolute" else None,
                    label=label,
                )
            )
        elif plan.mode == "absolute" and i in new_boxes:
            cmds.append(MergeableBoxes([(i, new_boxes[i])], label=label, merge_key=new_drag_key()))
        page = plan.page if paged else 0
        if node.page != page:
            cmds.append(SetAttr(i, "page", page, label=label))
        if plan.mode == "grid" and plan.cell is not None:
            cell = plan.cell.model_copy(update={"column": plan.cell.column + k})
            cmds.append(SetAttr(i, "cell", cell, label=label))
    if plan.switch_page is not None:
        cmds.append(
            SetField(
                container.id,
                "props",
                "current",
                plan.switch_page,
                label="Switch tab",
                merge_key=new_drag_key("tab"),
            )
        )
    if plan.mode == "flex" and plan.index is not None:
        order = [k.id for k in doc.children(container.id) if k.id not in ids]
        at = min(plan.index, len(order))
        order[at:at] = ids
        if order != [k.id for k in doc.children(container.id)] or any(
            doc.get_node(i).parent_id != container.id for i in ids
        ):
            cmds.append(ReorderChildren(order, label=label))
    if not cmds:
        return None
    return Batch(cmds, label=label)
