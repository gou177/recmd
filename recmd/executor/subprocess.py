from contextlib import ExitStack, contextmanager
import os
from pathlib import PurePath
from subprocess import Popen
from typing import IO
from recmd.command import AnyStream, Command, CompleteCommand, RunningCommand
from recmd.executor.abc import SyncExecutor
from recmd.stream import FileStream, Stream, StreamName


class SubprocessExecutor(SyncExecutor):
    @contextmanager
    def run(self, command: Command):
        with ExitStack() as stack:
            stdin, stdin_stream = self.prepare_stream(command.stdin, "stdin")
            stack.callback(self.close_stream, stdin_stream)
            stdout, stdout_stream = self.prepare_stream(command.stdout, "stdout")
            stack.callback(self.close_stream, stdout_stream)
            stderr, stderr_stream = self.prepare_stream(command.stderr, "stderr")
            stack.callback(self.close_stream, stderr_stream)

            env = command.environment
            if command.inherit_env:
                env = os.environ | env
            process = Popen(
                command.cmd,
                stdin=stdin,
                stdout=stdout,
                stderr=stderr,
                env=env,
                cwd=command.cwd,
                **command.options,
            )
            command.running = RunningCommand(process.pid, process)

            self.setup_stream(stdin_stream, process.stdin, "stdin")
            self.setup_stream(stdout_stream, process.stdout, "stdout")
            self.setup_stream(stderr_stream, process.stderr, "stderr")
            try:
                yield
            finally:
                status = process.wait()
                command.complete = CompleteCommand(status)

    def setup_stream(
        self, stream: Stream | None, io: IO[bytes] | None, name: StreamName
    ):
        if stream is None or io is None:
            return
        stream.init((io, name))

    def close_stream(self, stream: Stream | None):
        if stream is None:
            return
        stream.close()

    def prepare_stream(self, stream: AnyStream, name: StreamName):
        if isinstance(stream, str | PurePath):
            stream = FileStream(stream)
        if isinstance(stream, Stream):
            return stream.setup(name), stream
        return stream, None
