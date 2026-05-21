from __future__ import annotations

from dataclasses import dataclass

from py_vui.model.nodes import Node
from py_vui.model.project import py_vuiProject, validate_project


@dataclass
class ProjectDocument:
    project: py_vuiProject

    def validate(self) -> None:
        validate_project(self.project)

    def get_node(self, node_id: str) -> Node:
        return self.project.nodes[node_id]

    def children(self, parent_id: str) -> list[Node]:
        kids = [n for n in self.project.nodes.values() if n.parent_id == parent_id]
        return sorted(kids, key=lambda n: (n.z_index, n.id))

    def replace_project(self, project: py_vuiProject) -> None:
        self.project = project
