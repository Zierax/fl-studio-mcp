# Architecture

FL Studio is a closed desktop app — its only scripting path is its own
MIDI-controller Python API, which runs *inside* the DAW. This project bridges
the gap with a two-process design.

## Overview

```
+-------------+   stdio (JSON-RPC)   +--------------------+   files + MIDI   +-----------------------+
| MCP client  | <------------------> | FastMCP server     |  mcp_command.json   | FL Studio          |
| (Claude,    |                       | (Python, the 165 |  + note 127         | controller script  |
|  Cursor,    |                       |  tools)            | -----------------> | device_FLStudioMCP |
|  ...)       |                       |                    |  mcp_response.json  | (runs in FL Studio)|
+-------------+                       +--------------------+ <----------------- +-----------------------+
```

## The two halves

### 1. The MCP server (this repository's Python)

- Entry point: `src/fl_studio_mcp/server.py` (FastMCP over stdio).
- Tools are grouped in `src/fl_studio_mcp/tools/` and register into the server
  at startup (`register_*_tools` in `tools/__init__.py`).
- To talk to FL Studio it:
  1. Writes the command as JSON to `mcp_command.json` in FL's
     `Settings/Hardware/FLStudioMCP/` folder. The write is **atomic** (temp
     file + rename), so the controller never reads a half-written file.
     The response file is **truncated in place, not deleted**, because
     FL Studio's older interpreters can write to an existing file but
     cannot create a new one.
  2. Sends a MIDI **note-on 127** on the connected virtual port — this is the
     "doorbell" that makes the controller read the file.
  3. Waits (configurable timeout, default 2 s) for the response on either
     of the two channels described below.
- MIDI plumbing lives in `src/fl_studio_mcp/utils/`:
  - `midi_connection.py` — the JSON round-trip (`send_command`) and the
    connection state.
  - `ports.py` — scores the available MIDI ports and picks the one that looks
    like the bridge (see [Port selection](#port-selection)).
  - `paths.py` — resolves FL Studio's `Hardware/FLStudioMCP/` folder, including
    cloud-redirected user data folders.
  - `connection.py` — the public wrapper the tools use.

### 2. The controller script (lives *inside* FL Studio)

`fl_controller/device_FLStudioMCP.py` is a standard FL Studio MIDI controller
script. It must be copied to:

```
%USERPROFILE%\Documents\Image-Line\FL Studio\Settings\Hardware\FLStudioMCP\
```

Its loop is `OnMidiMsg()` → if the incoming message is **note 127** →
`execute_pending_command()`:

1. Read `mcp_command.json`.
2. Dispatch on `action`:
   - `raw.call` / `raw.list` / `raw.consts` — universal passthrough to any
     function/constant of FL's API modules (`channels`, `mixer`, `transport`,
     `patterns`, `playlist`, `general`, `ui`, `arrangement`, `plugins`,
     `device`, `midi`).
   - `transport.*`, `mixer.*`, `channels.*`, ... — high-level action handlers
     that use those raw calls under the hood (e.g. `channels.getAll`,
     `mixer.getAllTracks`).
   - `system.*` — introspection: which modules exist, the full callable
     surface, constants and the runtime diagnostics.
3. Write the result (serialized) to `mcp_response.json`.

So the "raw" tools (`fl_raw_command`, `fl_api_list_functions`,
`fl_api_list_constants`) are just thin client-side wrappers over the same
passthrough — whatever FL exposes, the client can reach.

## The controller runs on a stripped interpreter

FL Studio does not embed a normal Python installation. It ships a cut-down
CPython 3.9 whose standard library is largely missing — on FL Studio 21 the
bundled `Shared/Python/Lib` folder contains nothing but `midi.py` and
`utils.py`. `import json`, `import os`, `import pathlib` and `import
importlib` all fail there, which used to abort the controller during
initialisation.

The controller therefore uses **builtins only**:

| Need | Without the standard library |
|------|------------------------------|
| JSON | `_json_dumps` / `_json_loads` — a self-contained codec whose output is byte-identical to `json.dumps(..., indent=2)` |
| Paths | string helpers (`_join_path`, `_path_name`, `_file_exists`, `_read_text`, `_write_text`) |
| Locating the hardware folder | `sys.path` — FL Studio puts the controller folder on it, so the script can find its own `mcp_command.json` without `os` |
| Module discovery | the `__import__` builtin instead of `importlib` |

The only imports are `sys`, `_io`, `time` (all compiled into the interpreter)
and the FL Studio API modules. `tests/test_device_script.py` enforces this
by loading the script with the missing modules blocked.

File access has a second, independent restriction: **FL Studio's scripting
interpreter has a read-only filesystem in the older builds** (confirmed on
FL Studio 21.0.3). `open()` is not even exposed in `builtins`; `_io.open()`
can read but raises `RuntimeError: File access disabled` for write modes.
This is a deliberate sandbox (PEP 578 audit events) and cannot be turned off
from inside FL Studio.

## The two response channels

Because the response file may be unwritable, the controller has two ways
to send a response back and the server accepts whichever arrives first:

| Channel | When it is used | Path |
|---------|-----------------|------|
| **Response file** | Whenever the build permits writing (`wb` first, then `r+b` into the pre-created file) | `mcp_response.json` |
| **MIDI out** | Whenever a file write fails | `device.midiOutSysex()` to the output port linked to the controller |

The MIDI channel is not a hack — it is the mechanism Image-Line documents
for controllers that send data back to the host, and it is what the
original [flapi](https://maddyguthridge.com/portfolio/projects/flapi)
project used.  Responses are encoded as ASCII (the JSON codec escapes
everything above `0x7E`, keeping every byte inside the 7-bit MIDI range)
and split into system exclusive messages of at most 700 payload bytes,
because the Windows MIDI API refuses larger buffers.

The server opens an input port with the same name as its output port,
reassembles the chunks and correlates them with the request id.  This
requires the controller to have an **output port** assigned in FL Studio
MIDI Settings (set it to the same port number as the input port).

`fl_diagnostics()` reports `file_access`, `midi_out_assigned` and
`response_channel` so the active channel is never a guess.  The controller
also prints the result of a file-access probe to the Script output at
startup.

## Port selection

Choosing "the first MIDI output port" reliably picks a software synth
(`Microsoft GS Wavetable Synth 0`, ...) instead of the virtual port FL Studio
listens on, and every call then times out.

`utils/ports.py` normalises the port names (`"FL Studio MCP 1"` and
`"FLStudioMCP 1"` both become `flstudiomcp1`) and scores them:

- a port named after the bridge wins (score +100),
- any other MCP-ish port comes next (+40),
- virtual MIDI drivers score +10,
- known software synths are penalised (-50).

If nothing scores above zero the first port is used, but the status reports
`port_is_guess: true` so the problem stays visible. `fl_connect(port_name=...)`
always wins over the automatic choice.

## Folder resolution

Both halves have to agree on where `mcp_command.json` lives. The server
resolves the folder itself (`utils/paths.py`): the documented
`~/Documents/Image-Line/FL Studio/Settings/Hardware/FLStudioMCP`, the
OneDrive/iCloud redirected variants, and finally the `FL_STUDIO_MCP_DIR`
environment variable — which always wins.

The controller resolves it from `sys.path`, i.e. from the folder FL Studio
actually loaded the script from. `COMMAND_DIR_OVERRIDE` at the top of the
script is the manual escape hatch.

## Hot reload

The controller re-reads its own file once per second (`OnIdle()` →
`_check_hot_reload()`). If the `MCP_VERSION = N` marker at the top of the file
changed, it re-compiles and re-executes itself. This means:

- You can edit `fl_controller/device_FLStudioMCP.py` in the repo and copy it
  over — **no "Update MIDI scripts" needed**, no FL restart.
- Version bumps must be *unique-ish and monotonic* — reuse a previous number
  and FL will think nothing changed. See
  [DEVELOPMENT.md](DEVELOPMENT.md) for the release process.

## Message flow example

```
client: fl_set_tempo(bpm=140)
server: {"action": "tempo.set", "params": {"bpm": 140.0}}
        → write mcp_command.json (atomically)
        → MIDI note 127 on port "FLStudioMCP 1"
FL:     OnMidiMsg → execute_pending_command → mixer.setCurrentTempo(...)
        → write mcp_response.json {"success": true, ...}
server: reads response → returns to client
```

## Failure semantics

- **Timeout**: no `mcp_response.json` within the deadline → the tool returns
  an error that names the MIDI port and the command folder. Usual causes: FL
  not running, port not enabled, controller type not selected, or the script
  errored (check **Script output**).
- **Stale response**: the server deletes `mcp_response.json` before each
  trigger so an old file can never be mistaken for a fresh answer.
- **Partial response**: the controller writes the response in a single write;
  if the server still catches it mid-write it retries until the timeout.
- **Serialization**: results are wrapped as `{"value": ...}` or
  `{"success": true, ...}`; lists/bytes are converted to JSON-safe forms.

## Port names

loopMIDI creates `FLStudioMCP 0`, `FLStudioMCP 1`, ... — the server scores
them automatically and prefers the ones named after the bridge.
`fl_connect(port_name=...)` can force a specific port.
