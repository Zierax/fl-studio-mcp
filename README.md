# FL Studio MCP

An [MCP](https://modelcontextprotocol.io) server that lets AI assistants
**control FL Studio fully** — transport, mixer, channel rack, plugins,
patterns, step sequencer, piano roll, and the entire FL scripting API —
over a virtual MIDI trigger + JSON command channel.

> **Version 1.2.0** · MIT License · © 2026 Ziad Salah (Zierax)

[![Listed on MCP Market](https://mcpmarket.com/badge/server/fl-studio-3.svg)](https://mcpmarket.com/server/fl-studio-3?utm_source=readme&utm_medium=badge)

---

## Why this exists

FL Studio's scripting API is powerful but unreachable from Python. This
project bridges the gap:

```
MCP client (Claude, Cursor, ...)
        │  stdio (JSON-RPC)
        ▼
   FastMCP server (Python)          ── the 164 tools
        │  writes mcp_command.json + triggers MIDI note 127
        ▼
   FL Studio controller script      ── runs INSIDE FL Studio,
        │  executes the FL scripting API, writes mcp_response.json
        ▼
   FL Studio project                ── the DAW itself
```

## Features

| Area | Capabilities |
|------|--------------|
| **Transport** | Play, stop, record, song position/length, loop mode, playback speed, tempo, shuffle |
| **Mixer** | Volume, pan, mute, solo, arm, name, color, stereo separation; routing, sends, EQ, FX slots, peaks |
| **Channel rack** | List/inspect/select channels, live note triggering, volume/pan/mute/solo/name/color, pitch, step sequences, shuffle |
| **Patterns** | Create, list, select, rename, clone, clear, set length |
| **Plugins** | Name, parameter list/get/set, presets, colors |
| **Step sequencer** | Read/write/clear step patterns with per-step pitch, velocity, pan |
| **Piano roll** | Add notes/chords (exact timing), delete, clear, read state |
| **Playlist** | Track names, colors, mute/solo/select, full playlist state |
| **Advanced** | Raw access to every function of every FL API module, undo history, project info, markers, device info, UI automation hints |

## Requirements

- **FL Studio 20.7+** on Windows or macOS (tested on FL Studio 2025 / Windows
  and FL Studio 21.0.3 / Windows)
- **Python 3.10+**
- **[uv](https://github.com/astral-sh/uv)** (recommended package manager)
- A virtual MIDI port:
  - Windows: [loopMIDI](https://www.tobias-erichsen.de/software/loopmidi.html)
  - macOS: IAC Driver (enable it in Audio MIDI Setup)

> **FL Studio 21 and older:** FL Studio embeds a *stripped* CPython interpreter
> without the standard library, so the controller script uses nothing but
> builtins — no `json`, `os`, `pathlib` or `importlib`. Nothing extra has to be
> installed for those versions.

## Quick start

### 1. Install the controller script in FL Studio

Run the installer, or copy `fl_controller/device_FLStudioMCP.py` manually (see
[docs/SETUP.md](docs/SETUP.md) for both options):

```powershell
# Windows (PowerShell)
.\install.ps1
```

```bash
# macOS / Linux
./install.sh
```

### 2. Point FL Studio at the script

1. Restart FL Studio (or press **Options → Update MIDI scripts**).
2. **Options → MIDI Settings** → under **Input**, select your virtual port
   (e.g. `FLStudioMCP 1`).
3. Set its **Controller type** to `FL Studio MCP Controller` and enable the
   port.

### 3. Connect the server

Add this to your MCP client's configuration file (Claude Desktop:
`claude_desktop_config.json`; Claude Code: `~/.claude.json`):

```json
{
  "mcpServers": {
    "fl-studio": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/FL-MCP", "fl-studio-mcp"]
    }
  }
}
```

Replace `/path/to/FL-MCP` with the folder you cloned the repository into. On
Windows use a path with escaped backslashes, e.g.
`"D:\\Projects\\FL-MCP"`. The server is a standard stdio MCP server — any MCP
client can use it.

Then talk to it in natural language:

> "Connect to FL Studio, set the tempo to 140 BPM and create a pattern named 'Drop'."

> "Program a kick on steps 0, 4, 8, 12 of channel 0 and a snare on steps 4 and 12 of channel 1."

> "Set mixer track 3 volume to 80%, pan it slightly left, and solo track 1."

### 4. Check the bridge

Ask your client to run `fl_diagnostics`. It reports the MIDI port in use, the
folder the command files live in, and the FL Studio API version — the fastest
way to see what is misconfigured.

## Documentation

Everything lives in [docs/](docs/):

| Document | Contents |
|----------|----------|
| [docs/SETUP.md](docs/SETUP.md) | Full installation: Windows, macOS, manual vs installer, first run |
| [docs/TOOLS.md](docs/TOOLS.md) | The complete tool catalog with arguments and examples |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | How the MIDI + JSON bridge and hot-reload work |
| [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | Fixes for the problems people actually hit |
| [docs/LIMITATIONS.md](docs/LIMITATIONS.md) | What the FL Studio API can and cannot do |
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | Adding tools, versioning, testing, releasing |
| [docs/MENTION.md](docs/MENTION.md) | Credits and backbone projects |

## AI prompt pack

[prompts/](prompts/) turns the server into a producer rather than a command
runner: a standing directive, the tool map and read-back pairings, the
nine-phase production workflow, style specs for twelve genres, and
checkable quality gates.

| File | What it does |
|------|--------------|
| [prompts/CORE.md](prompts/CORE.md) | The standing directive — role, verification invariant, creative rules |
| [prompts/BRIDGE.md](prompts/BRIDGE.md) | Tool map, FL API limits, failure branches, recovery |
| [prompts/WORKFLOW.md](prompts/WORKFLOW.md) | The nine production phases, with a gate at the end of each |
| [prompts/RECIPE.md](prompts/RECIPE.md) | The style card and a worked example |
| [prompts/GENRES.md](prompts/GENRES.md) | Twelve style specs with real numbers |
| [prompts/ARRANGEMENT.md](prompts/ARRANGEMENT.md) | Energy curves, section lengths, layer logic, hooks |
| [prompts/THEORY.md](prompts/THEORY.md) | Key and mode, bass writing, melody craft |
| [prompts/MIXING.md](prompts/MIXING.md) | Balance → pan → routing → EQ → FX → automation → loudness |
| [prompts/QC.md](prompts/QC.md) | Quality gates and the diagnostic table for a weak result |

## Known limitations (summary)

- The FL Studio scripting API **cannot create channels or load audio files** —
  the server controls whatever already exists in the project.
- **Playlist clips cannot be placed programmatically** — pattern management is
  fully automated, arranging on the timeline is not.
- Live-triggered notes are not persisted unless recording is on; for written
  music use the step sequencer or piano roll tools.

Full details: [docs/LIMITATIONS.md](docs/LIMITATIONS.md).

## Project layout

```
fl_controller/
  device_FLStudioMCP.py   ← the script that runs inside FL Studio (hot-reloadable)
src/fl_studio_mcp/
  server.py               ← MCP entry point + connection tools
  utils/                  ← MIDI trigger, JSON command channel, connection,
                            port scoring, path resolution
  tools/                  ← 9 tool groups: transport, mixer, channels, patterns,
                             plugins, sequencer, piano_roll, advanced, fullcontrol
scripts/                  ← installer helpers, scenario harness, benchmark
prompts/                  ← the AI prompt pack (directive, workflow, styles, gates)
tests/                    ← pytest suite (controller script, JSON codec, ports, prompts)
logs/                     ← run artifacts: execution logs, scenario and benchmark reports
docs/                     ← this documentation
install.ps1 / install.sh  ← one-command installers
```

## Development

```bash
uv sync
uv run pytest            # unit tests (no FL Studio required)
uv run ruff check src/ tests/ fl_controller/device_FLStudioMCP.py
```

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for the full workflow.

## Credits

Built on the backbone of
[karl-andres/fl-studio-mcp](https://github.com/karl-andres/fl-studio-mcp)
(piano roll integration inspired by
[calvinw/fl-studio-mcp](https://github.com/calvinw/fl-studio-mcp)). FL API
reference: [IL-Group/FL-Studio-API-Stubs](https://github.com/IL-Group/FL-Studio-API-Stubs).
See [docs/MENTION.md](docs/MENTION.md).

## License

MIT — see [LICENSE](LICENSE).
