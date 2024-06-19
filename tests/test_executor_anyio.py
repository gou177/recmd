from pathlib import Path
import sys
from tempfile import TemporaryDirectory

import anyio
import pytest

from recmd.executor.anyio import AnyioExecutor
from recmd.shell import sh
from recmd.stream import Capture, IOStream, Send


@sh
def python(code: str):
    return sh(f"{sys.executable} -c {code}")


async def receive_all(stream) -> bytes:
    result = b""
    while True:
        try:
            value = await stream.receive()
            if isinstance(value, bytearray):
                value = bytes(value)
            result += value
        except anyio.EndOfStream:
            break
    return result


@pytest.mark.anyio
@sh
async def test_process_start():
    with AnyioExecutor().use():
        assert await python("print()")


@pytest.mark.anyio
@sh
async def test_process_stdout():
    with AnyioExecutor().use():
        assert (await python("print(123)").output()).strip() == "123"


@pytest.mark.anyio
@sh
async def test_process_stdout_file():
    with AnyioExecutor().use(), TemporaryDirectory() as dir:
        assert await (python("print(123)") >> (Path(dir) / "test"))
        assert (Path(dir) / "test").read_text() == "123\n"


@pytest.mark.anyio
@sh
async def test_process_stdin():
    with AnyioExecutor().use():
        out = await python("print(input(), end='')").send("123").output()
        assert out == "123"


@pytest.mark.anyio
@sh
async def test_process_stdin_file():
    with AnyioExecutor().use(), TemporaryDirectory() as dir:
        dir = Path(dir)
        file = dir / "test"
        file.write_text("value")
        async with (
            file >> python("import sys;print(sys.stdin.read(),end='')") >> IOStream()
        ) as process:
            result = await process.stdout.async_read.receive()
            assert result == b"value"
        assert process


@pytest.mark.anyio
@sh
async def test_process_stdin_bytes():
    with AnyioExecutor().use():
        process = (
            Send("value")
            >> python("import sys;print(sys.stdin.read(),end='')")
            >> Capture[bytes]()
        )
        assert await process
        result = process.stdout.get()
        assert result == b"value"


@pytest.mark.anyio
@sh
async def test_process_pipe():
    with AnyioExecutor().use():
        async with python("print(123)") | python(
            "print(input())"
        ) >> IOStream() as group:
            result = (await receive_all(group.commands[-1].stdout.async_read)).replace(
                b"\r", b""
            )
            assert b"123\n" == result
