"""Locate the FL Studio hardware folder used by the MCP command channel.

The MCP server and the FL Studio controller script exchange commands and
responses through two files that live next to the controller script, inside
FL Studio's user data folder::

    <user data>/FL Studio/Settings/Hardware/FLStudioMCP/mcp_command.json
    <user data>/FL Studio/Settings/Hardware/FLStudioMCP/mcp_response.json

Finding that folder is not always trivial:

* on Windows the user data folder can be redirected into OneDrive, in which
  case the server (``~/Documents``) and FL Studio (``~/OneDrive/Documents``)
  disagree about the location,
* on macOS the documents folder can live inside iCloud Drive,
* FL Studio itself allows the user data folder to be moved anywhere.

This module resolves the folder from a list of candidates and lets the user
override it explicitly through the ``FL_STUDIO_MCP_DIR`` environment
variable.
"""

from __future__ import annotations

import os
from pathlib import Path

#: Name of the folder the MCP controller is installed into.
HARDWARE_FOLDER = "FLStudioMCP"

#: Name of the controller script FL Studio loads.
CONTROLLER_FILE = "device_FLStudioMCP.py"

#: Name of the command file written by the server.
COMMAND_FILE = "mcp_command.json"

#: Name of the response file written by the controller script.
RESPONSE_FILE = "mcp_response.json"

#: Environment variable that overrides the resolved folder.
ENV_OVERRIDE = "FL_STUDIO_MCP_DIR"


def _cloud_documents_roots(home: Path) -> list[Path]:
    """Return cloud-synced ``Documents`` roots that may hold the user data.

    OneDrive on Windows creates ``~/OneDrive`` (or ``~/OneDrive - <org>``)
    and iCloud on macOS uses ``~/Library/Mobile Documents``.
    """
    roots: list[Path] = []

    try:
        entries = sorted(home.iterdir())
    except OSError:
        entries = []

    for entry in entries:
        if not entry.is_dir():
            continue
        name = entry.name.lower()
        if name.startswith("onedrive"):
            roots.append(entry / "Documents")

    macos_icloud = home / "Library" / "Mobile Documents" / "com~apple~CloudDocs"
    if macos_icloud.is_dir():
        roots.append(macos_icloud / "Documents")

    return roots


def candidate_directories() -> list[Path]:
    """Return every folder that could hold the MCP controller script.

    The order matters: the first entry that actually contains the controller
    script wins, so the most likely locations come first.
    """
    home = Path.home()
    candidates: list[Path] = []

    override = os.environ.get(ENV_OVERRIDE)
    if override:
        candidates.append(Path(override).expanduser())

    # The documented default location (Windows and macOS).
    candidates.append(
        home / "Documents" / "Image-Line" / "FL Studio" / "Settings" / "Hardware" / HARDWARE_FOLDER
    )

    # Cloud redirected user data folders.
    for root in _cloud_documents_roots(home):
        candidates.append(
            root / "Image-Line" / "FL Studio" / "Settings" / "Hardware" / HARDWARE_FOLDER
        )

    # FL Studio on Linux (Wine/Proton) keeps its settings here.
    candidates.append(home / ".fl-studio" / "Settings" / "Hardware" / HARDWARE_FOLDER)

    # De-duplicate while preserving order.
    unique: list[Path] = []
    for candidate in candidates:
        if candidate not in unique:
            unique.append(candidate)
    return unique


def resolve_hardware_dir(create: bool = False) -> Path:
    """Return the folder that holds the MCP controller script.

    A candidate is only accepted when it actually contains the controller
    script, which proves FL Studio loads the controller from there.  When no
    candidate matches, the default location is returned so the folder can be
    created for a fresh install.
    """
    candidates = candidate_directories()

    for candidate in candidates:
        try:
            if (candidate / CONTROLLER_FILE).is_file():
                return candidate
        except OSError:
            continue

    resolved = candidates[0] if candidates else Path.home() / HARDWARE_FOLDER
    if create:
        try:
            resolved.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
    return resolved


def command_path(hardware_dir: Path | None = None) -> Path:
    """Return the path of the command file."""
    base = hardware_dir if hardware_dir is not None else resolve_hardware_dir()
    return base / COMMAND_FILE


def response_path(hardware_dir: Path | None = None) -> Path:
    """Return the path of the response file."""
    base = hardware_dir if hardware_dir is not None else resolve_hardware_dir()
    return base / RESPONSE_FILE
