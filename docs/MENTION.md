# Project Mentions and Backbone Credit

This project extends and builds upon work done by the original
[**karl-andres/fl-studio-mcp**](https://github.com/karl-andres/fl-studio-mcp)
repository, which served as the backbone (base codebase and architecture) for
this fork/derivative work.

## Backbone Project

| Attribute   | Value                                                        |
|-------------|--------------------------------------------------------------|
| Repository  | https://github.com/karl-andres/fl-studio-mcp                 |
| Role        | Backbone codebase - architecture, MIDI + JSON transport,     |
|             | piano-roll integration, and the original tool set            |
| License     | MIT                                                          |

The original project itself drew on:

- [calvinw/fl-studio-mcp](https://github.com/calvinw/fl-studio-mcp) - the
  Piano Roll integration approach (JSON files + keystroke triggering).

## What We Keep From the Backbone

- The hybrid **MIDI + JSON** communication architecture (command file,
  trigger note, controller script, response file).
- The **Piano Roll** (ComposeWithLLM / ControlPlane) scripting approach.
- The overall `scripts/`, `fl_controller/`, and `src/fl_studio_mcp/`
  repository layout and the original connection/tool modules.

## What Was Added / Changed In This Project

- **Reworked the transport layer** - dropped the keystroke-based DAW control
  path; all transport, mixer, channel, plugin, pattern, and step-sequencer
  actions now run through the MIDI controller script (`FLStudioMCP`).
- **Status, pattern, and step-sequencer capabilities were added:**
  - Pattern lifecycle: create / list / select / rename / clone / clear /
    set length (see `src/fl_studio_mcp/tools/patterns.py`).
  - Step-sequencer composition: per-step pitch, velocity, and pan on any
    channel, enabling melodies through the step sequencer
    (see `src/fl_studio_mcp/tools/sequencer.py`).
  - Tempo control and shuffle readback
    (see `src/fl_studio_mcp/tools/transport.py`).
  - Channel type introspection and coarse pitch control
    (see `src/fl_studio_mcp/tools/channels.py`).
- **Documentation overhaul** - a full `docs/` reference and a rewritten
  README.

## Third-Party Libraries

| Library | Purpose                                      |
|---------|----------------------------------------------|
| FastMCP | MCP server framework                         |
| mido    | MIDI message handling (Python)               |
| python-rtmidi | MIDI port backend for mido             |
| pynput  | Keystroke triggering for the Piano Roll path |

See the [README credits](../README.md#credits) for the full list.