# Architecture

> This document describes how FL Studio MCP actually works internally: the
> two communication channels, the message protocol, and the key files.

## High-Level Overview

The MCP server needs to run commands *inside* FL Studio. FL Studio does not
expose a public automation/network API, but it does run **MIDI controller
scripts** written in its internal Python (the `midi` module). The project
leverages a controller script named **FL Studio MCP Controller**
(`device_FLStudioMCP.py`) installed in FL Studio's Hardware folder.

The server talks to that script through two independent channels:

```
+-------------------+                      +---------------------------+
|   MCP Client      |   stdio (JSON-RPC)   |      MCP Server           |
|  Claude Desktop,  | <------------------->|  FastMCP (Python)         |
|  Claude Code,     |                      |  server.py                |
|  Cursor, ...      |                      |                           |
+-------------------+                      |  +--------------------+   |
                                           |  | tools/             |   |
                                           |  | transport.py       |   |
                                           |  | mixer.py           |   |
                                           |  | channels.py        |   |
                                           |  | patterns.py        |   |
                                           |  | sequencer.py       |   |
                                           |  | plugins.py         |   |
                                           |  | piano_roll.py      |   |
                                           |  +----------+---------+   |
                                           |             |             |
                                           |  +----------+---------+   |
                                           |  | utils/             |   |
                                           |  | midi_connection.py |   |
                                           |  | connection.py      |   |
                                           |  | fl_trigger.py      |   |
                                           |  +--------------------+   |
                                           +-------------+-------------+
                                                         |
          Channel A (MIDI + JSON)                 Channel B (Piano Roll)
                                                         |
                     +---------------------+    +--------+--------+
                     |  virtual MIDI port  |    |  JSON request   |
                     |  (loopMIDI / IAC)   |    |  file + hotkey  |
                     +----------+----------+    +--------+--------+
                                |                          |
                     +----------v----------+    +----------v----------+
                     |   FL Studio         |    |   FL Studio         |
                     |  MIDI controller    |    |  Piano Roll script  |
                     |  script             |    |  (ComposeWithLLM)   |
                     |  FLStudioMCP        |    |                     |
                     +---------------------+    +---------------------+
```

- **Channel A (MIDI + JSON)** - all transport, mixer, channel, plugin,
  pattern, and step-sequencer actions.
- **Channel B (Piano Roll)** - persistent note/piano-roll edits, using the
  Piano Roll scripting API.

## Channel A - MIDI + JSON Command Protocol

Files exchanged (inside the FL Studio hardware scripts folder):

| File                      | Writer          | Reader          | Purpose              |
|---------------------------|-----------------|-----------------|----------------------|
| `mcp_command.json`        | MCP server      | controller      | Command + params     |
| `mcp_response.json`       | controller      | MCP server      | Command result       |

Sequence for every command (implemented in
`src/fl_studio_mcp/utils/midi_connection.py`):

1. Ensure an output MIDI port is open. Port selection order:
   1. First port whose name contains `FLStudioMCP`
   2. Else first port whose name contains `loopMIDI`
   3. Else the first available output port
2. Write the command to `mcp_command.json`:

   ```json
   {
     "action": "transport.start",
     "params": {}
   }
   ```

   Every action has the form `category.verb`, e.g. `mixer.setTrackVolume`,
   `patterns.create`, `channels.setSteps`.
3. Delete any stale `mcp_response.json`.
4. Send a MIDI `note_on` message with **note = 127, velocity = 127** on the
   output port.
5. Poll for `mcp_response.json` every 50 ms until it appears (default
   timeout: 2-5 s), parse it, delete it, and return the result:

   ```json
   {
     "success": true,
     "is_playing": false
   }
   ```

6. If no response arrives in time, return
   `{"success": false, "error": "Timeout waiting for FL Studio response..."}`.

### Controller Script (`fl_controller/device_FLStudioMCP.py`)

Installed at:

```
<FL Studio>/Settings/Hardware/FLStudioMCP/device_FLStudioMCP.py
```

Handles `OnMidiMsg()`: any `note_on` with note 127 is treated as the trigger;
it then reads `mcp_command.json`, dispatches the `action` string through a
handler table, and writes the result to `mcp_response.json`.

Supported action categories (see [TOOLS.md](TOOLS.md) for the exact mapping):

| Category  | Actions                                                              |
|-----------|----------------------------------------------------------------------|
| transport | start, stop, record, getStatus, setPosition, getLength, setLoopMode, |
|           | setPlaybackSpeed, getTempo, setTempo, getShuffle                     |
| patterns  | count, list, get, create, select, rename, clone, duplicate, clear,   |
|           | setLength, move                                                      |
| mixer     | getTrackCount, getTrackInfo, getAllTracks, setTrackVolume,           |
|           | setTrackPan, muteTrack, soloTrack, armTrack, setTrackName,           |
|           | setTrackColor, setStereoSep                                          |
| channels  | getCount, getInfo, getAll, getSelected, select, selectOne,           |
|           | triggerNote, setVolume, setPan, mute, solo, setName, setColor,       |
|           | routeToMixer, getType, setPitch, getSteps, setSteps, clearSteps,     |
|           | getGridBit, setGridBit, getStepSequence, setStepSequence             |
| plugins   | isValid, getName, getParamCount, getParams, getParamValue,           |
|           | setParamValue, getPresetCount, nextPreset, prevPreset, getColor      |

The header of the script matters; a mismatch between the device's folder name
and `# supportedDevices` makes FL Studio refuse to load it (load -> unload
loops). Required header:

```python
# name=FL Studio MCP Controller
# supportedDevices=FLStudioMCP
```

`supportedDevices` must exactly match the device name registered for the
virtual MIDI port in FL Studio's MIDI Settings.

### MIDI Ports

- The server opens an **output** port. With loopMIDI, one pair of in/out
  ports is created ("FLStudioMCP 1" and "FLStudioMCP 2"); the server holds
  the output end and FL Studio reads the input end.
- FL Studio's MIDI Settings must have the corresponding **Input** port
  enabled and assigned **Controller type = FL Studio MCP Controller**
  (alternatively, type `FLStudioMCP` when selecting from the list).

## Channel B - Piano Roll (JSON + Hotkey)

The Piano Roll scripting API runs in FL Studio's *Piano roll scripts* folder
via `ComposeWithLLM.pyscript` (bound to `Ctrl+Alt+Y` / `Cmd+Opt+Y`). The MCP
server cannot call this API directly, so it:

1. Appends requests to `<Settings>/Piano roll scripts/mcp_request.json`.
2. Sends the hotkey (`fl_trigger.py` foregrounds the FL Studio window on
   Windows, then uses `pynput` to press `Ctrl+Alt+Y`).
3. The script reads the requests, edits notes, and exports state to
   `piano_roll_state.json`.

Because this path uses a global hotkey, FL Studio briefly comes to the
foreground on Windows whenever a piano-roll tool runs.

## Connection Lifecycle

- `FLConnection` (in `utils/connection.py`) wraps a module-level
  `MIDIConnection` singleton.
- The connection is **lazy**: the first tool call triggers a connect.
- `fl_connect` calls `reset_connection()` to force a fresh attempt, and
  `fl_connection_status` reports the port in use and every port it found.

## File Layout

```
FL-MCP/
+-- fl_controller/
|   +-- device_FLStudioMCP.py         # MIDI controller script (in FL Studio)
+-- scripts/
|   +-- ComposeWithLLM.pyscript       # Piano Roll script (in FL Studio)
|   +-- ControlPlane.pyscript         # Control Plane script (in FL Studio)
|   +-- setup.sh                      # script installer (macOS/Linux)
|   +-- install_mcp_for_claude.sh     # Claude config installer (macOS/Linux)
|   +-- install_mcp_for_claude.ps1    # Claude config installer (Windows)
+-- src/fl_studio_mcp/
|   +-- server.py                     # FastMCP entry point
|   +-- tools/
|   |   +-- transport.py              # transport tools (+ tempo/shuffle)
|   |   +-- mixer.py                  # mixer tools
|   |   +-- channels.py               # channel rack tools (+ type/pitch)
|   |   +-- patterns.py               # pattern lifecycle tools
|   |   +-- sequencer.py              # step-sequencer composition tools
|   |   +-- plugins.py                # plugin parameter tools
|   |   +-- piano_roll.py             # piano-roll tools (hotkey channel)
|   +-- utils/
|       +-- connection.py             # FLConnection wrapper
|       +-- midi_connection.py        # MIDI + JSON transport
|       +-- fl_trigger.py             # hotkey trigger (macOS/Windows)
+-- install.sh / install.ps1          # one-command installers
+-- pyproject.toml                    # uv/pip project definition
+-- README.md                         # project index
+-- docs/                             # this documentation set
```