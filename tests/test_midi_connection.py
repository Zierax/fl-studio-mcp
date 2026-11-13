"""Tests for the MIDI command channel.

The command/response exchange is the heart of the bridge, so it is tested
with a fake ``mido`` module: no virtual MIDI driver is needed in CI.
"""

from __future__ import annotations

import json
import sys
import types

import pytest

from fl_studio_mcp.utils import midi_connection


class FakeMessage:
    def __init__(self, kind, note=None, velocity=None):
        self.kind = kind
        self.note = note
        self.velocity = velocity


class FakePort:
    def __init__(self, name):
        self.name = name
        self.sent = []
        self.closed = False

    def send(self, message):
        self.sent.append(message)

    def close(self):
        self.closed = True


class FakeMido(types.ModuleType):
    def __init__(self, output_names):
        super().__init__("mido")
        self._output_names = list(output_names)
        self.opened: list[str] = []

    def get_output_names(self):
        return list(self._output_names)

    def open_output(self, name):
        self.opened.append(name)
        return FakePort(name)

    def Message(self, kind, note=None, velocity=None):
        return FakeMessage(kind, note, velocity)


@pytest.fixture
def fake_mido(monkeypatch):
    """Install a fake ``mido`` module with a configurable port list."""
    state = {"names": ["FLStudioMCP 1"], "module": None}

    def _install(names):
        module = FakeMido(names)
        state["names"] = names
        state["module"] = module
        monkeypatch.setitem(sys.modules, "mido", module)
        return module

    state["install"] = _install
    _install(state["names"])
    return state


@pytest.fixture
def connection(tmp_path, fake_mido):
    """A MIDIConnection bound to a temporary hardware folder."""
    hardware = tmp_path / "FLStudioMCP"
    hardware.mkdir()
    return midi_connection.MIDIConnection(hardware_dir=hardware), hardware


def test_connect_uses_the_bridge_port(connection, fake_mido):
    fake_mido["install"](["Microsoft GS Wavetable Synth 0", "FLStudioMCP 1"])
    conn, _ = connection
    assert conn.connect() is True
    assert conn.port_name == "FLStudioMCP 1"
    assert conn.get_status()["port_is_guess"] is False


def test_connect_reports_a_guess_for_unknown_ports(connection, fake_mido):
    fake_mido["install"](["Microsoft GS Wavetable Synth 0"])
    conn, _ = connection
    assert conn.connect() is True
    status = conn.get_status()
    assert status["port_is_guess"] is True
    assert "does not look like" in status["error"]


def test_connect_can_be_forced_to_a_port(connection, fake_mido):
    fake_mido["install"](["A", "B"])
    conn, _ = connection
    conn.set_preferred_port("B")
    assert conn.connect() is True
    assert conn.port_name == "B"


def test_connect_fails_without_ports(connection, fake_mido):
    fake_mido["install"]([])
    conn, _ = connection
    assert conn.connect() is False
    assert "No MIDI output ports" in conn.connection_error


def test_connect_fails_when_the_preferred_port_is_missing(connection, fake_mido):
    fake_mido["install"](["A"])
    conn, _ = connection
    conn.set_preferred_port("missing")
    assert conn.connect() is False
    assert "was found" in conn.connection_error


def test_command_roundtrip(connection, fake_mido):
    conn, hardware = connection
    conn.connect()

    # Simulate the controller script answering the command.
    def respond():
        command_file = hardware / "mcp_command.json"
        for _ in range(200):
            if command_file.exists():
                payload = json.loads(command_file.read_text(encoding="utf-8"))
                (hardware / "mcp_response.json").write_text(
                    json.dumps({"success": True, "echo": payload["action"]}),
                    encoding="utf-8",
                )
                return
        raise AssertionError("the command file was never written")

    import threading

    thread = threading.Thread(target=respond)
    thread.start()
    try:
        result = conn.send_command("transport.start", {"x": 1}, timeout=5.0)
    finally:
        thread.join()

    assert result["success"] is True
    assert result["echo"] == "transport.start"


def test_command_file_is_utf8_encoded(connection, fake_mido):
    conn, hardware = connection
    conn.connect()
    conn.send_command("channels.setChannelName", {"name": "kick é 日本語"}, timeout=0.2)
    raw = (hardware / "mcp_command.json").read_bytes()
    assert raw.decode("utf-8")


def test_timeout_reports_the_port_and_folder(connection, fake_mido):
    conn, hardware = connection
    conn.connect()
    result = conn.send_command("transport.start", {}, timeout=0.2)
    assert result["success"] is False
    assert "Timeout" in result["error"]
    assert str(hardware) in result["error"]


def test_status_lists_candidates(connection, fake_mido):
    conn, hardware = connection
    conn.connect()
    status = conn.get_status()
    assert status["hardware_dir"] == str(hardware)
    assert status["command_file"] == str(hardware / "mcp_command.json")
    assert status["response_file"] == str(hardware / "mcp_response.json")
    assert status["hardware_dir_candidates"]
