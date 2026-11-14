# ARRANGEMENT — Structure That Moves

The arrangement is the difference between a loop with variations and a
track. It is decided in Phase 1 of the [workflow](WORKFLOW.md) and realised
in Phase 6.

Related: [RECIPE.md](RECIPE.md) (the section map), [THEORY.md](THEORY.md)
(harmony per section), [QC.md](QC.md) (gates).

---

## 1. Start with the energy curve, not the section names

Write 0–10 energy for each section **before** you decide what the
sections are called.

```
INTRO      ▁▁▂      2
VERSE      ▃▃▃▃     4
HOOK       ▇▇█▇     8
VERSE 2    ▃▃▅▅     5
BREAK      ▁▁       1
HOOK 2     ▇▇███   9
OUTRO      ▂▂       3
```

Then check the curve:

- [ ] It **rises** somewhere and **falls** somewhere.
- [ ] The peak is near the end, not in the middle.
- [ ] Every dip is followed by something bigger.
- [ ] No two adjacent sections have the same number.

If the curve is flat, the track is flat — this is a structural problem, not
a mixing problem.

## 2. Section lengths

| Section | Typical bars | Why |
|---------|--------------|-----|
| Intro | 2–8 | enough to set the world, short enough not to lose the listener |
| Verse | 8–16 | long enough to develop, short enough to move |
| Pre-chorus / build | 4–8 | a trajectory, not a section |
| Hook / chorus | 8–16 | the payoff; repeat it, don't extend it |
| Break / drop | 2–8 | the *purpose* is the silence |
| Bridge | 4–16 | new information, not a repeat |
| Outro | 4–8 | resolve, do not fade out of nothing |

Rules:

- **8 is the unit.** Sections built in multiples of 8 read as intentional;
  6-bar sections read as a mistake unless the whole track is in 3s or 5s.
- **Sections must change length when they change function.** A hook that
  is 8 bars but 12 bars of energy is confusing.
- **The last section should be shorter or different**, not the same hook
  again.

## 3. What changes at a boundary

Each section boundary gets **one** signature move (see
[RECIPE.md](RECIPE.md)). It must be one of:

| Type | Example |
|------|---------|
| **Addition** | a new layer enters |
| **Removal** | a layer drops out |
| **Substitution** | the kick changes, the bass changes |
| **Register** | the melody moves up an octave, the harmony opens |
| **Space** | reverb opens, the mix goes wide, the drums thin out |
| **Density** | 16ths become 8ths, or the reverse |
| **Harmony** | the chord changes and stays changed |

Not a change: "it gets louder", "it gets more energetic". Those are
results, not moves.

## 4. The breath before the peak

The single highest-leverage arrangement gesture:

> **Drop everything for 1–2 bars immediately before the biggest moment.**

A drop needs somewhere to fall from. Without the breath, the loudest
section is just "louder than the others" and the track has no peak.

Implementation: mute the drums for two bars, keep the texture, let the
reverb tail of the previous section ring, then bring the kit back with an
added layer.

## 5. Layer logic

| Layer | Enters when | Leaves when |
|-------|-------------|-------------|
| Kick | first beat of the track | outro |
| Hats | after the first groove | the break |
| Bass | with the kick or one bar later | the outro |
| Lead | at the first hook | the break, then returns |
| Pad | late, to lift the hook | the outro |
| Percussion | only in high-energy sections | before the break |
| Texture | the intro, under everything | the very end |

Rules:

- **Enter late, leave early.** A layer that is present the whole time is
  not an arrangement decision.
- **One new layer per 8 bars** is a good density; two is the maximum.
- **Remove, don't hide.** In a sparse section, mute the layer. Turning it
  down under a louder one is not subtraction.

## 6. Hooks

A hook is a **1–2 bar motif** that recurs at structural joints.

- It should be recognisable with the drums removed.
- It should be *varied* on each return — the last one transposed, doubled,
  or rhythmically displaced.
- Place it at the joints: the first hook, after the first verse, after the
  break, in the outro.

Test: if the hook cannot be hummed after one hearing, it is not a hook —
it is a melody.

## 7. Working with the FL Studio limits

The FL Studio API **cannot place playlist clips** (see
[LIMITATIONS](https://github.com/Zierax/fl-studio-mcp/blob/master/docs/LIMITATIONS.md)).
So:

- Build **patterns** for each section — `fl_create_pattern`,
  `fl_set_pattern_length`, `fl_clone_pattern`. That is fully scriptable.
- **Name the patterns after the sections** (`HOOK A`, `VERSE 2`, `BREAK`)
  so the structure is readable in FL Studio's channel and on disk.
- **Tell the user exactly which pattern goes where** in the playlist, in
  order, with bar counts. They drag the clips; you have already done the
  thinking.
- Use `fl_marker_add(name=…)` at each section boundary so the timeline
  is navigable.

This turns an API limit into a delivery instruction.

## 8. The arrangement gate

- [ ] The section map has bar counts and energy values, and the curve
      rises and falls.
- [ ] Every boundary has exactly one named signature move.
- [ ] At least one breath precedes the peak.
- [ ] Layers enter late and leave early; nothing plays from bar 1 to the
      end unchanged.
- [ ] Patterns exist for every section, named after it, with the right
      length — read back with `fl_list_patterns`.
- [ ] The user has a written playlist order with bar counts.
