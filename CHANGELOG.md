# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
uses [semantic versioning](https://semver.org/).

The controller script carries its own `MCP_VERSION` hot-reload counter,
which is independent of the package version — see
[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md#versioning--releases).

## [v1.2.0] — 2026-11-14

### Added

- **FL Studio 21 and older are supported.** The controller script no
  longer imports the standard library: it carries a self-contained JSON
  codec, string-based path helpers and `__import__`-based module probing.
  FL Studio embeds a stripped CPython whose `Shared/Python/Lib` contains
  only `midi.py` and `utils.py`, so `import json` used to abort the
  controller during initialisation. Fixes [#2](https://github.com/Zierax/fl-studio-mcp/issues/2).
- **`fl_diagnostics`** — reports the MIDI port, the resolved command
  folder, the FL API version, the interpreter's builtin modules and which
  standard library modules are importable, in one call.
- **`fl_connect(port_name=, data_dir=)`** — force a specific MIDI port or
  command folder.
- **`utils/ports.py`** — scores the available MIDI ports so the bridge
  port wins over a software synth.
- **`utils/paths.py`** — resolves FL Studio's hardware folder, including
  OneDrive/iCloud-redirected user data, with `FL_STUDIO_MCP_DIR` as an
  override.
- **`system.diagnostics`** action on the controller side.
- **A rebuilt prompt pack** in `prompts/`: `CORE.md`, `BRIDGE.md`,
  `WORKFLOW.md`, `RECIPE.md`, `GENRES.md`, `ARRANGEMENT.md`, `THEORY.md`,
  `MIXING.md`, `QC.md`. `MAIN.md` and `STYLES.md` remain as pointers.
- **432 tests** — unit tests for the controller script, the JSON codec,
  the port scoring, the path resolution and the command channel, plus an
  end-to-end test that runs the bridge on a stripped (FL Studio 21)
  interpreter.
- A `logs/` folder for generated run artifacts, and a `logs/README.md`
  explaining them.

### Fixed

- **`install.ps1` was unusable.** 125 NUL bytes had replaced every `-`,
  so the Windows installer was not valid PowerShell.
- **Failures were reported as successes.** The controller answered every
  command with `"success": true` even when the handler returned an error,
  and every tool checked `success` before looking at `error`.
- **The generic command layer was dead.** `_convert_arg()` looked its
  argument up with the argument *kind* instead of its *name*, so every
  `GENERIC_COMMANDS` entry raised `KeyError`.
- **A late response could answer the wrong command.** Requests now carry
  an id that the controller echoes back.
- **Commands could be read half-written.** The command file is written
  atomically and encoded as UTF-8.
- **The wrong MIDI port was selected** — `output_ports[0]` was used.
- **The command folder was assumed**, so a relocated or cloud-redirected
  FL Studio user data folder silently broke the bridge.
- **`fl_connect(port_name=…)` was ignored** — the preference never
  reached the MIDI layer.
- **The pattern context was not restored** in `fl_set_channel_steps`.
- **Broken relative links** inside `docs/` (they pointed at `docs/docs/…`).
- **CRLF line endings** broke the POSIX shell installers
  (`bad interpreter: /bin/bash^M`).

### Changed

- The repository now passes `ruff check` (it did not before) and every
  text file ends with a newline.
- The documentation no longer hard-codes the author's checkout path.
- `docs/DEVELOPMENT.md` describes the versioning accurately and lists the
  checks a release has to pass.

## [v1.1.1] — 2026-08-18

### Fixed

- Removed a duplicate `fl_channel_step_param` registration.

## [v1.1.0] — 2026-08-17

### Added

- The first AI prompt pack: `MAIN.md`, `WORKFLOW.md` and `STYLES.md`.

### Fixed

- Tempo units in the transport handlers (EPB vs BPM) and the
  `raw.call` result key.

## [v1.0.0] — 2026-08-17

- First public release: the full FL Studio scripting surface (transport,
  mixer, channel rack, patterns, plugins, step sequencer, piano roll,
  playlist), the MIDI + JSON bridge, and the Claude/Codex MCP
  configuration.

[Unreleased]: https://github.com/Zierax/fl-studio-mcp/compare/v1.2.0...HEAD
[v1.2.0]: https://github.com/Zierax/fl-studio-mcp/compare/v1.1.1...v1.2.0
[v1.1.1]: https://github.com/Zierax/fl-studio-mcp/compare/v1.1.0...v1.1.1
[v1.1.0]: https://github.com/Zierax/fl-studio-mcp/compare/v1...v1.1.0
[v1.0.0]: https://github.com/Zierax/fl-studio-mcp/releases/tag/v1
