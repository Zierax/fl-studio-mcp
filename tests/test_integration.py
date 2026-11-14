"""End-to-end test of the bridge on a FL Studio 21 style interpreter.

This is the regression test for GitHub issue #2: the controller script is
loaded with the standard library modules FL Studio does not ship blocked,
and a complete command/response round-trip is driven through the real
``MIDIConnection`` with a fake MIDI driver standing in for FL Studio.
"""

from __future__ import annotations

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


class FakeMessage:
    def __init__(self, kind, note=None, velocity=None):
        self.kind = kind
        self.note = note
        self.velocity = velocity


class FakePort:
    """A MIDI output port that behaves like FL Studio's input."""

    def __init__(self, name, on_trigger=None):
        self.name = name
        self.on_trigger = on_trigger
        self.sent = []
        self.closed = False

    def send(self, message):
        self.sent.append(message)
        if self.on_trigger is not None and message.note == 127:
            self.on_trigger()

    def close(self):
        self.closed = True


class FakeMido(types.ModuleType):
    def __init__(self, output_names):
        super().__init__("mido")
        self._output_names = list(output_names)
        self.port = None

    def get_output_names(self):
        return list(self._output_names)

    def open_output(self, name):
        self.port = FakePort(name, on_trigger=self._trigger)
        return self.port

    def Message(self, kind, note=None, velocity=None):
        return FakeMessage(kind, note, velocity)

    def _trigger(self):
        pass


@pytest.fixture
def fl21_environment(tmp_path, monkeypatch):
    """A FL Studio 21 look-alike: no standard library, a hardware folder."""
    hardware = tmp_path / "FLStudioMCP"
    hardware.mkdir()

    # The controller script is installed in the hardware folder, and FL
    # Studio puts that folder on sys.path.
    (hardware / DEVICE_SCRIPT.name).write_text(
        DEVICE_SCRIPT.read_text(encoding="utf-8"), encoding="utf-8"
    )

    stubs = install_stubs()
    monkeypatch.syspath_prepend(str(hardware))

    source = DEVICE_SCRIPT.read_text(encoding="utf-8")
    device = types.ModuleType("device_FLStudioMCP")
    device.__file__ = str(hardware / DEVICE_SCRIPT.name)

    # Loading the script must work without the standard library ...
    with BlockedImports(FL_UNAVAILABLE_MODULES):
        exec(compile(source, str(device.__file__), "exec"), device.__dict__)

    # ... and so must running it: from now on only imports issued by the
    # controller script itself are rejected.
    with BlockedImports(FL_UNAVAILABLE_MODULES, namespaces=(device.__dict__,)):
        yield device, hardware

    restore_modules(stubs)


def test_the_controller_finds_its_own_folder_without_os(fl21_environment):
    """FL Studio's Hardware folder is discovered through sys.path."""
    device, hardware = fl21_environment
    assert device.SCRIPT_DIR == str(hardware)
    assert device.COMMAND_FILE.endswith("mcp_command.json")
    assert device.RESPONSE_FILE.endswith("mcp_response.json")


def test_command_roundtrip_on_fl_studio_21(fl21_environment, monkeypatch):
    """A complete command/response cycle works without the standard library."""
    device, hardware = fl21_environment

    # The controller reacts to the MIDI trigger, like the real script does.
    fake_mido = FakeMido(["FLStudioMCP 1"])
    monkeypatch.setitem(sys.modules, "mido", fake_mido)

    connection = midi_connection.MIDIConnection(hardware_dir=hardware)

    def trigger():
        device.execute_pending_command()

    fake_mido._trigger = trigger

    result = connection.send_command("transport.getStatus", {}, timeout=5.0)

    assert result["success"] is True
    assert "is_playing" in result
    assert result["id"], "the response must carry the request id"


def test_generic_action_works_on_fl_studio_21(fl21_environment, monkeypatch):
    """The generic command layer also works without the standard library."""
    device, hardware = fl21_environment

    fake_mido = FakeMido(["FLStudioMCP 1"])
    monkeypatch.setitem(sys.modules, "mido", fake_mido)

    connection = midi_connection.MIDIConnection(hardware_dir=hardware)
    fake_mido._trigger = device.execute_pending_command

    result = connection.send_command(
        "channels.selectChannel", {"channel": 2, "select": True}, timeout=5.0
    )
    assert result["success"] is True
    assert result["fn"] == "selectChannel"
    assert result["args"] == [2, 1]


def test_unicode_survives_the_roundtrip(fl21_environment, monkeypatch):
    """Non-ASCII parameters are not mangled by the encoding."""
    device, hardware = fl21_environment

    fake_mido = FakeMido(["FLStudioMCP 1"])
    monkeypatch.setitem(sys.modules, "mido", fake_mido)

    connection = midi_connection.MIDIConnection(hardware_dir=hardware)
    fake_mido._trigger = device.execute_pending_command

    name = "kick é 日本語"
    result = connection.send_command(
        "channels.setName", {"index": 0, "name": name}, timeout=5.0
    )
    assert result["success"] is True
    # The controller echoed the name back through its own JSON encoder.
    assert result["name"] == name

    command = json.loads((hardware / "mcp_command.json").read_text(encoding="utf-8"))
    assert command["params"]["name"] == name
