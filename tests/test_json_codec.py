"""Tests for the self-contained JSON codec in the FL Studio controller script.

FL Studio does not ship the ``json`` standard library module, so the
controller script implements its own codec.  These tests pin the behaviour to
the standard library's, because the MCP server parses the controller's
output with the real ``json`` module.
"""

from __future__ import annotations

import json
import math

import pytest

from tests.conftest import load_device_script


@pytest.fixture(scope="module")
def codec():
    module = load_device_script()
    return module._json_dumps, module._json_loads


CASES = [
    {},
    [],
    {"action": "transport.start", "params": {}},
    {"a": [1, 2, 3], "b": {"c": True, "d": None}},
    {"s": 'quote " backslash \\ newline \n tab \t ctrl \x01 del \x7f'},
    {"unicode": "héllo wörld — 日本語"},
    {"emoji": "🎵"},
    [1, 2.5, -3, 1e10, 1e-10, 0.1, -0.0],
    "plain",
    123,
    True,
    False,
    None,
    {"nested": {"deep": {"deeper": [{"x": 1}, {"y": [True, False, None]}]}}},
    {"empty_obj": {}, "empty_arr": []},
    {"key with space": "value"},
    {"big": 10**30, "neg": -(10**30)},
]


@pytest.mark.parametrize("value", CASES)
def test_dumps_matches_stdlib(codec, value):
    dumps, _ = codec
    assert dumps(value) == json.dumps(value, indent=2)


@pytest.mark.parametrize("value", CASES)
def test_loads_matches_stdlib(codec, value):
    _, loads = codec
    assert loads(json.dumps(value, indent=2)) == value


@pytest.mark.parametrize("value", CASES)
def test_roundtrip(codec, value):
    dumps, loads = codec
    assert loads(dumps(value)) == value


def test_output_is_ascii_only(codec):
    dumps, _ = codec
    encoded = dumps({"unicode": "héllo 日本語 🎵"})
    assert encoded.isascii(), "the command channel must stay ASCII safe"
    assert "\\u00e9" in encoded


def test_non_finite_floats_match_stdlib(codec):
    dumps, loads = codec
    for value in (float("nan"), float("inf"), float("-inf")):
        assert dumps({"v": value}) == json.dumps({"v": value}, indent=2)
    assert math.isnan(loads(dumps({"v": float("nan")}))["v"])
    assert loads(dumps({"v": float("inf")}))["v"] == float("inf")
    assert loads(dumps({"v": float("-inf")}))["v"] == float("-inf")


def test_compact_output_has_no_whitespace(codec):
    dumps, loads = codec
    text = dumps({"a": 1, "b": [1, 2]}, indent=0)
    assert text == '{"a":1,"b":[1,2]}'
    assert loads(text) == {"a": 1, "b": [1, 2]}


def test_escapes_are_unescaped(codec):
    _, loads = codec
    text = r'"a\"b\\c\/d\be\ff\ng\rh\ti"'
    assert loads(text) == 'a"b\\c/d\be\ff\ng\rh\ti'


def test_unicode_escape_and_surrogate_pair(codec):
    _, loads = codec
    assert loads(r'"é"') == "é"
    assert loads(r'"🎵"') == "🎵"
    assert loads(r'"😀"') == "\U0001f600"


@pytest.mark.parametrize(
    "text",
    ["", "{", "[1,", '{"a"}', '{"a":}', "tru", '{"a": 1} extra', '"unterminated', "01x"],
)
def test_invalid_documents_raise(codec, text):
    _, loads = codec
    with pytest.raises(ValueError):
        loads(text)


def test_whitespace_is_ignored(codec):
    _, loads = codec
    assert loads('  {\n\t"a" :  [ 1 , 2 ]  }\r\n') == {"a": [1, 2]}


def test_error_mentions_position(codec):
    _, loads = codec
    with pytest.raises(ValueError) as excinfo:
        loads('{"a": 1, }')
    assert "char" in str(excinfo.value)


def test_control_characters_are_escaped(codec):
    dumps, loads = codec
    value = {"k": "\x00\x1f"}
    assert dumps(value) == json.dumps(value, indent=2)
    assert loads(dumps(value)) == value
