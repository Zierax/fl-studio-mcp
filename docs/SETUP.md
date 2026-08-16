# Setup Guide

Detailed, step-by-step setup for running the FL Studio MCP server. If you are
in a hurry, the one-command installers cover everything except the final FL
Studio MIDI settings.

## Prerequisites

| Requirement          | Version / Notes                              |
|----------------------|----------------------------------------------|
| FL Studio            | 20.7+ (needs the MIDI / Python scripting)    |
| Python               | 3.10+ (3.11-3.12 recommended)                |
| uv (recommended)     | https://github.com/astral-sh/uv              |
| Virtual MIDI port    | loopMIDI (Windows) or IAC Driver (macOS)     |
| MCP-capable client   | Claude Desktop, Claude Code, Cursor, ...     |

## Option A - One-Command Installer

### Windows

```powershell
# allow local scripts for this user (one-time)
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned -Force

# run the installer
.\install.ps1
```

### macOS / Linux

```bash
./install.sh
```

The installers will:

1. Install `uv` if missing.
2. Sync Python dependencies (`uv sync`).
3. Guide you through enabling virtual MIDI ports.
4. Copy `fl_controller/device_FLStudioMCP.py` into
   `<Documents>\Image-Line\FL Studio\Settings\Hardware\FLStudioMCP\`.
5. Copy the Piano Roll script (`scripts/ComposeWithLLM.pyscript`) into
   FL Studio's Piano roll scripts folder.
6. Optionally register the server with Claude Desktop / Claude Code.

After the installer, continue at
[Configure FL Studio MIDI Settings](#configure-fl-studio-midi-settings).

## Option B - Manual Installation

### 1. Install the Python dependencies

```bash
# uv (recommended)
uv sync

# or pip
pip install -e .
```

### 2. Enable a virtual MIDI port

The server and FL Studio communicate over a virtual MIDI cable.

**Windows - loopMIDI**

1. Download loopMIDI from https://www.tobias-erichsen.de/software/loopmidi.html
2. Install and launch it.
3. Add a new port named `FLStudioMCP` (any name works, but the server
   prefers ports containing `FLStudioMCP` or `loopMIDI`).
4. Keep loopMIDI running while using FL Studio.

**macOS - IAC Driver**

1. Open **Audio MIDI Setup** (Spotlight > "Audio MIDI Setup").
2. Press Cmd+2 (or Window > Show MIDI Studio).
3. Double-click **IAC Driver**, tick **Device is online**, press **Apply**.

### 3. Install the FL Studio scripts

**Controller script** (MIDI channel):

```bash
# Windows (PowerShell editing is optional; plain cmd works too)
mkdir "%USERPROFILE%\Documents\Image-Line\FL Studio\Settings\Hardware\FLStudioMCP"
copy fl_controller\device_FLStudioMCP.py "%USERPROFILE%\Documents\Image-Line\FL Studio\Settings\Hardware\FLStudioMCP\"

# macOS
mkdir -p ~/Documents/Image-Line/FL\ Studio/Settings/Hardware/FLStudioMCP
cp fl_controller/device_FLStudioMCP.py ~/Documents/Image-Line/FL\ Studio/Settings/Hardware/FLStudioMCP/
```

**Piano Roll script** (hotkey channel):

```bash
# Windows
copy scripts\ComposeWithLLM.pyscript "%USERPROFILE%\Documents\Image-Line\FL Studio\Settings\Piano roll scripts\"

# macOS
cp scripts/ComposeWithLLM.pyscript ~/Documents/Image-Line/FL\ Studio/Settings/Piano\ roll\ scripts/
```

Optionally `scripts/ControlPlane.pyscript` as well (a standalone,
keystroke-triggered alternative to the MIDI channel; it reads
`mcp_control_request.json` from the `Settings\Scripts` folder and is
triggered by the `Ctrl+Alt+M` / `Cmd+Opt+M` hotkey). The installers do
not copy it.

### 4. Configure FL Studio MIDI Settings

1. **Restart FL Studio** (midi scripts are scanned at startup).
2. **Options > MIDI Settings** (or press F10 and pick the MIDI tab).
3. Under **Input**, locate your virtual port:
   - loopMIDI -> something like `FLStudioMCP 1` (and a loopMIDI entry)
   - IAC Driver -> `IAC Driver Bus 1`
4. For the `FLStudioMCP 1` (virtual) port:
   - Set **Controller type** to **FL Studio MCP Controller**.
   - Make sure the port is highlighted/enabled.
5. If you also see a plain `loopMIDI` input entry, leave it at
   **`(generic controller)`** so it does not fight for the same messages.
6. Restart FL Studio once more, or hit **Update MIDI scripts** to pick up
   script changes without a restart.

> Tip: open **View > Script output** - on FL Studio with the controller
> loaded you should not see load/unload errors. A healthy controller prints
> nothing on load; errors usually mean a header mismatch (see
> [TROUBLESHOOTING.md](TROUBLESHOOTING.md)).

### 5. Register the MCP server with a client

**Claude Desktop**

- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "fl-studio": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "D:\\Axioms\\FL-MCP",
        "fl-studio-mcp"
      ]
    }
  }
}
```

(Windows paths need escaped backslashes; on macOS/Linux use
`/path/to/FL-MCP`.)

**Claude Code**

```bash
claude mcp add fl-studio -- uv run --directory /path/to/FL-MCP fl-studio-mcp
```

**Other MCP clients** (Cursor, Gemini CLI, Codex CLI, ...): the same
`command` / `args` pair applies; check the client's own MCP configuration
format. Only Claude Desktop / Claude Code are covered by the installer
scripts, and only those two are tested.

> Windows note: `uv run` may take a few seconds on first start. Keep the
> `--directory` argument pointing at the folder that contains
> `pyproject.toml`.

## Running the server manually

```bash
uv run fl-studio-mcp
# or, after pip install -e .
fl-studio-mcp
```

The server speaks MCP over stdio - it has no web UI. If you run it in a
terminal you will see it waiting for JSON-RPC requests from the client.

## Smoke test

1. Start FL Studio with a project open.
2. In your MCP client, call `fl_connect` - expect
   `Successfully connected to FL Studio via MIDI!`.
3. Call `fl_get_transport_status` - expect `is_playing: false` and a
   `position` value back.
4. Call `fl_get_tempo`, `fl_set_tempo(140)` to confirm the MIDI round-trip.

If 3 or 4 fail, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).