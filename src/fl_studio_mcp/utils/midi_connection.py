"""MIDI-based connection to FL Studio.

This module provides communication with FL Studio via MIDI messages and JSON files.
The approach is:
1. Write command data to a JSON file
2. Send a MIDI trigger note to FL Studio
3. FL Studio's MIDI controller script executes the command
4. Read the response from a JSON file
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from fl_studio_mcp.utils import paths
from fl_studio_mcp.utils.midi_response import ResponseAssembler
from fl_studio_mcp.utils.ports import describe_choice, find_port


class MIDIConnection:
    """MIDI-based connection to FL Studio.

    Communicates with FL Studio via:
    - JSON files for command/response data
    - MIDI trigger note to execute commands
    """

    TRIGGER_NOTE = 127

    def __init__(self, port_name: str | None = None, hardware_dir: Path | None = None) -> None:
        self._port = None
        self._port_name: str | None = None
        self._connected = False
        self._error: str | None = None
        self._preferred_port = port_name
        self._port_is_guess = False
        self._input_port = None
        self._input_name: str | None = None
        self._reader: threading.Thread | None = None
        self._reader_stop = threading.Event()
        self._assembler = ResponseAssembler()
        self._midi_response: dict[str, Any] | None = None
        self._midi_response_event = threading.Event()

        self._hardware_dir = paths.resolve_hardware_dir(create=True)
        if hardware_dir is not None:
            self._hardware_dir = Path(hardware_dir)
        self._command_file = self._hardware_dir / paths.COMMAND_FILE
        self._response_file = self._hardware_dir / paths.RESPONSE_FILE

    @property
    def port_name(self) -> str | None:
        """Name of the MIDI port currently in use."""
        return self._port_name

    @property
    def hardware_dir(self) -> Path:
        """Folder used for the command/response files."""
        return self._hardware_dir

    def set_hardware_dir(self, hardware_dir: Path) -> None:
        """Point the connection at another command/response folder."""
        self._hardware_dir = Path(hardware_dir)
        self._command_file = self._hardware_dir / paths.COMMAND_FILE
        self._response_file = self._hardware_dir / paths.RESPONSE_FILE

    def set_preferred_port(self, port_name: str | None) -> None:
        """Force the MIDI port used for the next connection attempt."""
        self._preferred_port = port_name

    @property
    def is_connected(self) -> bool:
        return self._connected and self._port is not None

    @property
    def connection_error(self) -> str | None:
        return self._error

    def connect(self) -> bool:
        if self._connected and self._port is not None:
            return True
        self._reader_stop.clear()
        self._assembler.reset()
        self._midi_response = None
        self._midi_response_event.clear()

        try:
            import mido
        except ImportError:
            self._error = (
                "mido library not installed. Install with: pip install mido python-rtmidi"
            )
            return False

        try:
            output_ports = mido.get_output_names()
        except Exception as e:
            self._error = f"Failed to get MIDI ports: {e}"
            return False

        if not output_ports:
            self._error = (
                "No MIDI output ports found. Create a virtual MIDI port "
                "(loopMIDI on Windows, IAC Driver on macOS) and make sure "
                "FL Studio listens on it."
            )
            return False

        target_port = find_port(output_ports, self._preferred_port)
        if target_port is None:
            self._error = (
                f"No MIDI port matching {self._preferred_port!r} was found. "
                f"Available ports: {output_ports}"
            )
            return False

        try:
            self._port = mido.open_output(target_port)
            self._port_name = target_port
            self._connected = True
            self._open_input_port(target_port)
            choice = describe_choice(output_ports, target_port)
            self._port_is_guess = bool(choice["is_guess"])
            if self._port_is_guess:
                self._error = (
                    f"Connected to {target_port!r}, but that port does not look "
                    "like the FL Studio MCP bridge. If calls time out, select "
                    "the virtual port FL Studio listens on explicitly."
                )
            else:
                self._error = None
            return True
        except Exception as e:
            self._error = f"Failed to open MIDI port '{target_port}': {e}"
            return False

    def _open_input_port(self, output_name: str) -> None:
        """Open the MIDI input port the controller answers on.

        FL Studio sends the response to the output port that is linked to
        the controller; that port is the counterpart of the one the server
        writes to, so the input with the same name is the right one.
        """
        if self._input_port is not None:
            return

        try:
            import mido
            input_names = list(mido.get_input_names())
        except Exception:
            return

        candidates: list[str] = []
        if output_name in input_names:
            candidates.append(output_name)
        for name in input_names:
            if name in candidates:
                continue
            if "flstudiomcp" in name.lower().replace(" ", ""):
                candidates.append(name)

        for name in candidates:
            try:
                self._input_port = mido.open_input(name)
            except Exception:
                continue
            self._input_name = name
            self._start_reader()
            return

    def _start_reader(self) -> None:
        """Read system exclusive messages in the background."""
        if self._reader is not None or self._input_port is None:
            return

        def _loop() -> None:
            while not self._reader_stop.is_set():
                try:
                    for message in self._input_port:
                        if self._reader_stop.is_set():
                            return
                        if getattr(message, "type", None) != "sysex":
                            continue
                        data = bytes(getattr(message, "data", b"") or b"")
                        text = self._assembler.add(data)
                        if text is None:
                            continue
                        try:
                            self._midi_response = json.loads(text)
                        except Exception:
                            continue
                        self._midi_response_event.set()
                except Exception:
                    time.sleep(0.05)

        self._reader = threading.Thread(target=_loop, daemon=True)
        self._reader.start()

    def _take_midi_response(self) -> dict[str, Any] | None:
        """Return a response that arrived over MIDI, if there is one."""
        if not self._midi_response_event.is_set():
            return None
        response = self._midi_response
        self._midi_response = None
        self._midi_response_event.clear()
        return response

    def disconnect(self) -> None:
        self._reader_stop.set()
        if self._reader is not None:
            self._reader = None
        if self._input_port is not None:
            try:
                self._input_port.close()
            except Exception:
                pass
            self._input_port = None
        if self._port is not None:
            try:
                self._port.close()
            except Exception:
                pass
            self._port = None
        self._connected = False
        self._port_name = None

    def ensure_connected(self) -> None:
        if not self.is_connected:
            if not self.connect():
                raise RuntimeError(
                    self._error or "Failed to connect to FL Studio via MIDI"
                )

    def _write_command(self, command: dict[str, Any]) -> None:
        """Write the command file atomically.

        The controller script reads the file as soon as the MIDI trigger
        arrives, so a partially written file would show up as a JSON error
        inside FL Studio.  Writing to a temporary file and renaming it makes
        the swap atomic on both POSIX and Windows.
        """
        payload = json.dumps(command, indent=2)
        temporary = self._command_file.with_name(self._command_file.name + ".tmp")
        temporary.write_text(payload, encoding="utf-8")
        os.replace(temporary, self._command_file)

    def send_command(
        self,
        action: str,
        params: dict[str, Any] | None = None,
        timeout: float = 5.0,
    ) -> dict[str, Any]:
        self.ensure_connected()

        # The id lets the server recognise a late response that belongs to an
        # earlier command instead of mistaking it for this one.
        request_id = uuid.uuid4().hex
        command = {
            "id": request_id,
            "action": action,
            "params": params or {},
        }

        try:
            self._write_command(command)
        except Exception as e:
            return {"success": False, "error": f"Failed to write command file: {e}"}

        # Keep the response file in place: older FL Studio interpreters can
        # write to an existing file but cannot create a new one.  Empty it
        # instead of deleting it.
        try:
            if self._response_file.exists():
                self._response_file.write_text("", encoding="utf-8")
            else:
                self._response_file.touch()
        except Exception:
            pass
        self._assembler.reset()
        self._midi_response = None
        self._midi_response_event.clear()

        try:
            import mido
            trigger_msg = mido.Message("note_on", note=self.TRIGGER_NOTE, velocity=127)
            self._port.send(trigger_msg)
        except Exception as e:
            return {"success": False, "error": f"Failed to send MIDI trigger: {e}"}

        return self._wait_for_response(timeout, request_id)

    def _wait_for_response(self, timeout: float, request_id: str | None = None) -> dict[str, Any]:
        start_time = time.time()
        poll_interval = 0.05
        last_error: str | None = None

        while time.time() - start_time < timeout:
            # Older FL Studio builds send the response over MIDI because
            # they cannot write to the filesystem.
            midi_response = self._take_midi_response()
            if midi_response is not None:
                return midi_response

            if self._response_file.exists():
                try:
                    response_text = self._response_file.read_text(encoding="utf-8")
                except Exception as e:
                    last_error = f"Failed to read response: {e}"
                    time.sleep(poll_interval)
                    continue

                if not response_text.strip():
                    time.sleep(poll_interval)
                    continue

                try:
                    response = json.loads(response_text)
                except json.JSONDecodeError as e:
                    # The controller may still be writing the file; give it
                    # a moment before giving up.
                    last_error = f"Invalid JSON in response: {e}"
                    time.sleep(poll_interval)
                    continue

                # A response that carries a different id belongs to an
                # earlier command: keep waiting for the right one.
                response_id = response.get("id") if isinstance(response, dict) else None
                if (
                    request_id is not None
                    and response_id is not None
                    and response_id != request_id
                ):
                    time.sleep(poll_interval)
                    continue

                return response

            time.sleep(poll_interval)

        if last_error:
            return {
                "success": False,
                "error": (
                    f"Timeout waiting for FL Studio response after {timeout}s "
                    f"({last_error}). Make sure FL Studio is running and the "
                    "MCP controller is enabled in MIDI Settings."
                ),
            }

        return {
            "success": False,
            "error": (
                f"Timeout waiting for FL Studio response after {timeout}s. "
                "Make sure FL Studio is running and the MCP controller is enabled "
                f"in MIDI Settings. The server is using MIDI port "
                f"{self._port_name!r} and the command folder {self._hardware_dir}."
            ),
        }

    def get_status(self) -> dict[str, Any]:
        try:
            import mido
            output_ports = mido.get_output_names()
        except Exception:
            output_ports = []

        return {
            "connected": self.is_connected,
            "port_name": self._port_name,
            "port_is_guess": self._port_is_guess,
            "preferred_port": self._preferred_port,
            "available_ports": output_ports,
            "hardware_dir": str(self._hardware_dir),
            "hardware_dir_candidates": [str(p) for p in paths.candidate_directories()],
            "command_file": str(self._command_file),
            "response_file": str(self._response_file),
            "error": self._error,
        }


_connection: MIDIConnection | None = None


def get_connection() -> MIDIConnection:
    global _connection
    if _connection is None:
        _connection = MIDIConnection()
    return _connection


def reset_connection() -> None:
    global _connection
    if _connection is not None:
        _connection.disconnect()
        _connection = None
