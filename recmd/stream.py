from pathlib import PurePath
import subprocess
from typing import (
    IO,
    TYPE_CHECKING,
    Any,
    Literal,
    Protocol,
    Type,
    TypeGuard,
    Union,
    overload,
)


if TYPE_CHECKING:
    from anyio.abc import AnyByteReceiveStream, AnyByteSendStream


StreamName = Literal["stdin", "stdout", "stderr"]
SyncIO = tuple[IO[bytes] | None, StreamName]
AsyncIO = (
    tuple[Union[None, "AnyByteReceiveStream"], Literal["stdout", "stderr"]]
    | tuple[Union[None, "AnyByteSendStream"], Literal["stdin"]]
)


class StreamError(RuntimeError):
    pass


class Stream:
    def setup(self, stream: StreamName) -> int | IO | None:
        """Will be called as Popen arg: (Popen(..., stdin=Stream.setup("stdin")))"""

    async def setup_async(self, stream: StreamName) -> int | IO | None:
        return self.setup(stream)

    def init(self, io: SyncIO):
        """Will be after process created: Stream.init(process.stdin, "stdin")"""

    async def init_async(self, io: AsyncIO):
        """Will be after process created: await Stream.init_async(process.stdin, "stdin")"""
        self.init((None, io[1]))

    def close(self):
        """Will be called after process end"""

    async def close_async(self):
        """Will be called after process end"""

    async def process_async(self):
        """Process something while process is running"""


class DescriptorReference(Stream):
    """Container for descriptor"""

    def __init__(self, descriptor: int | None = None):
        self.descriptor = descriptor

    def setup(self, stream: StreamName) -> int | IO | None:  # NOSONAR
        """Will be called as Popen arg: (Popen(..., stdin=Stream.setup("stdin")))"""
        return self.descriptor

    def init(self, io: SyncIO):
        _io, stream = io
        if has_fileno_guard(_io):
            if (
                self.descriptor
                and _io.fileno() != self.descriptor
                and self.descriptor > 0
            ):
                raise StreamError(f"Descriptor should not be overridden, {stream}")

            self.descriptor = _io.fileno()
        else:
            raise StreamError(f"Unable to get descriptor from {_io}, {stream}")

    async def init_async(self, io: AsyncIO):
        raise NotImplementedError()


class Pipe(DescriptorReference):
    """Ensures that producer process starts before consumer"""

    def setup(self, stream: StreamName) -> int:
        if stream == "stdin":
            if self.descriptor is None:
                raise StreamError(f"No descriptor to pass into {stream}")
            return self.descriptor
        else:
            if self.descriptor is not None:
                raise StreamError(
                    f"Descriptor should be empty before passing into {stream}"
                )
            return subprocess.PIPE

    async def setup_async(self, stream: StreamName):
        return subprocess.PIPE

    async def init_async(self, io: AsyncIO):
        if io[1] == "stdin":
            assert io[0] is not None
            self.async_write = io[0]
            return
        assert io[0] is not None
        self.async_read = io[0]

    async def process_async(self):
        if (
            hasattr(self, "_running")
            or not hasattr(self, "async_write")
            or not hasattr(self, "async_read")
        ):
            return
        self._running = True
        async with self.async_read, self.async_write:
            while True:
                import anyio

                try:
                    value = await self.async_read.receive()
                except anyio.EndOfStream:
                    break
                await self.async_write.send(value)


class DevNull(DescriptorReference):
    def __init__(self):
        super().__init__(subprocess.DEVNULL)

    def init(self, io: SyncIO):
        return

    async def init_async(self, io: AsyncIO):
        return


class HasFileno(Protocol):
    def fileno(self) -> int: ...


def has_fileno_guard(val: Any) -> TypeGuard[HasFileno]:
    return hasattr(val, "fileno")


class IOStream(DescriptorReference):
    sync_io: IO[bytes]

    def __init__(self):
        super().__init__(subprocess.PIPE)

    def get_io(self) -> IO[bytes]:
        return self.sync_io

    def init(self, io: SyncIO):
        assert io[0] is not None, "No stream passed"
        self.sync_io = io[0]

    async def init_async(self, io: AsyncIO):
        if io[1] == "stdin":
            assert io[0] is not None, "No async stream passed"
            self.async_write = io[0]
        else:
            assert io[0] is not None, "No async stream passed"
            self.async_read = io[0]


class Capture[T: str | bytes](IOStream):
    _output: Type[T] = bytes  # type: ignore
    data: bytes

    @overload
    def get(self: "Capture[str]") -> str: ...
    @overload
    def get(self) -> bytes: ...
    def get(self):
        if self._output is str:
            return self.data.decode()
        return self.data

    def __class_getitem__(cls, item: type[str]):
        return type(f"{cls.__name__}[{item.__name__}]", (cls,), {"_output": item})

    def close(self):
        if hasattr(self, "sync_io"):
            self.data = self.sync_io.read()

    async def close_async(self):
        if not hasattr(self, "async_read"):
            return
        self.data = await self.async_read.receive()


class Send(IOStream):
    """Write data and close"""

    def __init__(self, data: bytes | str) -> None:
        super().__init__()
        if isinstance(data, str):
            data = data.encode()
        self.data = data

    def init(self, io: SyncIO):
        super().init(io)
        self.sync_io.write(self.data)
        self.sync_io.close()

    async def init_async(self, io: AsyncIO):
        await super().init_async(io)
        await self.async_write.send(self.data)
        await self.async_write.aclose()


class FileStream(Stream):
    def __init__(self, path: PurePath | str, append: bool = True) -> None:
        self.path = path
        self.append = append
        super().__init__()

    def setup(self, stream: StreamName) -> int | IO | None:
        if stream == "stdin":
            self.file = open(self.path, "rb")
            return self.file
        self.file = open(self.path, "ab" if self.append else "wb")
        return self.file

    def close(self):
        if not self.file.closed:
            self.file.close()
