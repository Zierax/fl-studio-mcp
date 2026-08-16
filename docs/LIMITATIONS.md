# Limitations

What the FL Studio scripting API does and does not allow, and how this
project works around it. Read this before planning a workflow that depends
on one of these.

TL;DR: you can control and compose on anything that already exists in the
project, but you cannot *create* instruments, and you cannot arrange the
playlist timeline programmatically.

---

## 1. Cannot load new plugins

FL Studio's MIDI/Python scripting API does **not** provide
`plugins.loadPlugin` (or a channel-rack "add instrument" call). This means:

- The MCP server can never add a new VST/AU instrument to your project.
- Every instrument must be added once, by hand (or via sample drag-in) in
  the channel rack before the session starts.

**Workaround:** add the instrument once, save the project, and the server
can then control its parameters
(`fl_get_plugin_params`, `fl_set_plugin_param_value`), switch presets, and
program notes on it (step sequencer / piano roll).

## 2. Cannot create channels

There is no `channels.createChannel` equivalent. New sampler/synth
channels cannot be spawned from the API.

**Workaround:** preload channels in the project template; then the server
can name, route, pitch, mute, solo, and program them.

## 3. Cannot place clips on the playlist

The playlist API is **track-level only**. There is no API to drop a clip
onto the timeline at a position with a length.

**Workaround:** arrange patterns in the playlist manually. The server can
create/rename/select/clear patterns (which then appear in the playlist
panel), control mixer tracks, and set loop mode - but the actual timeline
placement is a manual step.

## 4. Real-time note triggering is not persistent

`fl_trigger_note` sends MIDI notes in real time. They will **not** appear
in the pattern unless FL Studio is recording at that moment.

**To make persistent music you have three supported paths:**

| Path | Tool(s) | Persists? | Best for |
|------|---------|-----------|----------|
| Step sequencer on/off | `fl_set_grid_bit`, `fl_set_step_sequence` | Yes | Drum patterns |
| Step sequencer with pitch/velocity/pan | `fl_set_channel_steps` | Yes | Melodies, grooves, per-step programming |
| Piano roll | `fl_send_notes`, `fl_send_chord` | Yes | Long notes, chords, melodies with durations |

## 5. Piano roll requires the scripting hotkey

Piano-roll edits go through the ComposeWithLLM script triggered by a global
hotkey. On Windows the FL Studio window must be foregroundable, so:

- FL Studio briefly takes focus per piano-roll call.
- If the window cannot be found, the trigger fails and you must press the
  hotkey manually (or call `fl_trigger_script`).

## 6. Controller script must be manually updated

FL Studio caches MIDI controller scripts in memory. After changing
`device_FLStudioMCP.py`, you must click **Update MIDI scripts** in MIDI
Settings (or restart FL Studio). The MCP server cannot reload it for you.

## 7. Platform parity

| Feature                | Windows | macOS |
|------------------------|---------|-------|
| MIDI + JSON channel    | loopMIDI required | IAC Driver |
| Piano-roll auto-trigger | Yes (foregrounds FL Studio) | Yes (osascript/pynput) |
| Linux                  | Not officially supported by FL Studio; MIDI channel falls back to `~/.fl-studio/Settings` | - |

## 8. Timing / latency

- Each MIDI command waits up to 2-5 s for the controller's response
  (50 ms polling). Rapid-fire automation (e.g. per-frame parameter sweeps)
  is not practical - plan for music-event-rate calls, not audio-rate
  automation.
- Piano-roll calls block for ~2 s (the `TRIGGER_DELAY`) after sending the
  hotkey, so the script has time to run.