# Credits

FL Studio MCP v1.1.1 is built on the work of several open projects.

## Backbone

- **[karl-andres/fl-studio-mcp](https://github.com/karl-andres/fl-studio-mcp)**
  — the original "control FL Studio via JSON + MIDI trigger" idea which this
  project started from. The command-file/response-file round trip and the
  high-level tool layout follow that architecture.

## Piano roll integration

- **[calvinw/fl-studio-mcp](https://github.com/calvinw/fl-studio-mcp)** —
  the pattern of a hotkey-triggered script (Ctrl+Alt+Y) that reads note
  requests from JSON and writes them into the piano roll. The `fl_send_notes`
  / `fl_send_chord` tools inherit from this approach.

## Reference

- **[IL-Group/FL-Studio-API-Stubs](https://github.com/IL-Group/FL-Studio-API-Stubs)**
  — the authoritative stub files for FL Studio's Python scripting API; the
  basis for the raw module surface (`fl_raw_command`) and for the docs.

## Frameworks

- **[FastMCP](https://github.com/jlowin/fastmcp)** — MCP server framework.
- **[mido](https://github.com/mido/mido)** — MIDI port handling.

## FL Studio itself

FL Studio's built-in **MIDI controller scripting API** is the single point of
integration — everything the server does funnels through it. That API and the
DAW are property of [Image-Line](https://www.image-line.com).

## License note

This project is MIT-licensed (see [LICENSE](../LICENSE)). The sample packs
mentioned in development logs are third-party and not part of this
repository.