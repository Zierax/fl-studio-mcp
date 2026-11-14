# Development

Working on this repo: adding tools, testing against FL Studio, and releasing.

## Layout reminder

```
fl_controller/device_FLStudioMCP.py   ← runs INSIDE FL Studio (the "remote")
src/fl_studio_mcp/tools/*.py          ← one file per tool group (the "client")
src/fl_studio_mcp/utils/              ← MIDI + JSON bridge
src/fl_studio_mcp/server.py           ← MCP entry point
tests/                                ← pytest suite (no FL Studio needed)
```

The interesting rule: **tools are thin wrappers**. The real work happens in
the controller script, which executes FL Studio's own API.

## Adding a new tool (typical case)

Suppose you want `fl_get_last_peak(channel)`.

### 1. Confirm the API can do it

```python
# any assistant or script:
fl_api_list_functions("channels", "get")   # lists every get* function
fl_raw_command("channels", "getLastPeak", [0])
```

If `fl_raw_command` already returns what you want, skip to step 3.

### 2. Add a handler in the controller first

In `fl_controller/device_FLStudioMCP.py`:

```python
elif action == "channels.getLastPeak":
    return channels.getLastPeak(int(params.get("channel", 0)))
```

Copy the file to FL's `Settings/Hardware/FLStudioMCP/` — **and bump the
version marker** so FL Studio reloads it:

```python
MCP_VERSION = 4   # was 3
```

No restart needed; the script hot-reloads on its 1-second idle tick.

### 3. Register the client-side tool

In `src/fl_studio_mcp/tools/channels.py` (or wherever it belongs):

```python
@mcp.tool()
def fl_get_last_peak(channel: int) -> float:
    """Peak level readback for a channel."""
    result = conn.send_command("channels.getLastPeak", {"channel": channel})
    return result.get("value", 0.0)
```

Make sure the `register_*_tools(mcp, conn)` function includes it, then `uv
sync && uv run fl-studio-mcp` to smoke-test.

## Running the tests

```bash
uv sync
uv run pytest
```

The suite needs neither FL Studio nor a MIDI driver:

| File | What it covers |
|------|----------------|
| `tests/test_device_script.py` | Loads the controller script with `json`, `os`, `pathlib`, `importlib` … blocked — the FL Studio 21 environment — and exercises dispatch, path discovery and the diagnostics action. |
| `tests/test_json_codec.py` | The self-contained JSON codec, compared byte-for-byte against the standard library. |
| `tests/test_ports.py` | MIDI port scoring (a software synth must never win over the bridge). |
| `tests/test_paths.py` | Resolution of FL Studio's hardware folder, including OneDrive redirection and the env override. |
| `tests/test_midi_connection.py` | The command/response round-trip with a fake `mido`. |
| `tests/test_server.py` | The MCP server boots and exposes the documented tools. |
| `tests/test_docs.py` | The docs: valid JSON snippets, no hard coded local paths, no broken links, consistent versions. |

`tests/conftest.py` holds the fixtures — most importantly the stub FL API
modules and the import blocker that reproduces FL Studio's stripped
interpreter.

## Testing against a live FL Studio

Unit tests cannot tell you whether FL Studio actually reacted, so the manual
flow is:

1. Open a scratch project in FL Studio (or use your working one).
2. Connect (`fl_connect`), then exercise the new tool.
3. Watch `Script output` in FL Studio for controller errors.
4. If the controller script changed, verify the reload printout:
   `[MCP] hot-reloaded to version N`.
5. Run `fl_diagnostics` to confirm both halves agree on the port and the
   command folder.

## Versioning & releases

The project uses **semantic versioning with a single v-prefixed tag**.
Examples: `v1`, `v1.1`, `v2` — and no 10/11-style ad-hoc numbers anywhere.

Three version numbers exist; keep them in sync:

| Where | What it is |
|-------|------------|
| `fl_controller/device_FLStudioMCP.py` → `MCP_VERSION` | The hot-reload marker. **Must change on every controller edit.** Use the same number as the tag (`1`, `1.1`, ...). |
| `pyproject.toml` → `version` | The Python package version (`1.1.1`). |
| Git tag | The release, e.g. `v1`. |

Release checklist:

```bash
# 1. bump MCP_VERSION in device_FLStudioMCP.py + version in pyproject.toml
# 2. update docs if the tool surface changed (docs/TOOLS.md!)
uv sync                       # keep the lockfile fresh
uv run fl-studio-mcp          # boots? then:
git add -A && git commit -m "release: v1"
git tag v1                    # tag the release
git push origin master --tags # then publish a GitHub release from the tag
```

Notes:

- **Never skip the `MCP_VERSION` bump** — stale controllers silently run old
  code and the symptoms look like "FL ignores everything".
- Keep `docs/TOOLS.md` accurate; it is the contract users rely on.
- Personal/dev scratch scripts do **not** belong in this repo — keep them
  outside (e.g. a `FL-MCP-DEV` folder) so the release stays clean.

## Coding style

- `ruff` is configured in `pyproject.toml` (line-length 100):
  ```bash
  uv run ruff check src/ tests/ fl_controller/device_FLStudioMCP.py
  ```
- The controller script runs inside FL Studio's **stripped** Python — it may
  use **builtins only** (`sys`, `time` and the FL modules). No standard
  library module (`json`, `os`, `pathlib`, `importlib`, ...) and no external
  pip dependency in `fl_controller/`. `tests/test_device_script.py` fails the
  build if that rule is broken.
- All client tools return JSON-safe types (dicts, lists, floats, strings).
- User-facing tool descriptions should state units (0.0–1.0, 0-based index)
  so models don't guess.
