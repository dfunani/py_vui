from __future__ import annotations
from collections import deque
from datetime import date
from uuid import UUID
from pydantic import BaseModel, ConfigDict, model_validator

from py_vui.models.nodes import Node, WindowNodeType
from py_vui.models.schema import ADAPTER_ID, AdapterID, SCHEMA_VERSION, SchemaVersion


class PrjoectMetaData(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: str
    created_at: date
    updated_at: date


class py_vuiProject(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: SchemaVersion = SCHEMA_VERSION
    meta: PrjoectMetaData
    adapter: AdapterID = ADAPTER_ID
    root_id: UUID
    nodes: list[Node]

    @model_validator(mode="after")
    def validate_nodes(self) -> py_vuiProject:
        # Validate the nodes
        nodes_hash_set = self.get_nodes_hash_set()
        self.validate_root_id(nodes_hash_set)

        # Validate the roots
        roots = self.get_roots()
        self.validate_roots(roots)
        self.validate_nodes_references(nodes_hash_set)
        self.validate_nodes_cycles(nodes_hash_set)

        return self

    def validate_root_id(self, nodes_hash_set: set[UUID]) -> None:
        if self.root_id not in nodes_hash_set:
            raise ValueError(f"root_id {self.root_id} not found in nodes")

    def validate_roots(self, roots: list[Node]) -> None:
        if len(roots) != 1:
            raise ValueError(f"expected exactly one root, got {len(roots)}: {roots!r}")

        root = roots[0]
        if root.id != self.root_id:
            raise ValueError(
                f"root_id {self.root_id} must be the only node with parent_id None"
            )

        if root.type != WindowNodeType:
            raise ValueError(f"root node must be type 'window', got {root.type!r}")

    def validate_nodes_references(self, nodes_hash_set: set[UUID]) -> None:
        for node in self.nodes:
            if node.parent_id and node.parent_id not in nodes_hash_set:
                raise ValueError(
                    f"node {node.id} references missing parent {node.parent_id}"
                )

    def validate_nodes_cycles(self, nodes_hash_set: set[UUID]) -> None:
        queued_node_ids: set[UUID] = set()
        de_queue: deque[UUID] = deque([self.root_id])
        while de_queue:
            current_node_id = de_queue.popleft()
            if current_node_id in queued_node_ids:
                msg = f"cycle detected at {current_node_id!r}"
                raise ValueError(msg)

            queued_node_ids.add(current_node_id)
            for node in self.nodes:
                if node.parent_id == current_node_id:
                    de_queue.append(node.id)

        if queued_node_ids != nodes_hash_set:
            orphan_node_ids = nodes_hash_set - queued_node_ids
            msg = f"orphan nodes not reachable from root: {sorted(orphan_node_ids)!r}"
            raise ValueError(msg)

    def get_node(self, node_id: UUID) -> Node:
        return next(node for node in self.nodes if node.id == node_id)

    def get_children(self, parent_id: UUID) -> list[Node]:
        return [node for node in self.nodes if node.parent_id == parent_id]

    def get_roots(self) -> list[Node]:
        return [node for node in self.nodes if node.parent_id is None]

    def get_nodes_map(self) -> dict[UUID, Node]:
        return {node.id: node for node in self.nodes}

    def get_nodes_hash_set(self) -> set[UUID]:
        return {node.id for node in self.nodes}

    def get_node_index(self, node_id: UUID) -> int:
        node = self.get_node(node_id)
        if node.parent_id is None:
            return -1
        return self.nodes.index(node)
