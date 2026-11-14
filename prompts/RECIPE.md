# RECIPE — The Style Card

One card per track. It is the contract between the brief, the plan and the
verification. It travels with the session: written in Phase 1, referenced
in every later phase, updated when a decision changes.

Related: [GENRES.md](GENRES.md) (specs to fill it from),
[WORKFLOW.md](WORKFLOW.md) (when to fill it), [QC.md](QC.md) (gates).

---

## The card

```
STYLE:        <one line: genre + the specific sub-mood>
BPM:          <number>            KEY: <tonic + mode>
REFERENCE:    <track + what to copy from it, or "none">
LENGTH:       <bars>              METER: <n/d>

ROLES
  kick        ch <idx> → mx <idx>   role: <what it does>
  snare/clap  ch <idx> → mx <idx>   role: ...
  808/bass    ch <idx> → mx <idx>   role: ...
  hats        ch <idx> → mx <idx>   role: ...
  lead        ch <idx> → mx <idx>   role: ...
  pad/texture ch <idx> → mx <idx>   role: ...

SECTION MAP            BARS   ENERGY   WHAT CHANGES
  intro                    8      2     ...
  hook                     8      7     ...
  verse                   16      4     ...
  ...
  outro                    4      1     ...

SIGNATURE MOVES          (one per section change)
  → <what happens, and why it is not generic>

MIX TARGETS
  kick    <fader>  <pan>  <eq note>
  bass    ...
  ...

LOUDNESS:    <target LUFS + where it is set>
```

## Rules for filling it

1. **Every number is a decision.** "140" is a decision only if you can say
   why 140 and not 130 or 150. Write the reason next to it.
2. **Every role maps to a channel that exists.** Look it up with
   `fl_get_all_channels()`. If a role has no channel, reuse one and say so.
3. **Energy is a curve, not a label.** Write 0–10 per section. If the
   numbers do not rise and fall, the arrangement will not either.
4. **"WHAT CHANGES" is the point of the section map.** "more drums" is not
   a change; "kick drops out, hats double, reverb opens" is.
5. **One signature move per boundary.** Four ideas at one boundary is
   noise, not contrast.
6. **Loudness is a mastering decision, not a mixing one.** Set the target
   in the card and apply it at the master, not by pushing every track up.

## Filling the card from a reference track

A reference is only useful if it becomes numbers. Do not copy the feeling —
copy the measurements.

```
REFERENCE ANALYSIS
  tempo         <BPM you measured>
  meter         <n/d>
  key           <tonic + mode, or "modal / atonal">
  groove        <straight | swung | triplet>  swing %: <value>
  section map   <name × bars, from the reference>
  energy        <0–10 per section, from the reference>
  low end       <how the bass sits against the kick: locked | answering | sliding>
  top end       <bright | warm | dark>   <which element carries the melody>
  space         <dry | room | hall>   <reverb on what>
  width         <what is wide, what is mono>
  hook          <the 1–2 bar motif, described or as scale degrees>
```

Then **change at least one thing deliberately** — a straight copy is not
work. Say what you changed and why it still sounds like the reference.

## Filling the card from a genre spec

Copy the relevant block from [GENRES.md](GENRES.md) and then adapt it to the
project: the BPM to the room, the roles to the channels that exist, the
section map to the length the user asked for.

A genre spec is a **starting point**, not a template to paste. If the
brief contradicts it, the brief wins and the spec shrinks to reference
material.

## Worked example

```
STYLE:        dark trap, half-time, whispered hook over a drowned 808
BPM:          146  (half-time feel at 73; the reference sits at 146 and
                    the space needs the extra weight)
KEY:          F minor  (F gives the hook a dark root without going to
                    C, which every other dark track uses)
REFERENCE:    "X" — copied the half-time snare placement and the
              sub-drop before the hook; changed the melody (added the
              flattened 2nd) and used a 2-bar breath before the drop
LENGTH:       44 bars   METER: 4/4

ROLES
  kick        ch 0  → mx 1   role: hard kick, every beat except bar 3 of each 8
  clap        ch 1  → mx 2   role: layered under the snare, 4 dB down
  hats        ch 3  → mx 3   role: 16ths, 50% velocity variation, swung 12%
  808         ch 4  → mx 4   role: answers the kick, slides into every 4th downbeat
  lead        ch 6  → mx 5   role: sparse hook, one off-key note per 8 bars
  texture     ch 9  → mx 6   role: vinyl noise bed, invisible

SECTION MAP            BARS   ENERGY   WHAT CHANGES
  intro                    4      1     808 + vinyl only, no kick
  hook A                   8      7     full kit, hook melody
  verse                   12      4     kick + hats + 808 only
  hook B                   8      8     hook A + lead double + sub-drop
  break                    4      2     everything drops except texture
  outro                    8      3     hook A, 808 tail

SIGNATURE MOVES
  → break: 4 bars of near-silence before the final hook (the drop needs
    somewhere to fall from)
  → hook B: sub-drop one beat before the downbeat, not on it
  → lead: one note a quarter-tone flat, once per 8 bars

MIX TARGETS
  kick    0.86  centre  cut 250 Hz, boost 3 kHz
  808     0.74  centre  LP 120 Hz
  hats    0.52  wide    HP 400 Hz
  lead    0.66  centre  +2 dB at 8 kHz

LOUDNESS:    -9 LUFS (punchy demo master), applied at the master
```
