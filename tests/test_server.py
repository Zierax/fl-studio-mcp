"""Tests for the MCP server surface.

These tests make sure the server boots, exposes the expected tools and that
the connection helpers behave as documented.
"""

from __future__ import annotations

import pytest

fastmcp = pytest.importorskip("fastmcp")


@pytest.fixture(scope="module")
def server_module():
    from fl_studio_mcp import server

    return server


def _tool_names(server_module) -> set[str]:
    import asyncio

    tools = asyncio.run(server_module.mcp.list_tools())
    return {tool.name for tool in tools}


def test_server_exposes_the_connection_tools(server_module):
    names = _tool_names(server_module)
    for name in (
        "fl_connect",
        "fl_connection_status",
        "fl_diagnostics",
    ):
        assert name in names, f"missing tool: {name}"


def test_server_exposes_the_tool_surface(server_module):
    names = _tool_names(server_module)
    # The catalogue is large; a few representatives from every group.
    for name in (
        "fl_play",
        "fl_set_track_volume",
        "fl_get_all_channels",
        "fl_create_pattern",
        "fl_plugin_info",
        "fl_set_grid_bit",
        "fl_send_notes",
        "fl_raw_command",
        "fl_api_surface",
    ):
        assert name in names, f"missing tool: {name}"


def test_connect_accepts_an_explicit_port(server_module):
    """fl_connect must allow overriding the automatic MIDI port choice."""
    import asyncio

    tools = asyncio.run(server_module.mcp.list_tools())
    connect = next(tool for tool in tools if tool.name == "fl_connect")
    properties = connect.parameters.get("properties", {})
    assert "port_name" in properties
    assert "data_dir" in properties


def test_diagnostics_returns_a_report(server_module):
    result = server_module.fl_diagnostics()
    assert "server" in result
    assert "fl_studio" in result
    assert "available_ports" in result["server"]
    assert "hardware_dir" in result["server"]


def test_status_lists_the_resolved_paths(server_module):
    result = server_module.fl_connection_status()
    assert "connected" in result
    assert "port_name" in result
    assert "hardware_dir" in result
    assert "hardware_dir_candidates" in result
