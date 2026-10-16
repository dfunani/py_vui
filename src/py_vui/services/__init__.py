"""Non-UI services: project lifecycle, templates, recent files, settings, runtime."""

from py_vui.services.project_service import ProjectService, RunSpec
from py_vui.services.recent import RecentProjects
from py_vui.services.templates import TemplateInfo, list_templates, load_template

__all__ = [
    "ProjectService", "RecentProjects", "RunSpec", "TemplateInfo", "list_templates",
    "load_template",
]
