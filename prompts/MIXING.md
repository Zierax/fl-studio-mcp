# MIXING — Engineering the Balance

The order matters: **balance → pan → routing → EQ → FX → automation →
loudness**. Every stage assumes the previous one is right. Skipping to EQ
because something "sounds muddy" is the most common wasted hour in
mixing.

Related: [QC.md](QC.md) (mix gates), [BRIDGE.md § Mixer](BRIDGE.md#mixer)
(tool map), [RECIPE.md](RECIPE.md) (targets).

---

## 1. Balance (faders first)

Set a fader for every role before touching anything else. Use the kick as
the reference.

| Role | Starting fader | Note |
|------|----------------|------|
| Kick | 0.85–0.90 | the reference |
| Sub / 808 | 0.70–0.78 | must be *felt* against the kick, not heard |
| Snare / clap | 0.70–0.80 | 3–6 dB under the kick |
| Hats | 0.45–0.60 | clearly under, still audible |
| Lead / melody | 0.60–0.70 | forward, above the rhythm |
| Pad / texture | 0.30–0.45 | present, never competing |
| Percussion | 0.40–0.55 | place by role, not by ear alone |

Rules:

- **The kick and the bass must not fight.** If the low end is muddy, the
  bass is too high or the kick is too low — one of them moves.
- **If you mute the kick and nothing is missing, the kick is doing
  nothing.** It should hold the track together when soloed.
- **If you mute the bass and nothing is missing, there is no bass.** It
  should be felt in the chest, not heard as a note.

Write with `fl_mixer_track_set(track=, volume=…)` (many tracks at once)
and read back with `fl_mixer_track_state(track=)`.

## 2. Pan (width is a decision)

| Element | Position |
|---------|----------|
| Kick, sub, snare, lead, bass | centre (0.0) |
| Hats | L/R, or one centre + one side |
| Clap | slightly wide or with the snare |
| Percussion | spread across the field |
| Pads / texture | wide, 0.6–0.8 |
| Doubled lead | hard-ish L/R |

The classic mistake is panning by habit. Decide: **is this element
supposed to occupy space?** If not, it is centred.

`fl_mixer_track_set(track=, pan=…)` — values are −1.0 (left) to 1.0
(right), 0.0 is centre.

## 3. Routing (get the sends right)

```
fl_mixer_route(track=<src>, dest=<bus>, value=<1>)
fl_mixer_route_level(track=<src>, dest=<bus>, level=<0–1>)
fl_mixer_route_send_active(track=<src>, dest=<bus>)
```

The pattern that works:

- **One reverb bus**, fed by the elements that need space (lead, snare,
  clap, pads) — *not* by the kick, bass or hats.
- **One delay bus** for throws, fed by at most two elements.
- The reverb send level is the main "space" control: 0.15–0.25 for a
  lead, 0.05–0.12 for a snare, higher only in a breakdown.
- **Read the routing back** with `fl_mixer_route_send_active` — a send
  that was not created is a silence you cannot hear.

## 4. EQ (3 bands, and that is enough)

This FL build's mixer EQ has **3 bands**, and the arguments are
`(track, band)`.

```
fl_mixer_equalizer(track=, mode="bands")                       # read
fl_mixer_equalizer(track=, mode="set", band=, gain=, freq=, q=) # write
fl_mixer_equalizer(track=, mode="get", band=)                  # verify
```

A three-band workflow that actually works:

| Band | Use for |
|------|---------|
| low | cut mud around 200–400 Hz on channels that fight the kick; cut 60–80 Hz on everything except kick and sub |
| mid | presence: 2–5 kHz for snares and leads; cut 300–500 Hz on guitars that get muddy |
| high | air on the lead (8–12 kHz); tame sibilance (6–9 kHz) |

Rules:

- **Subtract before you add.** A muddy mix is fixed with a cut, not a
  boost.
- **Never EQ a channel you have not heard in isolation.** Solo it, then
  decide.
- **One EQ move per element per session.** If you need three moves, the
  problem is the arrangement or the balance.
- Cut by ear and by `fl_mixer_peaks`, never by guesswork.

## 5. FX

```
fl_mixer_fx_info(track=)                 # what is already on the track
fl_mixer_fx_mix_level(track=, slot=, level=)
fl_mixer_track_set(track=, ...)          # + slot routing
```

- **Read the chain before writing to it.** You do not know what is
  already there.
- **Prefer sends over inserts** for time-based effects (reverb, delay).
  Inserts change the signal; sends add to it.
- **The master track is not a mixing tool.** Heavy glue compression and
  saturation belong on a bus if you have one, not on Master.
- Keep one effect per job. Two reverbs means the wrong one is louder.

## 6. Dynamics & automation

```
fl_mixer_automate(track=, value=, rec_event_id=)   # a fader ride
fl_channel_event(channel=, event="volume", value=) # channel automation
```

- **A static mix is a flat mix.** Automate at least one thing per track:
  a filter, a level, a send level.
- **Automate with a reason**: a rise into a drop, a duck under a vocal,
  a filter opening across 8 bars.
- **Rides should be slow.** 1–2 dB over 8 bars reads as movement;
  10 dB over a bar reads as a mistake.

## 7. Metering

```
fl_mixer_peaks(track=, mode=)    # mode 0 = L, 1 = R, 2 = L+R
```

Targets:

| Signal | Target peak |
|--------|-------------|
| Kick | −6 dBFS (so it can survive limiting) |
| Snare | −8 dBFS |
| Bass | −6 dBFS |
| Hats | −18 dBFS |
| Master | −1 dBFS peak, no clipping |

Peak readings are instantaneous — check a few times while the section
that matters is playing.

## 8. Loudness (the last step, and it is not a mix decision)

| Target | Use for |
|--------|---------|
| −9 LUFS | loud demo master, streaming with impact |
| −14 LUFS | the standard streaming target |
| −18 LUFS | broadcast-style, dynamic, "correct" |
| −23 LUFS | true peak reference for streaming |

Two rules that people get wrong constantly:

1. **Loudness is set at the master**, after the mix is finished — by a
   limiter and a gain stage, not by pushing every track up.
2. **-14 LUFS in the brief does not mean "make everything louder"**. It
   means the master ends there. If the mix needs +6 dB, the arrangement
   is missing energy, not the faders.

Write the target in the [recipe card](RECIPE.md) and apply it last.

## 9. The mix gate

Before calling a mix done:

- [ ] Every role has a written fader, pan and EQ, read back from FL.
- [ ] Kick, bass and snare do not fight; each survives solo.
- [ ] Reverb/delay are on sends, and the send levels are read back.
- [ ] No track is clipping; the master peaks below −1 dBFS.
- [ ] At least one automated movement exists.
- [ ] The loudness target is set at the master.
- [ ] The mix survives a two-bar drop-out (mentally) — the track still
      has an identity without the drums.
