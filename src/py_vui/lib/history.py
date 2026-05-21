from typing import Literal

from pydantic import BaseModel
from py_vui.commands import Command
from py_vui.models.project import py_vuiProject

CommandType = Literal["add", "undo", "redo"]


class CommandWrapper(BaseModel):
    type: CommandType
    command: Command


class History:
    _project: py_vuiProject

    def __init__(self, project: py_vuiProject, max_depth: int = 100):
        self._project = project
        self._max_depth = max_depth
        self._commands: list[CommandWrapper] = []
        self._undo_stack: list[Command] = []
        self._redo_stack: list[Command] = []

    def add(self, command: Command):
        command.apply(self._project)

        self._add_command("add", command)

        self._undo_stack.append(command)
        self._redo_stack.clear()

    def undo(self):
        if not self._undo_stack:
            raise ValueError("No more commands to undo")

        command = self._undo_stack.pop()
        command.revert(self._project)

        self._add_command("undo", command)

        self._redo_stack.append(command)

    def redo(self):
        if not self._redo_stack:
            return

        command = self._redo_stack.pop()
        command.apply(self._project)

        self._add_command("redo", command)

        self._undo_stack.append(command)

    def _add_command(self, command_type: CommandType, command: Command):
        self._commands.append(
            CommandWrapper(
                type=command_type,
                command=command,
            )
        )
