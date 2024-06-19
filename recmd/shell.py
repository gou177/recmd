from typing import Callable, overload
from .command import Command
from .patcher import patch_function
from .shell_patch import patch_shell_arguments


@overload
def sh[C: Callable](cmd: C) -> C: ...
@overload
def sh(cmd: str | list[str]) -> Command[None, None, None]: ...
def sh(cmd: str | list[str] | Callable):
    if isinstance(cmd, str | list):
        return Command(cmd)
    patch_function(cmd, patcher=patch_shell_arguments)
    return cmd


def shell(cmd: str | list[str]):
    assert isinstance(cmd, list), "apply @sh to parent function"
    return cmd
