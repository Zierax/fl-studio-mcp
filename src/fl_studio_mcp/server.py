"""FL Studio MCP Server - Control FL Studio via Model Context Protocol.

This MCP server provides tools to control FL Studio through two mechanisms:
1. MIDI + JSON - Real-time control of mixer, transport, channels, and plugins
2. Piano Roll Scripts - Persistent note placement via JSON + keystroke triggering

Requirements:
- FL Studio 20.7+ running
- FLStudioMCP controller script installed (run: ./scripts/setup.sh)
- On Mac: IAC Driver enabled in Audio MIDI Setup
- On Windows: loopMIDI virtual MIDI ports configured
- For piano roll: ComposeWithLLM.pyscript installed in FL Studio

Limitations:
- Cannot load new plugins (only control existing ones)
- Cannot place clips on the playlist timeline programmatically
"""

from __future__ import annotations

from fastmcp import FastMCP

from fl_studio_mcp.tools import (
    register_advanced_tools,
    register_channel_tools,
    register_fullcontrol_tools,
    register_mixer_tools,
    register_pattern_tools,
    register_piano_roll_tools,
    register_plugin_tools,
    register_sequencer_tools,
    register_transport_tools,
)
from fl_studio_mcp.utils.connection import get_connection, reset_connection

# Create the MCP server
mcp = FastMCP(
    name="fl-studio-mcp",
    instructions="""
FL Studio MCP Server - Control FL Studio from AI assistants.

This server provides tools to control FL Studio through its Python scripting API.
FL Studio must be running with the FLStudioMCP MIDI controller enabled.

Available tool categories:
- Transport: Play, stop, record, tempo, position control
- Mixer: Volume, pan, mute, solo, track management
- Channels: Channel info, note triggering, step sequencer
- Patterns: Create, list, select, rename, clone, clear, set length
- Step Sequencer: Program melodies with per-step pitch/velocity/pan
- Plugins: Parameter control, preset navigation (cannot load new plugins)
- Advanced: Raw FL API passthrough (fl_raw_command), automation events,
  mixer routing/sends, built-in EQ, metering, FX chains, swing
  (shuffle), step parameters, playlist control, global actions
  (save/undo/play/snap), tempo via the real API, project info
- Full Control: fl_raw_action reaches the ENTIRE 240+ command surface
  (mixer/channels/transport/patterns/playlist/general/ui/arrangement/
  device/plugins), fl_api_surface self-discovers the exact API of this FL
  build, plugin param maps and presets, mixer track full state, channel
  full state, time signature, undo manager, UI windows, arrangement
  markers/selection, device (hardware) state and MIDI out, global events
  (REC_Tempo, REC_MainVol, REC_MainShuffle, ...)

Important limitations:
1. Cannot load new VST/AU plugins - only control existing ones
2. Cannot place clips on the playlist timeline programmatically
3. Note triggering (fl_trigger_note) is real-time only - notes won't persist
   unless FL Studio is recording. Use step sequencer (fl_set_grid_bit,
   fl_set_channel_steps) for persistent patterns.
4. Use fl_api_surface + fl_api_list_functions before raw calls - this FL
   build (api_version 40) differs from modern FL25 docs (e.g. EQ args are
   reversed (track, band), 3 bands only, no shuffle getters, swing via
   channels.event swing_mix, tempo EPB = BPM*1000, no arrangement time
   helpers).
""",
)


# Register connection status resource
@mcp.resource("fl://status")
def get_fl_status() -> str:
    """Get FL Studio connection status."""
    conn = get_connection()
    if conn.is_connected:
        return "Connected to FL Studio via MIDI"
    else:
        return f"Not connected: {conn.connection_error}"


@mcp.resource("fl://project")
def get_project_info() -> dict:
    """Get current FL Studio project information."""
    conn = get_connection()

    if not conn.is_connected:
        return {"error": conn.connection_error}

    try:
        result = conn.send_command("transport.getStatus")
        if not result.get("success", False) and "error" in result:
            return {"error": result["error"]}

        return {
            "is_playing": result.get("is_playing", False),
            "is_recording": result.get("is_recording", False),
            "position": result.get("position", ""),
            "loop_mode": result.get("loop_mode", "pattern"),
        }
    except Exception as e:
        return {"error": str(e)}


# Connection management tools
@mcp.tool()
def fl_connect() -> str:
    """Connect or reconnect to FL Studio via MIDI.

    Use this tool to:
    - Check if FL Studio is connected
    - Retry connection after starting FL Studio
    - Reconnect if the connection was lost

    Returns the connection status.
    """
    # Reset connection state to force a fresh connection attempt
    reset_connection()

    conn = get_connection()
    try:
        conn.ensure_connected()
    except RuntimeError as e:
        return f"Connection failed: {e}"
    return "Successfully connected to FL Studio via MIDI!"


@mcp.tool()
def fl_connection_status() -> dict:
    """Get the current FL Studio connection status.

    Returns information about whether FL Studio is connected
    and any error messages if not.
    """
    conn = get_connection()
    # Eagerly attempt a connection so the reported status reflects actual
    # reachability rather than the lazily-initialized flag.
    try:
        conn.ensure_connected()
    except RuntimeError:
        pass
    status = conn.get_status()
    return {
        "connected": status.get("connected", False),
        "port_name": status.get("port_name"),
        "available_ports": status.get("available_ports", []),
        "error": status.get("error"),
    }


# Register all tools
register_transport_tools(mcp)
register_mixer_tools(mcp)
register_channel_tools(mcp)
register_plugin_tools(mcp)
register_pattern_tools(mcp)
register_sequencer_tools(mcp)
register_piano_roll_tools(mcp)
register_advanced_tools(mcp)
register_fullcontrol_tools(mcp)


def main():
    """Run the FL Studio MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
