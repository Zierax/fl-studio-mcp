"""Tests for the sysex response channel used when FL Studio cannot write files."""

from __future__ import annotations

import json

from fl_studio_mcp.utils.midi_response import (
    MANUFACTURER,
    ResponseAssembler,
    encode_chunk,
    encode_response,
    parse_chunk,
)


def test_encode_parse_roundtrip():
    chunks = encode_response('{"success": true, "value": 42}')
    assert len(chunks) == 1
    assembler = ResponseAssembler()
    result = None
    for chunk in chunks:
        result = assembler.add(chunk)
    assert result == '{"success": true, "value": 42}'


def test_chunking_of_large_payloads():
    payload = "x" * 2000
    chunks = encode_response(payload, chunk_size=700)
    assert len(chunks) == 3

    assembler = ResponseAssembler()
    result = None
    for chunk in chunks:
        result = assembler.add(chunk)
        assert result is None or result == payload
    assert result == payload


def test_out_of_order_chunks():
    chunks = encode_response("a" * 1500, chunk_size=700)
    assembler = ResponseAssembler()
    assert assembler.add(chunks[2]) is None
    assert assembler.add(chunks[0]) is None
    assert assembler.add(chunks[1]) == "a" * 1500


def test_empty_response():
    chunks = encode_response("")
    assert len(chunks) == 1
    assert ResponseAssembler().add(chunks[0]) == ""


def test_non_ours_is_ignored():
    assembler = ResponseAssembler()
    assert assembler.add(bytes((0xF0, 0x7E, 0x01, 0xF7))) is None
    assert assembler.add(b"") is None


def test_parse_chunk_handles_f0_f7_and_bare_body():
    chunk = encode_chunk(0, 5, b"hello")
    assert parse_chunk(chunk) == (0, 5, b"hello")
    assert parse_chunk(chunk[1:-1]) == (0, 5, b"hello")


def test_manufacturer_id_is_present():
    assert MANUFACTURER == bytes((0x7D, 0x4D, 0x43))
    for chunk in encode_response("x" * 100):
        assert chunk[0] == 0xF0
        assert chunk[-1] == 0xF7
        assert chunk[1:4] == MANUFACTURER


def test_a_new_response_resets_partial_state():
    assembler = ResponseAssembler()
    first = encode_response("a" * 1400, chunk_size=700)
    assert assembler.add(first[0]) is None
    # A response with a different total length starts a new one.
    second = encode_response("b")
    assert assembler.add(second[0]) == "b"


def test_reset_discards_partial_response():
    assembler = ResponseAssembler()
    chunks = encode_response("x" * 1400, chunk_size=700)
    assembler.add(chunks[0])
    assembler.reset()
    assert assembler.add(chunks[1]) is None
    # The pair completes the (new) response, in either order.
    assert assembler.add(chunks[0]) == "x" * 1400


def test_payload_is_ascii_and_midi_safe():
    payload = json.dumps({"name": "kick 日本語 🎵"}, ensure_ascii=True)
    for chunk in encode_response(payload):
        body = chunk[1:-1]
        assert all(0 <= byte <= 127 for byte in body)
