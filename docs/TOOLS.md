# Tool Reference

Complete reference for every MCP tool exposed by the FL Studio MCP server.
Tools are grouped by category; the table format is:

`Tool name` - what it does (arguments: `arg = default`)

---

## Connection

| Tool | Description |
|------|-------------|
| `fl_connect()` | Force a fresh connection attempt to FL Studio via MIDI. Call after starting FL Studio or if the connection was lost. |
| `fl_connection_status()` | Report connection state: `connected`, `port_name`, `available_ports`, `error`. Actively attempts a connection. |

---

## Transport

| Tool | Description |
|------|-------------|
| `fl_play()` | Toggle play/pause. |
| `fl_stop()` | Stop playback and reset position. |
| `fl_record()` | Toggle recording. |
| `fl_get_transport_status()` | Returns `is_playing`, `is_recording`, `position`, `loop_mode`. |
| `fl_set_song_position(position: float, mode: int = 2)` | Seek. `mode`: 0 = percent (0-1), 1 = ms, 2 = seconds, 3 = ticks, 4 = bars:steps:ticks. |
| `fl_get_song_length()` | Returns `ticks`, `seconds`, `milliseconds`. |
| `fl_set_loop_mode(mode: str)` | `"pattern"` or `"song"`. |
| `fl_set_playback_speed(speed: float)` | 0.25x - 4.0x. |
| `fl_set_tempo(bpm: float)` | Set project tempo, 20-999 BPM (e.g. 140 for trap). |
| `fl_get_tempo()` | Returns `tempo` (float BPM). |
| `fl_get_shuffle()` | Returns `shuffle` (0-100 swing %). |

---

## Patterns

| Tool | Description |
|------|-------------|
| `fl_get_pattern_count()` | Returns `count`, `max`, `active`. |
| `fl_list_patterns()` | All patterns with `index`, `name`, `length_beats`, `color`, `is_active`. |
| `fl_get_pattern(index: int = -1)` | Pattern details; `-1` = active pattern. |
| `fl_create_pattern(name: str = "")` | Create a pattern in the first free slot and make it active. |
| `fl_select_pattern(index: int)` | Make a pattern active. |
| `fl_rename_pattern(name: str, index: int = -1)` | Rename (default active pattern). |
| `fl_clone_pattern(index: int = -1)` | Copy a pattern to a new one. |
| `fl_clear_pattern(index: int = -1)` | Clear all data in a pattern. |
| `fl_set_pattern_length(length: int, index: int = -1)` | Length in beats: 4 = one 4/4 bar, 16 = four bars. |

> The controller script also exposes `patterns.duplicate` and
> `patterns.move` at the protocol level (they exist in
> `device_FLStudioMCP.py`); dedicated MCP tools for them are not yet
> registered.

---

## Step Sequencer (composition engine)

Program per-step patterns - including melodies - directly on channels.

| Tool | Description |
|------|-------------|
| `fl_get_channel_steps(channel: int, steps: int = 16)` | Read each step: `step`, `enabled`, `note`, `velocity`, `pan`. |
| `fl_set_channel_steps(channel: int, steps: list[dict])` | Program steps. Each entry: `step` (required, 0-based), `enabled` (optional), `note` (optional, MIDI, 60 = middle C), `velocity` (optional, default 100), `pan` (optional, 0-127, 64 = center). |
| `fl_clear_channel_steps(channel: int, steps: int = 16)` | Disable all steps on a channel. |

### `fl_set_channel_steps` examples

Drum pattern on channel 0 - kick on beats 1, 2, 3, 4 (16th grid):

```json
[
  {"step": 0, "enabled": true},
  {"step": 4, "enabled": true},
  {"step": 8, "enabled": true},
  {"step": 12, "enabled": true}
]
```

16th-note arpeggio melody on channel 1:

```json
[
  {"step": 0, "enabled": true, "note": 60, "velocity": 100},
  {"step": 2, "enabled": true, "note": 64, "velocity": 90},
  {"step": 4, "enabled": true, "note": 67, "velocity": 100},
  {"step": 6, "enabled": true, "note": 72, "velocity": 95}
]
```

MIDI note numbers: 60 = C4 (middle C), 64 = E4, 67 = G4, 72 = C5, 57 = A3
(Am root), 65 = F4, 59 = B3.

---

## Mixer

| Tool | Description |
|------|-------------|
| `fl_get_mixer_track_count()` | Usually 125 tracks (0-124); 0 = Master. |
| `fl_get_mixer_track_info(track: int)` | `name`, `volume`, `volume_db`, `pan`, `stereo_separation`, `is_muted`, `is_solo`, `is_armed`, `color`. |
| `fl_get_all_mixer_tracks(include_empty: bool = False)` | `include_empty=false` skips default-named tracks. |
| `fl_set_track_volume(track: int, volume: float)` | 0.0 - 1.25 (default 0.8 ~ -5.2 dB; > 1.0 may clip). |
| `fl_set_track_pan(track: int, pan: float)` | -1.0 (left) to 1.0 (right), 0 = center. |
| `fl_mute_track(track: int, muted: bool = None)` | `None` toggles. |
| `fl_solo_track(track: int, solo: bool = None, mode: int = 3)` | `mode`: 1 = solo+source, 2 = solo+sends, 3 = both (default), 4 = track only. |
| `fl_arm_track(track: int)` | Toggle record-arm. |
| `fl_set_track_name(track: int, name: str)` | Empty string resets to default. |
| `fl_set_track_color(track: int, red: int, green: int, blue: int)` | RGB 0-255. |
| `fl_set_stereo_separation(track: int, separation: float)` | -1.0 (mono) to 1.0 (full width), 0 = default. |

---

## Channels

| Tool | Description |
|------|-------------|
| `fl_get_channel_count(global_count: bool = True)` | Total channels, or only the current group. |
| `fl_get_channel_info(index: int, use_global_index: bool = True)` | `name`, `color`, `volume`, `pan`, `pitch`, `is_muted`, `is_solo`, `is_selected`, `target_fx_track`. |
| `fl_get_all_channels()` | All channels with basic properties. |
| `fl_get_selected_channel()` | The currently selected channel (or None). |
| `fl_select_channel(index: int, select: bool = True)` | Select or deselect. |
| `fl_select_one_channel(index: int)` | Select exclusively (deselects the rest). |
| `fl_trigger_note(channel: int, note: int, velocity: int = 100, midi_channel: int = -1)` | Real-time only - not persisted unless recording. `velocity = 0` releases the note. |
| `fl_set_channel_volume(index: int, volume: float)` | 0.0 - 1.0. |
| `fl_set_channel_pan(index: int, pan: float)` | -1.0 to 1.0, 0 = center. |
| `fl_mute_channel(index: int, muted: bool = None)` | `None` toggles. |
| `fl_solo_channel(index: int, solo: bool = None)` | `None` toggles. |
| `fl_set_channel_name(index: int, name: str)` | Rename a channel. |
| `fl_set_channel_color(index: int, red: int, green: int, blue: int)` | RGB 0-255. |
| `fl_route_channel_to_mixer(channel_index: int, mixer_track: int)` | Route to a mixer track. |
| `fl_get_channel_type(index: int)` | `channel_type_id`, `channel_type` (sampler / synthesizer / audio clip / ...), `channel_name`. |
| `fl_set_channel_pitch(index: int, pitch: int)` | Coarse pitch, -120 to +120 semitones. |
| `fl_get_grid_bit(channel: int, position: int)` | Is a step active (simple on/off). |
| `fl_set_grid_bit(channel: int, position: int, value: bool)` | Set a step on/off. |
| `fl_get_step_sequence(channel: int, steps: int = 16)` | Step on/off list. |
| `fl_set_step_sequence(channel: int, pattern: list[bool])` | Set a full on/off pattern. |

> For pitches, velocities, and pans per step, prefer the
> [Step Sequencer](#step-sequencer-composition-engine) tools.

---

## Plugins

Control **existing** plugins only - FL Studio's scripting API cannot load
new VST/AU instruments programmatically. For channel-rack plugins pass
`index`; for mixer effects pass `index` = mixer track and
`slot_index` = effect slot.

| Tool | Description |
|------|-------------|
| `fl_is_plugin_valid(index: int, slot_index: int = -1, use_global_index: bool = True)` | Does a plugin exist here. |
| `fl_get_plugin_name(index: int, slot_index: int = -1, use_global_index: bool = True)` | Plugin name. |
| `fl_get_plugin_param_count(index: int, slot_index: int = -1, use_global_index: bool = True)` | Number of parameters. |
| `fl_get_plugin_params(index: int, slot_index: int = -1, use_global_index: bool = True, max_params: int = 50)` | Param list with current values. |
| `fl_get_plugin_param_value(param_index: int, plugin_index: int, slot_index: int = -1, use_global_index: bool = True)` | Param `index`, `name`, `value`, `value_string`. |
| `fl_set_plugin_param_value(param_index: int, value: float, plugin_index: int, slot_index: int = -1, use_global_index: bool = True)` | Set value (usually 0.0-1.0, depends on the param). |
| `fl_get_preset_count(index: int, slot_index: int = -1, use_global_index: bool = True)` | Number of presets. |
| `fl_next_preset(index: int, slot_index: int = -1, use_global_index: bool = True)` | Next preset. |
| `fl_prev_preset(index: int, slot_index: int = -1, use_global_index: bool = True)` | Previous preset. |
| `fl_get_plugin_color(index: int, slot_index: int = -1, use_global_index: bool = True)` | Plugin color. |

---

## Piano Roll

Persistent note edits via the ComposeWithLLM Piano Roll script, triggered by
a hotkey (`Ctrl+Alt+Y` on Windows, `Cmd+Opt+Y` on macOS). FL Studio will
briefly come to the foreground on Windows so the hotkey reaches it.

| Tool | Description |
|------|-------------|
| `fl_send_notes(notes: list[dict], mode: str = "add", auto_trigger: bool = True)` | Add or replace notes. Note fields: `midi` (required int), `duration` (required float, quarter notes), `time` (optional, default 0), `velocity` (optional, default 0.8). `mode="replace"` clears existing notes first. |
| `fl_send_chord(midi_notes: list[int], time: float = 0, duration: float = 1.0, velocity: float = 0.8, auto_trigger: bool = True)` | Chord convenience wrapper. E.g. `[60, 64, 67]` = C major. |
| `fl_delete_notes(notes: list[dict], auto_trigger: bool = True)` | Delete by `midi` + `time`: `[{"midi": 60, "time": 0}]`. |
| `fl_clear_piano_roll(auto_trigger: bool = True)` | Clear all notes. |
| `fl_get_piano_roll_state()` | Read `ppq` and `notes` from the last export. Run the script once first, or call `fl_trigger_script`. |
| `fl_clear_request_queue()` | Drop pending requests without executing. |
| `fl_trigger_script()` | Manually send the hotkey to process the request queue. |
| `fl_get_piano_roll_info()` | Platform, keystroke, script dirs, file-existence flags. |

### `fl_send_notes` example

```json
[
  {"midi": 60, "duration": 1.0, "time": 0},
  {"midi": 64, "duration": 1.0, "time": 0},
  {"midi": 67, "duration": 1.0, "time": 0},
  {"midi": 60, "duration": 0.5, "time": 1.0}
]
```

C major chord at beat 0 plus a C4 eighth-note at beat 1.

---

## Resources

The server also exposes two MCP resources (read-only):

| Resource | Content |
|----------|---------|
| `fl://status` | Connection state string. |
| `fl://project` | `is_playing`, `is_recording`, `position`, `loop_mode` from `transport.getStatus`. |

---

## Notes on return values

- Tools return either a human-readable string or a dict/list, depending on
  the tool; every wrapper surfaces FL Studio errors as
  `{"error": "..."}` / `Error: ...`.
- Indexing conventions: mixer track 0 = Master; channel indexing is global
  by default; pattern and step indices are 0-based.
- All parameter ranges are enforced server-side before anything is sent to
  FL Studio.