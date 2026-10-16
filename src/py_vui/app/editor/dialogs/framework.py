"""Target-framework chooser with a compatibility report, and the requirements dialog."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QRadioButton,
    QWidget,
)

from py_vui.app.editor.code_tabs import RequirementsEditor
from py_vui.app.editor.dialogs.common import (
    FRAMEWORK_INFO,
    add_buttons,
    make_dialog_base,
    supported_count,
)
from py_vui.app.editor.dialogs.framework_facts import facts_for, project_caveats
from py_vui.commands import History, SetProjectAttr
from py_vui.core.document import ProjectDocument
from py_vui.core.registry import FRAMEWORKS


def compatibility_report(doc: ProjectDocument, framework: str) -> list[str]:
    """Problems that really apply to generating ``doc`` for ``framework`` (adapter-derived)."""
    return project_caveats(doc, framework)


class FrameworkDialog(QDialog):
    def __init__(self, doc: ProjectDocument, history: History, parent: QWidget | None = None,
                 ) -> None:
        super().__init__(parent)
        self.doc, self.history = doc, history
        self.framework = doc.project.framework
        lay = make_dialog_base(self, "Target framework", (520, 460))
        self._radios: dict[str, QRadioButton] = {}
        for fw in FRAMEWORKS:
            label, desc = FRAMEWORK_INFO[fw]
            ok, total = supported_count(fw)
            rb = QRadioButton(f"{label} - {ok}/{total} widgets")
            rb.setToolTip(desc)
            rb.setChecked(fw == self.framework)
            rb.toggled.connect(lambda on, f=fw: on and self.select(f))
            lay.addWidget(rb)
            lay.addWidget(self._hint(desc))
            self._radios[fw] = rb
        lay.addWidget(QLabel("Compatibility report"))
        self.report = QListWidget()
        lay.addWidget(self.report, 1)
        lay.addWidget(QLabel("How this generator behaves"))
        self.facts = QListWidget()
        self.facts.setWordWrap(True)
        lay.addWidget(self.facts, 1)
        add_buttons(self, lay)
        self._fill()

    @staticmethod
    def _hint(text: str) -> QLabel:
        lb = QLabel(text)
        lb.setEnabled(False)
        lb.setContentsMargins(22, 0, 0, 4)
        return lb

    def select(self, fw: str) -> None:
        self.framework = fw
        self._radios[fw].setChecked(True)
        self._fill()

    def _fill(self) -> None:
        self.report.clear()
        lines = compatibility_report(self.doc, self.framework)
        if not lines:
            self.report.addItem("Everything in this project is supported.")
        for ln in lines:
            self.report.addItem(ln)
        self.facts.clear()
        for fact in facts_for(self.framework):
            self.facts.addItem(fact.text)

    def accept(self) -> None:
        if self.framework != self.doc.project.framework:
            cmd = SetProjectAttr("framework", self.framework, label=f"Framework: {self.framework}")
            cmd.merge_key = None
            self.history.push(self.doc, cmd)
        super().accept()


class RequirementsDialog(QDialog):
    def __init__(self, doc: ProjectDocument, history: History, parent: QWidget | None = None,
                 ) -> None:
        super().__init__(parent)
        lay = make_dialog_base(self, "Requirements", (480, 440))
        self.editor = RequirementsEditor()
        self.editor.bind(doc, history, None)
        lay.addWidget(self.editor)
        add_buttons(self, lay, QDialogButtonBox.StandardButton.Close)
