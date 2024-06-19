from abc import ABC, abstractmethod
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, AsyncContextManager, ClassVar, ContextManager


if TYPE_CHECKING:
    from recmd.command import Command


class AsyncExecutor(ABC):
    context: ClassVar = ContextVar["AsyncExecutor"]("recmd.executor.AsyncExecutor")

    @classmethod
    def get(cls) -> "AsyncExecutor":
        self = cls.context.get(None)
        if self is None:
            raise RuntimeError(
                "No async executor is set (to enable default install anyio)"
            )
        return self

    @abstractmethod
    def run(self, command: "Command") -> AsyncContextManager: ...

    @contextmanager
    def use(self):
        reset = self.context.set(self)
        try:
            yield self
        finally:
            self.context.reset(reset)


class SyncExecutor(ABC):
    context: ClassVar = ContextVar["SyncExecutor"]("recmd.executor.SyncExecutor")

    implicit_start: bool
    """Allow process to be started via assert"""

    def __init__(self, implicit_start: bool = False) -> None:
        super().__init__()

        self.implicit_start = implicit_start

    @classmethod
    def get(cls) -> "SyncExecutor":
        self = cls.context.get(None)
        if self is None:
            raise RuntimeError("No sync executor is set")
        return self

    @abstractmethod
    def run(self, command: "Command") -> ContextManager: ...

    @contextmanager
    def use(self):
        reset = self.context.set(self)
        try:
            yield self
        finally:
            self.context.reset(reset)
