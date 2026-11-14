# QC — Quality Gates and Diagnosis

Two jobs:

1. **Gates** — checkable conditions that must hold before the track is
   called finished. Every gate is *evidence*, not opinion.
2. **Diagnosis** — what to do when a track is not good yet.

Related: [WORKFLOW.md](WORKFLOW.md) (where the gates sit),
[CORE.md](CORE.md) (the verification invariant), [MIXING.md](MIXING.md).

---

## How to run a gate

A gate is passed or failed **against a read-back from FL Studio**.

```
PASS  fl_get_tempo() = 146 = the card's BPM
FAIL  fl_get_tempo() = 120 != the card's BPM  →  fix and re-verify
OPEN  not checked yet
```

Never mark a gate passed because it "sounds right" in your head. If a
gate cannot be checked, it is OPEN, and you say so.

## The gates

### G1 — Project integrity
- [ ] `fl_connect()` succeeds and `fl_connection_status()` reports a
      connected bridge.
- [ ] The project has the intended tempo, meter and loop mode.
- [ ] The patterns that exist match the section map.
- [ ] Every channel in the card's role table exists, with the right name
      and type.
- [ ] No channel is left routed to Master by accident.

### G2 — Groove
- [ ] Every drum channel's steps read back with the intended pattern.
- [ ] Velocities vary (a grid of identical velocities is a red flag).
- [ ] Swing is applied where intended and nowhere else.
- [ ] At least one intentional deviation from the grid exists per 8 bars.

### G3 — Low end
- [ ] The bass reads back with pitch, not only on/off.
- [ ] The kick and bass do not occupy the same frequency range.
- [ ] The relationship (lock / answer / contradiction) is stated.
- [ ] The sub is centred and mono.

### G4 — Melody & harmony
- [ ] `fl_get_piano_roll_state` shows exactly the intended notes — no
      leftovers from a previous take.
- [ ] The melody's range is stated and deliberate.
- [ ] Every section has a harmonic centre or a deliberate static.
- [ ] One deliberate imperfection exists — and only one.

### G5 — Arrangement
- [ ] The energy curve rises and falls.
- [ ] Every section boundary has exactly one named signature move.
- [ ] A breath precedes the peak.
- [ ] Layers enter late and leave early.
- [ ] Patterns exist for every section, correctly named and sized
      (`fl_list_patterns`).
- [ ] The user has a written playlist order with bar counts.

### G6 — Mix
- [ ] Every role has a written fader, pan and EQ, read back.
- [ ] Each of kick, bass and snare survives solo.
- [ ] Reverb/delay are on sends, with send levels read back.
- [ ] No clipping; master peaks below −1 dBFS (`fl_mixer_peaks`).
- [ ] At least one automated movement exists.
- [ ] The loudness target is set at the master.

### G7 — Delivery
- [ ] The session summary contains real numbers, not adjectives.
- [ ] The decisions are listed with reasons.
- [ ] The open gates are listed explicitly.
- [ ] One next step is proposed (not asked for).
- [ ] A final undo point exists (`fl_save_undo`), so the state is
      recoverable.

---

## Diagnosing a weak result

When the track is not good yet, **diagnose before you change anything**.
Re-rolling blind is how a session burns four hours.

### Step 1 — name the symptom in one sentence

Not "it sounds bad". One of:

- "the hook does not stand out"
- "the low end is muddy"
- "the track is flat"
- "the drums sound synthetic"
- "the transition is weak"
- "it is too long / too short"
- "the mix is too loud / too quiet"

### Step 2 — classify it

| Symptom class | Usual cause | Where to fix |
|---------------|--------------|--------------|
| **Arrangement** | energy curve is flat, sections repeat | [ARRANGEMENT.md](ARRANGEMENT.md) |
| **Groove** | the grid is uniform, no swing, no variation | Phase 3, [THEORY.md § 3](THEORY.md) |
| **Low end** | kick and bass overlap, or there is no bass | [MIXING.md § 1](MIXING.md) |
| **Tonal** | everything is in one mode and one register | [THEORY.md § 1](THEORY.md) |
| **Space** | no reverb, everything dry, no width | [MIXING.md § 3](MIXING.md) |
| **Detail** | no texture, nothing behind the front line | Phase 5 |
| **Level** | everything is loud, or the master is too quiet | [MIXING.md § 8](MIXING.md) |
| **Technical** | the write did not land | [BRIDGE.md § 4](BRIDGE.md#4-timeouts-and-failure-branches) |

### Step 3 — change the minimum

One change per iteration. Take an undo point first:

```
fl_save_undo(name="before <the single change>")
```

Then make the change, re-run the affected gate, and compare.

### Step 4 — verify the change landed

Re-read the state. If the read disagrees with the write, the change did
not happen — do not continue on the assumption that it did.

### Symptom → likely fix

| Symptom | First thing to try |
|---------|--------------------|
| "flat" | raise the energy contrast: mute a layer in the verse, add one in the hook |
| "muddy" | cut 200–400 Hz on the offending channel, or lower the bass |
| "the hook does not stick" | give the hook its own frequency space — sidechain the pad, cut the bass under it, add a delay |
| "the drums sound fake" | add velocity variation and one humanised hit per 8 bars; swing the hats |
| "the transition is weak" | a 1–2 bar breath before the change, plus one added layer after it |
| "it is too dense" | remove a layer in the quiet section rather than lowering it |
| "the bass is weak" | check the frequency range — is a sub competing with it? |
| "it sounds like every other track" | change the mode, the tempo or the register — not the mixer |

---

## The pre-delivery read

Before you deliver, run these three calls. If they disagree with your
summary, the summary is wrong:

```
fl_project_snapshot()     # whole-project state
fl_get_tempo()            # the number you are about to claim
fl_mixer_peaks(track=0)   # the peak you are about to claim
```

Then deliver the summary. Short, numeric, honest about what is still
open.
