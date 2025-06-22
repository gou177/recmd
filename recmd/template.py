import sys
from typing import Never

from recmd.exceptions import TransformError
from recmd.shell_patch import iterate_arguments


if sys.version_info >= (3, 14):
    from string.templatelib import Template, Interpolation
else:
    Template = Never
    Interpolation = Never

FORMATTERS = {"s": str, "r": repr, "a": ascii}


def split_template(template: Template):
    group: list[Interpolation | str] = []
    quotation = None
    for value in template:
        if isinstance(value, Interpolation):
            group.append(value)
            continue
        assert isinstance(value, str)

        for i, (chunk, quotation) in enumerate(iterate_arguments(value, quotation)):
            if i > 0:
                yield group.copy()
                group.clear()
            if chunk:
                group.append(chunk)
    if quotation is not None:
        raise TransformError(f"{quotation} is not closed")
    if group:
        yield group


def _is_expand(interpolation: Interpolation):
    return bool(interpolation.format_spec) and (
        interpolation.format_spec == "*"
        or interpolation.format_spec.startswith("*!")
        or interpolation.format_spec.startswith("*:")
    )


def _to_string(item: str | Interpolation):
    if isinstance(item, Interpolation):
        if _is_expand(item):
            raise TransformError(":* arguments should not have prefixes/postfixes")
        value = item.value
        if item.conversion:
            formatter = FORMATTERS[item.conversion]
            value = formatter(value)
        if item.format_spec:
            value = format(value, item.format_spec)
        if not isinstance(value, str):
            return str(value)
        return value
    return item


def template_to_command(template: Template):
    for group in split_template(template):
        group = list(group)
        if (
            len(group) == 1
            and isinstance(group[0], Interpolation)
            and _is_expand(group[0])
        ):
            if group[0].conversion:
                raise TransformError(
                    f"Transform (!{group[0].conversion}) should be after :*, not before"
                )
            fmt = group[0].format_spec.removeprefix("*")
            value = list(group[0].value)
            if fmt.startswith("!"):
                formatter = FORMATTERS[fmt.removeprefix("!")[0]]
                fmt = fmt[2:]
                value = [formatter(x) for x in group[0].value]
            if fmt.startswith(":"):
                spec = fmt.removeprefix(":")
                value = [format(x, spec) for x in group[0].value]
            yield from value
            continue
        yield "".join(_to_string(x) for x in group)
