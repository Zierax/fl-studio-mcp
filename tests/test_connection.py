"""Tests for the public connection wrapper.

The wrapper is what the tools use, so the overrides it accepts have to
reach the MIDI layer -- otherwise "connect to this exact port" quietly
does nothing.
"""

from __future__ import annotations

import sys
import types

import pytest

from fl_studio_mcp.utils import connection as connection_module


class FakePort:
    def __init__(self, name):
        self.name = name
        self.closed = False

    def send(self, message):
        pass

    def close(self):
        self.closed = True


class FakeMido(types.ModuleType):
    def __init__(self, output_names):
        super().__init__("mido")
        self._output_names = list(output_names)

    def get_output_names(self):
        return list(self._output_names)

    def open_output(self, name):
        return FakePort(name)

    def Message(self, kind, note=None, velocity=None):
        return None


@pytest.fixture
def fake_mido(monkeypatch):
    module = FakeMido(["Port A", "Port B"])
    monkeypatch.setitem(sys.modules, "mido", module)
    yield module


@pytest.fixture(autouse=True)
def _clean_connection():
    yield
    connection_module.reset_connection()


def test_reset_connection_forwards_the_port(fake_mido, tmp_path):
    connection_module.reset_connection(port_name="Port B")
    conn = connection_module.get_connection()
    conn.ensure_connected()
    assert conn.get_status()["port_name"] == "Port B"


def test_reset_connection_forwards_the_folder(fake_mido, tmp_path):
    hardware = tmp_path / "FLStudioMCP"
    hardware.mkdir()
    connection_module.reset_connection(hardware_dir=hardware)
    conn = connection_module.get_connection()
    conn.ensure_connected()
    status = conn.get_status()
    assert status["hardware_dir"] == str(hardware)
    assert status["command_file"] == str(hardware / "mcp_command.json")


def test_connect_can_switch_the_port(fake_mido):
    conn = connection_module.get_connection()
    conn.ensure_connected()
    assert conn.get_status()["port_name"] == "Port A"

    assert conn.connect(port_name="Port B") is True
    assert conn.get_status()["port_name"] == "Port B"


def test_connect_can_switch_the_folder(fake_mido, tmp_path):
    hardware = tmp_path / "other"
    hardware.mkdir()
    conn = connection_module.get_connection()
    assert conn.connect(hardware_dir=hardware) is True
    assert conn.get_status()["hardware_dir"] == str(hardware)


def test_an_unknown_port_fails_loudly(fake_mido):
    conn = connection_module.get_connection()
    conn.ensure_connected()
    assert conn.connect(port_name="does not exist") is False
    assert "does not exist" in (conn.connection_error or "")
