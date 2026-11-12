# name=FL Studio MCP Controller
# supportedDevices=FLStudioMCP

MCP_VERSION = 3

"""
FL Studio MIDI Controller Script for MCP Integration.

This script runs inside FL Studio and receives MIDI trigger messages from the
MCP server. When triggered, it reads a command from a JSON file, executes the
corresponding FL Studio API function, and writes the response to another JSON file.

Communication flow:
1. MCP server writes command to mcp_command.json
2. MCP server sends MIDI note 127 (trigger)
3. This script receives the trigger via OnMidiMsg()
4. Script reads command JSON, executes FL Studio API
5. Script writes response to mcp_response.json
6. MCP server reads response

Compatibility with FL Studio's embedded Python
----------------------------------------------
FL Studio does not ship a normal Python installation: it embeds a *stripped*
CPython interpreter whose standard library is almost entirely removed.  On
FL Studio 21 the bundled ``Shared/Python/Lib`` folder only contains
``midi.py`` and ``utils.py``, so ``import json`` -- and ``os``, ``pathlib``,
``importlib``, ``builtins`` and friends -- fail with
``ModuleNotFoundError`` and the controller never finishes initialising.

Everything this script needs is therefore implemented with builtins only:

* a self-contained JSON codec (``_json_dumps`` / ``_json_loads``),
* string based path helpers instead of ``os.path`` / ``pathlib``,
* ``__import__`` based module probing instead of ``importlib``.

The only modules imported are ``sys`` (always built into the interpreter),
``time`` (built into the interpreter as well) and the FL Studio API modules.
"""

import sys

# FL Studio API modules (available when running inside FL Studio)
import channels
import mixer
import plugins
import transport

try:
    import general
except ImportError:  # pragma: no cover
    general = None

try:
    import ui
except ImportError:  # pragma: no cover
    ui = None

try:
    import playlist
except ImportError:  # pragma: no cover
    playlist = None

try:
    import patterns
except ImportError:  # pragma: no cover
    patterns = None

try:
    import arrangement
except ImportError:  # pragma: no cover
    arrangement = None

try:
    import midi
except ImportError:  # pragma: no cover
    midi = None

try:
    import device
except ImportError:  # pragma: no cover
    device = None

try:
    import time as _time
except ImportError:  # pragma: no cover - `time` is built into FL's interpreter
    _time = None


# =============================================================================
# SELF-CONTAINED JSON CODEC
#
# Replaces the `json` standard library module, which FL Studio does not
# ship.  The output is byte compatible with `json.dumps(..., indent=2)`:
# strings are escaped to pure ASCII (so the file can be read back with any
# locale encoding), floats use `repr()`, and non-finite floats use the
# `NaN` / `Infinity` / `-Infinity` literals that Python's json accepts.
# =============================================================================

_JSON_ESCAPE_MAP = {
    '"': '\\"',
    "\\": "\\\\",
    "\b": "\\b",
    "\f": "\\f",
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
}

_JSON_UNESCAPE_MAP = {
    '"': '"',
    "\\": "\\",
    "/": "/",
    "b": "\b",
    "f": "\f",
    "n": "\n",
    "r": "\r",
    "t": "\t",
}


def _json_escape(value):
    """Return *value* as an ASCII-only JSON string literal."""
    chunks = ['"']
    for char in value:
        escaped = _JSON_ESCAPE_MAP.get(char)
        if escaped is not None:
            chunks.append(escaped)
            continue
        code = ord(char)
        if 0x20 <= code <= 0x7E:
            chunks.append(char)
        elif code > 0xFFFF:
            # Non-BMP code point -> encode as a UTF-16 surrogate pair.
            code -= 0x10000
            chunks.append("\\u%04x\\u%04x" % (0xD800 + (code >> 10), 0xDC00 + (code & 0x3FF)))
        else:
            chunks.append("\\u%04x" % code)
    chunks.append('"')
    return "".join(chunks)


def _json_key(key):
    """Convert a mapping key into its JSON string form."""
    if isinstance(key, str):
        return key
    if key is True:
        return "true"
    if key is False:
        return "false"
    if key is None:
        return "null"
    return str(key)


def _json_number(value):
    """Format a float the way Python's json module does."""
    if value != value:  # NaN
        return "NaN"
    if value == float("inf"):
        return "Infinity"
    if value == float("-inf"):
        return "-Infinity"
    return repr(value)


def _json_write(value, out, indent, level):
    """Append the JSON representation of *value* to the *out* list."""
    if value is None:
        out.append("null")
    elif value is True:
        out.append("true")
    elif value is False:
        out.append("false")
    elif isinstance(value, str):
        out.append(_json_escape(value))
    elif isinstance(value, int):
        out.append(str(value))
    elif isinstance(value, float):
        out.append(_json_number(value))
    elif isinstance(value, dict):
        _json_write_object(value, out, indent, level)
    elif isinstance(value, (list, tuple)):
        _json_write_array(value, out, indent, level)
    else:
        # Not a JSON type: mirror `_serialize()` and use its repr.
        out.append(_json_escape(repr(value)))


def _json_write_object(value, out, indent, level):
    """Append a JSON object to the *out* list."""
    if not value:
        out.append("{}")
        return
    newline = "\n" if indent else ""
    pad = " " * (indent * (level + 1))
    closing = " " * (indent * level)
    out.append("{")
    first = True
    for key, item in value.items():
        if not first:
            out.append(",")
        first = False
        out.append(newline)
        out.append(pad)
        out.append(_json_escape(_json_key(key)))
        out.append(":")
        if indent:
            out.append(" ")
        _json_write(item, out, indent, level + 1)
    out.append(newline)
    out.append(closing)
    out.append("}")


def _json_write_array(value, out, indent, level):
    """Append a JSON array to the *out* list."""
    if not value:
        out.append("[]")
        return
    newline = "\n" if indent else ""
    pad = " " * (indent * (level + 1))
    closing = " " * (indent * level)
    out.append("[")
    first = True
    for item in value:
        if not first:
            out.append(",")
        first = False
        out.append(newline)
        out.append(pad)
        _json_write(item, out, indent, level + 1)
    out.append(newline)
    out.append(closing)
    out.append("]")


def _json_dumps(value, indent=2):
    """Serialise *value* into a JSON document.

    Mirrors ``json.dumps(value, indent=indent)`` but without importing the
    standard library.
    """
    out = []
    _json_write(value, out, indent, 0)
    return "".join(out)


class _JsonError(ValueError):
    """Raised when a JSON document cannot be parsed."""


class _JsonParser(object):
    """A small recursive-descent JSON parser."""

    __slots__ = ("_text", "_index", "_length")

    def __init__(self, text):
        self._text = text
        self._index = 0
        self._length = len(text)

    def error(self, message):
        """Raise a parse error positioned at the current offset."""
        raise _JsonError("%s: char %d" % (message, self._index))

    def parse(self):
        """Parse the whole document and return the resulting value."""
        self._skip_whitespace()
        value = self._parse_value()
        self._skip_whitespace()
        if self._index != self._length:
            self.error("Extra data")
        return value

    def _skip_whitespace(self):
        text = self._text
        index = self._index
        length = self._length
        while index < length and text[index] in " \t\n\r":
            index += 1
        self._index = index

    def _parse_value(self):
        if self._index >= self._length:
            self.error("Expecting value")
        char = self._text[self._index]
        if char == "{":
            return self._parse_object()
        if char == "[":
            return self._parse_array()
        if char == '"':
            return self._parse_string()
        if char == "t":
            return self._parse_literal("true", True)
        if char == "f":
            return self._parse_literal("false", False)
        if char == "n":
            return self._parse_literal("null", None)
        if char == "N":
            return self._parse_literal("NaN", float("nan"))
        if char == "I":
            return self._parse_literal("Infinity", float("inf"))
        if char == "-" and self._text.startswith("-Infinity", self._index):
            self._index += len("-Infinity")
            return float("-inf")
        return self._parse_number()

    def _parse_literal(self, literal, value):
        if self._text.startswith(literal, self._index):
            self._index += len(literal)
            return value
        self.error("Expecting value")

    def _parse_object(self):
        result = {}
        self._index += 1  # consume '{'
        self._skip_whitespace()
        if self._index < self._length and self._text[self._index] == "}":
            self._index += 1
            return result
        while True:
            self._skip_whitespace()
            if self._index >= self._length or self._text[self._index] != '"':
                self.error("Expecting property name enclosed in double quotes")
            key = self._parse_string()
            self._skip_whitespace()
            if self._index >= self._length or self._text[self._index] != ":":
                self.error("Expecting ':' delimiter")
            self._index += 1
            self._skip_whitespace()
            result[key] = self._parse_value()
            self._skip_whitespace()
            if self._index >= self._length:
                self.error("Expecting ',' delimiter")
            char = self._text[self._index]
            self._index += 1
            if char == "}":
                return result
            if char != ",":
                self.error("Expecting ',' delimiter")

    def _parse_array(self):
        result = []
        self._index += 1  # consume '['
        self._skip_whitespace()
        if self._index < self._length and self._text[self._index] == "]":
            self._index += 1
            return result
        while True:
            self._skip_whitespace()
            result.append(self._parse_value())
            self._skip_whitespace()
            if self._index >= self._length:
                self.error("Expecting ',' delimiter")
            char = self._text[self._index]
            self._index += 1
            if char == "]":
                return result
            if char != ",":
                self.error("Expecting ',' delimiter")

    def _parse_string(self):
        text = self._text
        index = self._index + 1  # skip the opening quote
        length = self._length
        chunks = []
        while True:
            if index >= length:
                self._index = index
                self.error("Unterminated string")
            char = text[index]
            if char == '"':
                self._index = index + 1
                return "".join(chunks)
            if char != "\\":
                chunks.append(char)
                index += 1
                continue
            index += 1
            if index >= length:
                self._index = index
                self.error("Unterminated string escape")
            escape = text[index]
            if escape == "u":
                code = self._parse_hex4(index + 1)
                index += 5
                if 0xD800 <= code <= 0xDBFF and text[index:index + 2] == "\\u":
                    low = self._parse_hex4(index + 2)
                    if 0xDC00 <= low <= 0xDFFF:
                        code = 0x10000 + ((code - 0xD800) << 10) + (low - 0xDC00)
                        index += 6
                chunks.append(chr(code))
                continue
            replacement = _JSON_UNESCAPE_MAP.get(escape)
            if replacement is None:
                self._index = index
                self.error("Invalid escape")
            chunks.append(replacement)
            index += 1

    def _parse_hex4(self, start):
        digits = self._text[start:start + 4]
        if len(digits) != 4:
            self._index = start
            self.error("Invalid \\uXXXX escape")
        try:
            return int(digits, 16)
        except ValueError:
            self._index = start
            self.error("Invalid \\uXXXX escape")

    def _parse_number(self):
        text = self._text
        start = self._index
        index = start
        length = self._length
        if index < length and text[index] == "-":
            index += 1
        digits_start = index
        while index < length and "0" <= text[index] <= "9":
            index += 1
        if index == digits_start:
            self._index = start
            self.error("Expecting value")
        is_float = False
        if index < length and text[index] == ".":
            is_float = True
            index += 1
            fraction_start = index
            while index < length and "0" <= text[index] <= "9":
                index += 1
            if index == fraction_start:
                self._index = start
                self.error("Expecting value")
        if index < length and text[index] in "eE":
            is_float = True
            index += 1
            if index < length and text[index] in "+-":
                index += 1
            exponent_start = index
            while index < length and "0" <= text[index] <= "9":
                index += 1
            if index == exponent_start:
                self._index = start
                self.error("Expecting value")
        raw = text[start:index]
        self._index = index
        if is_float:
            return float(raw)
        return int(raw)


def _json_loads(text):
    """Parse a JSON document and return the resulting value.

    Mirrors ``json.loads`` but without importing the standard library.
    """
    return _JsonParser(text).parse()


# =============================================================================
# FILESYSTEM HELPERS
#
# `os` and `pathlib` are not available inside FL Studio's stripped
# interpreter, so paths are handled with plain string operations and the
# builtin `open()`.
# =============================================================================

# Name of this script inside FL Studio's Hardware folder.
SCRIPT_FILENAME = "device_FLStudioMCP.py"

# Folder name the MCP controller is installed into (Hardware\<folder>).
HARDWARE_FOLDER = "FLStudioMCP"

# Manual override for the folder that holds the command/response files.
# Leave empty to auto-detect.  Set it to an absolute path when FL Studio's
# user data folder was relocated (for example to a cloud drive) and the
# MCP server cannot find it.
COMMAND_DIR_OVERRIDE = ""


def _path_separator():
    """Return the platform's path separator."""
    return "\\" if sys.platform == "win32" else "/"


def _join_path(directory, name):
    """Join a directory and a file name using the platform separator."""
    if not directory:
        return name
    if directory[-1] in ("/", "\\"):
        return directory + name
    return directory + _path_separator() + name


def _path_name(path):
    """Return the final component of *path* (without any directory part)."""
    trimmed = path
    while trimmed and trimmed[-1] in ("/", "\\"):
        trimmed = trimmed[:-1]
    for index in range(len(trimmed) - 1, -1, -1):
        if trimmed[index] in ("/", "\\"):
            return trimmed[index + 1:]
    return trimmed


def _file_exists(path):
    """Return True when *path* can be opened for reading."""
    try:
        handle = open(path, "rb")
    except Exception:
        return False
    try:
        handle.close()
    except Exception:
        pass
    return True


def _read_text(path):
    """Read *path* and decode it as UTF-8."""
    with open(path, "rb") as handle:
        return handle.read().decode("utf-8", "replace")


def _write_text(path, text):
    """Write *text* to *path* encoded as UTF-8."""
    with open(path, "wb") as handle:
        handle.write(text.encode("utf-8", "replace"))


def _discover_script_dir():
    """Find the folder this script lives in.

    FL Studio adds the controller folder to ``sys.path`` (which is why
    sibling modules can be imported from a MIDI script), and it is the only
    reliable way to locate the hardware folder without ``os``.  The search
    therefore looks for a ``sys.path`` entry that either contains this
    script or is named ``FLStudioMCP``.
    """
    entries = []
    for entry in sys.path:
        if entry and entry not in entries:
            entries.append(entry)

    # Strongest signal: the entry actually contains this script.
    for entry in entries:
        if _file_exists(_join_path(entry, SCRIPT_FILENAME)):
            return entry

    # Next best: the entry is the hardware folder we install into.
    for entry in entries:
        if _path_name(entry).lower() == HARDWARE_FOLDER.lower():
            return entry

    return ""


def _resolve_script_dir():
    """Resolve the folder used for the command/response files."""
    if COMMAND_DIR_OVERRIDE:
        return COMMAND_DIR_OVERRIDE
    return _discover_script_dir()


# Folder used to exchange commands and responses with the MCP server.
SCRIPT_DIR = _resolve_script_dir()
COMMAND_FILE = _join_path(SCRIPT_DIR, "mcp_command.json")
RESPONSE_FILE = _join_path(SCRIPT_DIR, "mcp_response.json")

# MIDI trigger note
TRIGGER_NOTE = 127

_HOT_RELOAD_CHECKED_AT = 0.0
_HOT_RELOAD_VERSION = MCP_VERSION


def _now():
    """Return the current time in seconds (0.0 when `time` is missing)."""
    if _time is None:
        return 0.0
    return _time.time()


def _check_hot_reload():
    """Self-reload the script file if it changed on disk (auto refresh)."""
    global _HOT_RELOAD_CHECKED_AT, _HOT_RELOAD_VERSION
    if _time is None:
        return
    now = _now()
    if now - _HOT_RELOAD_CHECKED_AT < 1.0:
        return
    _HOT_RELOAD_CHECKED_AT = now
    try:
        script_file = _join_path(SCRIPT_DIR, SCRIPT_FILENAME)
        if not _file_exists(script_file):
            return
        text = _read_text(script_file)
        match = None
        for line in text.splitlines():
            if line.startswith("MCP_VERSION"):
                try:
                    match = int(line.split("=")[1].strip())
                except Exception:
                    pass
                break
        if match is None:
            return
        if match != _HOT_RELOAD_VERSION:
            compiled = compile(text, script_file, "exec")
            exec(compiled, globals())
            _HOT_RELOAD_VERSION = match
            print(f"[MCP] hot-reloaded to version {match}")
    except Exception as e:
        print(f"[MCP] hot-reload failed: {e}")


def OnInit():
    print("FL Studio MCP Controller initialized")
    print(f"MCP_VERSION: {MCP_VERSION}")
    print(f"Command file: {COMMAND_FILE}")
    print(f"Response file: {RESPONSE_FILE}")
    if not SCRIPT_DIR:
        print(
            "[MCP] WARNING: could not locate the controller folder. "
            "Set COMMAND_DIR_OVERRIDE at the top of the script to the "
            "folder that holds mcp_command.json / mcp_response.json."
        )


def OnDeInit():
    print("FL Studio MCP Controller deinitialized")



def OnMidiMsg(event):
    _check_hot_reload()
    if event.midiId == 0x90 and event.data1 == TRIGGER_NOTE and event.data2 > 0:
        execute_pending_command()
        event.handled = True


def OnIdle():
    _check_hot_reload()


def execute_pending_command():
    """Read command from JSON file, execute it, and write response."""
    response = {"success": False, "error": None}

    try:
        # Read command file
        if not _file_exists(COMMAND_FILE):
            response["error"] = "No command file found"
            write_response(response)
            return

        command_text = _read_text(COMMAND_FILE)
        command = _json_loads(command_text)

        action = command.get("action", "")
        params = command.get("params", {})

        # Execute command and get result
        result = dispatch_command(action, params)
        response = {"success": True, **result}

    except _JsonError as e:
        response["error"] = f"Invalid JSON in command file: {e}"
    except Exception as e:
        response["error"] = f"Error executing command: {e}"

    write_response(response)


def write_response(response: dict):
    """Write response to JSON file."""
    try:
        _write_text(RESPONSE_FILE, _json_dumps(response, indent=2))
    except Exception as e:
        print(f"Error writing response: {e}")


def dispatch_command(action: str, params: dict) -> dict:
    """Route command to appropriate handler and return result."""

    # Transport commands
    if action == "transport.start":
        return handle_transport_start()
    elif action == "transport.stop":
        return handle_transport_stop()
    elif action == "transport.record":
        return handle_transport_record()
    elif action == "transport.getStatus":
        return handle_transport_get_status()
    elif action == "transport.setPosition":
        return handle_transport_set_position(params)
    elif action == "transport.getLength":
        return handle_transport_get_length()
    elif action == "transport.setLoopMode":
        return handle_transport_set_loop_mode(params)
    elif action == "transport.setPlaybackSpeed":
        return handle_transport_set_playback_speed(params)
    elif action == "transport.getTempo":
        return handle_transport_get_tempo()
    elif action == "transport.setTempo":
        return handle_transport_set_tempo(params)
    elif action == "transport.getShuffle":
        return handle_transport_get_shuffle()

    # Pattern commands
    elif action == "patterns.count":
        return handle_patterns_count()
    elif action == "patterns.list":
        return handle_patterns_list()
    elif action == "patterns.get":
        return handle_patterns_get(params)
    elif action == "patterns.create":
        return handle_patterns_create(params)
    elif action == "patterns.select":
        return handle_patterns_select(params)
    elif action == "patterns.rename":
        return handle_patterns_rename(params)
    elif action == "patterns.clone":
        return handle_patterns_clone(params)
    elif action == "patterns.duplicate":
        return handle_patterns_duplicate(params)
    elif action == "patterns.clear":
        return handle_patterns_clear(params)
    elif action == "patterns.setLength":
        return handle_patterns_set_length(params)
    elif action == "patterns.move":
        return handle_patterns_move(params)

    # Mixer commands
    elif action == "mixer.getTrackCount":
        return handle_mixer_get_track_count()
    elif action == "mixer.getTrackInfo":
        return handle_mixer_get_track_info(params)
    elif action == "mixer.getAllTracks":
        return handle_mixer_get_all_tracks(params)
    elif action == "mixer.setTrackVolume":
        return handle_mixer_set_track_volume(params)
    elif action == "mixer.setTrackPan":
        return handle_mixer_set_track_pan(params)
    elif action == "mixer.muteTrack":
        return handle_mixer_mute_track(params)
    elif action == "mixer.soloTrack":
        return handle_mixer_solo_track(params)
    elif action == "mixer.armTrack":
        return handle_mixer_arm_track(params)
    elif action == "mixer.setTrackName":
        return handle_mixer_set_track_name(params)
    elif action == "mixer.setTrackColor":
        return handle_mixer_set_track_color(params)
    elif action == "mixer.setStereoSep":
        return handle_mixer_set_stereo_sep(params)

    # Channel commands
    elif action == "channels.getCount":
        return handle_channels_get_count(params)
    elif action == "channels.getInfo":
        return handle_channels_get_info(params)
    elif action == "channels.getAll":
        return handle_channels_get_all()
    elif action == "channels.getSelected":
        return handle_channels_get_selected()
    elif action == "channels.select":
        return handle_channels_select(params)
    elif action == "channels.selectOne":
        return handle_channels_select_one(params)
    elif action == "channels.triggerNote":
        return handle_channels_trigger_note(params)
    elif action == "channels.setVolume":
        return handle_channels_set_volume(params)
    elif action == "channels.setPan":
        return handle_channels_set_pan(params)
    elif action == "channels.mute":
        return handle_channels_mute(params)
    elif action == "channels.solo":
        return handle_channels_solo(params)
    elif action == "channels.setName":
        return handle_channels_set_name(params)
    elif action == "channels.setColor":
        return handle_channels_set_color(params)
    elif action == "channels.routeToMixer":
        return handle_channels_route_to_mixer(params)
    elif action == "channels.getType":
        return handle_channels_get_type(params)
    elif action == "channels.setPitch":
        return handle_channels_set_pitch(params)
    elif action == "channels.getSteps":
        return handle_channels_get_steps(params)
    elif action == "channels.setSteps":
        return handle_channels_set_steps(params)
    elif action == "channels.clearSteps":
        return handle_channels_clear_steps(params)

    # Step sequencer commands
    elif action == "channels.getGridBit":
        return handle_channels_get_grid_bit(params)
    elif action == "channels.setGridBit":
        return handle_channels_set_grid_bit(params)
    elif action == "channels.getStepSequence":
        return handle_channels_get_step_sequence(params)
    elif action == "channels.setStepSequence":
        return handle_channels_set_step_sequence(params)

    # Plugin commands
    elif action == "plugins.isValid":
        return handle_plugins_is_valid(params)
    elif action == "plugins.getName":
        return handle_plugins_get_name(params)
    elif action == "plugins.getParamCount":
        return handle_plugins_get_param_count(params)
    elif action == "plugins.getParams":
        return handle_plugins_get_params(params)
    elif action == "plugins.getParamValue":
        return handle_plugins_get_param_value(params)
    elif action == "plugins.setParamValue":
        return handle_plugins_set_param_value(params)
    elif action == "plugins.getPresetCount":
        return handle_plugins_get_preset_count(params)
    elif action == "plugins.nextPreset":
        return handle_plugins_next_preset(params)
    elif action == "plugins.prevPreset":
        return handle_plugins_prev_preset(params)
    elif action == "plugins.getColor":
        return handle_plugins_get_color(params)

    # ===== V4: Full control =====
    # Raw passthrough
    elif action == "raw.call":
        return handle_raw_call(params)
    elif action == "raw.list":
        return handle_raw_list(params)
    elif action == "raw.consts":
        return handle_raw_consts(params)
    elif action == "system.modules":
        return handle_system_modules(params)
    elif action == "system.surface":
        return handle_system_surface(params)
    elif action == "system.diagnostics":
        return handle_system_diagnostics(params)

    # Undo / project / general
    elif action == "general.saveUndo":
        return handle_general_save_undo(params)
    elif action == "general.undo":
        return handle_general_undo()
    elif action == "general.undoUpDown":
        return handle_general_undo_up_down(params)
    elif action == "project.snapshot":
        return handle_project_snapshot(params)
    elif action == "general.info":
        return handle_general_info()
    elif action == "general.safeToEdit":
        return handle_general_safe_to_edit()
    elif action == "general.automateValue":
        return handle_general_automate_value(params)

    # Project metadata / global transport
    elif action == "project.info":
        return handle_project_info()
    elif action == "project.setTimeSig":
        return handle_project_set_time_sig(params)
    elif action == "project.setPPQ":
        return handle_project_set_ppq(params)
    elif action == "transport.action":
        return handle_transport_action(params)

    # Tempo (FL25 API)
    elif action == "tempo.get":
        return handle_tempo_get()
    elif action == "tempo.set":
        return handle_tempo_set(params)

    # Mixer routing / sends / EQ / peaks / fx chain
    elif action == "mixer.route":
        return handle_mixer_route(params)
    elif action == "mixer.routeLevel":
        return handle_mixer_route_level(params)
    elif action == "mixer.routeSendActive":
        return handle_mixer_route_send_active(params)
    elif action == "mixer.equalizer":
        return handle_mixer_equalizer(params)
    elif action == "mixer.peaks":
        return handle_mixer_peaks(params)
    elif action == "mixer.fxInfo":
        return handle_mixer_fx_info(params)
    elif action == "mixer.fxMixLevel":
        return handle_mixer_fx_mix_level(params)
    elif action == "mixer.linkChannel":
        return handle_mixer_link_channel(params)
    elif action == "mixer.automate":
        return handle_mixer_automate(params)

    # Channel events / shuffle / loop points
    elif action == "channels.event":
        return handle_channels_event(params)
    elif action == "channels.shuffle":
        return handle_channels_shuffle(params)
    elif action == "channels.loop":
        return handle_channels_loop(params)
    elif action == "channels.stepParam":
        return handle_channels_step_param(params)

    # Playlist
    elif action == "playlist.info":
        return handle_playlist_info(params)
    elif action == "playlist.setTrackName":
        return handle_playlist_set_track_name(params)
    elif action == "playlist.setTrackColor":
        return handle_playlist_set_track_color(params)
    elif action == "playlist.mute":
        return handle_playlist_mute(params)
    elif action == "playlist.solo":
        return handle_playlist_solo(params)
    elif action == "playlist.select":
        return handle_playlist_select(params)

    # UI feedback
    elif action == "piano.dumpScoreLog":
        return handle_piano_dump_score_log(params)
    elif action == "transport.position":
        return handle_transport_position()
    elif action == "arrangement.info":
        return handle_arrangement_info()
    elif action == "ui.hint":
        return handle_ui_hint(params)

    # ============================================================
    # GENERIC LAYER: full-surface coverage via declarative table
    # ============================================================
    else:
        generic = handle_generic_command(action, params)
        if generic is not None:
            return generic
        return {"error": f"Unknown action: {action}"}


# =============================================================================
# Transport Handlers
# =============================================================================


def handle_transport_start() -> dict:
    """Toggle play/pause."""
    transport.start()
    return {"is_playing": transport.isPlaying() == 1}


def handle_transport_stop() -> dict:
    """Stop playback."""
    transport.stop()
    return {"stopped": True}


def handle_transport_record() -> dict:
    """Toggle recording."""
    transport.record()
    return {"is_recording": transport.isRecording() == 1}


def handle_transport_get_status() -> dict:
    """Get transport status."""
    loop_mode = transport.getLoopMode()
    return {
        "is_playing": transport.isPlaying() == 1,
        "is_recording": transport.isRecording() == 1,
        "position": transport.getSongPosHint(),
        "loop_mode": "song" if loop_mode == 1 else "pattern",
    }


def handle_transport_set_position(params: dict) -> dict:
    """Set playback position."""
    position = params.get("position", 0)
    mode = params.get("mode", 2)  # Default: seconds
    transport.setSongPos(position, mode)
    return {"position": transport.getSongPosHint()}


def handle_transport_get_length() -> dict:
    """Get song length."""
    return {
        "ticks": transport.getSongLength(3),
        "seconds": transport.getSongLength(2),
        "milliseconds": transport.getSongLength(1),
    }


def handle_transport_set_loop_mode(params: dict) -> dict:
    """Set loop mode."""
    mode = params.get("mode", "pattern")
    current_mode = transport.getLoopMode()
    target_mode = 1 if mode.lower() == "song" else 0

    if current_mode != target_mode:
        transport.setLoopMode()

    return {"mode": mode}


def handle_transport_set_playback_speed(params: dict) -> dict:
    """Set playback speed."""
    speed = params.get("speed", 1.0)
    transport.setPlaybackSpeed(speed)
    return {"speed": speed}


def handle_transport_get_tempo() -> dict:
    """Get current tempo in BPM (this build returns raw EPB = BPM * 1000)."""
    try:
        tempo = mixer.getCurrentTempo()
        val = float(tempo)
        if val > 1000.0:
            val = val / 1000.0
        return {"tempo": val}
    except Exception as e:
        return {"error": f"Failed to get tempo: {e}"}


def handle_transport_set_tempo(params: dict) -> dict:
    """Set tempo in BPM (raw EPB = BPM * 1000)."""
    tempo = params.get("tempo", params.get("bpm", 120.0))
    try:
        mixer.setCurrentTempo(int(float(tempo) * 1000))
        back = mixer.getCurrentTempo()
        val = float(back)
        if val > 1000.0:
            val = val / 1000.0
        return {"tempo": val}
    except Exception as e:
        return {"error": f"Failed to set tempo: {e}"}


def handle_transport_get_shuffle() -> dict:
    """Get current shuffle amount."""
    try:
        shuffle = mixer.getShuffle()
        return {"shuffle": shuffle}
    except Exception:
        return {"shuffle": None, "error": "Shuffle not available in this FL Studio version"}


# =============================================================================
# Mixer Handlers
# =============================================================================


def handle_mixer_get_track_count() -> dict:
    """Get number of mixer tracks."""
    return {"count": mixer.trackCount()}


def handle_mixer_get_track_info(params: dict) -> dict:
    """Get info about a mixer track."""
    track = params.get("track", 0)
    return {
        "index": track,
        "name": mixer.getTrackName(track),
        "volume": mixer.getTrackVolume(track),
        "volume_db": mixer.getTrackVolume(track, 1),
        "pan": mixer.getTrackPan(track),
        "stereo_separation": mixer.getTrackStereoSep(track),
        "is_muted": mixer.isTrackMuted(track) == 1,
        "is_solo": mixer.isTrackSolo(track) == 1,
        "is_armed": mixer.isTrackArmed(track) == 1,
        "color": hex(mixer.getTrackColor(track)),
    }


def handle_mixer_get_all_tracks(params: dict) -> dict:
    """Get info about all mixer tracks."""
    include_empty = params.get("include_empty", False)
    tracks = []
    track_count = mixer.trackCount()

    for i in range(track_count):
        name = mixer.getTrackName(i)

        # Skip empty tracks if requested
        if not include_empty and (not name or name.startswith("Insert ")):
            if i != 0:  # Always include master
                continue

        tracks.append({
            "index": i,
            "name": name if name else ("Master" if i == 0 else f"Insert {i}"),
            "volume": mixer.getTrackVolume(i),
            "pan": mixer.getTrackPan(i),
            "is_muted": mixer.isTrackMuted(i) == 1,
            "is_solo": mixer.isTrackSolo(i) == 1,
        })

    return {"tracks": tracks}


def handle_mixer_set_track_volume(params: dict) -> dict:
    """Set mixer track volume."""
    track = params.get("track", 0)
    volume = params.get("volume", 0.8)
    mixer.setTrackVolume(track, volume)
    return {
        "volume": mixer.getTrackVolume(track),
        "volume_db": mixer.getTrackVolume(track, 1),
    }


def handle_mixer_set_track_pan(params: dict) -> dict:
    """Set mixer track pan."""
    track = params.get("track", 0)
    pan = params.get("pan", 0.0)
    mixer.setTrackPan(track, pan)
    return {"pan": mixer.getTrackPan(track)}


def handle_mixer_mute_track(params: dict) -> dict:
    """Mute/unmute mixer track."""
    track = params.get("track", 0)
    muted = params.get("muted")  # None = toggle

    if muted is None:
        mixer.muteTrack(track, -1)
    else:
        mixer.muteTrack(track, 1 if muted else 0)

    return {
        "is_muted": mixer.isTrackMuted(track) == 1,
        "track_name": mixer.getTrackName(track),
    }


def handle_mixer_solo_track(params: dict) -> dict:
    """Solo/unsolo mixer track."""
    track = params.get("track", 0)
    solo = params.get("solo")  # None = toggle
    mode = params.get("mode", 3)

    if solo is None:
        mixer.soloTrack(track, -1, mode)
    else:
        mixer.soloTrack(track, 1 if solo else 0, mode)

    return {
        "is_solo": mixer.isTrackSolo(track) == 1,
        "track_name": mixer.getTrackName(track),
    }


def handle_mixer_arm_track(params: dict) -> dict:
    """Toggle arm state of mixer track."""
    track = params.get("track", 0)
    mixer.armTrack(track)
    return {
        "is_armed": mixer.isTrackArmed(track) == 1,
        "track_name": mixer.getTrackName(track),
    }


def handle_mixer_set_track_name(params: dict) -> dict:
    """Set mixer track name."""
    track = params.get("track", 0)
    name = params.get("name", "")
    mixer.setTrackName(track, name)
    return {"name": name}


def handle_mixer_set_track_color(params: dict) -> dict:
    """Set mixer track color."""
    track = params.get("track", 0)
    r = params.get("r", 0)
    g = params.get("g", 0)
    b = params.get("b", 0)
    # FL Studio uses BGR format
    color = (b << 16) | (g << 8) | r
    mixer.setTrackColor(track, color)
    return {"color": f"RGB({r}, {g}, {b})"}


def handle_mixer_set_stereo_sep(params: dict) -> dict:
    """Set mixer track stereo separation."""
    track = params.get("track", 0)
    separation = params.get("separation", 0.0)
    mixer.setTrackStereoSep(track, separation)
    return {"separation": separation}


# =============================================================================
# Channel Handlers
# =============================================================================


def handle_channels_get_count(params: dict) -> dict:
    """Get number of channels."""
    global_count = params.get("global_count", True)
    return {"count": channels.channelCount(global_count)}


def handle_channels_get_info(params: dict) -> dict:
    """Get info about a channel."""
    index = params.get("index", 0)
    use_global = params.get("use_global", True)

    return {
        "index": index,
        "name": channels.getChannelName(index, use_global),
        "color": hex(channels.getChannelColor(index, use_global)),
        "volume": channels.getChannelVolume(index, use_global),
        "pan": channels.getChannelPan(index, use_global),
        "pitch": channels.getChannelPitch(index, useGlobalIndex=use_global),
        "is_muted": channels.isChannelMuted(index, use_global) == 1,
        "is_solo": channels.isChannelSolo(index, use_global) == 1,
        "is_selected": channels.isChannelSelected(index, use_global) == 1,
        "target_fx_track": channels.getTargetFxTrack(index, use_global),
    }


def handle_channels_get_all() -> dict:
    """Get info about all channels."""
    channels_list = []
    count = channels.channelCount(True)

    for i in range(count):
        channels_list.append({
            "index": i,
            "name": channels.getChannelName(i, True),
            "is_muted": channels.isChannelMuted(i, True) == 1,
            "is_selected": channels.isChannelSelected(i, True) == 1,
            "target_fx_track": channels.getTargetFxTrack(i, True),
        })

    return {"channels": channels_list}


def handle_channels_get_selected() -> dict:
    """Get currently selected channel."""
    index = channels.selectedChannel(canBeNone=True, indexGlobal=True)

    if index is None or index < 0:
        return {"channel": None}

    return {
        "channel": {
            "index": index,
            "name": channels.getChannelName(index, True),
            "volume": channels.getChannelVolume(index, True),
            "pan": channels.getChannelPan(index, True),
            "is_muted": channels.isChannelMuted(index, True) == 1,
            "is_solo": channels.isChannelSolo(index, True) == 1,
        }
    }


def handle_channels_select(params: dict) -> dict:
    """Select/deselect a channel."""
    index = params.get("index", 0)
    select = params.get("select", True)
    channels.selectChannel(index, 1 if select else 0, True)
    return {
        "selected": select,
        "channel_name": channels.getChannelName(index, True),
    }


def handle_channels_select_one(params: dict) -> dict:
    """Select only one channel, deselecting others."""
    index = params.get("index", 0)
    channels.selectOneChannel(index, True)
    return {"channel_name": channels.getChannelName(index, True)}


def handle_channels_trigger_note(params: dict) -> dict:
    """Trigger a MIDI note on a channel."""
    channel = params.get("channel", 0)
    note = params.get("note", 60)
    velocity = params.get("velocity", 100)
    midi_channel = params.get("midi_channel", -1)
    channels.midiNoteOn(channel, note, velocity, midi_channel)
    return {"triggered": True, "note": note, "velocity": velocity}


def handle_channels_set_volume(params: dict) -> dict:
    """Set channel volume."""
    index = params.get("index", 0)
    volume = params.get("volume", 0.8)
    channels.setChannelVolume(index, volume, True)
    return {
        "volume": channels.getChannelVolume(index, True),
        "channel_name": channels.getChannelName(index, True),
    }


def handle_channels_set_pan(params: dict) -> dict:
    """Set channel pan."""
    index = params.get("index", 0)
    pan = params.get("pan", 0.0)
    channels.setChannelPan(index, pan, True)
    return {
        "pan": channels.getChannelPan(index, True),
        "channel_name": channels.getChannelName(index, True),
    }


def handle_channels_mute(params: dict) -> dict:
    """Mute/unmute channel."""
    index = params.get("index", 0)
    muted = params.get("muted")  # None = toggle

    if muted is None:
        channels.muteChannel(index, -1, True)
    else:
        channels.muteChannel(index, 1 if muted else 0, True)

    return {
        "is_muted": channels.isChannelMuted(index, True) == 1,
        "channel_name": channels.getChannelName(index, True),
    }


def handle_channels_solo(params: dict) -> dict:
    """Solo/unsolo channel."""
    index = params.get("index", 0)
    solo = params.get("solo")  # None = toggle

    if solo is None:
        channels.soloChannel(index, -1, True)
    else:
        channels.soloChannel(index, 1 if solo else 0, True)

    return {
        "is_solo": channels.isChannelSolo(index, True) == 1,
        "channel_name": channels.getChannelName(index, True),
    }


def handle_channels_set_name(params: dict) -> dict:
    """Set channel name."""
    index = params.get("index", 0)
    name = params.get("name", "")
    channels.setChannelName(index, name, True)
    return {"name": name}


def handle_channels_set_color(params: dict) -> dict:
    """Set channel color."""
    index = params.get("index", 0)
    r = params.get("r", 0)
    g = params.get("g", 0)
    b = params.get("b", 0)
    # FL Studio uses BGR format
    color = (b << 16) | (g << 8) | r
    channels.setChannelColor(index, color, True)
    return {"color": f"RGB({r}, {g}, {b})"}


def handle_channels_route_to_mixer(params: dict) -> dict:
    """Route channel to mixer track."""
    channel_index = params.get("channel_index", 0)
    mixer_track = params.get("mixer_track", 0)
    channels.setTargetFxTrack(channel_index, mixer_track, True)
    return {
        "channel_name": channels.getChannelName(channel_index, True),
        "mixer_track": mixer_track,
    }


# =============================================================================
# Step Sequencer Handlers
# =============================================================================


def handle_channels_get_grid_bit(params: dict) -> dict:
    """Get whether a step is active."""
    channel = params.get("channel", 0)
    position = params.get("position", 0)
    return {"value": channels.getGridBit(channel, position, True) == 1}


def handle_channels_set_grid_bit(params: dict) -> dict:
    """Set a step on or off."""
    channel = params.get("channel", 0)
    position = params.get("position", 0)
    value = params.get("value", False)
    channels.setGridBit(channel, position, 1 if value else 0, True)
    return {
        "value": value,
        "channel_name": channels.getChannelName(channel, True),
    }


def handle_channels_get_step_sequence(params: dict) -> dict:
    """Get step sequence for a channel."""
    channel = params.get("channel", 0)
    steps = params.get("steps", 16)
    sequence = []

    for i in range(steps):
        sequence.append(channels.getGridBit(channel, i, True) == 1)

    return {"sequence": sequence}


def handle_channels_set_step_sequence(params: dict) -> dict:
    """Set complete step sequence for a channel."""
    channel = params.get("channel", 0)
    pattern = params.get("pattern", [])

    for i, value in enumerate(pattern):
        channels.setGridBit(channel, i, 1 if value else 0, True)

    active_steps = sum(pattern)
    return {
        "active_steps": active_steps,
        "total_steps": len(pattern),
        "channel_name": channels.getChannelName(channel, True),
    }


# =============================================================================
# Plugin Handlers
# =============================================================================


def handle_plugins_is_valid(params: dict) -> dict:
    """Check if plugin exists at location."""
    index = params.get("index", 0)
    slot_index = params.get("slot_index", -1)
    use_global = params.get("use_global", True)

    if slot_index >= 0:
        valid = plugins.isValid(index, slot_index, True)
    else:
        valid = plugins.isValid(index, -1, use_global)

    return {"valid": valid == 1}


def handle_plugins_get_name(params: dict) -> dict:
    """Get plugin name."""
    index = params.get("index", 0)
    slot_index = params.get("slot_index", -1)
    use_global = params.get("use_global", True)

    if slot_index >= 0:
        name = plugins.getPluginName(index, slot_index, True)
    else:
        name = plugins.getPluginName(index, -1, use_global)

    return {"name": name}


def handle_plugins_get_param_count(params: dict) -> dict:
    """Get number of plugin parameters."""
    index = params.get("index", 0)
    slot_index = params.get("slot_index", -1)
    use_global = params.get("use_global", True)

    if slot_index >= 0:
        count = plugins.getParamCount(index, slot_index, True)
    else:
        count = plugins.getParamCount(index, -1, use_global)

    return {"count": count}


def handle_plugins_get_params(params: dict) -> dict:
    """Get all plugin parameters."""
    index = params.get("index", 0)
    slot_index = params.get("slot_index", -1)
    use_global = params.get("use_global", True)
    max_params = params.get("max_params", 50)

    if slot_index >= 0:
        param_count = plugins.getParamCount(index, slot_index, True)
    else:
        param_count = plugins.getParamCount(index, -1, use_global)

    param_list = []
    for i in range(min(param_count, max_params)):
        try:
            if slot_index >= 0:
                name = plugins.getParamName(i, index, slot_index, True)
                value = plugins.getParamValue(i, index, slot_index, True)
                value_str = plugins.getParamValueString(i, index, slot_index, True)
            else:
                name = plugins.getParamName(i, index, -1, use_global)
                value = plugins.getParamValue(i, index, -1, use_global)
                value_str = plugins.getParamValueString(i, index, -1, use_global)

            param_list.append({
                "index": i,
                "name": name,
                "value": value,
                "value_string": value_str,
            })
        except Exception as e:
            print(f"Warning: could not read param {i}: {e}")
            continue

    return {"params": param_list}


def handle_plugins_get_param_value(params: dict) -> dict:
    """Get specific parameter value."""
    param_index = params.get("param_index", 0)
    plugin_index = params.get("plugin_index", 0)
    slot_index = params.get("slot_index", -1)
    use_global = params.get("use_global", True)

    if slot_index >= 0:
        name = plugins.getParamName(param_index, plugin_index, slot_index, True)
        value = plugins.getParamValue(param_index, plugin_index, slot_index, True)
        value_str = plugins.getParamValueString(param_index, plugin_index, slot_index, True)
    else:
        name = plugins.getParamName(param_index, plugin_index, -1, use_global)
        value = plugins.getParamValue(param_index, plugin_index, -1, use_global)
        value_str = plugins.getParamValueString(param_index, plugin_index, -1, use_global)

    return {
        "index": param_index,
        "name": name,
        "value": value,
        "value_string": value_str,
    }


def handle_plugins_set_param_value(params: dict) -> dict:
    """Set plugin parameter value."""
    param_index = params.get("param_index", 0)
    value = params.get("value", 0.0)
    plugin_index = params.get("plugin_index", 0)
    slot_index = params.get("slot_index", -1)
    use_global = params.get("use_global", True)

    if slot_index >= 0:
        name = plugins.getParamName(param_index, plugin_index, slot_index, True)
        plugins.setParamValue(value, param_index, plugin_index, slot_index, True)
        new_value = plugins.getParamValue(param_index, plugin_index, slot_index, True)
        value_str = plugins.getParamValueString(param_index, plugin_index, slot_index, True)
    else:
        name = plugins.getParamName(param_index, plugin_index, -1, use_global)
        plugins.setParamValue(value, param_index, plugin_index, -1, use_global)
        new_value = plugins.getParamValue(param_index, plugin_index, -1, use_global)
        value_str = plugins.getParamValueString(param_index, plugin_index, -1, use_global)

    return {
        "name": name,
        "value": new_value,
        "value_string": value_str,
    }


def handle_plugins_get_preset_count(params: dict) -> dict:
    """Get number of plugin presets."""
    index = params.get("index", 0)
    slot_index = params.get("slot_index", -1)
    use_global = params.get("use_global", True)

    if slot_index >= 0:
        count = plugins.getPresetCount(index, slot_index, True)
    else:
        count = plugins.getPresetCount(index, -1, use_global)

    return {"count": count}


def handle_plugins_next_preset(params: dict) -> dict:
    """Switch to next preset."""
    index = params.get("index", 0)
    slot_index = params.get("slot_index", -1)
    use_global = params.get("use_global", True)

    if slot_index >= 0:
        plugin_name = plugins.getPluginName(index, slot_index, True)
        plugins.nextPreset(index, slot_index, True)
    else:
        plugin_name = plugins.getPluginName(index, -1, use_global)
        plugins.nextPreset(index, -1, use_global)

    return {"plugin_name": plugin_name}


def handle_plugins_prev_preset(params: dict) -> dict:
    """Switch to previous preset."""
    index = params.get("index", 0)
    slot_index = params.get("slot_index", -1)
    use_global = params.get("use_global", True)

    if slot_index >= 0:
        plugin_name = plugins.getPluginName(index, slot_index, True)
        plugins.prevPreset(index, slot_index, True)
    else:
        plugin_name = plugins.getPluginName(index, -1, use_global)
        plugins.prevPreset(index, -1, use_global)

    return {"plugin_name": plugin_name}


def handle_plugins_get_color(params: dict) -> dict:
    """Get plugin color."""
    index = params.get("index", 0)
    slot_index = params.get("slot_index", -1)
    use_global = params.get("use_global", True)

    if slot_index >= 0:
        color = plugins.getColor(index, slot_index, True)
    else:
        color = plugins.getColor(index, -1, use_global)

    return {"color": hex(color)}


# =============================================================================
# Pattern Handlers
# =============================================================================


def _patterns_supported() -> bool:
    return patterns is not None


def handle_patterns_count() -> dict:
    """Get number of patterns."""
    if not _patterns_supported():
        return {"error": "patterns module not available in this FL Studio version"}
    return {
        "count": patterns.patternCount(),
        "max": patterns.patternMax(),
        "active": patterns.patternNumber(),
    }


def handle_patterns_list() -> dict:
    """List all patterns with their properties."""
    if not _patterns_supported():
        return {"error": "patterns module not available in this FL Studio version"}

    result = []
    count = patterns.patternCount()
    active = patterns.patternNumber()

    for i in range(count):
        entry = {
            "index": i,
            "name": patterns.getPatternName(i),
            "is_active": (i == active),
        }
        try:
            entry["length_beats"] = patterns.getPatternLength(i)
        except Exception:
            entry["length_beats"] = None
        try:
            entry["color"] = hex(patterns.getPatternColor(i))
        except Exception:
            entry["color"] = None
        result.append(entry)

    return {"patterns": result, "count": count, "active": active}


def handle_patterns_get(params: dict) -> dict:
    """Get a single pattern's properties."""
    if not _patterns_supported():
        return {"error": "patterns module not available in this FL Studio version"}

    index = params.get("index", -1)
    if index < 0:
        index = patterns.patternNumber()

    if index >= patterns.patternCount():
        return {"error": f"Pattern {index} does not exist"}

    entry = {
        "index": index,
        "name": patterns.getPatternName(index),
        "is_active": (index == patterns.patternNumber()),
    }
    try:
        entry["length_beats"] = patterns.getPatternLength(index)
    except Exception:
        entry["length_beats"] = None
    try:
        entry["color"] = hex(patterns.getPatternColor(index))
    except Exception:
        entry["color"] = None
    return entry


def handle_patterns_create(params: dict) -> dict:
    """Create a new pattern (jumps to first empty slot)."""
    if not _patterns_supported():
        return {"error": "patterns module not available in this FL Studio version"}

    try:
        if midi is not None:
            patterns.findFirstNextEmptyPat(
                midi.FFNEP_FindFirst | midi.FFNEP_DontPromptName
            )
        else:
            patterns.jumpToPattern(patterns.patternCount())
    except Exception:
        patterns.jumpToPattern(patterns.patternCount())

    index = patterns.patternNumber()
    name = params.get("name", "")
    if name:
        patterns.setPatternName(index, name)

    return {
        "index": index,
        "name": patterns.getPatternName(index),
        "created": True,
    }


def handle_patterns_select(params: dict) -> dict:
    """Select a pattern as active."""
    if not _patterns_supported():
        return {"error": "patterns module not available in this FL Studio version"}

    index = params.get("index", 0)
    patterns.selectPattern(index, 1)
    patterns.jumpToPattern(index)
    return {
        "index": index,
        "name": patterns.getPatternName(index),
        "active": patterns.patternNumber(),
    }


def handle_patterns_rename(params: dict) -> dict:
    """Rename a pattern."""
    if not _patterns_supported():
        return {"error": "patterns module not available in this FL Studio version"}

    index = params.get("index", -1)
    if index < 0:
        index = patterns.patternNumber()
    name = params.get("name", "")
    patterns.setPatternName(index, name)
    return {"index": index, "name": patterns.getPatternName(index)}


def handle_patterns_clone(params: dict) -> dict:
    """Clone an existing pattern."""
    if not _patterns_supported():
        return {"error": "patterns module not available in this FL Studio version"}

    index = params.get("index", -1)
    if index < 0:
        index = patterns.patternNumber()

    prev_count = patterns.patternCount()
    patterns.clonePattern(index)
    new_index = patterns.patternCount() - 1
    if new_index < prev_count:
        new_index = prev_count

    return {"index": new_index, "name": patterns.getPatternName(new_index)}


def handle_patterns_duplicate(params: dict) -> dict:
    """Duplicate pattern data into a new pattern."""
    if not _patterns_supported():
        return {"error": "patterns module not available in this FL Studio version"}

    index = params.get("index", -1)
    if index < 0:
        index = patterns.patternNumber()

    try:
        new_index = patterns.duplicatePatternData(index)
        return {"index": new_index, "name": patterns.getPatternName(new_index)}
    except Exception as e:
        return {"error": f"duplicatePatternData failed: {e}"}


def handle_patterns_clear(params: dict) -> dict:
    """Clear all data from a pattern."""
    if not _patterns_supported():
        return {"error": "patterns module not available in this FL Studio version"}

    index = params.get("index", -1)
    if index < 0:
        index = patterns.patternNumber()

    patterns.clearPattern(index)
    return {"index": index, "cleared": True}


def handle_patterns_set_length(params: dict) -> dict:
    """Set pattern length in beats."""
    if not _patterns_supported():
        return {"error": "patterns module not available in this FL Studio version"}

    index = params.get("index", -1)
    if index < 0:
        index = patterns.patternNumber()
    length = params.get("length", 4)

    try:
        patterns.setPatternLength(index, length)
        return {"index": index, "length_beats": patterns.getPatternLength(index)}
    except Exception as e:
        return {"error": f"setPatternLength failed: {e}"}


def handle_patterns_move(params: dict) -> dict:
    """Move the active pattern left/right in the pattern list."""
    if not _patterns_supported():
        return {"error": "patterns module not available in this FL Studio version"}

    direction = params.get("direction", 1)
    try:
        patterns.movePattern(direction)
        index = patterns.patternNumber()
        return {"index": index, "name": patterns.getPatternName(index)}
    except Exception as e:
        return {"error": f"movePattern failed: {e}"}


# =============================================================================
# Extra Channel Handlers
# =============================================================================


def handle_channels_get_type(params: dict) -> dict:
    """Get the channel type (sampler, synthesizer, etc)."""
    index = params.get("index", 0)
    use_global = params.get("use_global", True)
    try:
        channel_type = channels.getChannelType(index, use_global)
        type_names = {
            0: "Sampler",
            1: "Audio Clip",
            2: "Automation",
            3: "Synthesizer",
            4: "Layer",
            5: "MIDI Out",
            6: "Removed?",
            7: "Aux?",
            8: "Hybrid (VST?)",
            9: "Patcher?",
            10: "Fruity Slicer?",
        }
        return {
            "channel_type_id": channel_type,
            "channel_type": type_names.get(channel_type, "Unknown"),
            "channel_name": channels.getChannelName(index, use_global),
        }
    except Exception as e:
        return {"error": f"getChannelType failed: {e}"}


def handle_channels_set_pitch(params: dict) -> dict:
    """Set channel pitch (coarse semitones, -120..120)."""
    index = params.get("index", 0)
    pitch = params.get("pitch", 0)
    use_global = params.get("use_global", True)
    try:
        channels.setChannelPitch(index, pitch, use_global)
        return {
            "pitch": channels.getChannelPitch(index, use_global),
            "channel_name": channels.getChannelName(index, use_global),
        }
    except Exception as e:
        return {"error": f"setChannelPitch failed: {e}"}


# =============================================================================
# Step Sequencer (Melody) Handlers
# =============================================================================


def handle_channels_get_steps(params: dict) -> dict:
    """Get per-step properties (pitch, velocity, pan) for a channel."""
    channel = params.get("channel", 0)
    steps = params.get("steps", 16)
    use_global = params.get("use_global", True)

    sequence = []
    for i in range(steps):
        enabled = channels.getGridBit(channel, i, use_global) == 1
        entry = {"step": i, "enabled": enabled}
        if enabled:
            try:
                entry["note"] = channels.getCurrentStepParam(
                    channel, i, 0, use_global
                )
            except Exception:
                entry["note"] = None
            try:
                entry["velocity"] = channels.getCurrentStepParam(
                    channel, i, 1, use_global
                )
            except Exception:
                entry["velocity"] = None
            try:
                entry["pan"] = channels.getCurrentStepParam(
                    channel, i, 4, use_global
                )
            except Exception:
                entry["pan"] = None
        sequence.append(entry)

    return {
        "channel": channel,
        "channel_name": channels.getChannelName(channel, use_global),
        "steps": sequence,
    }


def handle_channels_set_steps(params: dict) -> dict:
    """Set per-step properties (pitch, velocity, pan) for a channel.

    Expected params:
        channel: int - channel index
        steps: list of dicts with:
            - step: int - step index (0-based)
            - enabled: bool (optional) - set step on/off
            - note: int (optional) - MIDI note number for this step
            - velocity: int (optional) - 0-127
            - pan: int (optional) - 0-127, 64 = center
    """
    channel = params.get("channel", 0)
    steps_data = params.get("steps", [])
    use_global = params.get("use_global", True)
    pat_num = params.get("pat_num", -1)
    if pat_num == -1:
        try:
            pat_num = patterns.patternNumber()
        except Exception:
            pat_num = -1

    # Grid bits always target the CURRENT pattern, while
    # setStepParameterByIndex takes an explicit pattern: align both here.
    restore_pat = None
    if pat_num != -1 and _patterns_supported():
        try:
            if patterns.patternNumber() != pat_num:
                restore_pat = patterns.patternNumber()
                patterns.selectPattern(pat_num, 1)
                patterns.jumpToPattern(pat_num)
        except Exception:
            restore_pat = None

    def _restore():
        if restore_pat is not None:
            try:
                patterns.selectPattern(restore_pat, 1)
                patterns.jumpToPattern(restore_pat)
            except Exception:
                pass

    for entry in steps_data:
        step = entry.get("step", 0)

        if "enabled" in entry:
            channels.setGridBit(channel, step, 1 if entry["enabled"] else 0, use_global)

        if entry.get("enabled", True):
            if "note" in entry:
                try:
                    channels.setStepParameterByIndex(
                        channel, pat_num, step, 0, entry["note"], use_global
                    )
                except Exception as e:
                    _restore()
                    return {"error": f"setStepParameterByIndex(note) failed: {e}"}
            if "velocity" in entry:
                try:
                    channels.setStepParameterByIndex(
                        channel, pat_num, step, 1, entry["velocity"], use_global
                    )
                except Exception as e:
                    _restore()
                    return {"error": f"setStepParameterByIndex(velocity) failed: {e}"}
            if "pan" in entry:
                try:
                    channels.setStepParameterByIndex(
                        channel, pat_num, step, 4, entry["pan"], use_global
                    )
                except Exception as e:
                    _restore()
                    return {"error": f"setStepParameterByIndex(pan) failed: {e}"}

    _restore()
    return {
        "channel": channel,
        "channel_name": channels.getChannelName(channel, use_global),
        "steps_updated": len(steps_data),
        "version": 2,
    }


def handle_channels_clear_steps(params: dict) -> dict:
    """Disable all steps for a channel."""
    channel = params.get("channel", 0)
    steps = params.get("steps", 16)
    use_global = params.get("use_global", True)

    for i in range(steps):
        channels.setGridBit(channel, i, 0, use_global)

    return {
        "channel": channel,
        "channel_name": channels.getChannelName(channel, use_global),
        "cleared_steps": steps,
    }

# =============================================================================
# V4: Full Control Handlers
# =============================================================================

# Modules whitelisted for raw passthrough
_RAW_MODULES = {
    "channels": channels,
    "mixer": mixer,
    "transport": transport,
    "plugins": plugins,
    "patterns": patterns,
    "playlist": playlist,
    "general": general,
    "ui": ui,
    "arrangement": arrangement,
}

# Candidate API modules that may exist in newer FL versions; probed at runtime
_CANDIDATE_MODULES = [
    "channels", "mixer", "transport", "patterns", "playlist", "arrangement",
    "general", "ui", "plugins", "midi",
    "device", "device_surfaces", "projects", "content", "resources",
    "integrator", "api", "tools",
]

_VALIDATED_MODULES = {}


def _try_import(name):
    """Import a module by name without relying on `importlib`.

    `importlib` is not part of FL Studio's stripped standard library, but the
    `__import__` builtin is always available.
    """
    try:
        return __import__(name)
    except Exception:
        return None


def _probe_modules():
    """Discover which API modules this FL version actually ships.

    Safe: each candidate is imported in a fresh try/except.
    """
    found = {}
    for name in _CANDIDATE_MODULES:
        mod = _try_import(name)
        if mod is not None:
            found[name] = mod
    return found


def _serialize(value):
    """Convert an API return value into a JSON-safe structure."""
    if value is None or isinstance(value, (int, float, str, bool)):
        return value
    if isinstance(value, (tuple, list)):
        return [_serialize(v) for v in value]
    if isinstance(value, bytes):
        return value.hex()
    return repr(value)


def handle_raw_call(params: dict) -> dict:
    """Universal passthrough - call ANY function in a whitelisted module.

    params: {module: str, function: str, args: list}
"""
    module_name = params.get("module", "")
    function = params.get("function", "")
    args = params.get("args", []) or []

    if module_name not in _RAW_MODULES:
        return {"error": f"Module '{module_name}' not allowed. Allowed: {list(_RAW_MODULES.keys())}"}
    if not isinstance(args, list):
        return {"error": "args must be a list"}

    mod = _RAW_MODULES[module_name]
    if mod is None:
        return {"error": f"Module '{module_name}' not available in this FL Studio version"}

    try:
        func = getattr(mod, function)
    except AttributeError:
        return {"error": f"Function '{function}' not found in module '{module_name}'"}

    try:
        result = func(*args)
    except Exception as e:
        return {"error": f"{module_name}.{function}({args}) failed: {e}"}

    return {
        "module": module_name,
        "function": function,
        "value": _serialize(result),
    }


def handle_raw_list(params: dict) -> dict:
    """List callable functions in a whitelisted module (API discovery).

    params: {module: str, prefix: str (optional filter), limit: int}
    """
    module_name = params.get("module", "")
    prefix = params.get("prefix", "")
    limit = params.get("limit", 500)
    if module_name not in _RAW_MODULES:
        return {"error": f"Module '{module_name}' not allowed. Allowed: {list(_RAW_MODULES.keys())}"}
    mod = _RAW_MODULES[module_name]
    if mod is None:
        return {"error": f"Module '{module_name}' not available in this FL Studio version"}
    try:
        names = [n for n in dir(mod) if n.startswith(prefix) and not n.startswith("__")]
        names.sort()
        return {"module": module_name, "count": len(names), "functions": names[:limit]}
    except Exception as e:
        return {"error": f"Could not list module: {e}"}


def handle_raw_consts(params: dict) -> dict:
    """List constants in the midi module (e.g. FPT_*, REC_*).

    params: {prefix: str (required, e.g. 'FPT_', 'REC_', 'MaxInt'), limit: int}
    """
    if midi is None:
        return {"error": "midi module not available"}
    prefix = params.get("prefix", "")
    limit = params.get("limit", 500)
    try:
        names = [n for n in dir(midi) if n.startswith(prefix)]
        names.sort()
        out = []
        for n in names[:limit]:
            try:
                out.append({"name": n, "value": getattr(midi, n)})
            except Exception:
                out.append({"name": n})
        return {"prefix": prefix, "count": len(out), "constants": out}
    except Exception as e:
        return {"error": f"Could not list constants: {e}"}


def handle_system_modules(params: dict) -> dict:
    """Probe which FL API modules this version ships, and extend raw access to them.

    params: {} (no args needed)
    """
    global _RAW_MODULES
    found = _probe_modules()
    for name, mod in found.items():
        if name not in _RAW_MODULES and mod is not None:
            _RAW_MODULES[name] = mod
    return {
        "modules": sorted(found.keys()),
        "new_raw_modules": sorted(
            n for n in found if n in _RAW_MODULES and _RAW_MODULES[n] is found[n]
        ),
        "raw_allowed": sorted(_RAW_MODULES.keys()),
    }


def handle_system_surface(params: dict) -> dict:
    """Return the full callable function surface of one (or all) API modules.

    params: {module: str (optional; omit for all), prefix: str (optional filter)}
    """
    if not _RAW_MODULES:
        handle_system_modules({})
    name = params.get("module", "")
    prefix = params.get("prefix", "")
    result = {}
    targets = [name] if name else sorted(_RAW_MODULES.keys())
    for m in targets:
        mod = _RAW_MODULES.get(m)
        if mod is None:
            result[m] = {"available": False}
            continue
        names = [n for n in dir(mod) if (not prefix or n.startswith(prefix)) and not n.startswith("__")]
        names.sort()
        callable_names = [n for n in names if callable(getattr(mod, n))]
        const_names = [n for n in names if not callable(getattr(mod, n))]
        result[m] = {
            "available": True,
            "function_count": len(callable_names),
            "constant_count": len(const_names),
            "functions": callable_names,
            "constants": const_names,
        }
    return {"surface": result}


def handle_system_diagnostics(params: dict) -> dict:
    """Report the environment this controller is running in.

    This is the first thing to look at when the bridge misbehaves: it shows
    the FL Studio API version, the (heavily stripped) embedded Python, which
    standard library modules are importable and where the controller expects
    to find the command/response files.
    """
    diagnostics = {
        "mcp_version": MCP_VERSION,
        "script_dir": SCRIPT_DIR,
        "command_file": COMMAND_FILE,
        "response_file": RESPONSE_FILE,
        "script_dir_found": bool(SCRIPT_DIR),
        "command_dir_override": COMMAND_DIR_OVERRIDE,
        "python_version": getattr(sys, "version", "unknown"),
        "platform": sys.platform,
    }

    # FL Studio API version (20.7 = 1, 21.0 = 28, 2025 = 40+).
    try:
        diagnostics["fl_api_version"] = general.getVersion()
    except Exception:
        diagnostics["fl_api_version"] = None

    # Built-in modules: FL Studio compiles a cut-down CPython, so this list
    # is the authoritative answer to "what can I import here?".
    builtins_list = list(getattr(sys, "builtin_module_names", ()))
    diagnostics["builtin_modules"] = builtins_list

    # Which of the usual standard library modules can be imported.
    importable = {}
    for name in ("json", "os", "sys", "time", "pathlib", "importlib", "math", "binascii"):
        importable[name] = _try_import(name) is not None
    diagnostics["importable"] = importable

    # FL API modules available in this FL Studio build.
    available = {}
    for name, module in (
        ("channels", channels),
        ("mixer", mixer),
        ("transport", transport),
        ("plugins", plugins),
        ("patterns", patterns),
        ("playlist", playlist),
        ("general", general),
        ("ui", ui),
        ("arrangement", arrangement),
        ("device", device),
        ("midi", midi),
    ):
        available[name] = module is not None
    diagnostics["api_modules"] = available

    # Whether the command/response files are visible from here.
    diagnostics["command_file_exists"] = _file_exists(COMMAND_FILE)
    diagnostics["response_file_exists"] = _file_exists(RESPONSE_FILE)

    return {"diagnostics": diagnostics}


def handle_general_save_undo(params: dict) -> dict:
    """Save an undo snapshot before mutating the project."""
    if general is None:
        return {"error": "general module not available"}
    name = params.get("name", "MCP Change")
    flags = params.get("flags", 0)
    try:
        general.saveUndo(name, flags, 1)
        return {"undo_saved": True, "name": name}
    except Exception as e:
        return {"error": f"saveUndo failed: {e}"}


def handle_general_undo() -> dict:
    """Undo the last change."""
    if general is None:
        return {"error": "general module not available"}
    try:
        general.undo()
        return {"undone": True}
    except Exception as e:
        return {"error": f"undo failed: {e}"}


def handle_general_undo_up_down(params: dict) -> dict:
    """Jump through undo history by offset (-1 = undo, +1 = redo)."""
    if general is None:
        return {"error": "general module not available"}
    offset = params.get("offset", -1)
    try:
        general.undoUpDown(offset)
        return {"offset": offset}
    except Exception as e:
        return {"error": f"undoUpDown failed: {e}"}


def handle_general_info() -> dict:
    """Get general API info: version, undo state, changed flag."""
    if general is None:
        return {"error": "general module not available"}
    info = {}
    try:
        info["api_version"] = general.getVersion()
    except Exception:
        pass
    try:
        info["changed"] = general.getChangedFlag()
    except Exception:
        pass
    try:
        info["rec_ppq"] = general.getRecPPQ()
    except Exception:
        pass
    try:
        info["rec_ppb"] = general.getRecPPB()
    except Exception:
        pass
    try:
        info["undo_count"] = general.getUndoHistoryCount()
    except Exception:
        pass
    try:
        info["undo_pos"] = general.getUndoHistoryPos()
    except Exception:
        pass
    return info


def handle_general_safe_to_edit() -> dict:
    """Check whether it is safe to edit the project."""
    if general is None:
        return {"error": "general module not available"}
    try:
        return {"safe_to_edit": bool(general.safeToEdit())}
    except Exception as e:
        return {"error": f"safeToEdit failed: {e}"}


def handle_general_automate_value(params: dict) -> dict:
    """Write a GLOBAL automation event via general.processRECEvent.

    params:
      - event_id: midi.REC_* constant (e.g. REC_MainVol, REC_Tempo,
                  REC_MainShuffle, REC_SongPosition, REC_SongLength)
      - value: int event value
      - flags: midi.REC_* flags (default: REC_UpdateControl | REC_UpdateValue)
    """
    if general is None:
        return {"error": "general module not available"}
    event_id = params.get("event_id")
    value = params.get("value")
    if event_id is None or value is None:
        return {"error": "event_id and value are required"}
    flags = params.get("flags", -1)
    if flags == -1:
        flags = midi.REC_UpdateControl | midi.REC_UpdateValue
    try:
        general.processRECEvent(int(event_id), int(value), flags)
        return {"event_id": event_id, "value": int(value)}
    except Exception as e:
        return {"error": f"processRECEvent failed: {e}"}


def handle_project_info() -> dict:
    """Get project metadata: title, author, genre, time signature, tempo."""
    info = {}
    if general is not None:
        for key, fn in (
            ("title", "getProjectTitle"),
            ("author", "getProjectAuthor"),
            ("genre", "getProjectGenre"),
        ):
            try:
                info[key] = getattr(general, fn)()
            except Exception:
                pass
        try:
            info["numerator"] = general.getNumerator()
        except Exception:
            pass
        try:
            info["denominator"] = general.getDenominator()
        except Exception:
            pass
    return info


def handle_project_set_time_sig(params: dict) -> dict:
    """Set the project time signature (numerator/denominator)."""
    if general is None:
        return {"error": "general module not available"}
    numerator = params.get("numerator", 4)
    denominator = params.get("denominator", 4)
    try:
        general.setNumerator(numerator)
        general.setDenominator(denominator)
        return {"numerator": numerator, "denominator": denominator}
    except Exception as e:
        return {"error": f"set time signature failed: {e}"}


def handle_project_set_ppq(params: dict) -> dict:
    """Set the pulses-per-quarter (recording resolution)."""
    if general is None:
        return {"error": "general module not available"}
    ppq = params.get("ppq", 96)
    try:
        general.setRecPPQ(ppq)
        return {"ppq": ppq}
    except Exception as e:
        return {"error": f"setRecPPQ failed: {e}"}


def handle_transport_action(params: dict) -> dict:
    """Trigger a native FL Studio global action via transport.globalTransport.

    params: {action: str} where action is a name from the FPT_ map below.
"""
    action = params.get("action", "")
    value = params.get("value", 0)

    fpt_map = {}
    if midi is not None:
        for name in dir(midi):
            if name.startswith("FPT_"):
                try:
                    fpt_map[name[4:].lower()] = getattr(midi, name)
                except Exception:
                    pass

    key = action.lower()
    cmd = params.get("command")
    alias_map = {
        "start": "play",
        "stop": "stop",
        "toggle_play": "play",
        "toggle_play_stop": "play",
        "toggle_record": "record",
        "toggle_recording": "record",
        "saveas": "savenew",
        "save_as": "savenew",
        "prev_pattern": "previous",
        "next_pattern": "next",
        "prev": "previous",
        "nxt": "next",
        "toggle_metronome": "metronome",
        "count_down": "countdown",
        "fast_forward": "fastforward",
        "rewind2": "rewind",
        "mute_track": "mute",
        "stop_and_rewind": "rewind",
        "cut_mixer_track": "cut",
        "copy_mixer_track": "copy",
        "paste_mixer_track": "paste",
        "insert_mixer_track": "insert",
        "delete_mixer_track": "delete",
        "duplicate_mixer_track": "insert",
        "rename_mixer_track": "enter",
        "jump_begin": "rewind",
    }
    key = alias_map.get(key, key)
    if key not in fpt_map and cmd is None:
        return {"error": f"Unknown action '{action}'. Available: {sorted(fpt_map.keys())[:60]}"}

    if cmd is None:
        cmd = fpt_map[key]

    try:
        result = transport.globalTransport(cmd, value)
        return {"action": action, "command": cmd, "result": _serialize(result)}
    except Exception as e:
        return {"error": f"globalTransport({cmd}) failed: {e}"}


def handle_tempo_get() -> dict:
    """Get the real tempo in BPM (FL25 mixer.getCurrentTempo)."""
    try:
        tempo = mixer.getCurrentTempo()
        val = float(tempo)
        if val > 1000.0:
            return {"tempo": val / 1000.0, "raw": val}
        return {"tempo": val, "raw": val}
    except Exception as e:
        try:
            tempo = mixer.getCurrentTempo(False)
            val = float(tempo)
            return {"tempo": val / 1000.0, "raw": val}
        except Exception as e2:
            return {"error": f"getCurrentTempo failed: {e} / {e2}"}


def handle_tempo_set(params: dict) -> dict:
    """Set the tempo in BPM (raw EPB value = BPM * 1000)."""
    tempo = params.get("tempo", params.get("bpm", 140.0))
    try:
        epb = int(float(tempo) * 1000)
        mixer.setCurrentTempo(epb)
        return {"tempo": mixer.getCurrentTempo()}
    except Exception as e:
        return {"error": f"setCurrentTempo failed: {e}"}


def handle_mixer_route(params: dict) -> dict:
    """Add/remove a routing send from a mixer track to a destination.

    params: {track: int, dest: int, value: int (0 or 1), update_ui: bool}
    """
    track = params.get("track", 0)
    dest = params.get("dest", 0)
    value = params.get("value", 1)
    update_ui = params.get("update_ui", False)
    try:
        mixer.setRouteTo(track, dest, value, 1 if update_ui else 0)
        return {
            "track": track,
            "dest": dest,
            "value": value,
            "send_active": 1 if mixer.getRouteSendActive(track, dest) else 0,
        }
    except Exception as e:
        return {"error": f"setRouteTo failed: {e}"}


def handle_mixer_route_level(params: dict) -> dict:
    """Get/set the send level of a routing.

    params: {track: int, dest: int, level: float (0-1, optional to set)}
    """
    track = params.get("track", 0)
    dest = params.get("dest", 0)
    try:
        if "level" in params:
            mixer.setRouteToLevel(track, dest, float(params["level"]))
        level = mixer.getRouteToLevel(track, dest)
        return {"track": track, "dest": dest, "level": level}
    except Exception as e:
        return {"error": f"route level failed: {e}"}


def handle_mixer_route_send_active(params: dict) -> dict:
    """Check whether a routing send between two tracks is active."""
    track = params.get("track", 0)
    dest = params.get("dest", 0)
    try:
        return {"track": track, "dest": dest, "active": int(mixer.getRouteSendActive(track, dest))}
    except Exception as e:
        return {"error": f"getRouteSendActive failed: {e}"}


def handle_mixer_equalizer(params: dict) -> dict:
    """Control the built-in mixer track EQ.

    NOTE: this FL version uses (track, band) argument order and has 3 bands.

    params:
      - track: mixer track
      - mode: 'get' | 'set' | 'bands'
      - band: EQ band index
      - gain: gain in dB (for 'set')
      - freq: frequency in Hz (for 'set')
      - q: bandwidth Q (for 'set')
    """
    track = params.get("track", 0)
    mode = params.get("mode", "get")
    try:
        if mode == "bands":
            try:
                count = mixer.getEqBandCount(track)
            except Exception:
                count = mixer.getEqBandCount()
            bands = []
            for i in range(count):
                try:
                    bands.append({
                        "band": i,
                        "gain": mixer.getEqGain(track, i),
                        "freq": mixer.getEqFrequency(track, i),
                        "q": mixer.getEqBandwidth(track, i),
                    })
                except Exception:
                    pass
            return {"track": track, "count": count, "bands": bands}
        elif mode == "set":
            band = params.get("band", 0)
            if "gain" in params:
                mixer.setEqGain(track, band, float(params["gain"]))
            if "freq" in params:
                mixer.setEqFrequency(track, band, float(params["freq"]))
            if "q" in params:
                mixer.setEqBandwidth(track, band, float(params["q"]))
            return {
                "track": track,
                "band": band,
                "gain": mixer.getEqGain(track, band),
                "freq": mixer.getEqFrequency(track, band),
                "q": mixer.getEqBandwidth(track, band),
            }
        else:  # get one band
            band = params.get("band", 0)
            return {
                "track": track,
                "band": band,
                "gain": mixer.getEqGain(track, band),
                "freq": mixer.getEqFrequency(track, band),
                "q": mixer.getEqBandwidth(track, band),
            }
    except Exception as e:
        return {"error": f"equalizer failed: {e}"}


def handle_mixer_peaks(params: dict) -> dict:
    """Get peak levels for a mixer track.

    params: {track: int, mode: int (L=0, R=1, LR=2)}
    """
    track = params.get("track", 0)
    mode = params.get("mode", 0)
    try:
        return {"track": track, "peaks": mixer.getTrackPeaks(track, mode)}
    except Exception as e:
        return {"error": f"getTrackPeaks failed: {e}"}


def handle_mixer_fx_info(params: dict) -> dict:
    """Get the FX chain of a mixer track.

    params: {track: int, slots: int (default 10)} - returns valid plugin ids/names
    """
    track = params.get("track", 0)
    slots = params.get("slots", 10)
    chain = []
    for slot in range(slots):
        try:
            valid = mixer.isTrackPluginValid(track, slot)
            if valid:
                plugin_id = mixer.getTrackPluginId(track, slot)
                name = ""
                try:
                    name = plugins.getPluginName(track, slot, False)
                except Exception:
                    pass
                chain.append({"slot": slot, "plugin_id": plugin_id, "name": name})
        except Exception:
            pass
    return {"track": track, "fx_chain": chain, "count": len(chain)}


def handle_mixer_fx_mix_level(params: dict) -> dict:
    """Get/set the mix level of an FX slot.

    params: {track: int, slot: int, level: float (0-1, optional to set)}
    """
    track = params.get("track", 0)
    slot = params.get("slot", 0)
    try:
        if "level" in params:
            mixer.setPluginMixLevel(track, slot, float(params["level"]))
        level = mixer.getPluginMixLevel(track, slot)
        return {"track": track, "slot": slot, "mix_level": level}
    except Exception as e:
        return {"error": f"fx mix level failed: {e}"}


def handle_mixer_link_channel(params: dict) -> dict:
    """Directly link a channel to a mixer track (FL docs recommend over setTargetFxTrack).

    params: {channel: int, track: int, link: bool, select: bool}
    """
    channel = params.get("channel", 0)
    track = params.get("track", 0)
    link = params.get("link", params.get("select", False))
    select = params.get("select", False)
    try:
        mixer.linkChannelToTrack(channel, track, 1 if select else 0)
        return {"channel": channel, "track": track, "linked": bool(link)}
    except Exception as e:
        return {"error": f"linkChannelToTrack failed: {e}"}


def handle_mixer_automate(params: dict) -> dict:
    """Automate a mixer parameter via automateEvent (usually for volume/fader rides).

    params:
      - track: mixer track
      - rec_event_id: explicit REC event id (get via mixer.getEventValue/track constants)
      - value: float expected value (0-1)
      - flags: REC_* flags (optional)
      - res: resolution (optional)
    """
    track = params.get("track", 0)
    value = params.get("value", 1.0)
    try:
        if "rec_event_id" in params:
            event_id = int(params["rec_event_id"])
        else:
            event_id = mixer.getEventValue(track)
        args = [event_id, float(value)]
        if "flags" in params:
            args.append(int(params["flags"]))
            if "speed" in params:
                args.append(int(params["speed"]))
            if "increment" in params:
                args.append(int(params["increment"]))
            if "res" in params:
                args.append(int(params["res"]))
        result = mixer.automateEvent(*args)
        return {"event_id": event_id, "value": value, "result": _serialize(result)}
    except Exception as e:
        return {"error": f"automateEvent failed: {e}"}


def handle_channels_event(params: dict) -> dict:
    """Get/set a channel REC event value.

    params:
      - channel: channel index
      - event: one of 'volume' | 'pan' | 'pitch' | midi.REC_Chan_* constant name
      - value: float (optional - if present, sets the event)
      - flags: midi.REC_* flags for setting (default: REC_UpdateValue)
"""
    channel = params.get("channel", 0)
    event_name = params.get("event", "volume")
    value = params.get("value")
    if midi is None:
        return {"error": "midi module not available"}

    event_map = {
        "volume": "REC_Chan_Vol",
        "pan": "REC_Chan_Pan",
        "pitch": "REC_Chan_Pitch",
        "fcut": "REC_Chan_FCut",
        "fres": "REC_Chan_FRes",
        "ftype": "REC_Chan_FType",
        "cut": "REC_Chan_FCut",
        "res": "REC_Chan_FRes",
        "mute": "REC_Chan_Mute",
        "fx": "REC_Chan_FXTrack",
        "offset_vol": "REC_Chan_OfsVol",
        "offset_pan": "REC_Chan_OfsPan",
        "offset_pitch": "REC_Chan_OfsPitch",
        "offset_fcut": "REC_Chan_OfsFCut",
        "offset_fres": "REC_Chan_OfsFRes",
        "note_on": "REC_Chan_NoteOn",
        "note_off": "REC_Chan_NoteOff",
        "note_slide": "REC_Chan_NoteSlide",
        "note_num": "REC_Chan_Note_Num",
        "piano_roll": "REC_Chan_PianoRoll",
        "gate_time": "REC_Chan_GateTime",
        "porta_time": "REC_Chan_PortaTime",
        "smp_ofs": "REC_Chan_SmpOfs",
        "stretch_time": "REC_Chan_StretchTime",
        "time_ofs": "REC_Chan_TimeOfs",
        "swing_mix": "REC_Chan_SwingMix",
        "arpeggio_time": "REC_Chan_Arp_Time",
        "arpeggio_gate": "REC_Chan_Arp_Gate",
        "arpeggio_repeat": "REC_Chan_Arp_Repeat",
        "delay_time": "REC_Chan_Delay_Time",
        "crossfade": "REC_Chan_Crossfade",
        "clip": "REC_Chan_Clip",
    }
    const_name = event_map.get(event_name.lower(), event_name)
    if not hasattr(midi, const_name):
        return {"error": f"Unknown REC event '{const_name}'"}
    event_id = channels.getRecEventId(channel) + getattr(midi, const_name)
    flags = params.get("flags", -1)
    if flags == -1:
        flags = midi.REC_UpdateValue | midi.REC_UpdateControl

    try:
        if value is not None:
            if const_name in ("REC_Chan_Vol", "REC_Chan_OfsVol"):
                if 0.0 <= float(value) <= 1.0:
                    value = int(float(value) * 10000.0)
                else:
                    value = int(value)
            elif const_name in ("REC_Chan_Pan", "REC_Chan_OfsPan"):
                if -1.0 <= float(value) <= 1.0:
                    value = int((float(value) + 1.0) * 5000.0)
                else:
                    value = int(value)
            elif const_name in ("REC_Chan_Pitch", "REC_Chan_OfsPitch"):
                if -24.0 <= float(value) <= 24.0:
                    value = int(float(value) * 100.0)
                else:
                    value = int(value)
            elif const_name == "REC_Chan_SwingMix":
                if 0.0 <= float(value) <= 1.0:
                    value = int(float(value) * 100.0)
                else:
                    value = int(value)
            else:
                value = int(value)
            general.processRECEvent(event_id, value, flags)
        current = general.processRECEvent(event_id, 0, midi.REC_GetValue)
        return {"channel": channel, "event": const_name, "event_id": event_id, "value": current}
    except Exception as e:
        return {"error": f"processRECEvent failed: {e}"}


def handle_channels_shuffle(params: dict) -> dict:
    """Get/set the shuffle (swing) for a channel.

    params: {channel: int, value: float (0-1, optional to set)}
    """
    channel = params.get("channel", 0)
    try:
        if "value" in params:
            setter = getattr(channels, "setShuffle", None)
            if setter is None:
                return {"error": "channels.setShuffle not available in this FL version"}
            setter(channel, float(params["value"]))
        getter = getattr(channels, "getShuffle", None)
        if getter is None:
            return {"channel": channel, "shuffle": None,
                    "note": "getShuffle not available; set still works"}
        value = getter(channel)
        return {"channel": channel, "shuffle": value}
    except Exception as e:
        return {"error": f"shuffle failed: {e}"}


def handle_channels_loop(params: dict) -> dict:
    """Get/set the channel loop style.

    params:
      - channel: channel index
      - pattern: pattern index (default -1 = active)
      - loop: int loop style (0 = off, 1 = new, 2 = all, -1 = toggle);
               'start'/'end' are ignored (channel loops have no range)
    """
    channel = params.get("channel", 0)
    pattern = params.get("pattern", -1)
    loop = params.get("loop")
    if loop is None and "active" in params and params["active"]:
        loop = 1  # mimic the older active flag
    try:
        if loop is not None:
            patterns.setChannelLoop(channel, int(loop), pattern)
        style = patterns.getChannelLoopStyle(pattern, channel)
        return {"channel": channel, "pattern": pattern, "loop_style": style}
    except Exception as e:
        return {"error": f"channel loop failed: {e}"}


def handle_channels_step_param(params: dict) -> dict:
    """Get/set a step parameter for a channel step.

    params:
      - channel: channel index
      - step: step index (0-based)
      - param: int (0=note/pitch, 1=velocity, 2=release, 3=fine pitch,
               4=pan, 5=modX, 6=modY, 7=shift, 8=repeat)
               OR name string: 'note'|'pitch'|'velocity'|'release'|
               'finepitch'|'pan'|'modx'|'mody'|'shift'|'repeat'
      - value: int (optional - if present, sets the value)
      - pattern: pattern index (default -1 = active)
    """
    channel = params.get("channel", 0)
    step = params.get("step", 0)
    param = params.get("param", 0)
    pattern = params.get("pattern", -1)
    value = params.get("value")
    if isinstance(param, str):
        param_map = {
            "note": 0, "pitch": 0,
            "velocity": 1,
            "release": 2,
            "finepitch": 3, "fine_pitch": 3,
            "pan": 4,
            "modx": 5, "mod_x": 5,
            "mody": 6, "mod_y": 6,
            "shift": 7,
            "repeat": 8,
        }
        key = param.lower()
        if key not in param_map:
            return {"error": f"Unknown step param '{param}'. Use: {sorted(param_map.keys())}"}
        param = param_map[key]
    try:
        if value is not None:
            channels.setStepParameterByIndex(channel, pattern, step, param, int(value))
        current = channels.getCurrentStepParam(channel, step, param)
        return {
            "channel": channel,
            "step": step,
            "param": param,
            "pattern": pattern,
            "value": current,
        }
    except Exception as e:
        return {"error": f"step param failed: {e}"}


def handle_playlist_info(params: dict) -> dict:
    """Get basic playlist info: track count, track names, colors, mute/solo.

    params: {include_empty: bool} - if False (default), only includes tracks
            with custom names/colors (skips default 'Track N' entries).
    """
    if playlist is None:
        return {"error": "playlist module not available in this FL Studio version"}
    include_empty = params.get("include_empty", False)
    tracks = []
    try:
        count = playlist.trackCount()
        shown = 0
        for i in range(count):
            try:
                name = playlist.getTrackName(i)
                color = playlist.getTrackColor(i)
                row = {
                    "index": i,
                    "name": name,
                    "color": color,
                    "muted": playlist.isTrackMuted(i) == 1,
                    "solo": playlist.isTrackSolo(i) == 1,
                }
                if include_empty or name != "Track %d" % i or color != -12571053:
                    tracks.append(row)
                    shown += 1
                    if shown >= 300:
                        tracks.append({"truncated": True})
                        break
            except Exception:
                if include_empty:
                    tracks.append({"index": i, "error": "read failed"})
        return {"track_count": count, "shown": len(tracks), "tracks": tracks}
    except Exception as e:
        return {"error": f"playlist info failed: {e}"}


def handle_playlist_set_track_name(params: dict) -> dict:
    """Rename a playlist track."""
    if playlist is None:
        return {"error": "playlist module not available"}
    track = params.get("track", 0)
    name = params.get("name", "")
    try:
        playlist.setTrackName(track, name)
        return {"track": track, "name": name}
    except Exception as e:
        return {"error": f"setTrackName failed: {e}"}


def handle_playlist_set_track_color(params: dict) -> dict:
    """Set a playlist track color."""
    if playlist is None:
        return {"error": "playlist module not available"}
    track = params.get("track", 0)
    r = params.get("r", 0)
    g = params.get("g", 0)
    b = params.get("b", 0)
    try:
        color = (b << 16) | (g << 8) | r
        playlist.setTrackColor(track, color)
        return {"track": track, "color": f"RGB({r}, {g}, {b})"}
    except Exception as e:
        return {"error": f"setTrackColor failed: {e}"}


def handle_playlist_mute(params: dict) -> dict:
    """Mute/unmute a playlist track."""
    if playlist is None:
        return {"error": "playlist module not available"}
    track = params.get("track", 0)
    muted = params.get("muted")  # None = toggle
    try:
        if muted is None:
            muted = 1 - playlist.isTrackMuted(track)
        playlist.muteTrack(track, 1 if muted else 0)
        return {"track": track, "muted": playlist.isTrackMuted(track) == 1}
    except Exception as e:
        return {"error": f"muteTrack failed: {e}"}


def handle_playlist_solo(params: dict) -> dict:
    """Solo/unsolo a playlist track."""
    if playlist is None:
        return {"error": "playlist module not available"}
    track = params.get("track", 0)
    solo = params.get("solo")  # None = toggle
    try:
        if solo is None:
            solo = 1 - playlist.isTrackSolo(track)
        playlist.soloTrack(track, 1 if solo else 0)
        return {"track": track, "solo": playlist.isTrackSolo(track) == 1}
    except Exception as e:
        return {"error": f"soloTrack failed: {e}"}


def handle_playlist_select(params: dict) -> dict:
    """Select a playlist track."""
    if playlist is None:
        return {"error": "playlist module not available"}
    track = params.get("track", 0)
    select = params.get("select", True)
    try:
        playlist.selectTrack(track, 1 if select else 0)
        return {"track": track, "selected": bool(playlist.isTrackSelected(track))}
    except Exception as e:
        return {"error": f"selectTrack failed: {e}"}


def handle_ui_hint(params: dict) -> dict:
    """Display a hint message in FL Studio's hint bar."""
    if ui is None:
        return {"error": "ui module not available"}
    message = params.get("message", params.get("text", ""))
    try:
        ui.setHintMsg(message)
        return {"hint": message}
    except Exception as e:
        return {"error": f"setHintMsg failed: {e}"}

def handle_piano_dump_score_log(params: dict) -> dict:
    """Dump the played MIDI score into the piano roll of the selected channel.

    This is the KEY melody-writing capability: play MIDI notes via
    fl_trigger_note while recording-lite, then call this to persist them
    into the selected channel's piano roll.

    params: {time: int (seconds of score to dump), silent: bool (0/1)}
"""
    if general is None:
        return {"error": "general module not available"}
    score_time = params.get("time", 10)
    silent = params.get("silent", 1)
    try:
        general.dumpScoreLog(int(score_time), 1 if silent else 0)
        return {"score_log_dumped": True, "time": score_time, "silent": silent}
    except Exception as e:
        return {"error": f"dumpScoreLog failed: {e}"}


def handle_transport_position() -> dict:
    """Get the current playback position in human-readable and tick form."""
    pos = {}
    try:
        pos["hint"] = transport.getSongPosHint()
    except Exception:
        pass
    try:
        pos["song_pos"] = transport.getSongPos(0)
    except Exception:
        pass
    try:
        pos["recent_beat"] = transport.getRecentBeat(1)
    except Exception:
        pass
    return pos


def handle_arrangement_info() -> dict:
    """Get arrangement info: time signature events in the playlist."""
    info = {}
    try:
        info["num_tsevents"] = arrangement.getNumTSEvents()
    except Exception:
        pass
    try:
        for i in range(min(info.get("num_tsevents", 0), 16)):
            try:
                bar, num, den = arrangement.getTSEventTimeSig(i)
                info.setdefault("time_sigs", []).append({"event": i, "bar": bar, "num": num, "den": den})
            except Exception:
                pass
    except Exception:
        pass
    try:
        info["song_end_position"] = arrangement.getSongEndPosition()
    except Exception:
        pass
    return info

def handle_project_snapshot(params: dict) -> dict:
    """One-shot compact snapshot of the entire project state."""
    pass  # no major import needed
    snap = {}
    include_playlist = params.get("include_playlist", False)
    try:
        snap["tempo"] = handle_tempo_get()
    except Exception:
        pass
    try:
        snap["info"] = handle_general_info()
    except Exception:
        pass
    try:
        snap["project"] = handle_project_info()
    except Exception:
        pass
    try:
        snap["active_pattern"] = patterns.patternNumber()
        snap["patterns"] = []
        pc = patterns.patternCount()
        for i in range(pc):
            try:
                snap["patterns"].append({"index": i, "name": patterns.getPatternName(i), "length": patterns.getPatternLength(i)})
            except Exception:
                snap["patterns"].append({"index": i, "name": patterns.getPatternName(i)})
    except Exception as e:
        snap["patterns_error"] = str(e)
    try:
        channels_out = []
        cc = channels.channelCount()
        for i in range(cc):
            ch = {"index": i, "name": channels.getChannelName(i), "color": channels.getChannelColor(i), "muted": channels.isChannelMuted(i)}
            if include_playlist:
                try:
                    ch["mixer_track"] = channels.getChannelMixerTrack(i)
                except Exception:
                    pass
            channels_out.append(ch)
        snap["channels"] = channels_out
    except Exception as e:
        snap["channels_error"] = str(e)
    if include_playlist:
        try:
            snap["playlist"] = handle_playlist_info({"include_empty": False})
        except Exception:
            pass
    try:
        snap["playlist_layout"] = handle_transport_position()
    except Exception:
        pass
    return snap
# =============================================================================
# FULL-SURFACE GENERIC COMMAND LAYER
#
# Covers EVERY function of every module this FL version exposes (verified via
# system.surface): channels, mixer, transport, patterns, playlist, general,
# ui, arrangement, device, plugins.
#
# Format: "<module>.<name>" -> (fn, [(param, kind), ...])
#   kind: int | float | str | bool | color(r,g,b->0xBBGGRR) | epb(bpm->epb)
#         | sysex(list of ints -> bytes)
#   "get_" prefixed fns return {"value": <serialized result>}
#   setters return {"ok": True, "fn": fn, "args": [...]}
# =============================================================================

def _pack_color(params):
    if "color" in params:
        return int(params["color"])
    return (int(params.get("b", 0)) << 16) | (int(params.get("g", 0)) << 8) | int(params.get("r", 0))


def _convert_arg(param, kind, params):
    if kind == "int":
        return int(params[param])
    if kind == "float":
        return float(params[param])
    if kind == "str":
        return str(params[param])
    if kind == "bool":
        return 1 if params[param] else 0
    if kind == "epb":
        return int(float(params[param]) * 1000.0)
    if kind == "color":
        return _pack_color(params)
    if kind == "sysex":
        data = params[param]
        if isinstance(data, list):
            return bytes(data)
        if isinstance(data, str):
            return bytes(int(x, 16) for x in data.replace(" ", "").split(",") if x)
        return bytes()
    return params[param]


GENERIC_COMMANDS = {
    # ============================== MIXER ==============================
    "mixer.setTrackVolume": ("mixer", "setTrackVolume", [("track", "int"), ("value", "float")]),
    "mixer.setTrackPan": ("mixer", "setTrackPan", [("track", "int"), ("value", "float")]),
    "mixer.setTrackStereoSep": ("mixer", "setTrackStereoSep", [("track", "int"), ("value", "float")]),
    "mixer.setTrackColor": ("mixer", "setTrackColor", [("track", "int"), ("color", "color")]),
    "mixer.setTrackName": ("mixer", "setTrackName", [("track", "int"), ("name", "str")]),
    "mixer.setSlotColor": ("mixer", "setSlotColor", [("track", "int"), ("slot", "int"), ("color", "color")]),
    "mixer.setActiveTrack": ("mixer", "setActiveTrack", [("track", "int")]),
    "mixer.selectTrack": ("mixer", "selectTrack", [("track", "int"), ("select", "bool")]),
    "mixer.selectAll": ("mixer", "selectAll", []),
    "mixer.deselectAll": ("mixer", "deselectAll", []),
    "mixer.soloTrack": ("mixer", "soloTrack", [("track", "int"), ("solo", "bool")]),
    "mixer.muteTrack": ("mixer", "muteTrack", [("track", "int"), ("mute", "bool")]),
    "mixer.enableTrack": ("mixer", "enableTrack", [("track", "int"), ("enabled", "bool")]),
    "mixer.enableTrackSlots": ("mixer", "enableTrackSlots", [("track", "int"), ("enabled", "bool")]),
    "mixer.armTrack": ("mixer", "armTrack", [("track", "int"), ("armed", "bool")]),
    "mixer.setTrackNumber": ("mixer", "setTrackNumber", [("track", "int"), ("newNumber", "int")]),
    "mixer.setEqGain": ("mixer", "setEqGain", [("track", "int"), ("band", "int"), ("gain", "float")]),
    "mixer.setEqFrequency": ("mixer", "setEqFrequency", [("track", "int"), ("band", "int"), ("freq", "float")]),
    "mixer.setEqBandwidth": ("mixer", "setEqBandwidth", [("track", "int"), ("band", "int"), ("q", "float")]),
    "mixer.setRouteTo": ("mixer", "setRouteTo", [("track", "int"), ("dest", "int"), ("value", "float")]),
    "mixer.setRouteToLevel": ("mixer", "setRouteToLevel", [("track", "int"), ("dest", "int"), ("value", "float")]),
    "mixer.setPluginMixLevel": ("mixer", "setPluginMixLevel", [("track", "int"), ("slot", "int"), ("value", "float")]),
    "mixer.setPluginMuteState": ("mixer", "setPluginMuteState", [("track", "int"), ("slot", "int"), ("mute", "bool")]),
    "mixer.swapTrackChannels": ("mixer", "swapTrackChannels", [("track", "int")]),
    "mixer.revTrackPolarity": ("mixer", "revTrackPolarity", [("track", "int")]),
    "mixer.linkChannelToTrack": ("mixer", "linkChannelToTrack", [("channel", "int"), ("track", "int")]),
    "mixer.linkTrackToChannel": ("mixer", "linkTrackToChannel", [("channel", "int"), ("track", "int")]),
    "mixer.afterRoutingChanged": ("mixer", "afterRoutingChanged", []),
    "mixer.focusEditor": ("mixer", "focusEditor", [("track", "int")]),
    "mixer.setCurrentTempo": ("mixer", "setCurrentTempo", [("bpm", "epb")]),
    "mixer.automateEvent": ("mixer", "automateEvent", [("track", "int"), ("eventId", "int"), ("value", "int"), ("flags", "int")]),
    "mixer.getTrackVolume": ("mixer", "getTrackVolume", [("track", "int")]),
    "mixer.getTrackPan": ("mixer", "getTrackPan", [("track", "int")]),
    "mixer.getTrackStereoSep": ("mixer", "getTrackStereoSep", [("track", "int")]),
    "mixer.getTrackColor": ("mixer", "getTrackColor", [("track", "int")]),
    "mixer.getTrackName": ("mixer", "getTrackName", [("track", "int")]),
    "mixer.isTrackMuted": ("mixer", "isTrackMuted", [("track", "int")]),
    "mixer.isTrackSolo": ("mixer", "isTrackSolo", [("track", "int")]),
    "mixer.isTrackSelected": ("mixer", "isTrackSelected", [("track", "int")]),
    "mixer.isTrackArmed": ("mixer", "isTrackArmed", [("track", "int")]),
    "mixer.isTrackEnabled": ("mixer", "isTrackEnabled", [("track", "int")]),
    "mixer.isTrackMuteLock": ("mixer", "isTrackMuteLock", [("track", "int")]),
    "mixer.isTrackSlotsEnabled": ("mixer", "isTrackSlotsEnabled", [("track", "int")]),
    "mixer.isTrackAutomationEnabled": ("mixer", "isTrackAutomationEnabled", [("track", "int")]),
    "mixer.isTrackRevPolarity": ("mixer", "isTrackRevPolarity", [("track", "int")]),
    "mixer.isTrackSwapChannels": ("mixer", "isTrackSwapChannels", [("track", "int")]),
    "mixer.getTrackDockSide": ("mixer", "getTrackDockSide", [("track", "int")]),
    "mixer.getTrackInfo": ("mixer", "getTrackInfo", [("track", "int")]),
    "mixer.getTrackPeaks": ("mixer", "getTrackPeaks", [("track", "int")]),
    "mixer.getLastPeakVol": ("mixer", "getLastPeakVol", [("track", "int")]),
    "mixer.getTrackPluginId": ("mixer", "getTrackPluginId", [("track", "int"), ("slot", "int")]),
    "mixer.getPluginMixLevel": ("mixer", "getPluginMixLevel", [("track", "int"), ("slot", "int")]),
    "mixer.getPluginMuteState": ("mixer", "getPluginMuteState", [("track", "int"), ("slot", "int")]),
    "mixer.getEqBandCount": ("mixer", "getEqBandCount", []),
    "mixer.getEqGain": ("mixer", "getEqGain", [("track", "int"), ("band", "int")]),
    "mixer.getEqFrequency": ("mixer", "getEqFrequency", [("track", "int"), ("band", "int")]),
    "mixer.getEqBandwidth": ("mixer", "getEqBandwidth", [("track", "int"), ("band", "int")]),
    "mixer.getRouteToLevel": ("mixer", "getRouteToLevel", [("track", "int"), ("dest", "int")]),
    "mixer.getRouteSendActive": ("mixer", "getRouteSendActive", [("track", "int"), ("dest", "int")]),
    "mixer.getActiveEffectIndex": ("mixer", "getActiveEffectIndex", [("track", "int")]),
    "mixer.getTrackRecordingFileName": ("mixer", "getTrackRecordingFileName", [("track", "int")]),
    "mixer.getEventValue": ("mixer", "getEventValue", [("eventId", "int")]),
    "mixer.getEventIDName": ("mixer", "getEventIDName", [("eventId", "int")]),
    "mixer.getEventIDValueString": ("mixer", "getEventIDValueString", [("eventId", "int")]),
    "mixer.getAutoSmoothEventValue": ("mixer", "getAutoSmoothEventValue", [("track", "int"), ("eventId", "int")]),
    "mixer.remoteFindEventValue": ("mixer", "remoteFindEventValue", [("name", "str")]),
    "mixer.getSongStepPos": ("mixer", "getSongStepPos", []),
    "mixer.getSongTickPos": ("mixer", "getSongTickPos", []),
    "mixer.getRecPPS": ("mixer", "getRecPPS", []),
    "mixer.getCurrentTempo": ("mixer", "getCurrentTempo", []),
    "mixer.trackCount": ("mixer", "trackCount", []),
    "mixer.getTrackCount": ("mixer", "getTrackCount", []),
    "mixer.trackNumber": ("mixer", "trackNumber", []),

    # ============================= CHANNELS =============================
    "channels.setChannelVolume": ("channels", "setChannelVolume", [("channel", "int"), ("value", "float")]),
    "channels.setChannelPan": ("channels", "setChannelPan", [("channel", "int"), ("value", "float")]),
    "channels.setChannelPitch": ("channels", "setChannelPitch", [("channel", "int"), ("value", "int")]),
    "channels.setChannelName": ("channels", "setChannelName", [("channel", "int"), ("name", "str")]),
    "channels.setChannelColor": ("channels", "setChannelColor", [("channel", "int"), ("color", "color")]),
    "channels.setTargetFxTrack": ("channels", "setTargetFxTrack", [("channel", "int"), ("track", "int")]),
    "channels.selectChannel": ("channels", "selectChannel", [("channel", "int"), ("select", "bool")]),
    "channels.selectOneChannel": ("channels", "selectOneChannel", [("channel", "int")]),
    "channels.selectAll": ("channels", "selectAll", []),
    "channels.deselectAll": ("channels", "deselectAll", []),
    "channels.muteChannel": ("channels", "muteChannel", [("channel", "int"), ("muted", "bool")]),
    "channels.soloChannel": ("channels", "soloChannel", [("channel", "int"), ("solo", "bool")]),
    "channels.focusEditor": ("channels", "focusEditor", [("channel", "int")]),
    "channels.showCSForm": ("channels", "showCSForm", [("channel", "int"), ("show", "bool")]),
    "channels.showEditor": ("channels", "showEditor", [("channel", "int"), ("show", "bool")]),
    "channels.showGraphEditor": ("channels", "showGraphEditor", [("channel", "int"), ("show", "bool")]),
    "channels.updateGraphEditor": ("channels", "updateGraphEditor", [("channel", "int")]),
    "channels.closeGraphEditor": ("channels", "closeGraphEditor", []),
    "channels.setGridBit": ("channels", "setGridBit", [("channel", "int"), ("gridBit", "int"), ("value", "int")]),
    "channels.setStepParameterByIndex": ("channels", "setStepParameterByIndex", [("channel", "int"), ("step", "int"), ("paramIndex", "int"), ("value", "int")]),
    "channels.incEventValue": ("channels", "incEventValue", [("channel", "int"), ("value", "int"), ("eventId", "int")]),
    "channels.midiNoteOn": ("channels", "midiNoteOn", [("channel", "int"), ("note", "int"), ("velocity", "int")]),
    "channels.quickQuantize": ("channels", "quickQuantize", [("channel", "int"), ("mode", "int")]),
    "channels.rerollLoopStarterLoop": ("channels", "rerollLoopStarterLoop", []),
    "channels.rerollLoopStarterSample": ("channels", "rerollLoopStarterSample", []),
    "channels.rerollLoopStarterSteps": ("channels", "rerollLoopStarterSteps", []),
    "channels.fillEachNSteps": ("channels", "fillEachNSteps", [("channel", "int"), ("steps", "int"), ("value", "int")]),
    "channels.channelCount": ("channels", "channelCount", []),
    "channels.channelNumber": ("channels", "channelNumber", []),
    "channels.selectedChannel": ("channels", "selectedChannel", []),
    "channels.isChannelSelected": ("channels", "isChannelSelected", [("channel", "int")]),
    "channels.isChannelMuted": ("channels", "isChannelMuted", [("channel", "int")]),
    "channels.isChannelSolo": ("channels", "isChannelSolo", [("channel", "int")]),
    "channels.isChannelHighLighted": ("channels", "isHighLighted", [("channel", "int")]),
    "channels.isGraphEditorVisible": ("channels", "isGraphEditorVisible", [("channel", "int")]),
    "channels.getChannelIndex": ("channels", "getChannelIndex", []),
    "channels.getChannelMidiInPort": ("channels", "getChannelMidiInPort", [("channel", "int")]),
    "channels.getChannelType": ("channels", "getChannelType", [("channel", "int")]),
    "channels.getChannelName": ("channels", "getChannelName", [("channel", "int")]),
    "channels.getChannelPan": ("channels", "getChannelPan", [("channel", "int")]),
    "channels.getChannelPitch": ("channels", "getChannelPitch", [("channel", "int")]),
    "channels.getChannelVolume": ("channels", "getChannelVolume", [("channel", "int")]),
    "channels.getChannelColor": ("channels", "getChannelColor", [("channel", "int")]),
    "channels.getActivityLevel": ("channels", "getActivityLevel", [("channel", "int")]),
    "channels.getRecEventId": ("channels", "getRecEventId", [("channel", "int")]),
    "channels.getCurrentStepParam": ("channels", "getCurrentStepParam", [("channel", "int"), ("step", "int")]),
    "channels.getStepParam": ("channels", "getStepParam", [("channel", "int"), ("step", "int")]),
    "channels.getGridBit": ("channels", "getGridBit", [("channel", "int")]),
    "channels.getGridBitWithLoop": ("channels", "getGridBitWithLoop", [("channel", "int")]),
    "channels.isGridBitAssigned": ("channels", "isGridBitAssigned", [("channel", "int"), ("gridBit", "int")]),
    "channels.getTargetFxTrack": ("channels", "getTargetFxTrack", [("channel", "int")]),
    "channels.processRECEvent": ("channels", "processRECEvent", [("channel", "int"), ("value", "int"), ("eventId", "int"), ("flags", "int")]),

    # ============================= TRANSPORT =============================
    "transport.start": ("transport", "start", []),
    "transport.stop": ("transport", "stop", []),
    "transport.record": ("transport", "record", []),
    "transport.rewind": ("transport", "rewind", [("startStop", "int"), ("flags", "int")]),
    "transport.fastForward": ("transport", "fastForward", [("startStop", "int"), ("flags", "int")]),
    "transport.globalTransport": ("transport", "globalTransport", [("command", "int"), ("value", "int"), ("pmeflags", "int"), ("flags", "int")]),
    "transport.setSongPos": ("transport", "setSongPos", [("position", "int"), ("mode", "int")]),
    "transport.getSongPos": ("transport", "getSongPos", [("mode", "int")]),
    "transport.getSongPosHint": ("transport", "getSongPosHint", []),
    "transport.setLoopMode": ("transport", "setLoopMode", [("mode", "int")]),
    "transport.getLoopMode": ("transport", "getLoopMode", []),
    "transport.continuousMove": ("transport", "continuousMove", [("speed", "int"), ("startStop", "bool")]),
    "transport.continuousMovePos": ("transport", "continuousMovePos", [("speed", "int"), ("startStop", "bool")]),
    "transport.markerJumpJog": ("transport", "markerJumpJog", [("value", "int"), ("flags", "int")]),
    "transport.markerSelJog": ("transport", "markerSelJog", [("value", "int"), ("flags", "int")]),
    "transport.setPlaybackSpeed": ("transport", "setPlaybackSpeed", [("speedMultiplier", "float")]),
    "transport.getSongLength": ("transport", "getSongLength", [("mode", "int")]),
    "transport.isPlaying": ("transport", "isPlaying", []),
    "transport.isRecording": ("transport", "isRecording", []),
    "transport.getHWBeatLEDState": ("transport", "getHWBeatLEDState", []),

    # ============================= PATTERNS =============================
    "patterns.selectPattern": ("patterns", "selectPattern", [("pattern", "int")]),
    "patterns.selectAll": ("patterns", "selectAll", []),
    "patterns.deselectAll": ("patterns", "deselectAll", []),
    "patterns.jumpToPattern": ("patterns", "jumpToPattern", [("pattern", "int")]),
    "patterns.isPatternSelected": ("patterns", "isPatternSelected", [("pattern", "int")]),
    "patterns.setPatternName": ("patterns", "setPatternName", [("pattern", "int"), ("name", "str")]),
    "patterns.setPatternColor": ("patterns", "setPatternColor", [("pattern", "int"), ("color", "color")]),
    "patterns.getPatternName": ("patterns", "getPatternName", [("pattern", "int")]),
    "patterns.getPatternColor": ("patterns", "getPatternColor", [("pattern", "int")]),
    "patterns.getPatternLength": ("patterns", "getPatternLength", [("pattern", "int")]),
    "patterns.clonePattern": ("patterns", "clonePattern", [("from", "int"), ("to", "int")]),
    "patterns.movePattern": ("patterns", "movePattern", [("src", "int"), ("dest", "int")]),
    "patterns.patternCount": ("patterns", "patternCount", []),
    "patterns.patternNumber": ("patterns", "patternNumber", []),
    "patterns.patternMax": ("patterns", "patternMax", []),
    "patterns.getPatternGroupCount": ("patterns", "getPatternGroupCount", []),
    "patterns.getActivePatternGroup": ("patterns", "getActivePatternGroup", []),
    "patterns.getPatternGroupName": ("patterns", "getPatternGroupName", [("group", "int")]),
    "patterns.getPatternsInGroup": ("patterns", "getPatternsInGroup", [("group", "int")]),
    "patterns.isPatternDefault": ("patterns", "isPatternDefault", [("pattern", "int")]),
    "patterns.getChannelLoopStyle": ("patterns", "getChannelLoopStyle", [("channel", "int")]),
    "patterns.setChannelLoop": ("patterns", "setChannelLoop", [("channel", "int"), ("loopStyle", "int")]),
    "patterns.getBlockSetStatus": ("patterns", "getBlockSetStatus", [("pattern", "int")]),
    "patterns.findFirstNextEmptyPat": ("patterns", "findFirstNextEmptyPat", []),
    "patterns.setLoopStarterRootNote": ("patterns", "setLoopStarterRootNote", [("note", "int")]),
    "patterns.burnLoop": ("patterns", "burnLoop", [("pattern", "int")]),
    "patterns.ensureValidNoteRecord": ("patterns", "ensureValidNoteRecord", []),

    # ============================= PLAYLIST =============================
    "playlist.selectTrack": ("playlist", "selectTrack", [("track", "int"), ("select", "bool")]),
    "playlist.selectAll": ("playlist", "selectAll", []),
    "playlist.deselectAll": ("playlist", "deselectAll", []),
    "playlist.muteTrack": ("playlist", "muteTrack", [("track", "int"), ("mute", "bool")]),
    "playlist.muteTrackLock": ("playlist", "muteTrackLock", [("track", "int"), ("lock", "bool")]),
    "playlist.soloTrack": ("playlist", "soloTrack", [("track", "int"), ("solo", "bool")]),
    "playlist.setTrackName": ("playlist", "setTrackName", [("track", "int"), ("name", "str")]),
    "playlist.setTrackColor": ("playlist", "setTrackColor", [("track", "int"), ("color", "color")]),
    "playlist.scrollTo": ("playlist", "scrollTo", [("pos", "int")]),
    "playlist.selectTool": ("playlist", "selectTool", [("tool", "int")]),
    "playlist.triggerLiveClip": ("playlist", "triggerLiveClip", [("channel", "int"), ("clipIndex", "int")]),
    "playlist.refreshLiveClips": ("playlist", "refreshLiveClips", []),
    "playlist.lockDisplayZone": ("playlist", "lockDisplayZone", [("enabled", "bool")]),
    "playlist.incLiveLoopMode": ("playlist", "incLiveLoopMode", []),
    "playlist.incLivePosSnap": ("playlist", "incLivePosSnap", []),
    "playlist.incLiveTrigMode": ("playlist", "incLiveTrigMode", []),
    "playlist.incLiveTrigSnap": ("playlist", "incLiveTrigSnap", []),
    "playlist.liveBlockNumToTime": ("playlist", "liveBlockNumToTime", [("block", "int")]),
    "playlist.liveTimeToBlockNum": ("playlist", "liveTimeToBlockNum", [("time", "int")]),
    "playlist.getTrackName": ("playlist", "getTrackName", [("track", "int")]),
    "playlist.getTrackColor": ("playlist", "getTrackColor", [("track", "int")]),
    "playlist.isTrackMuted": ("playlist", "isTrackMuted", [("track", "int")]),
    "playlist.isTrackSolo": ("playlist", "isTrackSolo", [("track", "int")]),
    "playlist.isTrackSelected": ("playlist", "isTrackSelected", [("track", "int")]),
    "playlist.isTrackMuteLock": ("playlist", "isTrackMuteLock", [("track", "int")]),
    "playlist.getTrackActivityLevel": ("playlist", "getTrackActivityLevel", [("track", "int")]),
    "playlist.getTrackActivityLevelVis": ("playlist", "getTrackActivityLevelVis", [("track", "int")]),
    "playlist.trackCount": ("playlist", "trackCount", []),
    "playlist.getSongStartTickPos": ("playlist", "getSongStartTickPos", []),
    "playlist.getVisTimeBar": ("playlist", "getVisTimeBar", []),
    "playlist.getVisTimeStep": ("playlist", "getVisTimeStep", []),
    "playlist.getVisTimeTick": ("playlist", "getVisTimeTick", []),
    "playlist.getDisplayZone": ("playlist", "getDisplayZone", []),
    "playlist.getLiveBlockColor": ("playlist", "getLiveBlockColor", [("track", "int"), ("block", "int")]),
    "playlist.getLiveBlockStatus": ("playlist", "getLiveBlockStatus", [("track", "int"), ("block", "int")]),
    "playlist.getLiveLoopMode": ("playlist", "getLiveLoopMode", []),
    "playlist.getLivePosSnap": ("playlist", "getLivePosSnap", []),
    "playlist.getLiveTrigSnap": ("playlist", "getLiveTrigSnap", []),
    "playlist.getLiveTriggerMode": ("playlist", "getLiveTriggerMode", []),
    "playlist.getLiveStatus": ("playlist", "getLiveStatus", []),
    "playlist.getPerformanceModeState": ("playlist", "getPerformanceModeState", []),

    # ============================= GENERAL =============================
    "general.setNumerator": ("general", "setNumerator", [("numerator", "int")]),
    "general.setDenominator": ("general", "setDenominator", [("denominator", "int")]),
    "general.setRecPPQ": ("general", "setRecPPQ", [("ppq", "int")]),
    "general.processRECEvent": ("general", "processRECEvent", [("eventId", "int"), ("value", "int"), ("flags", "int")]),
    "general.restoreUndo": ("general", "restoreUndo", []),
    "general.restoreUndoLevel": ("general", "restoreUndoLevel", [("level", "int")]),
    "general.setUndoHistoryCount": ("general", "setUndoHistoryCount", [("count", "int")]),
    "general.setUndoHistoryLast": ("general", "setUndoHistoryLast", [("index", "int")]),
    "general.setUndoHistoryPos": ("general", "setUndoHistoryPos", [("pos", "int")]),
    "general.clearLog": ("general", "clearLog", []),
    "general.getVersion": ("general", "getVersion", []),
    "general.getProjectTitle": ("general", "getProjectTitle", []),
    "general.getProjectAuthor": ("general", "getProjectAuthor", []),
    "general.getProjectGenre": ("general", "getProjectGenre", []),
    "general.getRecPPB": ("general", "getRecPPB", []),
    "general.getRecPPQ": ("general", "getRecPPQ", []),
    "general.getChangedFlag": ("general", "getChangedFlag", []),
    "general.safeToEdit": ("general", "safeToEdit", []),
    "general.getUseMetronome": ("general", "getUseMetronome", []),
    "general.getPrecount": ("general", "getPrecount", []),
    "general.getUndoHistoryCount": ("general", "getUndoHistoryCount", []),
    "general.getUndoHistoryLast": ("general", "getUndoHistoryLast", []),
    "general.getUndoHistoryPos": ("general", "getUndoHistoryPos", []),
    "general.getUndoLevelHint": ("general", "getUndoLevelHint", []),
    "general.undo": ("general", "undo", []),
    "general.undoUp": ("general", "undoUp", []),
    "general.undoDown": ("general", "undoDown", []),
    "general.undoUpDown": ("general", "undoUpDown", [("value", "int")]),

    # ============================= UI =============================
    "ui.showWindow": ("ui", "showWindow", [("windowId", "int")]),
    "ui.hideWindow": ("ui", "hideWindow", [("windowId", "int")]),
    "ui.selectWindow": ("ui", "selectWindow", [("windowId", "int"), ("open", "int")]),
    "ui.setFocused": ("ui", "setFocused", [("windowId", "int")]),
    "ui.setHintMsg": ("ui", "setHintMsg", [("message", "str")]),
    "ui.setSnapMode": ("ui", "setSnapMode", [("snapMode", "int")]),
    "ui.snapOnOff": ("ui", "snapOnOff", [("snapOn", "bool")]),
    "ui.setTimeDispMin": ("ui", "setTimeDispMin", [("minimum", "int")]),
    "ui.setStepEditMode": ("ui", "setStepEditMode", [("editMode", "int")]),
    "ui.setBrowserAutoHide": ("ui", "setBrowserAutoHide", [("autoHide", "bool")]),
    "ui.navigateBrowser": ("ui", "navigateBrowser", [("mode", "int")]),
    "ui.navigateBrowserMenu": ("ui", "navigateBrowserMenu", [("mode", "int")]),
    "ui.navigateBrowserTabs": ("ui", "navigateBrowserTabs", [("dir", "int")]),
    "ui.selectBrowserMenuItem": ("ui", "selectBrowserMenuItem", [("itemIndex", "int")]),
    "ui.previewBrowserMenuItem": ("ui", "previewBrowserMenuItem", [("itemIndex", "int")]),
    "ui.toggleBrowserNode": ("ui", "toggleBrowserNode", [("itemIndex", "int")]),
    "ui.launchAudioEditor": ("ui", "launchAudioEditor", [("path", "str")]),
    "ui.openEventEditor": ("ui", "openEventEditor", [("eventId", "int")]),
    "ui.closeActivePopupMenu": ("ui", "closeActivePopupMenu", []),
    "ui.closeAllMenu": ("ui", "closeAllMenu", []),
    "ui.scrollWindow": ("ui", "scrollWindow", [("clickType", "int"), ("dir", "int")]),
    "ui.horZoom": ("ui", "horZoom", [("value", "int")]),
    "ui.verZoom": ("ui", "verZoom", [("value", "int")]),
    "ui.jog": ("ui", "jog", [("value", "int")]),
    "ui.jog2": ("ui", "jog2", [("value", "int")]),
    "ui.strip": ("ui", "strip", [("value", "int")]),
    "ui.stripHold": ("ui", "stripHold", [("value", "int")]),
    "ui.stripJog": ("ui", "stripJog", [("value", "int")]),
    "ui.moveJog": ("ui", "moveJog", [("value", "int")]),
    "ui.nextWindow": ("ui", "nextWindow", []),
    "ui.copy": ("ui", "copy", []),
    "ui.cut": ("ui", "cut", []),
    "ui.paste": ("ui", "paste", []),
    "ui.delete": ("ui", "delete", []),
    "ui.insert": ("ui", "insert", []),
    "ui.enter": ("ui", "enter", []),
    "ui.escape": ("ui", "escape", []),
    "ui.up": ("ui", "up", []),
    "ui.down": ("ui", "down", []),
    "ui.left": ("ui", "left", []),
    "ui.right": ("ui", "right", []),
    "ui.next": ("ui", "next", []),
    "ui.previous": ("ui", "previous", []),
    "ui.yes": ("ui", "yes", []),
    "ui.no": ("ui", "no", []),
    "ui.getVisible": ("ui", "getVisible", [("windowId", "int")]),
    "ui.getFocused": ("ui", "getFocused", []),
    "ui.getFocusedFormID": ("ui", "getFocusedFormID", []),
    "ui.getFocusedFormCaption": ("ui", "getFocusedFormCaption", []),
    "ui.getFocusedNodeCaption": ("ui", "getFocusedNodeCaption", []),
    "ui.getFocusedNodeFileType": ("ui", "getFocusedNodeFileType", []),
    "ui.getFocusedPluginName": ("ui", "getFocusedPluginName", []),
    "ui.getProgTitle": ("ui", "getProgTitle", []),
    "ui.getVersion": ("ui", "getVersion", []),
    "ui.getHintMsg": ("ui", "getHintMsg", []),
    "ui.getHintValue": ("ui", "getHintValue", []),
    "ui.getSnapMode": ("ui", "getSnapMode", []),
    "ui.getTimeDispMin": ("ui", "getTimeDispMin", []),
    "ui.getStepEditMode": ("ui", "getStepEditMode", []),
    "ui.isMetronomeEnabled": ("ui", "isMetronomeEnabled", []),
    "ui.isPrecountEnabled": ("ui", "isPrecountEnabled", []),
    "ui.isLoopRecEnabled": ("ui", "isLoopRecEnabled", []),
    "ui.isStartOnInputEnabled": ("ui", "isStartOnInputEnabled", []),
    "ui.isBrowserAutoHide": ("ui", "isBrowserAutoHide", []),
    "ui.isInPopupMenu": ("ui", "isInPopupMenu", []),
    "ui.isClosing": ("ui", "isClosing", []),
    "ui.showNotification": ("ui", "showNotification", [("message", "str")]),

    # ============================= ARRANGEMENT =============================
    "arrangement.selectionSet": ("arrangement", "selectionSet", [("start", "int"), ("end", "int")]),
    "arrangement.selectionClear": ("arrangement", "selectionClear", []),
    "arrangement.selectionIsActive": ("arrangement", "selectionIsActive", []),
    "arrangement.selectionStart": ("arrangement", "selectionStart", []),
    "arrangement.selectionEnd": ("arrangement", "selectionEnd", []),
    "arrangement.currentTime": ("arrangement", "currentTime", []),
    "arrangement.currentTimeHint": ("arrangement", "currentTimeHint", []),
    "arrangement.liveSelection": ("arrangement", "liveSelection", []),
    "arrangement.liveSelectionStart": ("arrangement", "liveSelectionStart", []),
    "arrangement.addAutoTimeMarker": ("arrangement", "addAutoTimeMarker", [("name", "str")]),
    "arrangement.getMarkerName": ("arrangement", "getMarkerName", [("index", "int")]),
    "arrangement.jumpToMarker": ("arrangement", "jumpToMarker", [("index", "int")]),

    # ============================= DEVICE =============================
    "device.getName": ("device", "getName", []),
    "device.getDeviceID": ("device", "getDeviceID", []),
    "device.isAssigned": ("device", "isAssigned", []),
    "device.isDoubleClick": ("device", "isDoubleClick", []),
    "device.isMidiOutAssigned": ("device", "isMidiOutAssigned", []),
    "device.getPortNumber": ("device", "getPortNumber", []),
    "device.getMasterSync": ("device", "getMasterSync", []),
    "device.setMasterSync": ("device", "setMasterSync", [("enabled", "bool")]),
    "device.directFeedback": ("device", "directFeedback", [("state", "int")]),
    "device.setHasMeters": ("device", "setHasMeters", [("hasMeters", "bool")]),
    "device.fullRefresh": ("device", "fullRefresh", []),
    "device.createRefreshThread": ("device", "createRefreshThread", []),
    "device.destroyRefreshThread": ("device", "destroyRefreshThread", []),
    "device.getIdleElapsed": ("device", "getIdleElapsed", []),
    "device.linkToLastTweaked": ("device", "linkToLastTweaked", []),
    "device.getLinkedChannel": ("device", "getLinkedChannel", []),
    "device.getLinkedInfo": ("device", "getLinkedInfo", []),
    "device.getLinkedValue": ("device", "getLinkedValue", []),
    "device.getLinkedValueString": ("device", "getLinkedValueString", []),
    "device.getLinkedParamName": ("device", "getLinkedParamName", []),
    "device.findEventID": ("device", "findEventID", [("hint", "str")]),
    "device.baseTrackSelect": ("device", "baseTrackSelect", [("track", "int")]),
    "device.hardwareRefreshMixerTrack": ("device", "hardwareRefreshMixerTrack", [("track", "int")]),
    "device.flrMidiCC": ("device", "flrMidiCC", [("event", "int"), ("value", "int"), ("flags", "int")]),
    "device.flrMidiNote": ("device", "flrMidiNote", [("event", "int"), ("value", "int"), ("flags", "int")]),
    "device.forwardMIDICC": ("device", "forwardMIDICC", [("event", "int"), ("value", "int"), ("flags", "int")]),
    "device.processMIDICC": ("device", "processMIDICC", [("event", "int"), ("value", "int"), ("flags", "int")]),
    "device.releaseCC": ("device", "releaseCC", [("event", "int")]),
    "device.repeatMidiEvent": ("device", "repeatMidiEvent", [("type", "int"), ("status", "int"), ("data1", "int"), ("data2", "int")]),
    "device.stopRepeatMidiEvent": ("device", "stopRepeatMidiEvent", []),
    "device.midiOutMsg": ("device", "midiOutMsg", [("status", "int"), ("data1", "int"), ("data2", "int")]),
    "device.midiOutNewMsg": ("device", "midiOutNewMsg", [("status", "int"), ("data1", "int"), ("data2", "int")]),
    "device.midiOutSysex": ("device", "midiOutSysex", [("sysex", "sysex")]),
    "device.sendMsgGeneric": ("device", "sendMsgGeneric", [("info", "int")]),
    "device.dispatch": ("device", "dispatch", [("event", "int"), ("data1", "int"), ("data2", "int")]),
    "device.dispatchReceiverCount": ("device", "dispatchReceiverCount", []),
    "device.dispatchGetReceiverPortNumber": ("device", "dispatchGetReceiverPortNumber", [("receiverIndex", "int")]),

    # ============================= PLUGINS =============================
    "plugins.getParamCount": ("plugins", "getParamCount", [("index", "int"), ("slotIndex", "int")]),
    "plugins.getParamName": ("plugins", "getParamName", [("paramIndex", "int"), ("index", "int"), ("slotIndex", "int")]),
    "plugins.getParamValue": ("plugins", "getParamValue", [("paramIndex", "int"), ("index", "int"), ("slotIndex", "int")]),
    "plugins.getParamValueString": ("plugins", "getParamValueString", [("paramIndex", "int"), ("index", "int"), ("slotIndex", "int")]),
    "plugins.setParamValue": ("plugins", "setParamValue", [("value", "float"), ("paramIndex", "int"), ("index", "int"), ("slotIndex", "int")]),
    "plugins.getPresetCount": ("plugins", "getPresetCount", [("index", "int"), ("slotIndex", "int")]),
    "plugins.nextPreset": ("plugins", "nextPreset", [("index", "int"), ("slotIndex", "int")]),
    "plugins.prevPreset": ("plugins", "prevPreset", [("index", "int"), ("slotIndex", "int")]),
    "plugins.isValid": ("plugins", "isValid", [("index", "int"), ("slotIndex", "int")]),
    "plugins.getName": ("plugins", "getName", [("index", "int"), ("slotIndex", "int")]),
    "plugins.getPluginName": ("plugins", "getPluginName", [("index", "int"), ("slotIndex", "int")]),
    "plugins.getColor": ("plugins", "getColor", [("index", "int"), ("slotIndex", "int")]),
    "plugins.getPadInfo": ("plugins", "getPadInfo", [("chanIndex", "int"), ("slotIndex", "int"), ("paramOption", "int"), ("paramIndex", "int")]),
}


def handle_generic_command(action: str, params: dict):
    """Execute ANY action defined in GENERIC_COMMANDS.

    Returns None if the action is not in the table (falls through to error).
    """
    entry = GENERIC_COMMANDS.get(action)
    if entry is None:
        # support 'get' alias: prefix "get." -> strip
        return None
    module_name, fn_name, arg_spec = entry
    mod = _RAW_MODULES.get(module_name)
    if mod is None:
        return {"error": f"Module '{module_name}' not available"}
    fn = getattr(mod, fn_name, None)
    if fn is None:
        return {"error": f"Function '{module_name}.{fn_name}' not available"}
    args = []
    try:
        for param, kind in arg_spec:
            args.append(_convert_arg(param, kind, params))
    except (KeyError, TypeError, ValueError) as e:
        return {"error": f"{action}: missing/invalid argument '{param}' ({e})",
                "expected": [p for p, _ in arg_spec]}
    try:
        result = fn(*args)
    except Exception as e:
        return {"error": f"{action}({args}) failed: {e}"}
    if fn_name.startswith("get") or fn_name in (
        "trackCount", "channelCount", "channelNumber", "patternCount",
        "patternNumber", "patternMax", "selectedChannel", "isPlaying",
        "isRecording", "selectionIsActive", "currentTime", "liveSelection",
        "dispatchReceiverCount", "getIdleElapsed", "safeToEdit",
        "isClosing", "getVersion", "isAssigned", "isDoubleClick",
        "isMidiOutAssigned", "getMasterSync", "getLinkedChannel",
        "getLinkedInfo", "getLinkedValue", "getLinkedParamName",
        "isGraphEditorVisible", "isBrowserAutoHide", "isInPopupMenu",
        "isPrecountEnabled", "isMetronomeEnabled", "isLoopRecEnabled",
        "isStartOnInputEnabled", "isChannelHighLighted", "isGridBitAssigned",
        "isHighLighted", "getChangedFlag", "getUseMetronome", "getPrecount",
    ):
        return {"value": _serialize(result), "fn": fn_name, "args": args}
    return {"ok": True, "fn": fn_name, "args": args, "result": _serialize(result)}