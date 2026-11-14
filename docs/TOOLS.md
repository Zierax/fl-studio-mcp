# Tools

Every tool the server exposes, grouped by area. All tools take a connection
for granted — call `fl_connect` first (the server usually auto-connects).

Conventions:

- **Channel / mixer track / pattern indices** are 0-based.
- **Volumes / pans / values** are 0.0–1.0 (pan 0.5 = center, 0 = hard left,
  1 = hard right).
- **Colors** are `(red, green, blue)` 0–255.
- Modes that fall back to `-1` use "the focused/current thing".

## Connection & status

| Tool | Description |
|------|-------------|
| `fl_connect` | Find and open the MIDI port that triggers FL Studio. Optional arguments: `port_name` (force an exact MIDI port, e.g. `"FLStudioMCP 1"`) and `data_dir` (the folder that holds `mcp_command.json` / `mcp_response.json`) |
| `fl_connection_status` | Whether the bridge is connected, the port used, whether the port was a guess, and every folder candidate that was considered |
| `fl_diagnostics` | Full diagnosis in one call: the server side view (MIDI port, command folder) plus the controller's own report (FL API version, which modules the embedded Python can import, the paths it resolved) |

Start with `fl_diagnostics` when the bridge misbehaves — it answers most of
the questions in [TROUBLESHOOTING.md](TROUBLESHOOTING.md) in one shot.

## Transport

| Tool | Description |
|------|-------------|
| `fl_play` | Start playback |
| `fl_stop` | Stop playback (and rewind if loop mode is off) |
| `fl_record` | Start recording |
| `fl_get_transport_status` | Playing, recording, loop mode, is-step-edit, tempo, song position/length, current pattern |
| `fl_set_song_position(position, mode)` | Jump the playhead (`mode`: 0 = steps, 1 = ms, 2 = bars/beats) |
| `fl_get_song_length` | Song length |
| `fl_set_loop_mode(mode)` | `"song"`, `"pattern"`, or `"none"` |
| `fl_set_playback_speed(speed)` | 0.0–2.0× |
| `fl_set_tempo(bpm)` | Set project tempo |
| `fl_get_tempo` | Current tempo |
| `fl_get_shuffle` | Swing/shuffle amount |

## Mixer

| Tool | Description |
|------|-------------|
| `fl_get_mixer_track_count` | Number of mixer tracks |
| `fl_get_mixer_track_info(track)` | Name, volume, pan, mute/solo/arm state, color, routed channels |
| `fl_get_all_mixer_tracks(include_empty)` | All tracks (optionally skipping empty ones) |
| `fl_set_track_volume(track, volume)` | 0.0–1.0 |
| `fl_set_track_pan(track, pan)` | 0.0–1.0 |
| `fl_mute_track(track, muted)` | Toggle or force mute |
| `fl_solo_track(track, solo, mode)` | Toggle or force solo (modes 0–3 for FL solo behavior) |
| `fl_arm_track(track)` | Record-arm |
| `fl_set_track_name(track, name)` | Rename |
| `fl_set_track_color(track, red, green, blue)` | Color |
| `fl_set_stereo_separation(track, separation)` | Stereo separation 0%–200% |

## Channel rack

| Tool | Description |
|------|-------------|
| `fl_get_channel_count(global_count)` | Channel count (global vs current pattern) |
| `fl_get_channel_info(index)` | Name, type, volume, pan, mute/solo, mixer route, color |
| `fl_get_all_channels` | Info for every channel |
| `fl_get_selected_channel` | The channel currently selected in the rack |
| `fl_select_channel(index, select)` | Select/deselect |
| `fl_select_one_channel(index)` | Select only this one |
| `fl_trigger_note(channel, key, velocity, duration)` | Audible preview note (not persisted) |
| `fl_set_channel_volume / _pan / _name` | Channel strip basics |
| `fl_mute_channel / fl_solo_channel` | Toggle or force |
| `fl_set_channel_color(index, r, g, b)` | Color |
| `fl_route_channel_to_mixer(channel_index, mixer_track)` | Route channel to mixer track |
| `fl_get_grid_bit / fl_set_grid_bit` | Single step on/off (get returns bool) |
| `fl_get_step_sequence / fl_set_step_sequence` | Read/write the full 16-step pattern (list of bools) |
| `fl_get_channel_type(index)` | `"sampler"`, `"synth"`, or `"layer"` |
| `fl_set_channel_pitch(index, pitch)` | Coarse pitch (semitone offset) |

## Patterns

| Tool | Description |
|------|-------------|
| `fl_get_pattern_count` | Total patterns |
| `fl_list_patterns` | Index + name for each |
| `fl_get_pattern(index)` | Name, length, selected state; `-1` = active |
| `fl_create_pattern(name)` | Append a new empty pattern |
| `fl_select_pattern(index)` | Make it the active pattern |
| `fl_rename_pattern(name, index)` | Rename (default: active) |
| `fl_clone_pattern(index)` | Duplicate |
| `fl_clear_pattern(index)` | Clear all step data |
| `fl_set_pattern_length(length, index)` | Bars long |

## Plugins

| Tool | Description |
|------|-------------|
| `fl_is_plugin_valid(channel, slot)` | Whether a plugin lives at that channel (5 = generator / instr., 6 = effect) |
| `fl_get_plugin_name(channel, slot)` | Plugin name |
| `fl_get_plugin_param_count(channel, slot)` | Number of parameters |
| `fl_get_plugin_params(channel, slot, index_begin, index_end)` | Parameter names + values |
| `fl_get_plugin_param_value(channel, slot, param_index)` | One value |
| `fl_set_plugin_param_value(channel, slot, param_index, value)` | Set one value |
| `fl_get_preset_count / fl_next_preset / fl_prev_preset` | Preset navigation |
| `fl_get_plugin_color(channel, slot)` | Plugin color |

## Piano roll

| Tool | Description |
|------|-------------|
| `fl_send_notes(notes, auto_trigger, clear, pattern)` | Add notes with exact timing (start step, length, pitch, velocity, pan) |
| `fl_send_chord(root, notes, start, root_vel, ...)` | Add a chord |
| `fl_delete_notes(notes)` | Remove specific notes |
| `fl_clear_piano_roll(auto_trigger)` | Empty the piano roll |
| `fl_get_piano_roll_state` | Read all notes in the active pattern |
| `fl_clear_request_queue` | Drop pending note requests |
| `fl_trigger_script` | Manually push the piano roll script |
| `fl_get_piano_roll_info` | Note count and bounds |

## Step sequencer

| Tool | Description |
|------|-------------|
| `fl_get_channel_steps(channel, steps)` | Per-step pitch/velocity/pan/flags for a channel |
| `fl_set_channel_steps(channel, steps)` | Program a melody: `[{step, note, velocity, pan}]` |
| `fl_clear_channel_steps(channel, steps)` | Blank the steps |

## Advanced (raw FL API access)

These give you **every function of every FL Studio API module** — anything in
the FL API not covered by the high-level tools is reachable here.

| Tool | Description |
|------|-------------|
| `fl_raw_command(module, function, args)` | Call anything: `fl_raw_command("channels", "getChannelName", [0])` |
| `fl_api_list_functions(module, prefix)` | Discover callable functions of a module |
| `fl_api_list_constants(prefix)` | Discover constants (e.g. `FPT_`, `REC_`, `Mixer_Event`) |
| `fl_project_info` | Open project name/path, version, PPQ |
| `fl_set_time_signature(num, den)` | Time signature |
| `fl_set_ppq(ppq)` | Pulses per quarter note |
| `fl_transport_action(action)` | `"play"`, `"stop"`, `"record"`, `"rewind"` |
| `fl_tempo_get / fl_tempo_set` | Tempo (set accepts BPM float) |
| `fl_general_info` | API version, undo count, mixer/channel counts |
| `fl_save_undo(name)` / `fl_undo` / `fl_undo_updown(steps)` | Undo history |
| `fl_safe_to_edit` | True while playback is stopped |
| `fl_project_snapshot(include_playlist)` | Everything about the project in one call |
| `fl_transport_position` | Playhead in bars/beats/ms |
| `fl_arrangement_info` | Playlist clip/pattern data |
| `fl_playlist_info / _set_track_name / _set_track_color / _mute / _solo / _select` | Playlist tracks |
| `fl_mixer_route(track, dest, value, width)` | Route/send with width |
| `fl_mixer_route_level / fl_mixer_route_send_active` | Send level / toggle |
| `fl_mixer_equalizer(track, mode, band, gain, freq, q)` | Per-band EQ read/write |
| `fl_mixer_peaks(track)` | L/R peak levels |
| `fl_mixer_fx_info(track, slots)` | FX slots + plugin names |
| `fl_mixer_fx_mix_level(track, slot, level)` | FX mix knob |
| `fl_mixer_link_channel(track, channel, link)` | Link channel to mixer track |
| `fl_mixer_automate(track, value)` | Write automation value |
| `fl_channel_shuffle / fl_channel_event / fl_channel_loop / fl_channel_step_param` | Channel internals |
| `fl_ui_hint(text)` | Show a hint inside FL Studio (useful for debugging) |

## Full control (state-oriented)

One-stop tools that read or write whole states, plus extras:

| Tool | Description |
|------|-------------|
| `fl_transport_state` / `fl_transport_song_pos` / `fl_transport_loop_mode` / `fl_transport_playback_speed` | Transport in one block |
| `fl_channel_state` / `fl_channel_steps` / `fl_channel_step_param` / `fl_channel_mute` / `fl_channel_solo` / `fl_channel_set` | Channel blocks |
| `fl_mixer_track_state` / `fl_mixer_track_volume` / `fl_mixer_track_pan` / `fl_mixer_track_mute` / `fl_mixer_track_solo` / `fl_mixer_track_set` / `fl_mixer_route_track` | Mixer blocks |
| `fl_pattern_info` / `fl_pattern_select` / `fl_pattern_rename` / `fl_pattern_clone` / `fl_pattern_burn_loop` / `fl_patterns_state` | Pattern blocks |
| `fl_plugin_info` / `fl_plugin_params` / `fl_plugin_param_read` / `fl_plugin_param_set` / `fl_plugin_param_name_to_index` / `fl_plugin_preset` | Plugin blocks |
| `fl_playlist_state` / `fl_playlist_track_mute` / `fl_playlist_track_solo` | Playlist state |
| `fl_arrangement_state` | Timeline layout |
| `fl_marker_add` / `fl_marker_name` / `fl_marker_jump` | Song markers |
| `fl_device_info` / `fl_device_full_refresh` / `fl_device_linked` / `fl_device_link_to_last_tweaked` / `fl_device_master_sync` / `fl_device_midi_out` | MIDI device control |
| `fl_general_event` / `fl_time_signature` | General |
| `fl_ui_notification` / `fl_ui_state` / `fl_ui_window` | UI feedback |
| `fl_raw_action(action, params)` | Raw action passthrough |
| `fl_undo_save` / `fl_undo_manager` / `fl_redo` | Undo system |
| `fl_api_constants` / `fl_api_surface` | API discovery |
| `fl_channel_swing` | Channel swing |
| `fl_piano_dump_score_log` | Paper-scroll score dump |

## Things the server cannot do

An honest list, so you don't waste prompts on them:

- **Create channels or load audio/sample files.** The FL API has no such call.
- **Place playlist clips.** Patterns can be managed, but arranging them on the
  timeline is a manual step.
- **Load VST plugins.** Plugins are controlled, never instantiated.
- **Persist live note triggers** (unless recording).

Workarounds and details: [docs/LIMITATIONS.md](LIMITATIONS.md)
