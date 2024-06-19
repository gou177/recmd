import pytest
from recmd import TransformError, apply_patch, patch_shell_arguments


def shell(data: str | list[str]) -> list:
    assert isinstance(data, list)
    return data


def test_basic_split():
    @apply_patch(patcher=patch_shell_arguments)
    def test():
        assert shell("a b c") == ["a", "b", "c"]

    test()


def test_include():
    @apply_patch(patcher=patch_shell_arguments)
    def test():
        assert shell(f"a b {1}") == ["a", "b", "1"]
        assert shell(f"a b {'1 2'}") == ["a", "b", "1 2"]

    test()


def test_prefix_and_postfix():
    @apply_patch(patcher=patch_shell_arguments)
    def test():
        assert shell(f"a b --arg={1}postfix f") == ["a", "b", "--arg=1postfix", "f"]

    test()


def test_double_space():
    @apply_patch(patcher=patch_shell_arguments)
    def test():
        assert shell(f"a b {1}  f") == ["a", "b", "1", "", "f"]

    test()


def test_quotation():
    @apply_patch(patcher=patch_shell_arguments)
    def test():
        assert shell(r"a\ b c") == ["a b", "c"]
        assert shell(rf"'a b\\ {1}'") == ["a b\\ 1"]
        assert shell(rf"'a b\'{1}'") == ["a b'1"]
        assert shell(rf'"a b\"{1}"') == ['a b"1']
        assert shell(rf'"a b\"{1}" " " \ \ ') == ['a b"1', " ", "  "]

    test()


def test_unwrap_conversion():
    @apply_patch(patcher=patch_shell_arguments)
    def test():
        assert shell(f"a b {[1, 2, 3]:*!s}") == ["a", "b", "1", "2", "3"]

    test()


def test_unwrap_format():
    @apply_patch(patcher=patch_shell_arguments)
    def test():
        assert shell(f"a b {[1, 2, 3]:*:.1f}") == ["a", "b", "1.0", "2.0", "3.0"]

    test()


def test_unwrap_format_fallback():
    @apply_patch(patcher=patch_shell_arguments)
    def test():
        assert shell(f"a b {1:*>2}") == ["a", "b", "*1"]

    test()


def test_invalid_escape():
    with pytest.raises(TransformError):

        @apply_patch(patcher=patch_shell_arguments)  # type: ignore
        def _():
            shell("\\a")


def test_non_strict_unwrap():
    @apply_patch(patcher=patch_shell_arguments)  # type: ignore
    def test():
        assert shell(f"a b {[1, 2, 3]:*}") == ["a", "b", 1, 2, 3]

    test()


def test_unwrap_conversion_error():
    with pytest.raises(TransformError):

        @apply_patch(patcher=patch_shell_arguments)
        def _():
            shell(f"a b {[]!a:*}")


def test_unwrap_prefix_err():
    with pytest.raises(TransformError):

        @apply_patch(patcher=patch_shell_arguments)
        def _():
            shell(f"a b test{[]:*}")


def test_unwrap_suffix_err():
    with pytest.raises(TransformError):

        @apply_patch(patcher=patch_shell_arguments)
        def _():
            shell(f"a b {[]:*}test")
