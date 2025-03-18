from contextlib import AsyncExitStack, ExitStack
from pathlib import PurePath
from typing import IO, Any, Callable, Literal, Self, cast, overload

from .executor.abc import AsyncExecutor, SyncExecutor
from .map_result import ResultMapper
from .stream import Pipe, Capture, Send, Stream


AnyStream = str | int | PurePath | Stream | None | IO


class Command[IN: AnyStream, OUT: AnyStream, ERR: AnyStream]:
    running: "RunningCommand"
    """Should be populated by executor"""
    complete: "CompleteCommand"
    """Should be populated by executor"""
    stdin: IN
    stdout: OUT
    stderr: ERR

    def __init__(
        self,
        cmd: list[str] | str,
        stdin: IN = None,
        stdout: OUT = None,
        stderr: ERR = None,
        inherit_env: bool = True,
        env: dict[str, str] | None = None,
        options: dict[str, Any] | None = None,
    ) -> None:
        assert isinstance(cmd, list), (
            "apply @sh decorator to function containing this statement"
        )
        self.cmd = cmd
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.cwd = None
        self.inherit_env = inherit_env
        self.environment = env or {}
        self.options = options or {}

    def did_start(self):
        return hasattr(self, "running")

    def did_complete(self):
        return hasattr(self, "complete")

    def pid(self):
        assert self.did_start()
        return self.running.pid

    def status(self) -> ResultMapper[Self, Callable[[Self], int]]:
        return self.map().apply(lambda x: x.complete.status)

    @overload  # (Command[*, None, *])           -> ResultMapper[Command[*, Capture[str],   *], ..., str]
    def output[_PI: AnyStream, _PE: AnyStream](
        self: "Command[_PI, None, _PE]", to_string: Literal[True] = True
    ) -> ResultMapper[
        "Command[_PI,  Capture[str], _PE]",
        Callable[["Command[_PI, Capture[str], _PE]"], str],
    ]: ...
    @overload  # (Command[*, None, *], False)    -> ResultMapper[Command[*, Capture[bytes], *], ..., bytes]
    def output[_PI: AnyStream, _PE: AnyStream](
        self: "Command[_PI, None, _PE]", to_string: Literal[False]
    ) -> ResultMapper[
        "Command[_PI,  Capture[bytes], _PE]",
        Callable[["Command[_PI, Capture[bytes], _PE]"], bytes],
    ]: ...
    @overload  # (Command[*, Capture[str], *])   -> ResultMapper[Command[*, Capture[str],   *], ..., str]
    def output[_PI: AnyStream, _PE: AnyStream](
        self: "Command[_PI, Capture[str], _PE]",
    ) -> ResultMapper[
        "Command[_PI,  Capture, _PE]",
        Callable[["Command[_PI, Capture[str], _PE]"], str],
    ]: ...
    @overload  # (Command[*, Capture[bytes], *]) -> ResultMapper[Command[*, Capture[bytes], *], ..., bytes]
    def output[_PI: AnyStream, _PE: AnyStream](
        self: "Command[_PI, Capture[bytes], _PE]",
    ) -> ResultMapper[
        "Command[_PI,  Capture[bytes], _PE]",
        Callable[["Command[_PI, Capture[bytes], _PE]"], bytes],
    ]: ...
    @overload  # (Command[*, Capture[Any], *])   -> ResultMapper[Command[*, Capture[Any],   *], ..., bytes]
    def output[_PI: AnyStream, _PE: AnyStream](
        self: "Command[_PI, Capture, _PE]",
    ) -> ResultMapper[
        "Command[_PI,  Capture, _PE]", Callable[["Command[_PI, Capture, _PE]"], bytes]
    ]: ...

    def output[_PI: AnyStream, _PE: AnyStream](  # type: ignore
        self: "Command[_PI, Any, _PE]", to_string: bool = True
    ) -> ResultMapper[
        "Command[_PI,  Capture, _PE]", Callable[["Command[_PI, Capture, _PE]"], bytes]
    ]:
        if self.stdout is None:
            if to_string:
                self.stdout = Capture[str]()
            else:
                self.stdout = Capture[bytes]()
        else:
            assert isinstance(self.stdin, Capture)
        return self.map().apply(lambda x: x.stdout.get())  # type: ignore

    def send[_PO: AnyStream, _PE: AnyStream](
        self: "Command[None, _PO, _PE]", data: str | bytes
    ) -> "Command[Send, _PO, _PE]":
        assert self.stdin is None

        return self.with_stdin(Send(data))

    def run(self):
        if self.did_start():
            if self.did_complete():
                return self
            self.running.wait().run()
            return self
        with SyncExecutor.get().run(self):
            return self

    async def run_async(self):
        if self.did_start():
            if self.did_complete():
                return self
            await self.running.wait()
            return self
        async with AsyncExecutor.get().run(self):
            return self

    def map(self):
        return ResultMapper(self)

    def env(self, env: dict[str, str] = {}, **kwargs: str):
        self._assert_not_started()
        self.environment.update(env)
        self.environment.update(kwargs)
        return self

    def _assert_not_started(self):
        assert not self.did_start(), "Unable to change started command"

    def with_stdin[_PO: AnyStream, _PE: AnyStream, _NI: AnyStream](
        self: "Command[Any, _PO, _PE]", stdin: _NI
    ) -> "Command[_NI, _PO, _PE]":
        self._assert_not_started()
        self.stdin = stdin
        return self  # type: ignore

    def with_stdout[_PI: AnyStream, _PE: AnyStream, _NO: AnyStream](
        self: "Command[_PI, Any, _PE]", stdout: _NO
    ) -> "Command[_PI, _NO, _PE]":
        self._assert_not_started()
        self.stdout = stdout
        return self  # type: ignore

    def with_stderr[_PI: AnyStream, _PO: AnyStream, _NE: AnyStream](
        self: "Command[_PI, _PO, Any]", stderr: _NE
    ) -> "Command[_PI, _PO, _NE]":
        self._assert_not_started()
        self.stderr = stderr
        return self  # type: ignore

    def with_cwd(self, cwd: str | PurePath | None):
        self.cwd = cwd
        return self

    def with_options(self, options: dict = {}, **kwargs):
        self.options.update(options)
        self.options.update(kwargs)
        return self

    def __rshift__[_PI: AnyStream, _PE: AnyStream, _NO: AnyStream](
        self: "Command[_PI, None, _PE]", stdout: _NO
    ) -> "Command[_PI, _NO, _PE]":
        return self.with_stdout(stdout)

    def __rrshift__[_PO: AnyStream, _PE: AnyStream, _NI: AnyStream](
        self: "Command[None, _PO, _PE]", stdin: _NI
    ) -> "Command[_NI, _PO, _PE]":
        return self.with_stdin(stdin)  # type: ignore

    def __ge__[_PI: AnyStream, _PO: AnyStream, _NE: AnyStream](
        self: "Command[_PI, _PO, None]", stderr: _NE
    ) -> "Command[_PI, _PO, _NE]":
        return self.with_stderr(stderr)  # type: ignore

    def copy(self):
        copy = type(self)(self.cmd)
        copy.__dict__ = self.__dict__.copy()
        return copy

    def __invert__(self):
        return self.run()

    def __await__(self):
        return self.run_async().__await__()

    def __or__[_PI: AnyStream, _PE: AnyStream, _NO: AnyStream, _NE: AnyStream](
        self: "Command[_PI, None, _PE]", value: "Command[None, _NO, _NE]"
    ) -> "CommandGroup[Command[_PI, Pipe, _PE], Command[Pipe, _NO, _NE]]":
        pipe = Pipe()
        return CommandGroup(self.with_stdout(pipe), value.with_stdin(pipe))

    def __and__[C: "Command"](self, value: C) -> "CommandGroup[Self, C]":
        return CommandGroup(self, value)

    def __bool__(self):
        if not self.did_complete():
            executor = SyncExecutor.context.get(None)
            if executor is None or not executor.implicit_start:
                raise RuntimeError(
                    "Unable to determine process status because process did not start and implicit_start is disabled"
                )
            self.run()
        return self.complete.status == 0

    def __enter__(self):
        self._ctx = SyncExecutor.get().run(self)
        self._ctx.__enter__()

        return self

    def __exit__(self, *args):
        self._ctx.__exit__(*args)

    async def __aenter__(self):
        self._actx = AsyncExecutor.get().run(self)
        await self._actx.__aenter__()

        return self

    async def __aexit__(self, *args):
        await self._actx.__aexit__(*args)


class RunningCommand:
    def __init__(self, pid: int, process: Any) -> None:
        self.pid = pid
        self._process = process

    def kill(self):
        return ResultMapper(self._process, no_run=True).apply(lambda x: x.kill())

    def terminate(self):
        return ResultMapper(self._process, no_run=True).apply(lambda x: x.terminate())

    def poll(self):
        return ResultMapper(self._process, no_run=True).apply(
            lambda x: cast(int | None, x.poll())
        )

    def wait(self):
        return ResultMapper(self._process, no_run=True).apply(
            lambda x: cast(int | None, x.wait())
        )


class CompleteCommand:
    def __init__(self, status: int) -> None:
        self.status = status


class CommandGroup[*C]:
    def __init__(self, *commands: *C) -> None:
        self.commands = commands

    def __or__[*_C, _PI: AnyStream, _PE: AnyStream, _NO: AnyStream, _NE: AnyStream](
        self: "CommandGroup[*_C, Command[_PI, None, _PE]]",
        value: Command[None, _NO, _NE],
    ) -> "CommandGroup[*_C, Command[_PI, Pipe, _PE], Command[Pipe, _NO, _NE]]":
        pipe = Pipe()
        return CommandGroup(
            *self.commands[:-1],
            self.commands[-1].with_stdout(pipe),  # type: ignore
            value.with_stdin(pipe),
        )

    @overload
    def __and__[CMD: "Command"](self, value: CMD) -> "CommandGroup[*C, CMD]": ...
    @overload
    def __and__[*_C](self, value: "CommandGroup[*_C]") -> "CommandGroup[*C, *_C]": ...
    def __and__(self, value):
        if isinstance(value, CommandGroup):
            return CommandGroup(*self.commands, *value.commands)
        return CommandGroup(*self.commands, value)

    def run(self):
        with self:
            return self

    async def run_async(self):
        async with self:
            return self

    def __enter__(self):
        self._ctx = ExitStack()
        self._ctx.__enter__()
        for command in self.commands:
            self._ctx.enter_context(command)  # type: ignore

        return self

    def __exit__(self, *args):
        self._ctx.__exit__(*args)

    async def __aenter__(self):
        self._actx = AsyncExitStack()
        await self._actx.__aenter__()
        for command in self.commands:
            await self._actx.enter_async_context(command)  # type: ignore
        return self

    async def __aexit__(self, *args):
        await self._actx.__aexit__(*args)

    def __invert__(self):
        return self.run()

    def __await__(self):
        return self.run_async().__await__()
