from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from recmd.executor.subprocess import SubprocessExecutor
from recmd.shell import sh
from recmd.stream import Capture, IOStream, Send


@sh
def python(code: str):
    return sh(f"{sys.executable} -c {code}")


@sh
def test_process_start():
    with SubprocessExecutor().use():
        assert ~python("print()")


@sh
def test_process_stdout():
    with SubprocessExecutor().use():
        assert (~python("print(123)").output()).strip() == "123"


@sh
def test_process_stdout_file():
    with SubprocessExecutor(True).use(), TemporaryDirectory() as dir:
        assert python("print(123)") >> (Path(dir) / "test")
        assert (Path(dir) / "test").read_text() == "123\n"


@sh
def test_process_stdin():
    with SubprocessExecutor().use():
        out = ~python("print(input(), end='')").send("123").output()
        assert out == "123"


@sh
def test_process_stdin_file():
    with SubprocessExecutor().use(), TemporaryDirectory() as dir:
        dir = Path(dir)
        file = dir / "test"
        file.write_text("value")
        with (
            file >> python("import sys;print(sys.stdin.read(),end='')") >> IOStream()
        ) as process:
            result = process.stdout.sync_io.read()
            assert result == b"value"
        assert process


@sh
def test_process_stdin_bytes():
    with SubprocessExecutor().use():
        process = (
            Send("value")
            >> python("import sys;print(sys.stdin.read(),end='')")
            >> Capture[bytes]()
        )
        assert ~process
        result = process.stdout.get()
        assert result == b"value"


@sh
def test_process_pipe():
    with SubprocessExecutor().use():
        with python("print(123)") | python("print(input())") >> IOStream() as group:
            result = group.commands[-1].stdout.sync_io.read().replace(b"\r", b"")
            assert b"123\n" == result
