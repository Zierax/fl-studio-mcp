"""Step sequencer composition tools for FL Studio.

These tools let you program per-step patterns on channels - including melodies
with pitch, velocity, and pan per step - directly through the step sequencer.
This is the core "composition engine" that works via the MIDI controller script.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastmcp import FastMCP


def register_sequencer_tools(mcp: FastMCP) -> None:
    """Register step sequencer tools with the MCP server."""
    from fl_studio_mcp.utils.connection import get_connection

    @mcp.tool()
    def fl_get_channel_steps(channel: int, steps: int = 16) -> dict:
        """Read the step sequencer pattern for a channel.

        Returns each step with:
            - step: Step index (0-based)
            - enabled: Whether the step is active
            - note: MIDI note number (if enabled)
            - velocity: Velocity 0-127 (if enabled)
            - pan: Pan 0-127, 64 = center (if enabled)

        Args:
            channel: Channel index
            steps: Number of steps to read (default 16)
        """
        conn = get_connection()
        result = conn.send_command("channels.getSteps", {
            "channel": channel,
            "steps": steps,
        })

        if not result.get("success", False) and "error" in result:
            return {"error": result["error"]}

        return {
            "channel": result.get("channel", channel),
            "channel_name": result.get("channel_name", ""),
            "steps": result.get("steps", []),
        }

    @mcp.tool()
    def fl_set_channel_steps(channel: int, steps: list[dict]) -> dict:
        """Program a step sequencer pattern on a channel.

        Each entry in steps should be a dict with:
            - step (required): Step index (0-based, e.g. 0-15 for 16 steps)
            - enabled (optional): True to activate the step, False to deactivate
            - note (optional): MIDI note number (60 = middle C). Use for melodic
              programming - each step can have a different pitch.
            - velocity (optional): Velocity 0-127 (default 100)
            - pan (optional): Pan 0-127, 64 = center

        Example - drum pattern on channel 0 (kick on beats 1 & 3):
            fl_set_channel_steps(0, [{"step": 0, "enabled": True},
                                     {"step": 4, "enabled": True},
                                     {"step": 8, "enabled": True},
                                     {"step": 12, "enabled": True}])

        Example - melody on channel 1 (16th-note arpeggio):
            fl_set_channel_steps(1, [
                {"step": 0, "enabled": True, "note": 60, "velocity": 100},
                {"step": 2, "enabled": True, "note": 64, "velocity": 90},
                {"step": 4, "enabled": True, "note": 67, "velocity": 100},
                {"step": 6, "enabled": True, "note": 72, "velocity": 95},
            ])

        Args:
            channel: Channel index
            steps: List of step definitions (see above)

        Returns:
            dict with 'channel', 'channel_name', 'steps_updated'
        """
        if not steps:
            return "Error: No steps provided"

        conn = get_connection()
        result = conn.send_command("channels.setSteps", {
            "channel": channel,
            "steps": steps,
        })

        if not result.get("success", False) and "error" in result:
            return {"error": result["error"]}

        return {
            "channel": result.get("channel", channel),
            "channel_name": result.get("channel_name", ""),
            "steps_updated": result.get("steps_updated", 0),
        }

    @mcp.tool()
    def fl_clear_channel_steps(channel: int, steps: int = 16) -> dict:
        """Clear (disable) all steps for a channel.

        Args:
            channel: Channel index
            steps: Number of steps to clear (default 16)
        """
        conn = get_connection()
        result = conn.send_command("channels.clearSteps", {
            "channel": channel,
            "steps": steps,
        })

        if not result.get("success", False) and "error" in result:
            return {"error": result["error"]}

        return {
            "channel": result.get("channel", channel),
            "channel_name": result.get("channel_name", ""),
            "cleared_steps": result.get("cleared_steps", 0),
        }
