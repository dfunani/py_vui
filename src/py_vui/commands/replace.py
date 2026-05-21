from py_vui.commands import Command
from py_vui.models.nodes import Node
from py_vui.models.project import py_vuiProject


class ReplaceNode(Command):
    node: Node
    new_node: Node

    def apply(self, project: py_vuiProject) -> None:
        if self.node.id != self.new_node.id:
            raise ValueError("node id mismatch")

        if self.node not in project.nodes:
            raise ValueError(f"missing node {self.node.id!r}")

        node_index = project.get_node_index(self.node.id)
        project.nodes[node_index] = self.new_node

    def revert(self, project: py_vuiProject) -> None:
        if self.new_node not in project.nodes:
            raise ValueError(f"missing node {self.new_node.id!r}")

        node_index = project.get_node_index(self.new_node.id)
        project.nodes[node_index] = self.node
