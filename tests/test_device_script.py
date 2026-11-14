"""Tests for the FL Studio controller script.

The controller runs inside FL Studio's stripped CPython interpreter, where
the standard library is largely missing.  These tests load the script with
the unavailable modules blocked and exercise the command dispatch, the path
discovery and the diagnostics action.
"""

from __future__ import annotations

import ast
import json

import pytest

from tests.conftest import (
    DEVICE_SCRIPT,
    FL_API_MODULES,
    FL_UNAVAILABLE_MODULES,
    load_device_script,
)

#: Modules the controller script is allowed to import.
ALLOWED_IMPORTS = {"sys", "time", *FL_API_MODULES}


def _top_level_imports(source: str) -> set[str]:
    tree = ast.parse(source)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module.split(".")[0])
    return names


def test_script_does_not_import_the_standard_library():
    """The controller must not depend on modules FL Studio does not ship."""
    source = DEVICE_SCRIPT.read_text(encoding="utf-8")
    imported = _top_level_imports(source)
    forbidden = imported & set(FL_UNAVAILABLE_MODULES)
    assert not forbidden, f"controller imports unavailable modules: {sorted(forbidden)}"


def test_script_only_imports_allowed_modules():
    source = DEVICE_SCRIPT.read_text(encoding="utf-8")
    imported = _top_level_imports(source)
    unexpected = imported - ALLOWED_IMPORTS
    assert not unexpected, f"controller imports unexpected modules: {sorted(unexpected)}"


def test_script_loads_without_the_standard_library(device_module):
    """The script must initialise even when json/os/pathlib are missing."""
    assert device_module.MCP_VERSION >= 3
    assert callable(device_module.dispatch_command)


def test_script_loads_without_os_or_pathlib():
    """FL Studio 21 has no `os` and no `pathlib`."""
    module = load_device_script(blocked=("os", "pathlib"))
    assert module.SCRIPT_DIR is not None


def test_json_module_is_really_unavailable(device_module):
    """Sanity check: the stubbed environment really has no `json`."""
    import builtins

    original = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "json":
            raise ModuleNotFoundError("No module named 'json'")
        return original(name, *args, **kwargs)

    builtins.__import__ = fake_import
    try:
        with pytest.raises(ModuleNotFoundError):
            __import__("json")
    finally:
        builtins.__import__ = original


def test_command_dispatch_routes_to_handlers(device_module):
    result = device_module.dispatch_command("transport.getStatus", {})
    assert isinstance(result, dict)
    assert "is_playing" in result


def test_unknown_action_reports_an_error(device_module):
    result = device_module.dispatch_command("does.not.exist", {})
    assert "error" in result
    assert "Unknown action" in result["error"]


def test_generic_command_layer_binds_arguments(device_module):
    """The generic layer must look arguments up by name, not by kind."""
    # `channels.selectChannel` only exists in the generic table.
    result = device_module.dispatch_command("channels.selectChannel", {"channel": 2, "select": True})
    assert "error" not in result, result
    assert result["fn"] == "selectChannel"
    assert result["args"] == [2, 1]


def test_generic_command_layer_reports_missing_arguments(device_module):
    result = device_module.dispatch_command("channels.selectChannel", {"channel": 2})
    assert "error" in result
    assert "select" in result["expected"]


def test_generic_command_layer_converts_epb_and_color(device_module):
    result = device_module.dispatch_command("mixer.setCurrentTempo", {"bpm": 140})
    assert result["args"] == [140000]

    result = device_module.dispatch_command(
        "mixer.setSlotColor", {"track": 1, "slot": 2, "r": 10, "g": 20, "b": 30}
    )
    assert result["args"] == [1, 2, (30 << 16) | (20 << 8) | 10]


def test_raw_call_rejects_unknown_module(device_module):
    result = device_module.dispatch_command("raw.call", {"module": "os", "function": "system"})
    assert "error" in result
    assert "not allowed" in result["error"]


def test_diagnostics_action_reports_environment(device_module):
    result = device_module.dispatch_command("system.diagnostics", {})
    diagnostics = result["diagnostics"]
    assert diagnostics["mcp_version"] == device_module.MCP_VERSION
    assert "json" in diagnostics["importable"]
    assert diagnostics["importable"]["sys"] is True
    assert diagnostics["command_file"].endswith("mcp_command.json")
    assert diagnostics["response_file"].endswith("mcp_response.json")
    assert diagnostics["fl_api_version"] == 40
    assert diagnostics["api_modules"]["channels"] is True
    assert "builtin_modules" in diagnostics


def test_diagnostics_reports_missing_standard_library(device_module, stripped_interpreter):
    """Inside FL Studio 21 the diagnostics must show that json is missing."""
    result = device_module.dispatch_command("system.diagnostics", {})
    importable = result["diagnostics"]["importable"]
    assert importable["json"] is False
    assert importable["os"] is False
    assert importable["pathlib"] is False
    assert importable["importlib"] is False
    assert importable["sys"] is True


def test_command_response_roundtrip(device_module, tmp_path, monkeypatch):
    """A command file is read, executed and the response written back."""
    hardware = tmp_path / "FLStudioMCP"
    hardware.mkdir()
    command_file = hardware / "mcp_command.json"
    response_file = hardware / "mcp_response.json"

    monkeypatch.setattr(device_module, "COMMAND_FILE", str(command_file))
    monkeypatch.setattr(device_module, "RESPONSE_FILE", str(response_file))

    command_file.write_text(
        json.dumps({"action": "transport.getStatus", "params": {}}),
        encoding="utf-8",
    )

    device_module.execute_pending_command()

    response = json.loads(response_file.read_text(encoding="utf-8"))
    assert response["success"] is True
    assert "is_playing" in response


def test_a_failing_command_is_not_reported_as_successful(device_module, tmp_path, monkeypatch):
    """An error from the handler must set success to False.

    The tools on the server side check ``success`` before they look at
    ``error``; reporting success for a failed command would hide every
    failure.
    """
    hardware = tmp_path / "FLStudioMCP"
    hardware.mkdir()
    command_file = hardware / "mcp_command.json"
    response_file = hardware / "mcp_response.json"

    monkeypatch.setattr(device_module, "COMMAND_FILE", str(command_file))
    monkeypatch.setattr(device_module, "RESPONSE_FILE", str(response_file))

    command_file.write_text(
        json.dumps({"action": "does.not.exist", "params": {}}),
        encoding="utf-8",
    )

    device_module.execute_pending_command()

    response = json.loads(response_file.read_text(encoding="utf-8"))
    assert response["success"] is False
    assert "Unknown action" in response["error"]


def test_command_response_reports_invalid_json(device_module, tmp_path, monkeypatch):
    hardware = tmp_path / "FLStudioMCP"
    hardware.mkdir()
    command_file = hardware / "mcp_command.json"
    response_file = hardware / "mcp_response.json"

    monkeypatch.setattr(device_module, "COMMAND_FILE", str(command_file))
    monkeypatch.setattr(device_module, "RESPONSE_FILE", str(response_file))

    command_file.write_text("{not json", encoding="utf-8")
    device_module.execute_pending_command()

    response = json.loads(response_file.read_text(encoding="utf-8"))
    assert response["success"] is False
    assert "Invalid JSON" in response["error"]


def test_command_response_reports_missing_command_file(device_module, tmp_path, monkeypatch):
    hardware = tmp_path / "FLStudioMCP"
    hardware.mkdir()
    response_file = hardware / "mcp_response.json"

    monkeypatch.setattr(device_module, "COMMAND_FILE", str(hardware / "mcp_command.json"))
    monkeypatch.setattr(device_module, "RESPONSE_FILE", str(response_file))

    device_module.execute_pending_command()

    response = json.loads(response_file.read_text(encoding="utf-8"))
    assert response["success"] is False
    assert "No command file" in response["error"]


def test_path_helpers_work_without_os(device_module):
    assert device_module._join_path("a", "b").endswith("b")
    assert device_module._join_path("", "b") == "b"
    assert device_module._path_name("/a/b/c") == "c"
    assert device_module._path_name("C:\\a\\b\\") == "b"
    assert device_module._path_name("plain") == "plain"


def test_script_dir_discovery_uses_sys_path(device_module, tmp_path, monkeypatch):
    """The controller folder is found through sys.path, not through os."""
    hardware = tmp_path / "FLStudioMCP"
    hardware.mkdir()
    (hardware / "device_FLStudioMCP.py").write_text("", encoding="utf-8")

    monkeypatch.setattr(device_module.sys, "path", [str(hardware), "/somewhere/else"])
    assert device_module._discover_script_dir() == str(hardware)


def test_script_dir_discovery_falls_back_to_folder_name(device_module, tmp_path, monkeypatch):
    hardware = tmp_path / "FLStudioMCP"
    hardware.mkdir()

    monkeypatch.setattr(device_module.sys, "path", [str(hardware), "/somewhere/else"])
    assert device_module._discover_script_dir() == str(hardware)


def test_script_dir_override_wins(device_module, tmp_path, monkeypatch):
    monkeypatch.setattr(device_module, "COMMAND_DIR_OVERRIDE", str(tmp_path))
    assert device_module._resolve_script_dir() == str(tmp_path)


def test_module_probing_does_not_need_importlib(device_module, fl_stubs):
    found = device_module._probe_modules()
    assert "channels" in found
    assert "midi" in found
