import ast
import traceback
from recmd.patcher import AnyFunctionDef, apply_patch, line_attributes


def fix_addition(function: AnyFunctionDef):
    for node in ast.walk(function):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            node.left = ast.Constant(value=1, **line_attributes(node.left))
            node.right = ast.Constant(value=1, **line_attributes(node.right))


def fix_assert_false(function: AnyFunctionDef):
    for node in ast.walk(function):
        if (
            isinstance(node, ast.Assert)
            and isinstance(node.test, ast.Constant)
            and node.test.value is False
        ):
            node.test.value = True


def test_function_patch():
    @apply_patch(patcher=fix_addition)
    def test_function_patch():
        assert 1 + 2 == 2

    test_function_patch()


def test_multiple_patch():
    @apply_patch(fix_assert_false)
    @apply_patch(fix_addition)
    def test_multiple_patch():
        assert 1 + 2 == 2
        assert False

    test_multiple_patch()


def test_lineno():
    @apply_patch(fix_assert_false)
    @apply_patch(fix_addition)
    def test_lineno():
        assert 1 + 2 == 2
        try:
            assert 2 == 1
            raise RuntimeError("Should raise error")
        except AssertionError as e:
            frame = traceback.extract_tb(e.__traceback__)[0]
            assert frame.line == "assert 2 == 1"

        assert False

    test_lineno()
