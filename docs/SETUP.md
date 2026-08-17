# Setup

This guide installs **FL Studio MCP** from a clone of the repository.
There are two ways: the one-command installer, or manual setup. Both are
covered below for Windows and macOS.

## Prerequisites

- **FL Studio 20.7+** — the MIDI controller scripting API is required.
  The project has been tested on FL Studio 2025 (Windows).
- **Python 3.10+**
- **[uv](https://github.com/astral-sh/uv)** — installs dependencies and runs
  the server (avoid polluting your system Python).
- **A virtual MIDI port**:
  - Windows: [loopMIDI](http://www.tobias-erichsen.de/software/loopmidi.html)
    — install it, open it, and add one port (e.g. `FLStudioMCP`). loopMIDI
    auto-names ports `FLStudioMCP 0`, `FLStudioMCP 1`, etc.
  - macOS: IAC Driver — enable it in **Applications → Utilities → Audio MIDI
    Setup → IAC Driver → double-click → "Device is online"**.

## Option A — Installer (recommended)

```powershell
# Windows (PowerShell) — run once for execution policy, then install
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned -Force
.\install.ps1
```

```bash
# macOS / Linux
./install.sh
```

The installer:

1. Installs `uv` if missing.
2. Installs the Python dependencies (`uv sync`).
3. Copies `fl_controller/device_FLStudioMCP.py` into FL Studio's controller
   folder (`Hardware\FLStudioMCP\`).
4. Copies `scripts/ComposeWithLLM.pyscript` into FL Studio's
   **Piano roll scripts** folder.
5. Registers the server with Claude Desktop / Claude Code.

### 1. Copy the controller script

The controller script **must live in FL Studio's hardware settings folder**:

```
Windows: %USERPROFILE%\Documents\Image-Line\FL Studio\Settings\Hardware\FLStudioMCP\
macOS:   ~/Documents/Image-Line/FL Studio/Settings/Hardware/FLStudioMCP/
```

Copy `fl_controller/device_FLStudioMCP.py` from the repository into that
folder (create it if missing).

### 1b. Piano roll support (optional but recommended)

The piano-roll tools (`fl_send_notes`, `fl_send_chord`, ...) work through a
separate FL Studio script that is triggered with a hotkey:

1. Copy `scripts/ComposeWithLLM.pyscript` into:
   ```
   Windows: %USERPROFILE%\Documents\Image-Line\FL Studio\Settings\Piano roll scripts\
   macOS:   ~/Documents/Image-Line/FL Studio/Settings/Piano roll scripts/
   ```
2. Press **Update MIDI scripts** (or restart FL Studio).
3. In FL Studio: **Scripts → Piano roll → ComposeWithLLM** — right-click and
   assign the keyboard shortcut **Ctrl+Alt+Y** (Cmd+Opt+Y on macOS). `fl_trigger_script`
   and the piano-roll tools use this keystroke; without it they will warn but
   still attempt the JSON path.

The `ControlPlane.pyscript` (Ctrl+Alt+M) is the legacy controller —
`device_FLStudioMCP.py` has replaced it; it exists for backwards
compatibility only.

### 2. Install Python dependencies

```bash
cd /path/to/FL-MCP
uv sync
```

(Or `pip install -e .` if you prefer pip.)

### 3. Point FL Studio at the controller

1. Restart FL Studio — or press **Options → Update MIDI scripts** (no restart
   needed as long as FL Studio was open when you copied the file).
2. **Options → MIDI Settings**.
3. In the **Input** list, find your virtual MIDI port (e.g. `FLStudioMCP 1`).
4. In the **Controller type** dropdown, select `FL Studio MCP Controller`.
5. Enable the port (click the power icon so it is highlighted; `Send
   master sync` should be off).

When FL Studio starts the script you should see (in **View → Script output**):

```
FL Studio MCP Controller initialized
Command file: ...\Settings\Hardware\FLStudioMCP\mcp_command.json
```

### 4. Configure your MCP client

Add this to your client's MCP config (Claude Desktop: `claude_desktop_config.json`;
Claude Code: `~/.claude.json` under `mcpServers`):

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

- On macOS/Linux use `/path/to/FL-MCP` instead of a Windows path.
- Any MCP-capable client (Claude, Cursor, VS Code Copilot, etc.) can use the
  same `command`/`args` pair — just restart the client after editing.

### 5. Verify

Run the server manually to confirm it boots:

```bash
uv run fl-studio-mcp
```

Then, in your MCP client, ask something like:

> "Connect to FL Studio and show me the current tempo and transport state."

If that works, the bridge is live. If not, see
[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

## Notes

- The server uses `fl_connect` automatically via the fallback port list; the
  first successful MIDI port wins. See `src/fl_studio_mcp/utils/midi_connection.py`.
- The controller script hot-reloads itself every second — editing
  `device_FLStudioMCP.py` on disk is enough; no `Update MIDI scripts` needed
  (it re-imports when the version marker changes, see
  [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)).
- JSON files `mcp_command.json` / `mcp_response.json` are created inside
  `Settings/Hardware/FLStudioMCP/` at runtime — that is normal, not trash.