# AI Prompts — FL Studio MCP

A prompt pack for driving FL Studio through this MCP server. The goal is
an AI that behaves like a **producer and mix engineer**: it decides, it
executes, it verifies, and it judges its own work against explicit gates.

Related: [docs/TOOLS.md](../docs/TOOLS.md) (the tool reference),
[docs/LIMITATIONS.md](../docs/LIMITATIONS.md) (what FL cannot do),
[docs/TROUBLESHOOTING.md](../docs/TROUBLESHOOTING.md) (when the bridge
misbehaves).

---

## Start here

| File | What it is | When to load it |
|------|------------|-----------------|
| **[CORE.md](CORE.md)** | The standing directive: role, the verification invariant, creative rules, the "words that do nothing" list, the session contract | **Always** |
| **[BRIDGE.md](BRIDGE.md)** | The operating manual: tool map by job, the read-back pairings, FL API limits, failure branches | **Always**, when working through the MCP bridge |
| **[WORKFLOW.md](WORKFLOW.md)** | The nine production phases with a gate at the end of each | For any multi-step session |
| **[RECIPE.md](RECIPE.md)** | The style card: the contract for one track, plus a worked example | At the start of a track |
| **[GENRES.md](GENRES.md)** | Twelve style specs with real numbers (BPM, key, swing, arrangement, mix) | When a genre is named or implied |
| **[ARRANGEMENT.md](ARRANGEMENT.md)** | Energy curves, section lengths, layer logic, hooks, and how to work around the playlist limit | Phase 6, or when a track feels flat |
| **[THEORY.md](THEORY.md)** | Key and mode, bass writing, melody craft, the tells of a generated melody | Phases 1, 4 and 5 |
| **[MIXING.md](MIXING.md)** | The mixing order: balance → pan → routing → EQ → FX → automation → loudness | Phase 7 |
| **[QC.md](QC.md)** | The quality gates and the diagnostic table for a weak result | Before delivering, and whenever something sounds wrong |

## How to use

### Pasting into a chat client

```
User: make a 140 BPM trap track
[paste CORE.md]
[paste BRIDGE.md]
[paste WORKFLOW.md]
[paste RECIPE.md]
[paste GENRES.md — only the style you need]
```

### Pinning them permanently (Claude Code / OpenCode / Codex)

```json
{
  "instructions": ["prompts/CORE.md", "prompts/BRIDGE.md"]
}
```

Load the rest on demand — a long always-on prompt dilutes the rules that
matter. `CORE.md` and `BRIDGE.md` are the two that should always be
present; everything else is a working document.

### Making a project instruction file

If you work on a track in a repo, combine them into a `CLAUDE.md` /
`AGENTS.md`:

```markdown
# Track: <name> — <style> — <BPM> — <key>

<contents of CORE.md>
<contents of BRIDGE.md>

## This track
<the filled recipe card from RECIPE.md>

## Current state
<last verified snapshot>
```

## Legacy files

| File | Status |
|------|--------|
| `MAIN.md` | Moved — the core directive is now [CORE.md](CORE.md). Kept as a pointer so existing pins keep working. |
| `STYLES.md` | Moved — split into [RECIPE.md](RECIPE.md) (the card) and [GENRES.md](GENRES.md) (the specs). Kept as a pointer. |

## Design principles

These are the ideas the pack is built on, borrowed from the best prompt
packs in the AI-music space (Suno producer briefs, the Ableton MCP skill
ecosystem, Claude Code skill design) and adapted to a real DAW bridge:

1. **Read before write, always.** A write that is not read back is not
   done. This is the single rule that makes the AI trustworthy — it is
   also the rule the whole pack is built around.
2. **The gate is the deliverable.** Not "it sounds good" but a numbered,
   checkable condition with evidence.
3. **Numbers, not adjectives.** BPM, fader values, bar counts, swing
   percentages. "Professional" and "radio-ready" are banned; they carry
   no information and produce no music.
4. **Failure branches are written down.** Every step says what to do when
   it fails, so a failure does not end the session.
5. **One idea per step.** A workflow that changes fifteen things at once
   cannot be debugged and cannot be undone.
6. **Structure over prose.** Cards, tables, checklists, templates — not
   essays. An AI follows a table better than a paragraph.
7. **Diagnose before changing.** Name the symptom, classify it, change
   the minimum, verify.

## The quick version

If you only read one file, read [CORE.md](CORE.md). If you only run one
tool, run `fl_diagnostics()` first.

---

These are working documents, not rigid commands. The AI stays flexible
and works with you, not over you — but it never claims a state it has not
read back.
