# FL Studio MCP Server

An [MCP](https://modelcontextprotocol.io) server that lets AI assistants
control **FL Studio** - transport, mixer, channel rack, plugin parameters,
pattern management, step-sequencer composition, and the piano roll - over a
virtual MIDI connection and FL Studio's own scripting APIs.

Built on the backbone of
[karl-andres/fl-studio-mcp](https://github.com/karl-andres/fl-studio-mcp)
(see [docs/MENTION.md](docs/MENTION.md)).

## Features

| Area | What you can do |
|------|-----------------|
| Transport | Play / pause / stop, record, seek, song length, loop mode, playback speed, tempo (BPM), shuffle readback |
| Mixer | Volume, pan, mute, solo (4 modes), record-arm, names, colors, stereo separation |
| Channel rack | List/inspect channels, select, route to mixer, real-time note trigger, volume/pan/mute/solo/name/color, channel type, coarse pitch |
| Patterns | Create, list, select, rename, clone, clear, set length |
| Step sequencer | Program **melodies** with per-step pitch, velocity, and pan; read back and clear patterns |
| Plugins | List parameters, get/set values, preset navigation (existing plugins only) |
| Piano roll | Add notes/chords with precise timing, delete notes, clear, read state |

## Documentation

The [docs/](docs/) folder is the full reference:

| Document | Contents |
|----------|----------|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | How the MIDI + JSON and Piano Roll channels work internally |
| [docs/SETUP.md](docs/SETUP.md) | Step-by-step installation on Windows and macOS |
| [docs/TOOLS.md](docs/TOOLS.md) | Every tool with arguments, defaults, and examples |
| [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | Fixes for connection/trigger problems |
| [docs/LIMITATIONS.md](docs/LIMITATIONS.md) | What the FL Studio API does and does not allow |
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | Working on the codebase, adding tools |
| [docs/MENTION.md](docs/MENTION.md) | Backbone project and credit attribution |

## Requirements

- **FL Studio 20.7+** (MIDI controller scripting API)
- **Python 3.10+**
- **uv** (recommended): https://github.com/astral-sh/uv
- A virtual MIDI port:
  - Windows: [loopMIDI](https://www.tobias-erichsen.de/software/loopmidi.html)
  - macOS: IAC Driver (built-in, must be enabled in Audio MIDI Setup)

## Quick Start

### One-command installer

```powershell
# Windows (PowerShell)
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned -Force   # once
.\install.ps1
```

```bash
# macOS / Linux
./install.sh
```

The installer installs uv + dependencies, copies the FL Studio scripts into
place, and registers the server with Claude Desktop/Claude Code.

### Then, in FL Studio

1. Restart FL Studio (or use **Update MIDI scripts** after copying scripts).
2. **Options > MIDI Settings**.
3. Under **Input**, select your virtual port (e.g. `FLStudioMCP 1`).
4. Set its **Controller type** to **FL Studio MCP Controller** and enable
   the port (highlight it).

> The full manual installation is in [docs/SETUP.md](docs/SETUP.md). If
> commands time out, start at [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

### MCP client configuration

```json
{
  "mcpServers": {
    "fl-studio": {
      "command": "uv",
      "args": ["run", "--directory", "D:\\Axioms\\FL-MCP", "fl-studio-mcp"]
    }
  }
}
```

(Adjust `--directory` to your clone; use `/path/to/FL-MCP` on macOS/Linux.)

This is a standard stdio MCP server, so any MCP-capable client can use the
same `command`/`args` pair. Only Claude Desktop and Claude Code are
covered by the installer scripts and are tested.

## Usage

Run manually for testing:

```bash
uv run fl-studio-mcp
```

Then, from your MCP client, call `fl_connect` first, then e.g.
`fl_get_transport_status`. See [docs/TOOLS.md](docs/TOOLS.md) for the full
tool catalog.

## Example Workflows

Natural-language prompts that work in any MCP client:

```
"Connect to FL Studio and show me the current tempo and transport state."
```

```
"Set the tempo to 140 BPM, then create a new pattern named 'Drop'."
```

```
"Program a kick pattern on channel 0 with kicks on steps 0, 4, 8, 12
 and a snare on steps 4 and 12 of channel 1."
```

```
"On channel 2, program a 16th-note melody: C4, E4, G4, A4 with
 velocity accents on the upbeats."
```

```
"Set mixer track 3 volume to 80% and pan it slightly left, then solo
 track 1."
```

```
"Add a C major arpeggio to the piano roll starting at beat 0: C4, E4,
 G4, C5, each a quarter note long."
```

```
"List the parameters of the plugin on channel 0 and set the filter
 cutoff to 50%."
```

## Limitations (summary)

- **Cannot load plugins or create channels** - instruments must already
  exist in the project; the server controls and programs what is there.
- **Cannot place playlist clips** - arrange patterns on the timeline
  yourself; pattern management is fully automated.
- Real-time note triggering is not persisted unless recording - use the
  step sequencer or piano roll tools for written music.

Details and workarounds in [docs/LIMITATIONS.md](docs/LIMITATIONS.md).

## Architecture (summary)

```
+-----------+     stdio      +----------------+   MIDI + JSON    +--------------------+
| MCP client| <------------> | FastMCP server | (note 127       |  FL Studio         |
| (Claude,  |                |                |  trigger,       |  controller script |
|  Cursor)  |                |                |  2s timeout)    |  transport, mixer, |
+-----------+                |                | --------------->|  channels,         |
                             |                |   JSON + hotkey  |  patterns, plugins |
                             |                | (Ctrl+Alt+Y,     |                    |
                             |                |  ~2s delay)      |  piano roll script |
                             +----------------+                  |  notes, chords     |
                                                                  +-------------------+
```

Full diagrams and message formats in
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Credits

- [karl-andres/fl-studio-mcp](https://github.com/karl-andres/fl-studio-mcp) - backbone project (see [docs/MENTION.md](docs/MENTION.md))
- [calvinw/fl-studio-mcp](https://github.com/calvinw/fl-studio-mcp) - piano roll integration approach
- [IL-Group/FL-Studio-API-Stubs](https://github.com/IL-Group/FL-Studio-API-Stubs) - FL Studio API reference
- [FastMCP](https://github.com/jlowin/fastmcp) - MCP server framework
- [mido](https://github.com/mido/mido) - MIDI library for Python

## License

MIT - copyright (c) 2026 **Ziad Salah (Zierax)**. See [LICENSE](LICENSE).