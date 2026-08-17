# WORKFLOW — Full Production Session inside FL Studio MCP

A step-by-step roadmap. Follow the phases in order, but always adapt — the
map serves the track, not the other way around. Every phase ends with a
**verification checkpoint** (read the real state back).

## Phase 0 — Connect and inspect (never skip)

1. `fl_connect` — make sure the bridge is up.
2. Read the full project state:
   - `fl_get_transport_status` + `fl_get_tempo` (BPM, length, loop mode)
   - `fl_get_all_channels` (names, types, routing)
   - `fl_get_pattern_count` + `fl_list_patterns`
   - `fl_get_all_mixer_tracks` (what's routed where)
3. Summarize: what exists, what's missing, what the user's instruction
   actually requires.

**Checkpoint**: your summary must match a real `fl_project_snapshot` — if
it doesn't, re-read.

## Phase 1 — Pre-production (decide before touching FL)

In one short block (no waiting for approval):

- Style recipe (from `STYLES.md` or adapted) and target BPM
- Key/scale decision (with a real musical reason)
- Song structure (BPM-accurate section map: lengths in bars)
- Arrangement narrative: how energy moves across sections

## Phase 2 — Instrumentation

- Use what exists first: `fl_get_all_channels` — pick channels whose names
  actually fit the roles needed (kick, snare, 808, hats, melody).
- Set tempo / time signature: `fl_set_tempo`, `fl_set_time_signature`.
- Route channels to mixer tracks: `fl_route_channel_to_mixer` per role, so
  mixing isn't done inside the channel rack.
- If a role has no channel, say so honestly (see `docs/LIMITATIONS.md` —
  the FL API cannot create channels) and pick a creative substitute from
  what exists.

**Checkpoint**: `fl_get_all_channels` reflects exactly your routing plan.

## Phase 3 — Drums (groove first)

- Program with the step sequencer: `fl_set_channel_steps` /
  `fl_get_channel_steps` — start from a groove, not a fill.
- Break the metronome feel on purpose 2–3 times per 8 bars (ghost notes,
  swing via `fl_channel_swing`, dropped 16ths).
- Layer with existing sounds when they genuinely improve the tone.

**Checkpoint**: `fl_get_channel_steps` per drum channel matches what you
wrote.

## Phase 4 — Bass / 808

- Write a bassline with pitch, not just rhythm: `fl_set_channel_steps` with
  per-step `note` values or the piano roll `fl_send_notes`.
- Make the 808 follow the kick pattern meaningfully (lock, or deliberately
  answer).
- Test low-end contrast at least once per section change.

**Checkpoint**: notes read back from `fl_get_piano_roll_state` (or steps)
of the bass channel.

## Phase 5 — Melody / harmony / textures

- Use the piano roll: `fl_send_chord` for harmonic blocks, `fl_send_notes`
  for leads — with deliberate human imperfection (offset, velocity
  variation, one surprise note).
- No section stays harmonically static for more than 8 bars.
- Add one texture layer that doesn't announce itself (subtle pad/detune/
  noise) — present but invisible.

**Checkpoint**: `fl_get_piano_roll_state` confirms written notes only — no
invented playback.

## Phase 6 — Arrangement

- Percentaged energy curve; place sections per Phase 1 map.
- Add hooks at structural joints; remove (don't hide) busy layers in
  breathe sections.
- Use markers if they help navigation: `fl_marker_add` / `fl_marker_name`.

**Checkpoint**: read the section map back (`fl_arrangement_info` for
clips/patterns state) — but remember playlist clip placement is manual in FL
(`docs/LIMITATIONS.md`).

## Phase 7 — Mix

- Start from volumes/pan per role: `fl_set_track_volume`, `fl_set_track_pan`
  — build a real balance, then use sends/routing (`fl_mixer_route`).
- Tame/highlight with the built-in per-band EQ (`fl_mixer_equalizer`) and
  FX slots (`fl_mixer_fx_info`) — read before you write.
- Use `fl_mixer_peaks` against a reference: kick ~-6 dBFS headroom target,
  vocal/lead sitting on center, 808 level proven by listening not guessing.
- Mute/solo flows (`fl_mute_track` / `fl_solo_track`) to sanity-check masking.

**Checkpoint**: final mixer read — volumes/pan/EQ written values match the
plan.

## Phase 8 — Deliver

- Save undo point first: `fl_save_undo("before master")`.
- Deliver what was done (real reads), decisions + reasons, and the next
  best step. Propose, don't ask.