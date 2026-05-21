from py_vui.commands import Command
from py_vui.models.nodes import Node
from py_vui.models.project import py_vuiProject
from py_vui.models.geometry import Rectangle


class SetNodeLayout(Command):
    node: Node
    new_layout: Rectangle
    _old_layout: Rectangle | None = None

    def apply(self, project: py_vuiProject) -> None:
        if self.node not in project.nodes:
            raise ValueError(f"missing node {self.node.id!r}")

        self._old_layout = self.node.layout.box.model_copy(deep=True)
        self.node.layout.box = self.new_layout
        node_index = project.get_node_index(self.node.id)
        project.nodes[node_index] = self.node

    def revert(self, project: py_vuiProject) -> None:
        if self.node not in project.nodes:
            raise ValueError(f"missing node {self.node.id!r}")
        if self._old_layout is None:
            raise ValueError("SetNodeLayout not applied")

        self.node.layout.box = self._old_layout
        node_index = project.get_node_index(self.node.id)
        project.nodes[node_index] = self.node
