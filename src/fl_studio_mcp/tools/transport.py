"""Transport control tools for FL Studio."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastmcp import FastMCP


def register_transport_tools(mcp: FastMCP) -> None:
    """Register transport control tools with the MCP server."""
    from fl_studio_mcp.utils.connection import get_connection

    @mcp.tool()
    def fl_play() -> str:
        """Start or pause FL Studio playback.

        Toggles between play and pause states. If stopped, starts playback.
        If playing, pauses playback.
        """
        conn = get_connection()
        result = conn.send_command("transport.start")

        if not result.get("success", False) and "error" in result:
            return f"Error: {result['error']}"

        is_playing = result.get("is_playing", False)
        return f"Playback {'started' if is_playing else 'paused'}"

    @mcp.tool()
    def fl_stop() -> str:
        """Stop FL Studio playback completely.

        Stops playback and resets the playback position.
        """
        conn = get_connection()
        result = conn.send_command("transport.stop")

        if not result.get("success", False) and "error" in result:
            return f"Error: {result['error']}"

        return "Playback stopped"

    @mcp.tool()
    def fl_record() -> str:
        """Toggle recording mode in FL Studio.

        When enabled, incoming MIDI and audio will be recorded.
        """
        conn = get_connection()
        result = conn.send_command("transport.record")

        if not result.get("success", False) and "error" in result:
            return f"Error: {result['error']}"

        is_recording = result.get("is_recording", False)
        return f"Recording {'enabled' if is_recording else 'disabled'}"

    @mcp.tool()
    def fl_get_transport_status() -> dict:
        """Get current transport status including playback and recording state.

        Returns information about whether FL Studio is playing, recording,
        the current position, and loop mode.
        """
        conn = get_connection()
        result = conn.send_command("transport.getStatus")

        if not result.get("success", False) and "error" in result:
            return {"error": result["error"]}

        return {
            "is_playing": result.get("is_playing", False),
            "is_recording": result.get("is_recording", False),
            "position": result.get("position", ""),
            "loop_mode": result.get("loop_mode", "pattern"),
        }

    @mcp.tool()
    def fl_set_song_position(position: float, mode: int = 2) -> str:
        """Set the playback position in FL Studio.

        Args:
            position: The position value. Interpretation depends on mode.
            mode: Position format:
                  0 = Percentage (0.0 to 1.0)
                  1 = Time in milliseconds
                  2 = Time in seconds (default)
                  3 = Position in ticks
                  4 = Position as bars:steps:ticks (encoded)
        """
        conn = get_connection()
        result = conn.send_command("transport.setPosition", {
            "position": position,
            "mode": mode,
        })

        if not result.get("success", False) and "error" in result:
            return f"Error: {result['error']}"

        new_pos = result.get("position", "")
        return f"Position set to {new_pos}"

    @mcp.tool()
    def fl_get_song_length() -> dict:
        """Get the total length of the current song/pattern.

        Returns the length in multiple formats for convenience.
        """
        conn = get_connection()
        result = conn.send_command("transport.getLength")

        if not result.get("success", False) and "error" in result:
            return {"error": result["error"]}

        return {
            "ticks": result.get("ticks", 0),
            "seconds": result.get("seconds", 0),
            "milliseconds": result.get("milliseconds", 0),
        }

    @mcp.tool()
    def fl_set_loop_mode(mode: str) -> str:
        """Set the loop mode between pattern and song.

        Args:
            mode: Either "pattern" or "song"
        """
        if mode not in ("pattern", "song"):
            return "Error: mode must be 'pattern' or 'song'"

        conn = get_connection()
        result = conn.send_command("transport.setLoopMode", {"mode": mode})

        if not result.get("success", False) and "error" in result:
            return f"Error: {result['error']}"

        return f"Loop mode set to {mode}"

    @mcp.tool()
    def fl_set_playback_speed(speed: float) -> str:
        """Set the playback speed multiplier.

        Args:
            speed: Speed multiplier from 0.25 (quarter speed) to 4.0 (4x speed).
                   1.0 is normal speed.
        """
        if not 0.25 <= speed <= 4.0:
            return "Error: Speed must be between 0.25 and 4.0"

        conn = get_connection()
        result = conn.send_command("transport.setPlaybackSpeed", {"speed": speed})

        if not result.get("success", False) and "error" in result:
            return f"Error: {result['error']}"

        return f"Playback speed set to {speed}x"

    @mcp.tool()
    def fl_set_tempo(bpm: float) -> str:
        """Set the project tempo in BPM.

        Args:
            bpm: Tempo in beats per minute (e.g. 140 for fast trap).
                 Typical range: 60-200.
        """
        if not 20 <= bpm <= 999:
            return "Error: Tempo must be between 20 and 999 BPM"

        conn = get_connection()
        result = conn.send_command("transport.setTempo", {"tempo": bpm})

        if not result.get("success", False) and "error" in result:
            return f"Error: {result['error']}"

        new_tempo = result.get("tempo", bpm)
        return f"Tempo set to {new_tempo} BPM"

    @mcp.tool()
    def fl_get_tempo() -> dict:
        """Get the current project tempo in BPM.

        Returns:
            dict with 'tempo' (float, BPM)
        """
        conn = get_connection()
        result = conn.send_command("transport.getTempo")

        if not result.get("success", False) and "error" in result:
            return {"error": result["error"]}

        return {"tempo": result.get("tempo", 120.0)}

    @mcp.tool()
    def fl_get_shuffle() -> dict:
        """Get the current shuffle (swing) amount.

        Returns:
            dict with 'shuffle' (0-100 swing percentage) and optional 'error'
        """
        conn = get_connection()
        result = conn.send_command("transport.getShuffle")

        if not result.get("success", False) and "error" in result:
            return {"error": result["error"]}

        return {"shuffle": result.get("shuffle", None)}
