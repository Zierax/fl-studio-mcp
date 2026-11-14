# WORKFLOW — A Full Production Session

Nine phases. Follow them in order, adapt to the brief, and **end every
phase with its gate** (a read-back, not an opinion).

Related: [CORE.md](CORE.md) (rules), [BRIDGE.md](BRIDGE.md) (tool map),
[QC.md](QC.md) (all gates in one place), [RECIPE.md](RECIPE.md) (the style
card), [MIXING.md](MIXING.md), [ARRANGEMENT.md](ARRANGEMENT.md),
[THEORY.md](THEORY.md).

---

## Phase 0 — Connect and read (never skip)

```
fl_connect()
fl_diagnostics()          # only when something feels off
fl_project_snapshot()
```

Extract from the snapshot and state plainly:

- tempo, meter, loop mode, song length
- the patterns that exist (count, names, which is active)
- the channels that exist (names, types, routing, mute/solo)
- the mixer tracks that exist (count, names)

Then map the brief onto what exists. **The channel rack is fixed** — your
job is to re-role what is there, not to wish for new channels.

> **Gate 0** — your summary of the project matches `fl_project_snapshot`.
> If it does not, re-read before continuing.

---

## Phase 1 — Brief and style card

Do this **before** touching FL Studio. Write the card from
[RECIPE.md](RECIPE.md); pick or adapt a spec from [GENRES.md](GENRES.md).

```
STYLE:        <one line>
BPM:          <number>            KEY: <tonic + mode>
REFERENCE:    <the track or "none">
SECTION MAP:  <name × bars, in order>
ENERGY:       <0–10 per section>
SIGNATURE:    <the one deliberate surprise, per section change>
ROLES:        <channel index → role>
```

Two rules:

1. **Every number has a reason.** 146 BPM because the reference sits there
   and the groove needs the space — not because 146 is the genre default.
2. **Decide the key and mode for the same reason.** See
   [THEORY.md](THEORY.md).

If the brief is still vague at this point, this is the one place to ask —
offer two or three fully specified options, not an open question.

> **Gate 1** — the card is complete, and every role has a channel index
> that really exists.

---

## Phase 2 — Foundation (tempo, meter, routing)

```
fl_set_tempo(tempo=<BPM>)
fl_time_signature(numerator=, denominator=)
```

Route every channel that has a role to its own mixer track:

```
fl_route_channel_to_mixer(channel=<idx>, mixer_track=<idx>)
```

Routing first matters: mixing a channel that still sits on Master is
mixing blind. Put the master track last and leave it alone.

If two roles share a channel, say so in the card and pick which role wins
(the beat usually does).

> **Gate 2** — `fl_get_tempo` returns the card's BPM, and
> `fl_get_all_channels` shows every routed role pointing at the intended
> mixer track.

---

## Phase 3 — Groove (drums before anything else)

The groove is the track. Melody on a bad groove is still a bad track.

1. `fl_get_channel_steps(channel=…)` — see what is already there.
2. `fl_set_channel_steps(channel=…, steps=[…])` — write the whole pattern
   with note, velocity and pan in one call.
3. Apply swing where it belongs: `fl_channel_swing(channel=, value=)`.
   Swing on the hats, not on the kick.
4. Humanise: vary velocity ±8–15, offset a few hats by a 16th, leave the
   kick and snare grid tight.

Deliberate detail that separates a groove from a pattern:

- a ghost snare in bar 3 of every 8
- a hat dropped on the "and" of 4 in the last bar of a phrase
- one kick pushed a 32nd late, once per 8 bars
- the snare losing velocity for one bar before a drop

> **Gate 3** — `fl_get_channel_steps` for every drum channel matches the
> intended pattern, and you can state the swing value you used.

---

## Phase 4 — Low end (kick ↔ 808 relationship)

Write the bass with **pitch**, not only rhythm.

```
fl_set_channel_steps(channel=<bass>, steps=[{step, enabled, note, velocity, pan}])
```

- The 808 should **answer** the kick, not double it: lock for the drop,
  deliberately contradict it under the hook.
- Roll off above ~120 Hz if it muddies the kick — check with
  `fl_mixer_peaks` and by ear.
- Slide into the downbeat of every 4 bars; that is the single most
  effective 808 gesture.
- Keep the sub mono and centred.

> **Gate 4** — bass steps read back with the right notes (not just
> on/off), and you can describe how it relates to the kick in one
> sentence.

---

## Phase 5 — Melody and harmony

```
fl_select_one_channel(index=<lead>)      # the piano roll acts on the selection
fl_send_notes(channel=<lead>, notes=[…])
fl_get_piano_roll_state(channel=<lead>)   # read back
```

Rules that matter:

- **Singable contour**: a melody is a phrase, not a scale walk. Limit
  consecutive intervals, leave a rest where a phrase needs air.
- **Harmony changes with the section**: no section may sit on one chord
  for more than 8 bars without a change.
- **One deliberate imperfection**: one note off the grid, one note
  microtonal, one velocity that breaks the pattern.
- **A texture layer that does not announce itself** — a pad, a detuned
  double, a noise layer. Present but invisible.
- The piano-roll tool **adds to** the channel; use
  `fl_clear_piano_roll` first if you are rewriting, otherwise you stack
  two melodies on top of each other.

> **Gate 5** — `fl_get_piano_roll_state` shows only the notes you intend:
> no leftover melody from a previous take.

---

## Phase 6 — Arrangement

Place the section map from Phase 1 and give it a shape.

- **Energy curve first**: write the 0–10 energy per section *before* you
  place anything. Section order should follow the curve, not the template.
- **Breathers before peaks**: a near-empty bar before a drop makes the
  drop land. Energy without a dip is just "loud".
- **Hooks at the joints**: a one- or two-bar motif that recurs when the
  structure turns.
- **Remove, don't hide**: in a sparse section, mute a layer. Hiding it
  under a louder one is not subtraction.
- **Markers**: `fl_marker_add(name=…)` at each section start makes the
  track navigable and makes the structure verifiable.

> **Gate 6** — `fl_arrangement_state` and `fl_list_patterns` show the
> intended section count and names; markers exist for each boundary.

---

## Phase 7 — Mix

Follow [MIXING.md](MIXING.md) in order: balance → routing → EQ → FX →
automation. The short version:

1. **Balance** — set a fader for every role, with the kick as the
   reference. Rough, but a real balance.
2. **Pan** — kick, bass and lead centred; hats wide; anything that needs
   width wide.
3. **EQ** — `fl_mixer_equalizer(mode="bands")` to read the bands, then
   carve: cut the kick's mud band, cut the snare's boxiness, air on the
   lead. 3 bands only in this build.
4. **FX** — read `fl_mixer_fx_info` before writing. Reverb and delay
   belong on a send, not on the insert.
5. **Check** — `fl_mixer_peaks` on the loudest tracks, mute/solo pairs to
   find masking.

> **Gate 7** — every role's fader, pan and EQ are written and read back;
> no track peaks are clipping.

---

## Phase 8 — Judge and finish

Run the gates in [QC.md](QC.md). For each one, state **pass / open /
fail** with the evidence. Then:

```
fl_save_undo(name="before master")
```

Deliver:

1. **What is in the project** — from reads, with numbers (BPM, key,
   section map, fader values).
2. **The decisions** — one line each, with the musical reason.
3. **The gate results** — what is still open.
4. **The single best next step**, proposed.

---

## Phase 9 — Iterate (when the user comes back)

Do not restart from zero. Read the current state first, then:

1. Name the specific problem ("the hook has no low end").
2. Diagnose it before fixing it ([QC.md § Diagnosing a weak result](QC.md#diagnosing-a-weak-result)).
3. Change the minimum number of things that could fix it.
4. Re-run the affected gates only.

Take an undo point before the change so it can be reverted:
`fl_save_undo(name="before <the change>")`.
