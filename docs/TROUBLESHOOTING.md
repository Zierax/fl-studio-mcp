# Troubleshooting

The failure modes below are the ones that actually happen. Read the "usual
cause" first; 90% of the time it is one of these three:

1. **The port is not enabled** in FL Studio MIDI settings,
2. **The controller type is not selected**,
3. **FL Studio is not running** while the client calls `fl_connect`.

---

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
MCP_VERSION = 1
```

If you edit the file but reuse the same version number, FL Studio keeps the
old code. Bump `MCP_VERSION`, then just trigger any command (or wait a
second) — see [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

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

1. `fl_connection_status` → is the server connected?
2. `fl_general_info` → does the bridge round-trip?
3. `fl_api_list_functions("channels", "get")` → does raw access work?
4. Check `Script output` in FL Studio for the controller's prints/errors.
5. Manual test: run `uv run fl-studio-mcp` and watch the command files
   `mcp_command.json` / `mcp_response.json` appear and update in
   `Settings/Hardware/FLStudioMCP/`.