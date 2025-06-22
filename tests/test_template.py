import pytest
from recmd import TransformError, shell


def test_basic_split():
    assert shell(t"a b c") == ["a", "b", "c"]


def test_include():
    assert shell(t"a b {1}") == ["a", "b", "1"]
    assert shell(t"a b {'1 2'}") == ["a", "b", "1 2"]


def test_prefix_and_postfix():
    assert shell(t"a b --arg={1}postfix t") == ["a", "b", "--arg=1postfix", "t"]


def test_double_space():
    assert shell(t"a b {1}  t") == ["a", "b", "1", "", "t"]


def test_quotation():
    assert shell(rt"a\ b c") == ["a b", "c"]
    assert shell(rt"'a b\\ {1}'") == ["a b\\ 1"]
    assert shell(rt"'a b\'{1}'") == ["a b'1"]
    assert shell(rt'"a b\"{1}"') == ['a b"1']
    assert shell(rt'"a b\"{1}" " " \ \ ') == ['a b"1', " ", "  "]


def test_unwrap_conversion():
    assert shell(t"a b {[1, 2, 3]:*!s}") == ["a", "b", "1", "2", "3"]


def test_unwrap_format():
    assert shell(t"a b {[1, 2, 3]:*:.1f}") == ["a", "b", "1.0", "2.0", "3.0"]


def test_unwrap_format_fallback():
    assert shell(t"a b {1:*>2}") == ["a", "b", "*1"]


def test_invalid_escape():
    with pytest.raises(TransformError):
        shell(t"\\a")


def test_non_strict_unwrap():
    assert shell(t"a b {[1, 2, 3]:*}") == ["a", "b", 1, 2, 3]


def test_unwrap_conversion_error():
    with pytest.raises(TransformError):
        shell(t"a b {[]!a:*}")


def test_unwrap_prefix_err():
    with pytest.raises(TransformError):
        shell(t"a b test{[]:*}")


def test_unwrap_suffix_err():
    with pytest.raises(TransformError):
        shell(t"a b {[]:*}test")
