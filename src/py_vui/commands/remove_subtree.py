from collections import deque
from uuid import UUID
from py_vui.commands import Command
from py_vui.models.nodes import Node
from py_vui.models.project import py_vuiProject


def _collect_subtree(project: py_vuiProject, node: Node) -> set[Node]:
    subtree: set[Node] = set([node])
    stack = deque([node])
    while stack:
        current_node = stack.popleft()
        subtree.add(current_node)
        for child in project.get_children(current_node.id):
            stack.append(child)
    return subtree


def _remove_nodes(project: py_vuiProject, nodes: set[Node]) -> None:
    for node in nodes:
        project.nodes.remove(node)


class RemoveSubtree(Command):
    node: Node
    _removed: set[Node] | None = None

    def apply(self, project: py_vuiProject) -> None:
        if not self.node.parent_id or self.node.parent_id == project.root_id:
            raise ValueError("cannot remove project root subtree")
        if self.node not in project.nodes:
            raise ValueError(f"missing node {self.node.id!r}")

        subtree = _collect_subtree(project, self.node)
        self._removed = subtree
        _remove_nodes(project, self._removed)

    def revert(self, project: py_vuiProject) -> None:
        if not self._removed:
            raise ValueError("RemoveSubtree not applied")

        for node in self._removed:
            project.nodes.append(node)

        self._removed = None
