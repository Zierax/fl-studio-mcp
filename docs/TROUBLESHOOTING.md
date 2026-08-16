# Troubleshooting

Common problems, in rough order of how often they bite.

---

## 1. "Unknown action" errors

**Symptom:** calling e.g. `fl_set_tempo` returns `Unknown action: ...`,
or all the new pattern/sequencer tools fail while old ones work.

**Cause:** FL Studio is running an **old version of the controller script**.
MIDI scripts are loaded into memory; files copied to the Hardware folder
are not re-read automatically.

**Fix:**

1. In FL Studio: **Options > MIDI Settings**.
2. Click **Update MIDI scripts** (or restart FL Studio entirely, which
   reloads everything).
3. Retry the tool call.

---

## 2. "Timeout waiting for FL Studio response"

**Symptom:** commands time out after 2-5 s, `mcp_response.json` never
appears.

**Possible causes, in order:**

1. **The controller is not loaded** - FL Studio did not load
   `device_FLStudioMCP.py`.
   - Check **View > Script output**: a failing header shows load/unload
     errors.
   - The file must sit in
     `<Documents>\Image-Line\FL Studio\Settings\Hardware\FLStudioMCP\`
     and its header must match:
     `# name=FL Studio MCP Controller` / `# supportedDevices=FLStudioMCP`.
   - Use **Update MIDI scripts** or restart FL Studio after changing it.
2. **The MIDI port is misconfigured.**
   - The server opens an **output** port whose name contains `FLStudioMCP`
     (fallback `loopMIDI`, then any port).
   - FL Studio needs an **Input** port enabled and set to controller type
     **FL Studio MCP Controller**, port enabled (highlighted).
   - If both `FLStudioMCP 1` and a plain `loopMIDI` input appear, leave the
     plain `loopMIDI` entry as `(generic controller)`.
3. **loopMIDI is not running** (Windows) / **IAC Driver disabled** (macOS).
4. **Two controller scripts racing**: an old copy of the script elsewhere
   in the Hardware folder with the same device name.

**Diagnosis steps:**

- `fl_connection_status()` - shows `port_name` and `available_ports`.
- In loopMIDI: enable **"Log incoming"** / monitor and confirm the trigger
  note (note 127) arrives after a tool call.
- In FL Studio **Script output**: a healthy controller receives `OnMidiMsg`
  with note 127 (if debug logging is enabled in the script).

---

## 3. Controller loads and immediately unloads (load -> unload loops)

**Cause:** device-name mismatch. FL Studio matches the folder/device name
against `# supportedDevices` in the script header, and to the controller
selection in MIDI Settings.

**Fixes:**

- The Hardware subfolder is `FLStudioMCP` and the header must say
  `# supportedDevices=FLStudioMCP` (exactly, no extra spaces).
- In MIDI Settings the controller type selected for the port must be
  **FL Studio MCP Controller** (the `# name=` value).
- A script whose header is unparsable (e.g. non-ASCII characters in the
  `# name=` line) gets rejected silently - keep headers ASCII.

---

## 4. "No MIDI output ports found" / `fl_connection_status` shows no ports

- **Windows:** install and run loopMIDI; create at least one port.
- **macOS:** enable the IAC Driver - Audio MIDI Setup > IAC Driver >
  "Device is online".
- If ports exist but the server picks a wrong one, name them so they
  contain `FLStudioMCP` - the server prefers that token.

---

## 5. Piano Roll script not triggering

1. First time only: run **Tools > Scripting > ComposeWithLLM** once in FL
   Studio so FL Studio registers the script and its hotkey.
2. **macOS:** grant Accessibility permissions when prompted.
3. **Windows:** the server foregrounds the FL Studio window before pressing
   `Ctrl+Alt+Y`. If FL Studio is minimized to the system tray or not
   running, the trigger cannot find the window and returns a warning -
   press the hotkey manually instead.
4. Confirm the hotkey is actually bound: edit the script header if needed
   (the `# shortName` / assignments) or press `Ctrl+Alt+Y` yourself and
   watch **Script output**.
5. After updating any server code, **fully restart the MCP client**
   (Claude Desktop/Code). Reconnecting the MCP server alone does NOT
   respawn the underlying process - it keeps running stale code.

---

## 6. Stale code after pulling/editing the repo

The MCP client spawns the server process once. After `git pull` or edits:

1. Stop/restart the MCP client, or kill the `fl-studio-mcp` process.
2. Restart FL Studio (controller script).
3. Then retest.

---

## 7. FL Studio pops to the foreground on Windows piano-roll calls

Expected: the trigger path needs FL Studio focused to deliver the hotkey.
If you find it disruptive, set `auto_trigger=False` on the piano-roll tools
and trigger manually with `fl_trigger_script()` or the hotkey.

---

## 8. Errors that are actually FL Studio API limits

| Error / behavior                      | Reality                                        |
|---------------------------------------|------------------------------------------------|
| "Cannot load a plugin"                | API has no `loadPlugin`; add instruments by hand or via the plugin picker. |
| "Cannot create a channel"             | No `createChannel` in the controller API.     |
| "Cannot place clips on the playlist"  | Playlist API is track-level only.              |
| `fl_trigger_note` notes disappear     | Real-time only; record, or use step sequencer / piano-roll tools. |

---

## Appendix - Debug checklist (fastest first)

| Step                              | Tool / place                              |
|-----------------------------------|-------------------------------------------|
| Is loopMIDI/IAC running?          | Task Manager / Audio MIDI Setup           |
| Are MIDI ports visible?           | `fl_connection_status()`                  |
| Is the controller loaded?         | FL Studio MIDI Settings, Script output    |
| Does the trigger note arrive?     | loopMIDI logging                          |
| Does the response file appear?    | `mcp_response.json` in Hardware\FLStudioMCP |
| Restart both sides               | FL Studio + MCP client                    |