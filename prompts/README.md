# AI Prompts — Creative Direction for FL Studio MCP

Ready-to-paste guidance files. Append them **after** any user instruction so
the AI runs as a "creative director + hands-on executor" — not a command
runner: creative, hard-working, and verification-first (no hallucination).

## How to use

```
User: make a 140 BPM trap track ...
[paste the contents of prompts/MAIN.md here]
[also add prompts/WORKFLOW.md when working inside FL Studio MCP (most cases)]
```

| File | When to add |
|------|-------------|
| `MAIN.md` | **Always** — core rules: creativity + anti-laziness + anti-hallucination |
| `WORKFLOW.md` | When the work happens **inside FL Studio via MCP** |
| `STYLES.md` | When you want a ready-made style recipe (pick one, adapt) |

## Better: permanent configuration

If you use Claude Code or OpenCode, pin `MAIN.md` as permanent instructions
instead of pasting every time:

```json
// opencode.json or CLAUDE.md
{
  "instructions": ["prompts/MAIN.md", "prompts/WORKFLOW.md"]
}
```

Relax: these files are a working framework, not rigid commands. The AI stays
flexible and works with you, not over you.

## Contents

- `MAIN.md` — the core directive: mindset, creativity rules, anti-laziness
  rules, anti-hallucination rules.
- `WORKFLOW.md` — an executable roadmap for a full production session inside
  FL Studio MCP (from inspection to master) with verification checkpoints.
- `STYLES.md` — ready style recipes (dark trap, phonk, rage) with full
  specs, fully adaptable.