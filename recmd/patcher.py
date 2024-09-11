import ast
from contextlib import suppress
import inspect
import sys
import types
from typing import TYPE_CHECKING, Annotated, Any, Callable, Concatenate

try:
    from typing_extensions import Doc  # type: ignore
except ImportError:
    if not TYPE_CHECKING:

        def _doc(x):
            return x

        Doc = _doc

__all__ = [
    "patch_function",
    "apply_patch",
    "AnyFunctionDef",
    "line_attributes",
    "get_ast",
]

AnyFunctionDef = ast.FunctionDef | ast.AsyncFunctionDef
type Patcher[**P] = Annotated[
    Callable[Concatenate[AnyFunctionDef, P], Any],
    Doc("Function that accepts ast.FunctionDef and modifies it inplace"),
]


def getsource(obj):
    """inspect.getsource with PEP 302 (New Import Hooks) support"""
    if (
        hasattr(obj, "__globals__")
        and hasattr(obj, "__module__")
        and (loader := obj.__globals__.get("__loader__")) is not None
        and hasattr(loader, "get_source")
    ):
        with suppress(Exception):
            return loader.get_source(obj.__module__)
    return inspect.getsource(sys.modules[obj.__module__])


def get_ast(obj: Callable):
    """Get ast.Module containing with only function from arguments in body, will add __recmd_ast__ attribute to allow multiple patches"""
    if hasattr(obj, "__recmd_ast__"):
        assert (
            isinstance(obj.__recmd_ast__, ast.Module)
            and len(obj.__recmd_ast__.body) == 1
            and isinstance(obj.__recmd_ast__.body[0], ast.FunctionDef)
        ), "Invalid value of __recmd_ast__"
        return obj.__recmd_ast__
    tree = ast.parse(getsource(obj))
    body = None
    for item in ast.walk(tree):
        if (
            isinstance(item, AnyFunctionDef)
            and item.name == obj.__name__
            and item.end_lineno
            and (
                (
                    item.decorator_list
                    and item.decorator_list[0].lineno == obj.__code__.co_firstlineno
                )
                or item.lineno == obj.__code__.co_firstlineno
            )
        ):
            assert (
                body is None
            ), f"Unable to resolve double definition of {obj.__name__} in {inspect.getfile(obj)}"
            body = item
    assert (
        body is not None
    ), f"Unable to resolve definition of {obj.__name__} in {inspect.getfile(obj)}"
    tree.body = [body]
    obj.__recmd_ast__ = tree
    return obj.__recmd_ast__


def apply_ast(function: Callable, module: ast.Module):
    """Update __code__ of function inplace"""
    consts = compile(module, inspect.getfile(function), "exec").co_consts
    code = None
    # fix for inline generics (def name[T])
    for const in consts:
        if isinstance(const, types.CodeType) and const.co_name.startswith("<"):
            consts = consts + const.co_consts

    for const in consts:
        if (
            isinstance(const, types.CodeType)
            and const.co_name == function.__name__
            and const.co_firstlineno == function.__code__.co_firstlineno
        ):
            assert code is None, "Unable to find right code"
            code = const

    assert code is not None, "Unable to find code"
    function.__code__ = code


def patch_function(
    function: Annotated[
        Callable,
        Doc("Ast of this function will be passed to patcher and then updated in place"),
    ],
    patcher: Patcher,
):
    """Update __code__ of function inplace. Multiple patches can be applied using this function"""

    module = get_ast(function)
    assert isinstance(module.body[0], AnyFunctionDef)
    patcher(module.body[0])
    apply_ast(function, module)


def apply_patch(patcher: Patcher):
    """Update __code__ of function inplace."""

    def wrapper[F: Callable](function: F) -> F:
        patch_function(function, patcher)
        return function

    return wrapper


def line_attributes(value: ast.AST):
    """Helper function for ast manipulation"""

    return dict(
        lineno=value.lineno,
        col_offset=value.col_offset,
        end_lineno=value.end_lineno,
        end_col_offset=value.end_col_offset,
    )
