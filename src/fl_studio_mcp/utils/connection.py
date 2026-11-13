"""FL Studio connection management via MIDI.

This module provides the connection interface to FL Studio using MIDI messages
and JSON files for communication. It replaces the previous Flapi-based approach.

The communication flow is:
1. MCP server writes command to JSON file
2. MCP server sends MIDI trigger note
3. FL Studio controller script executes the command
4. FL Studio controller writes response to JSON file
5. MCP server reads response
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fl_studio_mcp.utils.midi_connection import (
    get_connection as get_midi_connection,
)
from fl_studio_mcp.utils.midi_connection import (
    reset_connection as reset_midi_connection,
)


class FLConnection:
    """Wrapper for FL Studio connection via MIDI.

    Provides a simple interface for sending commands to FL Studio
    and receiving responses.
    """

    def __init__(self, port_name: str | None = None, hardware_dir: Path | None = None) -> None:
        self._midi = get_midi_connection()
        self._port_name = port_name
        self._hardware_dir = hardware_dir

    def ensure_connected(self) -> None:
        """Ensure connection to FL Studio is active. Raises RuntimeError if not."""
        self._midi.ensure_connected()

    def connect(
        self,
        port_name: str | None = None,
        hardware_dir: Path | None = None,
    ) -> bool:
        """(Re)connect to FL Studio, optionally forcing a port and folder.

        Args:
            port_name: Exact MIDI port to use (e.g. ``"FLStudioMCP 1"``).
                When omitted the best matching port is chosen automatically.
            hardware_dir: Folder holding the command/response files. Useful
                when FL Studio's user data folder was relocated.
        """
        wanted_port = port_name or self._port_name
        wanted_dir = hardware_dir or self._hardware_dir
        if wanted_port is not None:
            self._port_name = wanted_port
        if wanted_dir is not None:
            self._hardware_dir = Path(wanted_dir)

        # A different port or folder requires a fresh connection.
        self._midi.disconnect()
        if wanted_dir is not None:
            self._midi.set_hardware_dir(Path(wanted_dir))
        if wanted_port is not None:
            self._midi.set_preferred_port(wanted_port)
        return self._midi.connect()

    @property
    def is_connected(self) -> bool:
        """Check if connected to FL Studio."""
        return self._midi.is_connected

    @property
    def connection_error(self) -> str | None:
        """Get the last connection error, if any."""
        return self._midi.connection_error

    def send_command(
        self,
        action: str,
        params: dict[str, Any] | None = None,
        timeout: float = 2.0,
    ) -> dict[str, Any]:
        """Send a command to FL Studio and wait for response.

        Args:
            action: The command action (e.g., "transport.start", "mixer.setTrackVolume")
            params: Optional parameters for the command
            timeout: Maximum time to wait for response in seconds

        Returns:
            Response dictionary from FL Studio

        Raises:
            RuntimeError: If not connected or command fails
        """
        return self._midi.send_command(action, params, timeout)

    def get_status(self) -> dict[str, Any]:
        """Get connection status information."""
        return self._midi.get_status()


# Global connection instance
_connection: FLConnection | None = None


def get_connection() -> FLConnection:
    """Get the global FL Studio connection instance."""
    global _connection
    if _connection is None:
        _connection = FLConnection()
    return _connection


def reset_connection(
    port_name: str | None = None,
    hardware_dir: Path | None = None,
) -> None:
    """Reset the connection state to allow reconnection attempts."""
    global _connection
    reset_midi_connection()
    _connection = None
    if port_name is not None or hardware_dir is not None:
        _connection = FLConnection(port_name=port_name, hardware_dir=hardware_dir)
