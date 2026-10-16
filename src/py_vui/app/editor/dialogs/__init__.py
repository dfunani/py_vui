"""Editor dialogs (all ``QDialog`` subclasses; callers use ``.exec()``)."""

from py_vui.app.editor.dialogs.assets import AssetManagerDialog
from py_vui.app.editor.dialogs.export import ExportDialog
from py_vui.app.editor.dialogs.framework import FrameworkDialog, RequirementsDialog
from py_vui.app.editor.dialogs.help_dialogs import AboutDialog, PreferencesDialog, ShortcutsDialog
from py_vui.app.editor.dialogs.menu_designer import MenuDesignerDialog
from py_vui.app.editor.dialogs.new_project import NewProjectDialog, TemplateGalleryDialog
from py_vui.app.editor.dialogs.plugins import PluginManagerDialog
from py_vui.app.editor.dialogs.theme_editor import ThemeEditorDialog

__all__ = [
    "AboutDialog",
    "AssetManagerDialog",
    "ExportDialog",
    "FrameworkDialog",
    "MenuDesignerDialog",
    "NewProjectDialog",
    "PluginManagerDialog",
    "PreferencesDialog",
    "RequirementsDialog",
    "ShortcutsDialog",
    "TemplateGalleryDialog",
    "ThemeEditorDialog",
]
