import ast
from typing import Callable, Concatenate
from .exceptions import TransformError
from .patcher import AnyFunctionDef, line_attributes

try:
    from loguru import logger  # type: ignore

    trace = logger.trace
except ImportError:
    import logging

    trace = logging.getLogger(__name__).debug


__all__ = ["patch_shell_arguments"]


NAMES = ["sh", "shell"]
STRING_START = ["'", '"']
ESCAPE = "\\"
Quotation = str | None


def iterate_arguments(data: str, quotation: Quotation):  # NOSONAR
    group = ""

    is_escape = False
    for char in data:
        if (
            char == " " and not is_escape and quotation is None
        ):  # space outside quotation
            yield group, quotation
            group = ""
            continue
        elif char == quotation and not is_escape:  # end of quoted string
            quotation = None
            continue
        elif char in STRING_START and not is_escape:  # start of quoted string
            quotation = char
            continue

        if is_escape:
            is_escape = False
            if (quotation and char not in [ESCAPE, quotation]) or (
                not quotation and char not in [ESCAPE, " "]
            ):
                raise TransformError(f"Invalid escape: '\\{char}' in {data!r}")
        elif char == ESCAPE:
            is_escape = True
        if not is_escape:
            group += char

    if is_escape is True:
        raise TransformError(f"Escape is not used in {data!r}")
    yield group, quotation


def split_joined_string(node: ast.JoinedStr):
    group: list[ast.expr] = []
    quotation = None
    for value in node.values:
        if not isinstance(value, ast.Constant):
            group.append(value)
            continue
        assert isinstance(value.value, str)

        for i, (chunk, quotation) in enumerate(
            iterate_arguments(value.value, quotation)
        ):
            if i > 0:
                yield group.copy()
                group.clear()
            group.append(
                ast.Constant(value=chunk, kind=value.kind, **line_attributes(value))
            )
    if quotation is not None:
        raise TransformError(f"{quotation} is not closed")
    if group:
        yield group


def merge_group(group: list[ast.expr]):
    if len(group) == 1 and isinstance(group[0], ast.Constant):
        return group[0]

    group = [x for x in group if not (isinstance(x, ast.Constant) and x.value == "")]
    if (
        len(group) == 1
        and isinstance(group[0], ast.FormattedValue)
        and isinstance(group[0].format_spec, ast.JoinedStr)
        and group[0].format_spec.values
        and isinstance(group[0].format_spec.values[0], ast.Constant)
        and isinstance(group[0].format_spec.values[0].value, str)
        and (
            group[0].format_spec.values[0].value == "*"
            or group[0].format_spec.values[0].value.startswith("*!")
            or group[0].format_spec.values[0].value.startswith("*:")
        )
    ):
        value = group[0].value
        if group[0].conversion != -1:
            raise TransformError(
                f":* arguments should have conversion after :* (:*!{chr(group[0].conversion)})"
            )
        fmt = group[0].format_spec.values[0].value.removeprefix("*")
        conversion = -1
        if fmt.startswith("!"):
            if fmt[1] not in ["a", "s", "r"]:
                raise TransformError(f"Invalid conversion: !{fmt[1]}")
            conversion = ord(fmt[1])
            fmt = fmt[2:]

        should_format = fmt.startswith(":")
        if conversion > 0 or should_format:
            fmt = fmt.removeprefix(":")
            # (f"{x!{conversion}:{fmt}}" for x in {value})
            value = ast.GeneratorExp(
                elt=ast.JoinedStr(
                    values=[
                        ast.FormattedValue(
                            conversion=conversion,
                            value=ast.Name(
                                id="x",
                                ctx=ast.Load(),
                                **line_attributes(group[0].format_spec),
                            ),
                            format_spec=ast.JoinedStr(
                                values=[
                                    ast.Constant(
                                        value=fmt,
                                        **line_attributes(group[0].format_spec),
                                    ),
                                    *group[0].format_spec.values[1:],
                                ],
                                **line_attributes(group[0].format_spec),
                            )
                            if should_format
                            else None,
                            **line_attributes(value),
                        )
                    ],
                    **line_attributes(value),
                ),
                generators=[
                    ast.comprehension(
                        target=ast.Name(
                            id="x",
                            ctx=ast.Store(),
                            **line_attributes(group[0].format_spec),
                        ),
                        iter=value,
                        ifs=[],
                        is_async=0,
                    )
                ],
                **line_attributes(group[0]),
            )

        return ast.Starred(value, ast.Load(), **line_attributes(group[0].value))
    max_end_line = max(node.end_lineno for node in group if node.end_lineno)
    for node in group:
        if (  # TODO: refactor?
            isinstance(node, ast.FormattedValue)
            and isinstance(node.format_spec, ast.JoinedStr)
            and node.format_spec.values
            and isinstance(node.format_spec.values[0], ast.Constant)
            and isinstance(node.format_spec.values[0].value, str)
            and (
                node.format_spec.values[0].value == "*"
                or node.format_spec.values[0].value.startswith("*!")
                or node.format_spec.values[0].value.startswith("*:")
            )
        ):
            raise TransformError(":* arguments should not have prefixes/postfixes")

    return ast.JoinedStr(
        list(group),
        lineno=min(node.lineno for node in group),
        col_offset=min(node.col_offset for node in group),
        end_col_offset=max(
            node.end_col_offset
            for node in group
            if node.end_lineno == max_end_line and node.end_col_offset
        ),
        end_lineno=max_end_line,
    )


def string_to_list(node: ast.JoinedStr | ast.Constant):
    if isinstance(node, ast.Constant):
        node = ast.JoinedStr(values=[node], **line_attributes(node))
    arguments = []
    for group in split_joined_string(node):
        arguments.append(merge_group(group))

    return ast.List(
        elts=arguments,
        ctx=ast.Load(),
        **line_attributes(node),
    )


def patch_shell_arguments[**P](
    function: AnyFunctionDef,
    names: list[str] = NAMES,
    convert: Callable[
        Concatenate[ast.JoinedStr | ast.Constant, P],
        ast.expr,
    ] = string_to_list,
    *args: P.args,
    **kwargs: P.kwargs,
):
    r"""
    Transform f-string argument to list that can be safely passed to shell

    rules:
    1.  only calls with signature `sh("")` / `sh(f"")` / `shell(f"")` / `something.sh(f"")` / `something.shell(f"")` are changed
    2.  split argument 0 by space (`"a b"` -> `["a", "b"]`)
    3.  double space are honored (`"a  b"` -> `["a", "", "b"]`)
    4.  f-strings arguments are inlined within respected arguments (f"abc{'def'}gh 123{456}" -> [f"abd{'def'}gh", f"123{456}"])
    5.  arguments with :* formatting are unwrapped ("ls -l {['dir', 'dir2']!a}" -> ["ls", "-l", "dir", "dir2"])
    6.  formatting for :* arguments can be specified after :* ("ls -l {[1]:*:.2f}" -> ["ls", "-l", "1.00"])
    7.  conversion for :* arguments also can be specified after :* but before formatting ("ls -l {[1]:*!s}" -> ["ls", "-l", "1"])
    8.  :* is passed as is if no formatting applied ("ls -l {[1]:*}" -> ["ls", "-l", 1])
    9.  arguments can be quoted to include spaces ("'a b' c" -> ["a b", "c"])
    10. spaces and quotes can be escaped using \ ("'a\' b' c d\ e \\" -> ["a' b", "c", "d e", "\"])

    Examples:
    * `shell(f'echo --arg={1}postfix')` to `shell([f'echo', f'--arg={1}postfix'])`
    * `shell(f'echo {['a', 'b']:*}')` to `shell([f'echo', *['a', 'b']])`
    """

    for node in ast.walk(function):
        if (
            isinstance(node, ast.Call)
            and (
                # __sh(...)__
                (isinstance(node.func, ast.Name) and node.func.id in names)
                # __object.sh(...)__
                or (isinstance(node.func, ast.Attribute) and node.func.attr in names)
            )
            and (
                # ...(__f""__)
                isinstance(node.args[0], ast.JoinedStr)
                # ...(__""__)
                or (
                    isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)
                )
            )
        ):
            prev = ast.unparse(node)
            node.args[0] = convert(node.args[0], *args, **kwargs)
            trace(f"transformed shell {prev} -> {ast.unparse(node)}")
