from py_vui.commands import Command
from py_vui.models.nodes import Node
from py_vui.models.project import py_vuiProject


def _is_descendant(project: py_vuiProject, node: Node, parent: Node) -> bool:
    if node.id == parent.id:
        return True
    for child in project.get_children(node.id):
        if _is_descendant(project, child, parent):
            return True
    return False


class NewParentNode(Command):
    node: Node
    new_parent: Node
    _node: Node | None = None

    def apply(self, project: py_vuiProject) -> None:
        if self.node.id == project.root_id:
            raise ValueError("cannot reparent root node")
        if self.new_parent not in project.nodes:
            raise ValueError("new parent node not found")
        if self.new_parent.id == self.node.id:
            raise ValueError("node already has this parent")
        if _is_descendant(project, self.node, self.new_parent):
            raise ValueError("cannot reparent a node into its own subtree")

        self._node = self.node.model_copy(deep=True)
        self.node = self.new_parent.model_copy(deep=True)

    def revert(self, project: py_vuiProject) -> None:
        if self._node is None:
            raise ValueError("NewParentNode not applied")

        self.node = self._node
        self._node = None
