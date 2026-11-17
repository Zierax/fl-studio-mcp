"""Reassemble responses that FL Studio sends back over MIDI.

FL Studio's scripting interpreter has a read-only filesystem in the older
builds (FL Studio 21 raises ``RuntimeError: File access disabled`` when a
file is opened for writing), so the response cannot always travel through
``mcp_response.json``.  FL Studio *can* send data back to a controller
though -- that is what ``device.midiOutSysex()`` is for -- so the controller
sends the response as system exclusive messages and this module puts it
back together.

The wire format is deliberately simple::

    F0 7D 4D 43 <seq> <total>>14> <total>>7> <total> <payload...> F7

* ``7D 4D 43`` -- manufacturer id (non-commercial, "MC")
* ``seq``       -- index of this chunk, 7 bit
* the three total bytes -- the length of the whole payload, 21 bit, so a
  payload of up to 2 MB fits
* the payload   -- ASCII (the JSON codec escapes everything above 0x7E,
  which keeps every byte inside the 7-bit range MIDI data bytes allow)

The Windows MIDI API refuses buffers larger than 1024 bytes, so the
controller chunks the payload.
"""

from __future__ import annotations

#: Manufacturer id of the response messages.
MANUFACTURER = bytes((0x7D, 0x4D, 0x43))

#: Number of header bytes before the payload: manufacturer + seq + length.
HEADER_SIZE = 7


def encode_chunk(index: int, total: int, payload: bytes) -> bytes:
    """Build one system exclusive chunk of a response."""
    header = MANUFACTURER + bytes(
        (
            index & 0x7F,
            (total >> 14) & 0x7F,
            (total >> 7) & 0x7F,
            total & 0x7F,
        )
    )
    return bytes((0xF0,)) + header + payload + bytes((0xF7,))


def encode_response(text: str, chunk_size: int = 700) -> list[bytes]:
    """Split a response into system exclusive messages."""
    payload = text.encode("ascii", "replace")
    total = len(payload)
    chunks: list[bytes] = []
    offset = 0
    while offset < total:
        chunks.append(encode_chunk(len(chunks), total, payload[offset : offset + chunk_size]))
        offset += chunk_size
    if not chunks:
        chunks.append(encode_chunk(0, 0, b""))
    return chunks


def parse_chunk(data: bytes) -> tuple[int, int, bytes] | None:
    """Parse one system exclusive message.

    Returns ``(index, total, payload)`` or ``None`` when the message is not
    one of ours.
    """
    if not data:
        return None

    body = data
    if body[0] == 0xF0:
        body = body[1:]
    if body and body[-1] == 0xF7:
        body = body[:-1]

    if len(body) < HEADER_SIZE or body[: len(MANUFACTURER)] != MANUFACTURER:
        return None

    index = body[len(MANUFACTURER)] & 0x7F
    length_bytes = body[len(MANUFACTURER) + 1 : len(MANUFACTURER) + 4]
    total = (length_bytes[0] << 14) | (length_bytes[1] << 7) | length_bytes[2]
    payload = body[HEADER_SIZE:]
    return index, total, payload


class ResponseAssembler:
    """Collects response chunks and yields the complete payload."""

    def __init__(self) -> None:
        self._chunks: dict[int, bytes] = {}
        self._total: int | None = None

    def add(self, data: bytes) -> str | None:
        """Add one chunk; return the full response once it is complete."""
        parsed = parse_chunk(data)
        if parsed is None:
            return None

        index, total, payload = parsed
        if self._total is None:
            self._total = total
        elif total != self._total:
            # A new response started; drop what we have.
            self._chunks.clear()
            self._total = total

        self._chunks[index] = payload

        if self._total == 0 and index == 0:
            return ""

        # `total` is the byte length of the whole payload, not the number
        # of chunks.  The response is complete once the chunks we have are
        # contiguous from index 0 and their combined size is `total`.
        count = len(self._chunks)
        if count > 0 and all(index in self._chunks for index in range(count)):
            joined = b"".join(self._chunks[i] for i in range(count))
            if len(joined) == self._total:
                self._chunks.clear()
                self._total = None
                return joined.decode("ascii", "replace")

        return None

    def reset(self) -> None:
        """Forget any partially received response."""
        self._chunks.clear()
        self._total = None
