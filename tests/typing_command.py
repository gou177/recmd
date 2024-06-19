from typing import Annotated, Any, Callable, Coroutine, Never, assert_type
from recmd.command import Command
from recmd.map_result import ResultMapper
from recmd.stream import Capture, DescriptorReference, DevNull, Pipe, Send


async def typing_none():
    cmd = Command([])
    assert_type(cmd.stdin, None)
    assert_type(cmd.stdout, None)
    assert_type(cmd.stderr, None)


async def typing_streams():
    cmd = (
        Command([])
        .with_stdin(Send(""))
        .with_stdout(Capture())
        .with_stderr(DescriptorReference())
    )
    assert_type(cmd.stdin, Send)
    assert_type(cmd.stdout, Capture)
    assert_type(cmd.stderr, DescriptorReference)


async def typing_group_pipe():
    cmd = Command([]) | Command([])
    assert_type(
        cmd.commands, tuple[Command[None, Pipe, None], Command[Pipe, None, None]]
    )

    assert_type(cmd.commands[0], Command[None, Pipe, None])
    assert_type(cmd.commands[1], Command[Pipe, None, None])


async def typing_group_triple_pipe():
    cmd = Command([]) | Command([]) | Command([])
    assert_type(
        cmd.commands,
        tuple[
            Command[None, Pipe, None],
            Command[Pipe, Pipe, None],
            Command[Pipe, None, None],
        ],
    )


async def typing_group_and():
    cmd = Command([]) & Command([]).with_stdout(Capture())
    assert_type(
        cmd.commands, tuple[Command[None, None, None], Command[None, Capture, None]]
    )

    assert_type(cmd.commands[0], Command[None, None, None])
    assert_type(cmd.commands[1], Command[None, Capture, None])


async def typing_group_triple_and():
    pipe: Annotated[Pipe, 1] = Pipe()
    cmd = (
        Command([]).with_stdout(pipe)
        & Command([]).with_stdin(Send("")).with_stderr(DevNull())
        & Command([]).with_stdin(pipe)
    )
    assert_type(
        cmd.commands,
        tuple[
            Command[None, Pipe, None],
            Command[Send, None, DevNull],
            Command[Pipe, None, None],
        ],
    )


async def typing_mixed():
    pipe: Annotated[Pipe, 1] = Pipe()
    cmd = (
        Command([]).with_stdout(pipe)
        & Command([]).with_stdin(Send("")).with_stderr(DevNull())
        & Command([]).with_stdin(pipe)
        & (Command([]) | Command([]))
    )
    assert_type(
        cmd.commands,
        tuple[
            Command[None, Pipe, None],
            Command[Send, None, DevNull],
            Command[Pipe, None, None],
            Command[None, Pipe, None],
            Command[Pipe, None, None],
        ],
    )


async def typing_apply():
    cmd = Command([]).output(False).apply(bytes.decode)
    assert_type(
        cmd,
        ResultMapper[
            Command[None, Capture[bytes], None],
            Callable[[Command[None, Capture[bytes], None]], bytes],
            Callable[[bytes], str],
        ],
    )
    assert_type(cmd.run(), str)
    assert_type(cmd.input, Command[None, Capture[bytes], None])


async def typing_apply_async():
    async def async_pass[T](value: T) -> T: ...

    cmd = Command([]).output().apply(async_pass).apply(str.title)
    assert_type(
        cmd,
        ResultMapper[
            Command[None, Capture[str], None],
            Callable[[Command[None, Capture[str], None]], str],
            Callable[[str], Coroutine[Any, Any, str]],
            Callable[
                [str], Coroutine[Any, Any, str]
            ],  # bytes.decode is marked as async despite being sync so .run() returns Never
        ],
    )
    assert_type(await cmd.run_async(), str)
    assert_type(cmd.run(), Never)
