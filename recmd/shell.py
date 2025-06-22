from typing import Callable, Never, overload
from .command import Command
from .patcher import patch_function
from .shell_patch import patch_shell_arguments
from .template import Template, template_to_command


@overload
def sh[C: Callable](cmd: C) -> C: ...
@overload
def sh(cmd: str | list[str] | Template) -> Command[None, None, None]: ...
def sh(cmd: str | list[str] | Template | Callable):
    if Template is not Never and isinstance(cmd, Template):
        cmd = list(template_to_command(cmd))
    if isinstance(cmd, str | list):
        return Command(cmd)
    patch_function(cmd, patcher=patch_shell_arguments)
    return cmd


def shell(cmd: str | list[str] | Template):
    if Template is not Never and isinstance(cmd, Template):
        cmd = list(template_to_command(cmd))
    assert isinstance(cmd, list), "apply @sh to parent function"
    return cmd
