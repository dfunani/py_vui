"""py_vui core: registry-driven document model shared by the editor and all adapters."""

from py_vui.core import catalog as _catalog  # noqa: F401
from py_vui.core.document import (
    Diagnostic,
    ProjectDocument,
    make_node,
    new_project,
    validate_project,
)
from py_vui.core.model import (
    SCHEMA_VERSION,
    Box,
    ContainerLayout,
    HandlerDef,
    Node,
    Project,
)
from py_vui.core.registry import FRAMEWORKS, WidgetSpec, get_spec

__all__ = [
    "FRAMEWORKS", "SCHEMA_VERSION", "Box", "ContainerLayout", "Diagnostic", "HandlerDef",
    "Node", "Project", "ProjectDocument", "WidgetSpec", "get_spec", "make_node",
    "new_project", "validate_project",
]
