from __future__ import annotations

import json
from typing import Any

from PySide6.QtCore import QMimeData
from PySide6.QtWidgets import QApplication

from py_vui.commands.builtins import collect_subtree_ids
from py_vui.model.document import ProjectDocument
from py_vui.model.nodes import Node

MIME_SUBTREE = "application/x-py-vui-subtree"


def copy_subtree_to_clipboard(doc: ProjectDocument, root_id: str) -> bool:
    if root_id == doc.project.root_id:
        return False
    ids = collect_subtree_ids(doc, root_id)
    payload: dict[str, Any] = {
        "nodes": {
            nid: doc.project.nodes[nid].model_dump(mode="json", by_alias=True)
            for nid in ids
        },
        "rootId": root_id,
    }
    mime = QMimeData()
    mime.setData(MIME_SUBTREE, json.dumps(payload).encode("utf-8"))
    QApplication.clipboard().setMimeData(mime)
    return True


def read_subtree_from_clipboard() -> dict[str, Node] | None:
    mime = QApplication.clipboard().mimeData()
    if not mime.hasFormat(MIME_SUBTREE):
        return None
    raw = json.loads(bytes(mime.data(MIME_SUBTREE)).decode("utf-8"))
    nodes_raw: dict[str, Any] = raw["nodes"]
    from py_vui.model.nodes import (
        ButtonNode,
        CheckboxNode,
        ComboBoxNode,
        FrameNode,
        GroupBoxNode,
        LabelNode,
        LineEditNode,
        ListWidgetNode,
        ProgressBarNode,
        RadioButtonNode,
        ScrollAreaNode,
        SliderNode,
        SpinBoxNode,
        TabWidgetNode,
        TextEditNode,
        WindowNode,
    )

    type_map: dict[str, type[Node]] = {
        "window": WindowNode,
        "frame": FrameNode,
        "label": LabelNode,
        "button": ButtonNode,
        "line_edit": LineEditNode,
        "checkbox": CheckboxNode,
        "combo_box": ComboBoxNode,
        "text_edit": TextEditNode,
        "radio_button": RadioButtonNode,
        "spin_box": SpinBoxNode,
        "slider": SliderNode,
        "list_widget": ListWidgetNode,
        "group_box": GroupBoxNode,
        "tab_widget": TabWidgetNode,
        "progress_bar": ProgressBarNode,
        "scroll_area": ScrollAreaNode,
    }
    out: dict[str, Node] = {}
    for nid, data in nodes_raw.items():
        cls = type_map[data["type"]]
        out[nid] = cls.model_validate(data)
    return out
