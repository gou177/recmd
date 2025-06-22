from contextlib import suppress
from .exceptions import TransformError
from .patcher import (
    patch_function,
    apply_patch,
    AnyFunctionDef,
    line_attributes,
    get_ast,
)
from .shell_patch import patch_shell_arguments
from .executor.abc import SyncExecutor, AsyncExecutor
from .shell import sh, shell
from .stream import Capture, DevNull, FileStream, IOStream, Send, Stream, Pipe
from .executor.subprocess import SubprocessExecutor

SyncExecutor.set_default(SubprocessExecutor())

with suppress(ImportError):
    from .executor.anyio import AnyioExecutor

    AsyncExecutor.set_default(AnyioExecutor())

__all__ = [
    "TransformError",
    "patch_function",
    "apply_patch",
    "AnyFunctionDef",
    "line_attributes",
    "get_ast",
    "patch_shell_arguments",
    "SyncExecutor",
    "AsyncExecutor",
    "AnyioExecutor",
    "SubprocessExecutor",
    "sh",
    "shell",
    "Capture",
    "DevNull",
    "FileStream",
    "IOStream",
    "Send",
    "Stream",
    "Pipe",
]
