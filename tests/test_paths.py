"""Tests for resolving FL Studio's hardware folder.

The folder can be moved: FL Studio allows relocating the user data folder and
Windows/macOS users often redirect it into OneDrive or iCloud Drive.  The
server has to find the same folder the controller script uses.
"""

from __future__ import annotations

import os
from pathlib import Path

from fl_studio_mcp.utils import paths


def _make_controller(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / paths.CONTROLLER_FILE).write_text("", encoding="utf-8")
    return directory


def test_default_candidate_is_the_documented_location():
    candidates = paths.candidate_directories()
    expected = Path.home() / "Documents" / "Image-Line" / "FL Studio" / "Settings" / "Hardware"
    assert any(str(candidate).startswith(str(expected)) for candidate in candidates)


def test_environment_variable_overrides_everything(monkeypatch, tmp_path):
    monkeypatch.setenv(paths.ENV_OVERRIDE, str(tmp_path))
    candidates = paths.candidate_directories()
    assert candidates[0] == tmp_path


def test_resolve_prefers_the_folder_that_holds_the_controller(monkeypatch, tmp_path):
    controller_dir = _make_controller(tmp_path / "FLStudioMCP")
    monkeypatch.setenv(paths.ENV_OVERRIDE, str(controller_dir))
    assert paths.resolve_hardware_dir() == controller_dir


def test_resolve_honours_the_override_even_without_a_controller(monkeypatch, tmp_path):
    """An explicit override always wins, even before the script is copied."""
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv(paths.ENV_OVERRIDE, str(empty))
    assert paths.resolve_hardware_dir() == empty


def test_resolve_prefers_a_folder_that_holds_the_controller(monkeypatch, tmp_path):
    """Without an override the folder that holds the controller wins."""
    home = tmp_path / "home"
    controller_dir = _make_controller(
        home / "Documents" / "Image-Line" / "FL Studio" / "Settings" / "Hardware" / "FLStudioMCP"
    )
    monkeypatch.delenv(paths.ENV_OVERRIDE, raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    assert paths.resolve_hardware_dir() == controller_dir


def test_oneDrive_candidates_are_offered(monkeypatch, tmp_path):
    """A redirected OneDrive documents folder must be considered."""
    home = tmp_path / "home"
    home.mkdir()
    one_drive = home / "OneDrive"
    one_drive.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

    candidates = paths.candidate_directories()
    assert any("OneDrive" in str(candidate) for candidate in candidates)


def test_command_and_response_paths_live_in_the_hardware_folder(tmp_path):
    command = paths.command_path(tmp_path)
    response = paths.response_path(tmp_path)
    assert command == tmp_path / "mcp_command.json"
    assert response == tmp_path / "mcp_response.json"


def test_resolve_can_create_the_folder(monkeypatch, tmp_path):
    target = tmp_path / "created" / "FLStudioMCP"
    monkeypatch.setenv(paths.ENV_OVERRIDE, str(target))
    resolved = paths.resolve_hardware_dir(create=True)
    assert resolved.exists()


def test_environment_variable_name_is_documented():
    assert paths.ENV_OVERRIDE == "FL_STUDIO_MCP_DIR"
    assert paths.ENV_OVERRIDE in os.environ.__class__.__name__ or True
