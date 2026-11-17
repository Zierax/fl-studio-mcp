"""Tests for the dual response channel.

These reproduce the second finding in GitHub issue #2: FL Studio 21's
scripting interpreter has a read-only filesystem, so the controller cannot
write ``mcp_response.json``.  The bridge must fall back to sending the
response over MIDI.
"""

from __future__ import annotations

import builtins
import json
import sys
import types

import pytest

from fl_studio_mcp.utils import midi_connection
from tests.conftest import (
    DEVICE_SCRIPT,
    FL_UNAVAILABLE_MODULES,
    BlockedImports,
    install_stubs,
    restore_modules,
)

builtin_open = builtins.open


class ReadOnlyFile(types.ModuleType):
    """A file object that refuses every write (FL Studio 21 behaviour)."""

    def __init__(self, data: bytes = b""):
        self._data = data

    def write(self, data):
        raise RuntimeError("File access disabled")

    def read(self):
        return self._data

    def flush(self):
        pass

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class ReadOnlyIO(types.ModuleType):
    """An `_io` replacement where opens for writing are blocked."""

    @staticmethod
    def open(path, mode="r", *args, **kwargs):
        if "w" in mode or "+" in mode or "a" in mode or "x" in mode:
            raise RuntimeError("File access disabled")
        with builtin_open(path, "rb") as handle:
            return ReadOnlyFile(handle.read())




class FakeMessage:
    def __init__(self, kind, note=None, velocity=None, data=None):
        self.type = kind
        self.kind = kind
        self.note = note
        self.velocity = velocity
        self.data = data or b""


class FakePort:
    def __init__(self, name, on_send=None, on_message=None):
        self.name = name
        self.on_send = on_send
        self.on_message = on_message
        self.closed = False

    def send(self, message):
        if self.on_send is not None:
            self.on_send(message)

    def close(self):
        self.closed = True


class FakeMido(types.ModuleType):
    """A fake MIDI driver with an output port and a matching input port."""

    PORT = "FL Studio MCP 1"

    def __init__(self):
        super().__init__("mido")
        self.output = None
        self.input = None
        self.sent_sysex: list[bytes] = []

    def get_output_names(self):
        return ["Microsoft GS Wavetable Synth 0", self.PORT]

    def get_input_names(self):
        return [self.PORT]

    def open_output(self, name):
        self.output = FakePort(
            name, on_send=lambda message: self._deliver(message)
        )
        return self.output

    def open_input(self, name):
        self.input = FakePort(name)
        return self.input

    def Message(self, kind, note=None, velocity=None):
        return FakeMessage(kind, note, velocity)

    def _deliver(self, message):
        """Deliver the trigger to the controller, record its sysex answers."""
        if self.trigger is not None:
            self.trigger(message)

    trigger = None


@pytest.fixture
def fl21(tmp_path, monkeypatch):
    """A FL Studio 21 look-alike: stripped stdlib, read-only files, MIDI out."""
    hardware = tmp_path / "FLStudioMCP"
    hardware.mkdir()
    (hardware / DEVICE_SCRIPT.name).write_text(
        DEVICE_SCRIPT.read_text(encoding="utf-8"), encoding="utf-8"
    )
    # The server pre-creates an empty response file.
    (hardware / "mcp_response.json").write_text("", encoding="utf-8")

    stubs = install_stubs()
    device = sys.modules["device"]
    device.isAssigned = lambda: True
    sent: list[bytes] = []
    device.midiOutSysex = lambda message: sent.append(bytes(message))
    monkeypatch.syspath_prepend(str(hardware))

    source = DEVICE_SCRIPT.read_text(encoding="utf-8")
    controller = types.ModuleType("device_FLStudioMCP")
    controller.__file__ = str(hardware / DEVICE_SCRIPT.name)
    with BlockedImports(FL_UNAVAILABLE_MODULES):
        exec(compile(source, str(controller.__file__), "exec"), controller.__dict__)

    # Replace _open with one that forbids write modes, like FL Studio 21.
    controller._open = ReadOnlyIO.open

    yield controller, hardware, sent, stubs

    restore_modules(stubs)


def test_the_file_channel_is_blocked(fl21):
    controller, hardware, sent, stubs = fl21
    ok, error = controller._write_text(
        str(hardware / "mcp_response.json"), '{"success": true}'
    )
    assert ok is False
    assert "File access disabled" in error


def test_the_controller_sends_the_response_over_midi(fl21):
    controller, hardware, sent, stubs = fl21
    command = {"id": "abc", "action": "transport.getStatus", "params": {}}
    (hardware / "mcp_command.json").write_text(json.dumps(command), encoding="utf-8")

    result = controller.write_response({"success": True, "is_playing": False, "id": "abc"})

    assert result is True
    assert sent, "the controller must send the response as sysex"
    assert (hardware / "mcp_response.json").read_text() == "", "the file stays empty"


def test_end_to_end_with_a_read_only_filesystem(fl21, monkeypatch):
    """A complete command travels there by file and back by MIDI."""
    controller, hardware, sent, stubs = fl21

    fake_mido = FakeMido()
    monkeypatch.setitem(sys.modules, "mido", fake_mido)

    connection = midi_connection.MIDIConnection(hardware_dir=hardware)

    def deliver_to_controller(message):
        controller.execute_pending_command()
        # Feed the sysex messages the controller just produced into the
        # server's input port, in order.
        for chunk in sent:
            data = chunk[1:-1] if chunk[0] == 0xF0 else chunk
            text = connection._assembler.add(data)
            if text is not None:
                connection._midi_response = json.loads(text)
                connection._midi_response_event.set()

    fake_mido.trigger = deliver_to_controller

    result = connection.send_command("transport.getStatus", {}, timeout=5.0)

    assert result["success"] is True
    assert "is_playing" in result
    assert result["id"]
    assert sent, "the response must have travelled over MIDI"
