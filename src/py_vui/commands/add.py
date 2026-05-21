from py_vui.commands import Command
from py_vui.models.nodes import Node
from py_vui.models.project import py_vuiProject


class AddNode(Command):
    node: Node

    def apply(self, project: py_vuiProject) -> None:
        nodes_hash_set = project.get_nodes_hash_set()
        if self.node.id in nodes_hash_set:
            raise ValueError(f"duplicate node id {self.node.id!r}")

        if (
            self.node.parent_id is not None
            and self.node.parent_id not in nodes_hash_set
        ):
            raise ValueError(f"missing parent {self.node.parent_id!r}")

        node_index = project.get_node_index(self.node.id)
        project.nodes[node_index] = self.node

    def revert(self, project: py_vuiProject) -> None:
        node_index = project.get_node_index(self.node.id)
        del project.nodes[node_index]
