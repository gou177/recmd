from contextlib import AsyncExitStack, asynccontextmanager
import os
from pathlib import PurePath

from anyio import create_task_group
import anyio.abc
from recmd.command import AnyStream, Command, CompleteCommand, RunningCommand
from recmd.executor.abc import AsyncExecutor
from recmd.stream import FileStream, Stream, StreamName, AsyncIO


class AnyioExecutor(AsyncExecutor):
    @asynccontextmanager
    async def run(self, command: Command):
        async with AsyncExitStack() as stack:
            stdin, stdin_stream = await self.prepare_stream(command.stdin, "stdin")
            stack.push_async_callback(self.close_stream, stdin_stream)
            stdout, stdout_stream = await self.prepare_stream(command.stdout, "stdout")
            stack.push_async_callback(self.close_stream, stdout_stream)
            stderr, stderr_stream = await self.prepare_stream(command.stderr, "stderr")
            stack.push_async_callback(self.close_stream, stderr_stream)

            env = command.environment
            if command.inherit_env:
                env = os.environ | env
            process = await anyio.open_process(
                command.cmd,
                stdin=stdin,
                stdout=stdout,
                stderr=stderr,
                env=env,
                cwd=command.cwd,
                **command.options,
            )

            command.running = RunningCommand(process.pid, process)

            await self.setup_stream(stdin_stream, (process.stdin, "stdin"))
            await self.setup_stream(stdout_stream, (process.stdout, "stdout"))
            await self.setup_stream(stderr_stream, (process.stderr, "stderr"))

            try:
                async with create_task_group() as tg:
                    tg.start_soon(self.process_stream, stdin_stream)
                    tg.start_soon(self.process_stream, stdout_stream)
                    tg.start_soon(self.process_stream, stderr_stream)
                    yield
            finally:
                status = await process.wait()
                command.complete = CompleteCommand(status)

    async def setup_stream(self, stream: Stream | None, io: AsyncIO):
        if stream is None or io is None:
            return
        await stream.init_async(io)

    async def process_stream(self, stream: Stream | None):
        if stream is None:
            return
        await stream.process_async()

    async def close_stream(self, stream: Stream | None):
        if stream is None:
            return
        await stream.close_async()

    async def prepare_stream(self, stream: AnyStream, name: StreamName):
        if isinstance(stream, str | PurePath):
            stream = FileStream(stream)
        if isinstance(stream, Stream):
            return await stream.setup_async(name), stream
        return stream, None
