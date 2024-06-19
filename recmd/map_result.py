from inspect import iscoroutine
from typing import (
    Any,
    Callable,
    Coroutine,
    Generator,
    Never,
    Protocol,
    Self,
    overload,
)


class Runnable(Protocol):
    def run(self) -> Self: ...

    async def run_async(self) -> Self: ...


class ResultMapper[I: Runnable, *O]:
    input: I

    def __init__(self, input: I, *steps: *O, no_run: bool = False) -> None:
        self.input = input
        self._steps = steps
        self.no_run = no_run

    @overload
    def apply[_I: Runnable, NT](
        self: "ResultMapper[_I]",
        cb: Callable[[_I], NT],
    ) -> "ResultMapper[_I, Callable[[_I], NT]]": ...
    @overload
    def apply[_I: Runnable, *_S, TI, T, NT](  # NOSONAR
        self: "ResultMapper[_I, *_S, Callable[[TI], Coroutine[Any,Any,T]]]",
        cb: Callable[[T], Coroutine[Any, Any, NT] | NT],
    ) -> "ResultMapper[_I, *_S, Callable[[TI], Coroutine[Any,Any,T]], Callable[[T], Coroutine[Any,Any,NT]]]": ...
    @overload
    def apply[_I: Runnable, *_S, TI, T, NT](  # NOSONAR
        self: "ResultMapper[_I, *_S, Callable[[TI], T]]", cb: Callable[[T], NT]
    ) -> "ResultMapper[_I, *_S, Callable[[TI], T], Callable[[T], NT]]": ...

    def apply(self, cb):  # type: ignore
        return ResultMapper(self.input, *self._steps, cb, no_run=self.no_run)

    @overload
    def run[_I: Runnable, *_S](
        self: "ResultMapper[_I, *_S, Callable[[Any], Coroutine], Any]",
    ) -> Never: ...  # warn user that that user should use run_async
    @overload
    def run[_I: Runnable, *_S, T](
        self: "ResultMapper[_I, *_S, Callable[[Any], T]]",
    ) -> T: ...
    def run[_I: Runnable, *_S, T](
        self: "ResultMapper[_I, *_S, Callable[[Any], T]]",
    ) -> T:
        if self.no_run:
            value = self.input
        else:
            value = self.input.run()
        for step in self._steps:
            value = step(value)  # type: ignore

        return value  # type: ignore

    async def run_async[_I: Runnable, *_S, T](
        self: "ResultMapper[_I, *_S, Callable[[Any], Coroutine[Any,Any,T] | T]]",
    ) -> T:
        if self.no_run:
            value = self.input
        else:
            value = await self.input.run_async()

        for step in self._steps:
            value = step(value)  # type: ignore
            if iscoroutine(value):
                value = await value

        return value  # type: ignore

    def __invert__[_I: Runnable, *_S, T](
        self: "ResultMapper[_I, *_S, Callable[[Any], T]]",
    ) -> T:
        return self.run()

    def __await__[_I: Runnable, *_S, T](
        self: "ResultMapper[_I, *_S, Callable[[Any], Coroutine[Any,Any,T] | T]]",
    ) -> Generator[Any, Any, T]:
        return self.run_async().__await__()
