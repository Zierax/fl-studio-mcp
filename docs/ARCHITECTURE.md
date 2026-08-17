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
     `Settings/Hardware/FLStudioMCP/` folder.
  2. Sends a MIDI **note-on 127** on the connected virtual port — this is the
     "doorbell" that makes the controller read the file.
  3. Waits (configurable timeout, default 2 s) for `mcp_response.json` to
     appear, then returns its contents to the client.
- MIDI plumbing lives in `src/fl_studio_mcp/utils/`:
  - `midi_connection.py` — finds a usable MIDI port (tries a candidate list;
    the first one that answers a ping wins) and exposes `send_trigger()`.
  - `connection.py` — the JSON round-trip (`send_command`) and connection state.

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
     surface, constants.
3. Write the result (serialized) to `mcp_response.json`.

So the "raw" tools (`fl_raw_command`, `fl_api_list_functions`,
`fl_api_list_constants`) are just thin client-side wrappers over the same
passthrough — whatever FL exposes, the client can reach.

## Hot reload

The controller re-reads its own file once per second (`OnIdle()` →
`_check_hot_reload()`). If the `MCP_VERSION = N` marker at the top of the file
changed, it re-compiles and re-executes itself. This means:

- You can edit `fl_controller/device_FLStudioMCP.py` in the repo and copy it
  over — **no "Update MIDI scripts" needed**, no FL restart.
- Version bumps must be *unique-ish and monotonic* — reuse a previous number
  and FL will think nothing changed. See
  [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for the release process.

## Message flow example

```
client: fl_set_tempo(bpm=140)
server: {"action": "tempo.set", "params": {"bpm": 140.0}}
        → write mcp_command.json
        → MIDI note 127 on port "FLStudioMCP 1"
FL:     OnMidiMsg → execute_pending_command → mixer.setCurrentTempo(...)
        → write mcp_response.json {"success": true, ...}
server: reads response → returns to client
```

## Failure semantics

- **Timeout**: no `mcp_response.json` within the deadline → the tool returns
  an error. Usual causes: FL not running, port not enabled, controller type
  not selected, or the script errored (check **Script output**).
- **Stale response**: the server deletes `mcp_response.json` before each
  trigger so an old file can never be mistaken for a fresh answer.
- **Serialization**: results are wrapped as `{"value": ...}` or
  `{"success": true, ...}`; lists/bytes are converted to JSON-safe forms.

## Port names

loopMIDI creates `FLStudioMCP 0`, `FLStudioMCP 1`, ... — the server's default
candidate list tries `FLStudioMCP 1`, `FLStudioMCP 0`, and generic names.
`fl_connect(port_name=...)` can force a specific port.