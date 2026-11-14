# BRIDGE — Operating Manual for the FL Studio MCP Bridge

The mechanics of driving FL Studio through this MCP server: which tool to
call for which job, what the bridge can and cannot do, and how to recover
when a call fails.

Related: [CORE.md](CORE.md) (rules), [WORKFLOW.md](WORKFLOW.md) (phases),
[QC.md](QC.md) (gates).

---

## 0. Before anything else

```
fl_connect()          # connect (auto-selects the MIDI port)
fl_diagnostics()      # FL API version, port, command folder, importable modules
```

`fl_diagnostics` is cheap and answers most "why is nothing happening"
questions in one call. If it reports `port_is_guess: true`, pass
`fl_connect(port_name="FLStudioMCP 1")` with the exact name from
**Options → MIDI Settings → Input**.

Then read the project before touching it:

```
fl_project_snapshot()   # one round trip: transport, tempo, patterns, channels, playlist
```

## 1. Tool map

165 tools. Use the ones below; everything else is raw passthrough.

### Connection & diagnosis
| Tool | Use it for |
|------|-----------|
| `fl_connect(port_name=, data_dir=)` | (re)connect; force a MIDI port or a command folder |
| `fl_connection_status()` | is the bridge up, which port, was it a guess |
| `fl_diagnostics()` | full report: server side + FL side |
| `fl_safe_to_edit()` | is FL in a safe state to edit right now |

### Transport & global
| Tool | Use it for |
|------|-----------|
| `fl_play` / `fl_stop` / `fl_record` | transport |
| `fl_transport_state()` | playing, recording, loop mode, position, tempo — one call |
| `fl_set_tempo(tempo=)` / `fl_get_tempo()` | BPM |
| `fl_tempo_set(tempo=)` / `fl_tempo_get()` | BPM via the real FL25 API |
| `fl_set_song_position()` / `fl_transport_song_pos()` | playback position |
| `fl_set_loop_mode()` / `fl_transport_loop_mode()` | pattern vs song |
| `fl_set_playback_speed()` / `fl_transport_playback_speed()` | playback rate |
| `fl_time_signature(numerator=, denominator=)` / `fl_set_time_signature()` | meter |
| `fl_transport_action(action=)` | FL global actions (save, undo, snap, …) |
| `fl_marker_add(name=)` / `fl_marker_jump()` / `fl_marker_name()` | arrangement markers |

### Channels (channel rack)
| Tool | Use it for |
|------|-----------|
| `fl_get_all_channels()` | every channel: index, name, type, mute, solo, routing |
| `fl_get_channel_info(index=)` | one channel in detail |
| `fl_get_channel_type(index=)` | sampler / synth / audio clip / MIDI out |
| `fl_channel_state(channel=)` | full state of one channel |
| `fl_channel_set(channel=, ...)` | set several channel properties in one call |
| `fl_select_channel(index=)` / `fl_select_one_channel(index=)` | selection (matters for the piano roll!) |
| `fl_set_channel_name/color/volume/pan/pitch` | individual properties |
| `fl_mute_channel` / `fl_solo_channel` | channel mute/solo (None = toggle) |
| `fl_route_channel_to_mixer(channel=, mixer_track=)` | **routing — do this before mixing** |
| `fl_trigger_note(channel=, note=, velocity=)` | audition only — **does not persist** |
| `fl_plugin_info(channel=)` / `fl_plugin_params()` / `fl_plugin_param_set()` | the sound on a channel |
| `fl_plugin_param_read()` / `fl_plugin_param_name_to_index()` | read a plugin parameter by name |
| `fl_plugin_preset(channel=, direction=)` | step through presets |

### Step sequencer (drums, bass, plucks)
| Tool | Use it for |
|------|-----------|
| `fl_get_grid_bit(channel=, position=)` | one step |
| `fl_set_grid_bit(channel=, position=, value=)` | one step |
| `fl_get_step_sequence(channel=, steps=)` | whole pattern |
| `fl_set_step_sequence(channel=, pattern=[0/1...])` | whole pattern (16 steps) |
| `fl_get_channel_steps(channel=, steps=)` | steps **with pitch/velocity/pan** |
| `fl_set_channel_steps(channel=, steps=[{step, enabled, note, velocity, pan}])` | steps with pitch/velocity/pan |
| `fl_clear_channel_steps(channel=, steps=)` | wipe a pattern |
| `fl_channel_step_param(channel=, step=, param=, value=)` | one step's pitch/velocity/release/fine-pitch/pan/mod/shift/repeat |
| `fl_channel_swing(channel=, value=)` | per-channel shuffle (0–1) |

**Prefer `fl_set_channel_steps` over `fl_set_grid_bit`** — one call writes
the whole pattern *with* note, velocity and pan. `fl_set_grid_bit` is for
single-step tweaks.

### Piano roll (written melody & harmony)
| Tool | Use it for |
|------|-----------|
| `fl_send_notes(channel=, notes=[...])` | write notes (pitch, time, length, velocity) |
| `fl_send_chord(channel=, chord=, ...)` | a chord block |
| `fl_get_piano_roll_state(channel=)` | read back what was written |
| `fl_delete_notes(channel=, notes=[...])` | remove specific notes |
| `fl_clear_piano_roll(channel=)` | wipe the channel's notes |
| `fl_get_piano_roll_info()` | is the piano-roll integration alive |
| `fl_trigger_script()` | force the note request to be processed |
| `fl_clear_request_queue()` | drop a stuck request |

**The piano-roll tools act on the *selected* channel** — always
`fl_select_one_channel(index=)` first, then write, then read back with
`fl_get_piano_roll_state(channel=)`.

### Patterns
| Tool | Use it for |
|------|-----------|
| `fl_get_pattern_count()` / `fl_list_patterns()` | inventory |
| `fl_create_pattern(name=)` | new pattern, becomes active |
| `fl_select_pattern(index=)` / `fl_pattern_select(index=)` | switch the active pattern |
| `fl_rename_pattern(index=, name=)` | rename |
| `fl_clone_pattern(source=, dest=)` / `fl_pattern_clone()` | duplicate into a slot |
| `fl_clear_pattern(index=)` | empty a pattern |
| `fl_set_pattern_length(index=, length=)` | length in beats |
| `fl_patterns_state()` / `fl_pattern_info(index=)` | details |

### Mixer
| Tool | Use it for |
|------|-----------|
| `fl_get_all_mixer_tracks()` / `fl_get_mixer_track_info(track=)` | inventory |
| `fl_mixer_track_state(track=)` | full state of one track |
| `fl_mixer_track_set(track=, volume=, pan=, name=, color=, muted=, solo=)` | set many properties at once |
| `fl_set_track_volume(track=, value=)` / `fl_mixer_track_volume()` | fader (0–1) |
| `fl_set_track_pan(track=, value=)` / `fl_mixer_track_pan()` | pan (−1…1) |
| `fl_mute_track` / `fl_solo_track` / `fl_mixer_track_mute` / `fl_mixer_track_solo` | mute/solo |
| `fl_mixer_route(track=, dest=, value=)` | send/bus routing |
| `fl_mixer_route_track(track=, dest=, value=, width=)` | routing with width |
| `fl_mixer_route_level(track=, dest=, level=)` | send level |
| `fl_mixer_route_send_active(track=, dest=)` | is a send on |
| `fl_mixer_equalizer(track=, mode=, band=, gain=, freq=, q=)` | built-in EQ (**3 bands**, args are `(track, band)`) |
| `fl_mixer_fx_info(track=)` | what plugins sit on the track |
| `fl_mixer_fx_mix_level(track=, slot=, level=)` | FX slot mix level |
| `fl_mixer_peaks(track=, mode=)` | metering — mode 0=L, 1=R, 2=L+R |
| `fl_mixer_link_channel(channel=, track=)` | link a channel to a track |
| `fl_mixer_automate(track=, value=, rec_event_id=)` | fader rides / automation |

### Project, undo & raw
| Tool | Use it for |
|------|-----------|
| `fl_project_snapshot()` | whole-project state in one round trip |
| `fl_project_info()` | title, author, genre, PPQ, meter |
| `fl_save_undo(name=)` / `fl_undo_save(name=)` | named undo point — **take one before any risky change** |
| `fl_undo()` / `fl_redo(steps=)` / `fl_undo_updown(offset=)` | history |
| `fl_undo_manager()` | undo stack state |
| `fl_raw_command(module=, function=, args=[])` | call any FL API function directly |
| `fl_raw_action(action=)` | any FL control action by name |
| `fl_api_surface(module=)` | the exact API of *this* FL build |
| `fl_api_list_functions(module=, prefix=)` | list callables |
| `fl_api_constants(prefix=)` | `FPT_*`, `REC_*` constants |

## 2. What the bridge cannot do

Plan around these — they are FL API limits, not bugs:

| Limit | Work around it |
|-------|----------------|
| **Cannot create channels** | use the channels that exist; rename and re-role them. If a role is missing, substitute creatively and say so. |
| **Cannot load audio files** | work with the samples/instruments already installed. |
| **Cannot place playlist clips** | patterns are fully scriptable; the timeline is manual. Say where the clips go. |
| **Cannot automate the browser** | pick samples by channel/plugin state, not by browsing. |
| **Live-triggered notes do not persist** | `fl_trigger_note` auditions only. Written music needs the step sequencer or piano roll. |
| **EQ has 3 bands, args are `(track, band)`** | the FL25 docs are reversed for this build — check `fl_api_surface("mixer")`. |
| **Tempo API units differ by version** | `fl_tempo_get` returns BPM; the raw `mixer.getCurrentTempo` returns EPB (BPM × 1000). |

## 3. The write–read protocol

```
1. fl_save_undo(name="before <what you are about to change>")   # on risky changes
2. <the write>
3. <the matching read>                                             # prove it
4. if the read disagrees with the write -> report it, do not retry blindly
```

Read-back pairings:

| You wrote | Read back with |
|-----------|----------------|
| `fl_set_tempo` | `fl_get_tempo` |
| `fl_set_channel_steps` | `fl_get_channel_steps` |
| `fl_set_grid_bit` | `fl_get_grid_bit` |
| `fl_send_notes` | `fl_get_piano_roll_state` |
| `fl_mixer_track_set` | `fl_mixer_track_state` |
| `fl_channel_set` | `fl_channel_state` |
| `fl_route_channel_to_mixer` | `fl_get_channel_info` (check `target_fx_track`) |
| `fl_create_pattern` / `fl_rename_pattern` | `fl_list_patterns` |
| `fl_select_pattern` | `fl_get_pattern_count` (active index) |
| `fl_mixer_route` | `fl_mixer_route_send_active` |
| `fl_mixer_equalizer` | `fl_mixer_equalizer(mode="get")` |
| `fl_save_undo` | `fl_undo_manager` |

## 4. Timeouts and failure branches

The server waits ~2 s for a response by default. A timeout means the
bridge did not answer — it does **not** mean the write failed.

| Symptom | Likely cause | Do this |
|---------|--------------|---------|
| Timeout on every call | wrong MIDI port, or FL Studio not running | `fl_diagnostics()`, then `fl_connect(port_name=…)` |
| Timeout on one call | the script hit an exception | **View → Script output** in FL Studio, read the traceback |
| `Invalid JSON in command file` | a stale/partial command file | re-send the command; the server writes atomically now |
| `success: false` with an `error` | the handler failed | the error string says why — fix it, do not retry blindly |
| Tool returns `None`/empty | the function does not exist in this FL build | `fl_api_surface(module=)` / `fl_api_list_functions()` |
| Piano-roll writes do nothing | wrong channel selected | `fl_select_one_channel()` first, then `fl_get_piano_roll_info()` |

**Never treat "no error" as success** — a timeout is not a success, and a
missing read is not a verification.

## 5. Cost discipline

Every call is a round trip through a file and a MIDI trigger. Be deliberate:

- `fl_project_snapshot` (one call) beats 15 single reads.
- `fl_channel_set` (one call) beats 5 single setters.
- Batch related writes, then do one batched verification.
- Do not poll the same state repeatedly while waiting — the bridge is
  synchronous; the response arrives before the call returns.
