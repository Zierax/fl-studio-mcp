# Troubleshooting

The failure modes below are the ones that actually happen. Read the "usual
cause" first; 90% of the time it is one of these three:

1. **The port is not enabled** in FL Studio MIDI settings,
2. **The controller type is not selected**,
3. **FL Studio is not running** while the client calls `fl_connect`.

Start with `fl_diagnostics` — it reports the MIDI port, the command folder
and the FL Studio API version in one shot.

---

## `ModuleNotFoundError: No module named 'json'`

FL Studio embeds a **stripped** CPython interpreter. On FL Studio 21 the
bundled `Shared/Python/Lib` folder only contains `midi.py` and `utils.py`, so
the standard library is simply not there:

```
ModuleNotFoundError: No module named 'json'
ModuleNotFoundError: No module named 'os'
ModuleNotFoundError: No module named 'importlib.util'
```

**This is not a configuration problem and there is no workaround to install** —
you cannot make the standard library appear inside FL Studio.

The controller script solves it instead: it is written against **builtins
only**. The JSON codec, the path helpers and the module probing are
implemented in the script itself, so it initialises on FL Studio 21 just as
well as on FL Studio 2025. Nothing has to be installed.

If you still see this error, an **old copy of the script** is running:

1. Check **View → Script output**: the banner must say `MCP_VERSION: 4`.
   Versions 2 and older imported `json` and fail on FL Studio 21.
2. Copy the current `fl_controller/device_FLStudioMCP.py` over the one in
   `Settings/Hardware/FLStudioMCP/`.
3. Press **Options → Update MIDI scripts** (or restart FL Studio).

To confirm what the running script can import, call `fl_diagnostics` — its
`fl_studio.importable` map lists exactly which modules are available, and
`fl_studio.builtin_modules` lists everything the interpreter ships.

## Tools time out ("no response", "timeout")

The server waits for `mcp_response.json` after triggering MIDI note 127.

**Usual causes, in order:**

| Check | How | Fix |
|-------|-----|-----|
| FL Studio running? | Is the project open? | Start FL Studio. |
| Port enabled? | **Options → MIDI Settings → Input**: your port must be listed and its power icon highlighted. | Enable the port. |
| Controller type set? | Same window, `Controller type` column. | Select `FL Studio MCP Controller`. |
| Wrong port chosen? | `fl_connection_status` shows which port the server is on. | `fl_connect(port_name="FLStudioMCP 1")` — match the exact name. |
| LoopMIDI running? | loopMIDI must be open with the port created. | Open loopMIDI, create/add the port. |
| Script errored? | **View → Script output** in FL Studio. | Look for tracebacks; fix and press **Options → Update MIDI scripts**. |
| Stale response? | `mcp_response.json` may exist from a crash. | Delete it (the server does this per-command anyway). |

## The server picked the wrong MIDI port

Symptoms: the server reports `Microsoft GS Wavetable Synth 0` (or another
instrument) as its port, and every call times out.

The server scores the available ports and prefers the ones named after the
bridge (`FLStudioMCP`, `FL Studio MCP`), while known software synths are
penalised. When nothing matches, the first port is used as a last resort and
`fl_connection_status` reports `"port_is_guess": true`.

Fix it by naming the port explicitly:

```
fl_connect(port_name="FLStudioMCP 1")
```

The exact name is the one shown in **Options → MIDI Settings → Input**.

## The server and FL Studio use different folders

Symptoms: the server reports `Command file: ...` in one folder while FL Studio
writes its response somewhere else, and commands time out.

This usually happens when FL Studio's user data folder was moved (or
redirected into OneDrive/iCloud), because the server computes
`~/Documents/Image-Line/...` while FL Studio may use
`~/OneDrive/Documents/Image-Line/...`.

The server already searches the cloud-redirected locations, but you can be
explicit — either of these works:

- Set the environment variable for the MCP server process:
  ```
  FL_STUDIO_MCP_DIR=/path/to/Settings/Hardware/FLStudioMCP
  ```
  (on Windows: `set FL_STUDIO_MCP_DIR=D:\...\Hardware\FLStudioMCP`)

- Or pass it at runtime:
  ```
  fl_connect(data_dir="/path/to/Settings/Hardware/FLStudioMCP")
  ```

`fl_diagnostics` lists every candidate folder the server considered under
`server.hardware_dir_candidates`.

## "Could not open MIDI port" on startup / `fl_connect` fails

- loopMIDI port does not exist → create it in loopMIDI.
- Port name mismatch → pass the exact name: `fl_connect("FLStudioMCP 1")`.
- Another app (or a stuck server process) already holds the port → close
  other FL Studio MCP instances and retry.

## FL Studio does not react to midi tools but transport works

The transport buttons are real MIDI; the rest depends on JSON+MIDI both
working. If only some tools fail, check the **Script output** pane:
`Command file: ...` printed at init? If not, the script did not load.

## Changes to the controller script are ignored

The script hot-reloads only when the version marker changed:

```
MCP_VERSION = 4
```

If you edit the file but reuse the same version number, FL Studio keeps the
old code. Bump `MCP_VERSION`, then just trigger any command (or wait a
second) — see [DEVELOPMENT.md](DEVELOPMENT.md).

## Notes trigger but nothing audible / no state change

- Live trigger notes (`fl_trigger_note`) are **not persisted** — they only
  preview. Use step-sequencer or piano-roll tools for written music.
- The channel may be muted, or routed nowhere. Check
  `fl_get_channel_info(index)`.

## Values come back as `None` or empty

- The function may not exist in your FL Studio version (API grew over time) —
  use `fl_api_list_functions(module, prefix)` to check what's available.
- Some FL API functions return nothing by design when audio isn't rendering.

## Python version errors

- Ensure Python ≥ 3.10; `pyproject.toml` requires it.
- If `uv` fails to resolve, run `uv sync` with network access once.

## macOS specifics

- IAC Driver must be **online**: Audio MIDI Setup → IAC Driver → checkbox.
- Permissions: the terminal hosting the server may need microphone/input
  permissions granted once.

## Still stuck?

Use these probes to figure out where it breaks:

1. `fl_diagnostics` → MIDI port, command folder, FL API version, what the
   controller can import.
2. `fl_connection_status` → is the server connected, and on which port?
3. `fl_general_info` → does the bridge round-trip?
4. `fl_api_list_functions("channels", "get")` → does raw access work?
5. Check `Script output` in FL Studio for the controller's prints/errors.
6. Manual test: run `uv run fl-studio-mcp` and watch the command files
   `mcp_command.json` / `mcp_response.json` appear and update in
   `Settings/Hardware/FLStudioMCP/`.
