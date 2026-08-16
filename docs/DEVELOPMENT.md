# Development

Guide for working on the FL Studio MCP server itself.

## Prerequisites

- Python 3.10+ (project targets 3.10+; 3.12 is the tested install on
  Windows because of `python-rtmidi` wheels)
- `uv` (recommended): https://github.com/astral-sh/uv
- FL Studio with a working setup if you want to test against the real DAW

## Setup

```bash
# install dependencies incl. dev extras
uv sync --dev

# or pip
pip install -e ".[dev]"
```

## Commands

| Command | Purpose |
|---------|---------|
| `uv run fl-studio-mcp` | Run the MCP server (stdio) |
| `uv run ruff check .` | Lint (E, F, I, W rules, 100 col) |
| `uv run ruff check --fix .` | Lint + autofix |
| `uv run pytest` | Run tests |

## Repository layout

```
fl_controller/            FL Studio MIDI controller script (runs inside FL Studio)
scripts/                  FL Studio .pyscript files + installer helpers
src/fl_studio_mcp/        MCP server package
  server.py               FastMCP entry point, connection + resources
  tools/                  one module per tool category
  utils/                  transport plumbing (MIDI, trigger)
docs/                     documentation set
```

## Adding a new tool

1. **Controller side** (`fl_controller/device_FLStudioMCP.py`): add a
   `category.verb` handler in the action dispatch table, i.e. a function
   that uses the `midi` module (e.g. `patterns.patternCount`) and writes
   the result dict into the response.
   - Keep the header lines unchanged (`# name=...`, `# supportedDevices=...`).
   - Do not use `print()`; the script's output goes to FL Studio's Script
     output, not to the MCP server. Debug via the response JSON or an
     optional log file.
2. **Server side** (`src/fl_studio_mcp/tools/<category>.py`): add an
   `@mcp.tool()` function that calls
   `conn.send_command("category.verb", {...})` and unwraps the response
   into a friendly return value.
3. `ruff check` and `ruff check --fix`; ensure the controller file at least
   parses as Python 3 (it is Python 3 inside FL Studio).
4. Sync the controller to FL Studio:
   `<Documents>\Image-Line\FL Studio\Settings\Hardware\FLStudioMCP\` and
   **Update MIDI scripts** in MIDI Settings.
5. Update `docs/TOOLS.md`.

## Testing against the real DAW

There is no mocked API - integration tests require live FL Studio:

1. Start FL Studio, ensure the controller is loaded.
2. Run the server manually: `uv run fl-studio-mcp` (it blocks on stdio).
   For quick probing, use a small script that calls
   `FLConnection.send_command` directly:

   ```python
   from fl_studio_mcp.utils.connection import get_connection

   conn = get_connection()
   conn.ensure_connected()
   print(conn.send_command("transport.getStatus"))
   print(conn.send_command("patterns.count"))
   print(conn.send_command("transport.getTempo"))
   ```

3. After any controller change: **Update MIDI scripts** in FL Studio, or
   restart it (scripts in memory are stale otherwise).

## Style

- ruff, rules E/F/I/W, line length 100, target py310.
- Type hints everywhere (`| None` unions are fine on 3.10+).
- Tool docstrings describe args and return values - they are surfaced to
  the LLM by MCP, so keep them precise.
- ASCII-only comments/strings in `fl_controller/` (FL Studio's Python
  parser has historically been picky about encoding in script headers).