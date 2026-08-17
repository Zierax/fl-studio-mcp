"""Full-surface control tools (raw generic layer).

Covers every module that this FL Studio version exposes (verified via
system.surface): a generic free-form action tool reaching 240+ commands,
plus curated high-level tools for mixer tracks, channels, plugins,
transport, patterns, playlist, general, ui, arrangement and device.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastmcp import FastMCP


def register_fullcontrol_tools(mcp: FastMCP) -> None:
    """Register full-surface control tools with the MCP server."""
    from fl_studio_mcp.utils.connection import get_connection

    # ---------------------------------------------------------------
    # Generic surface access
    # ---------------------------------------------------------------

    @mcp.tool()
    def fl_raw_action(action: str, params: dict | None = None) -> dict:
        """Execute ANY FL Studio control action by its canonical name.

        The controller exposes 240+ named actions covering the FULL API
        surface of this FL version (all modules: channels, mixer, transport,
        patterns, playlist, general, ui, arrangement, device, plugins):

          - events & automation:    mixer.automateEvent, channels.processRECEvent
          - mixer:                  mixer.setTrackVolume/Pan/StereoSep/
                                    Color/Name, muted/solo/selected/armed,
                                    EQ (gain/freq/q per band),
                                    routing/sends, plugin mix levels,
                                    setCurrentTempo, automation events
          - channels:               channels.setChannelVolume/Pan/Pitch/
                                    Name/Color, mute/solo/select, grid bits,
                                    step parameters, target FX track
          - transport:              start/stop/record/rewind/globalTransport/
                                    setSongPos/setLoopMode/setPlaybackSpeed
          - patterns:               select/jump/setName/setColor/clone/move/
                                    groups/burnLoop/setChannelLoop
          - playlist:               mute/solo/select tracks, live clips,
                                    performance mode, tool selection
          - general:                setNumerator/setDenominator (time sig),
                                    processRECEvent (GLOBAL events e.g.
                                    REC_Tempo, REC_MainVol, REC_MainShuffle),
                                    undo stack management
          - ui:                     show/hide windows, hints, browser nav,
                                    snap modes, metronome, shortcuts
          - arrangement:            selection, markers, current time
          - device:                 MIDI device state, linked values,
                                    master sync, MIDI out
          - plugins:                param names/values, presets

        Explore available actions with fl_api_surface / fl_api_list_functions.

        Args:
            action: Controller action name (e.g. "mixer.setTrackVolume").
            params: JSON-safe dict of parameters for the action.

        Returns:
            The controller's response dict.
        """
        conn = get_connection()
        result = conn.send_command(action, params or {}, timeout=6.0)
        if not isinstance(result, dict):
            return {"error": "Invalid response from controller"}
        return result

    @mcp.tool()
    def fl_api_surface(module: str | None = None, prefix: str = "") -> dict:
        """Get the complete, verified API surface of this FL Studio version.

        Returns every callable function (and constants) per module, so the
        model can self-discover exactly what this FL build supports before
        calling fl_raw_action / fl_raw_command.

        Args:
            module: Optional module name to narrow (else all modules).
            prefix: Optional function-name prefix filter.

        Returns:
            {"surface": {module: {"functions": [...], "constants": [...]}}}
        """
        conn = get_connection()
        result = conn.send_command("system.surface", {"module": module or "", "prefix": prefix}, timeout=10.0)
        if not isinstance(result, dict) or "surface" not in result:
            # Fall back to per-module listing for older controllers
            from fl_studio_mcp.utils.connection import send_command  # noqa: F401

            return {"error": "system.surface not available on this controller version"}
        return result

    @mcp.tool()
    def fl_api_constants(prefix: str = "REC_") -> list:
        """List midi module constants (FPT_, REC_, wid*, SS_*, etc.) with values.

        Args:
            prefix: Constant name prefix, e.g. "REC_", "FPT_", "wid".

        Returns:
            List of {"name", "value"} dicts.
        """
        conn = get_connection()
        result = conn.send_command("raw.consts", {"prefix": prefix}, timeout=6.0)
        if not isinstance(result, dict):
            return []
        return result.get("constants", [])

    # ---------------------------------------------------------------
    # Mixer surface
    # ---------------------------------------------------------------

    @mcp.tool()
    def fl_mixer_track_state(track: int) -> dict:
        """Get full state of one mixer track: name, color, volume, pan,
        stereo separation, mute/solo/select/arm/enable flags, FX count."""
        conn = get_connection()
        out = {"track": track}
        for field, action in (
            ("name", "mixer.getTrackName"), ("color", "mixer.getTrackColor"),
            ("volume", "mixer.getTrackVolume"), ("pan", "mixer.getTrackPan"),
            ("stereo_sep", "mixer.getTrackStereoSep"),
            ("muted", "mixer.isTrackMuted"), ("solo", "mixer.isTrackSolo"),
            ("selected", "mixer.isTrackSelected"), ("armed", "mixer.isTrackArmed"),
            ("enabled", "mixer.isTrackEnabled"),
            ("mute_lock", "mixer.isTrackMuteLock"),
            ("slots_enabled", "mixer.isTrackSlotsEnabled"),
            ("reverse_polarity", "mixer.isTrackRevPolarity"),
            ("swap_channels", "mixer.isTrackSwapChannels"),
        ):
            r = conn.send_command(action, {"track": track}, timeout=3.0)
            if isinstance(r, dict) and "value" in r:
                out[field] = r["value"]
            elif isinstance(r, dict) and "error" in r:
                out[field + "_error"] = r["error"]
        return out

    @mcp.tool()
    def fl_mixer_track_set(track: int, volume: float | None = None, pan: float | None = None,
                           stereo_sep: float | None = None, name: str | None = None,
                           muted: bool | None = None, solo: bool | None = None,
                           selected: bool | None = None, armed: bool | None = None,
                           enabled: bool | None = None, rgb: list | None = None) -> str:
        """Set any combination of mixer track properties in ONE call.

        Args:
            track: Mixer track index.
            volume: 0.0-1.0 (0.8 = 80%).
            pan: -1.0 (left) .. 1.0 (right).
            stereo_sep: stereo separation/width.
            name: New track name.
            muted/solo/selected/armed/enabled: state flags.
            rgb: [r, g, b] 0-255 for track color.
        """
        conn = get_connection()
        done = []
        if volume is not None:
            conn.send_command("mixer.setTrackVolume", {"track": track, "value": volume}); done.append("volume")
        if pan is not None:
            conn.send_command("mixer.setTrackPan", {"track": track, "value": pan}); done.append("pan")
        if stereo_sep is not None:
            conn.send_command("mixer.setTrackStereoSep", {"track": track, "value": stereo_sep}); done.append("stereo_sep")
        if name is not None:
            conn.send_command("mixer.setTrackName", {"track": track, "name": name}); done.append("name")
        if muted is not None:
            conn.send_command("mixer.muteTrack", {"track": track, "mute": muted}); done.append("mute")
        if solo is not None:
            conn.send_command("mixer.soloTrack", {"track": track, "solo": solo}); done.append("solo")
        if selected is not None:
            conn.send_command("mixer.selectTrack", {"track": track, "select": selected}); done.append("select")
        if armed is not None:
            conn.send_command("mixer.armTrack", {"track": track, "armed": armed}); done.append("arm")
        if enabled is not None:
            conn.send_command("mixer.enableTrack", {"track": track, "enabled": enabled}); done.append("enable")
        if rgb:
            conn.send_command("mixer.setTrackColor", {"track": track, "r": int(rgb[0]), "g": int(rgb[1]), "b": int(rgb[2])}); done.append("color")
        if not done:
            return "No properties given"
        conn.send_command("general.saveUndo", {"name": "MCP mixer track set"})
        return f"Track {track}: set {'/'.join(done)}"

    @mcp.tool()
    def fl_mixer_track_volume(track: int, value: float) -> str:
        """Set mixer track fader to 0.0-1.0 (1.0 = 0dB)."""
        conn = get_connection()
        r = conn.send_command("mixer.setTrackVolume", {"track": track, "value": value})
        if isinstance(r, dict) and "error" in r:
            return f"Error: {r['error']}"
        v = conn.send_command("mixer.getTrackVolume", {"track": track})
        return f"Track {track} volume now {v.get('value') if isinstance(v, dict) else v}"

    @mcp.tool()
    def fl_mixer_track_pan(track: int, value: float) -> str:
        """Set mixer track pan -1.0 (L) .. 1.0 (R)."""
        conn = get_connection()
        r = conn.send_command("mixer.setTrackPan", {"track": track, "value": value})
        return f"Track {track} pan set" if not (isinstance(r, dict) and "error" in r) else f"Error: {r['error']}"

    @mcp.tool()
    def fl_mixer_track_mute(track: int, muted: bool | None = None) -> str:
        """Mute/unmute a mixer track (None = toggle)."""
        conn = get_connection()
        if muted is None:
            r = conn.send_command("mixer.isTrackMuted", {"track": track})
            muted = not (r.get("value") if isinstance(r, dict) else False)
        conn.send_command("mixer.muteTrack", {"track": track, "mute": muted})
        return f"Track {track} {'muted' if muted else 'unmuted'}"

    @mcp.tool()
    def fl_mixer_track_solo(track: int, solo: bool | None = None) -> str:
        """Solo/unsolo a mixer track (None = toggle)."""
        conn = get_connection()
        if solo is None:
            r = conn.send_command("mixer.isTrackSolo", {"track": track})
            solo = not (r.get("value") if isinstance(r, dict) else False)
        conn.send_command("mixer.soloTrack", {"track": track, "solo": solo})
        return f"Track {track} {'soloed' if solo else 'unsoloed'}"

    @mcp.tool()
    def fl_mixer_route_track(track: int, dest: int, value: float, width: float = 1.0) -> str:
        """Route mixer track to dest bus. value = send level 0-1, width = stereo."""
        conn = get_connection()
        r = conn.send_command("mixer.route", {"track": track, "dest": dest, "value": value, "width": width})
        return f"Routed {track} -> {dest} @ {value}" if not (isinstance(r, dict) and "error" in r) else f"Error: {r['error']}"



    @mcp.tool()
    def fl_channel_state(channel: int) -> dict:
        """Full state of one channel: index, name, type, color, volume, pan,
        pitch, mute, solo, selected, activity, midi port, target FX track."""
        conn = get_connection()
        out = {"channel": channel}
        for field, action, p in (
            ("name", "channels.getChannelName", {}),
            ("type", "channels.getChannelType", {}),
            ("color", "channels.getChannelColor", {}),
            ("volume", "channels.getChannelVolume", {}),
            ("pan", "channels.getChannelPan", {}),
            ("pitch", "channels.getChannelPitch", {}),
            ("muted", "channels.isChannelMuted", {}),
            ("solo", "channels.isChannelSolo", {}),
            ("selected", "channels.isChannelSelected", {}),
            ("activity", "channels.getActivityLevel", {}),
            ("midi_in_port", "channels.getChannelMidiInPort", {}),
            ("fx_track", "channels.getTargetFxTrack", {}),
            ("grid_bit", "channels.getGridBit", {}),
        ):
            r = conn.send_command(action, {"channel": channel, **p}, timeout=3.0)
            if isinstance(r, dict) and "value" in r:
                out[field] = r["value"]
            elif isinstance(r, dict) and "error" in r:
                out[field + "_error"] = r["error"]
        return out

    @mcp.tool()
    def fl_channel_set(channel: int, volume: float | None = None, pan: float | None = None,
                       pitch: int | None = None, name: str | None = None,
                       muted: bool | None = None, solo: bool | None = None,
                       selected: bool | None = None, rgb: list | None = None,
                       fx_track: int | None = None) -> str:
        """Set any combination of channel properties in ONE call.

        Args:
            channel: Channel index.
            volume: 0.0-1.0.
            pan: -1.0..1.0.
            pitch: semitones (-24..24).
            name: New channel name.
            muted/solo/selected: boolean flags.
            rgb: [r, g, b].
            fx_track: mixer track to route this channel to.
        """
        conn = get_connection()
        done = []
        if volume is not None:
            conn.send_command("channels.setChannelVolume", {"channel": channel, "value": volume}); done.append("volume")
        if pan is not None:
            conn.send_command("channels.setChannelPan", {"channel": channel, "value": pan}); done.append("pan")
        if pitch is not None:
            conn.send_command("channels.setChannelPitch", {"channel": channel, "value": pitch}); done.append("pitch")
        if name is not None:
            conn.send_command("channels.setChannelName", {"channel": channel, "name": name}); done.append("name")
        if muted is not None:
            conn.send_command("channels.muteChannel", {"channel": channel, "muted": muted}); done.append("mute")
        if solo is not None:
            conn.send_command("channels.soloChannel", {"channel": channel, "solo": solo}); done.append("solo")
        if selected is not None:
            conn.send_command("channels.selectChannel", {"channel": channel, "select": selected}); done.append("select")
        if rgb:
            conn.send_command("channels.setChannelColor", {"channel": channel, "r": int(rgb[0]), "g": int(rgb[1]), "b": int(rgb[2])}); done.append("color")
        if fx_track is not None:
            conn.send_command("channels.setTargetFxTrack", {"channel": channel, "track": fx_track}); done.append("fx_track")
        if not done:
            return "No properties given"
        conn.send_command("general.saveUndo", {"name": "MCP channel set"})
        return f"Channel {channel}: set {'/'.join(done)}"

    @mcp.tool()
    def fl_channel_mute(channel: int, muted: bool | None = None) -> str:
        """Mute/unmute a channel (None = toggle)."""
        conn = get_connection()
        if muted is None:
            r = conn.send_command("channels.isChannelMuted", {"channel": channel})
            muted = not (r.get("value") if isinstance(r, dict) else False)
        conn.send_command("channels.muteChannel", {"channel": channel, "muted": muted})
        return f"Channel {channel} {'muted' if muted else 'unmuted'}"

    @mcp.tool()
    def fl_channel_solo(channel: int, solo: bool | None = None) -> str:
        """Solo/unsolo a channel (None = toggle)."""
        conn = get_connection()
        if solo is None:
            r = conn.send_command("channels.isChannelSolo", {"channel": channel})
            solo = not (r.get("value") if isinstance(r, dict) else False)
        conn.send_command("channels.soloChannel", {"channel": channel, "solo": solo})
        return f"Channel {channel} {'soloed' if solo else 'unsoloed'}"


    @mcp.tool()
    def fl_channel_swing(channel: int, amount: float | None = None) -> dict:
        """Get/set per-channel swing (shuffle) 0-1 via REC_Chan_SwingMix.

        This is the working swing control for this FL version.
        """
        conn = get_connection()
        params: dict = {"channel": channel, "event": "swing_mix"}
        if amount is not None:
            params["value"] = amount
        return conn.send_command("channels.event", params)

    @mcp.tool()
    def fl_channel_steps(channel: int, steps: list, length: int = 64) -> str:
        """Write a step sequence for a channel (list of 0/1 per step).

        Args:
            channel: Channel index.
            steps: List of ints (0 = empty, 1 = on) — padded/truncated to length.
            length: Sequence length (default 64 = 16th-note grid over 4 bars is 64
                    steps if grid is 16ths; use 32 for 1 bar 32nds etc.)
        """
        conn = get_connection()
        seq = [1 if s else 0 for s in steps[:length]]
        seq += [0] * (length - len(seq))
        r = conn.send_command("channels.setSteps", {"channel": channel, "steps": seq}, timeout=6.0)
        if isinstance(r, dict) and "error" in r:
            return f"Error: {r['error']}"
        conn.send_command("general.saveUndo", {"name": "MCP step sequence"})
        return f"Channel {channel}: wrote {len(seq)} steps"

    @mcp.tool()
    def fl_channel_step_param(channel: int, step: int, param: str, value: int | None = None) -> dict:
        """Read/write a step parameter (velocity/pan/pitch/etc.) of a step.

        Args:
            channel: Channel index.
            step: Step index.
            param: 'velocity','pan','pitch','release','fine_pitch','mod_x',
                   'mod_y','shift','repeat' or raw index.
            value: Optional value to write (else read).
        """
        conn = get_connection()
        params: dict = {"channel": channel, "step": step, "param": param}
        if value is not None:
            params["value"] = value
        return conn.send_command("channels.stepParam", params)

    # ---------------------------------------------------------------
    # Plugin surface
    # ---------------------------------------------------------------

    @mcp.tool()
    def fl_plugin_info(channel: int, slot: int = -1) -> dict:
        """Get info about the plugin in a channel (or any plugin slot).

        Args:
            channel: Channel (or mixer track) index.
            slot: Plugin slot index (-1 = first/global plugin).
        """
        conn = get_connection()
        out = {"channel": channel, "slot": slot}
        v = conn.send_command("plugins.isValid", {"index": channel, "slot_index": slot})
        if isinstance(v, dict) and "valid" in v:
            out["valid"] = v["valid"]
        n = conn.send_command("plugins.getName", {"index": channel, "slot_index": slot})
        if isinstance(n, dict) and "name" in n:
            out["name"] = n["name"]
        c = conn.send_command("plugins.getParamCount", {"index": channel, "slot_index": slot})
        if isinstance(c, dict) and "count" in c:
            out["param_count"] = c["count"]
        return out

    @mcp.tool()
    def fl_plugin_params(channel: int, slot: int = -1, limit: int = 64) -> dict:
        """Read a plugin's parameter map: index, name, value (0-1), display string.

        Args:
            channel: Channel (or mixer track) index.
            slot: Plugin slot index (-1 = first/global plugin).
            limit: Max params to return (default 64, max 512).
        """
        conn = get_connection()
        return conn.send_command("plugins.getParams", {"index": channel, "slot_index": slot,
                                                       "max_params": min(limit, 512)}, timeout=8.0)

    @mcp.tool()
    def fl_plugin_param_set(channel: int, slot: int, param_index: int, value: float) -> str:
        """Set a plugin parameter value (0-1 normalized).

        Args:
            channel: Channel (or mixer track) index.
            slot: Plugin slot index (-1 = first/global plugin).
            param_index: Parameter index (see fl_plugin_params).
            value: 0.0-1.0 normalized value.
        """
        conn = get_connection()
        r = conn.send_command("plugins.setParamValue", {"param_index": param_index, "value": value,
                                                        "plugin_index": channel, "slot_index": slot})
        if isinstance(r, dict) and ("error" in r or not r):
            return f"Error: {r.get('error', 'unknown')}"
        conn.send_command("general.saveUndo", {"name": "MCP plugin param"})
        out = f"Param {param_index} ({r.get('name', '?')}) = {value}"
        if r.get("value_string"):
            out += f" ({r['value_string']})"
        return out

    @mcp.tool()
    def fl_plugin_param_name_to_index(channel: int, slot: int, param_name: str) -> int:
        """Find a plugin parameter index by its name (case-insensitive substring)."""
        conn = get_connection()
        r = conn.send_command("plugins.getParams", {"index": channel, "slot_index": slot,
                                                    "max_params": 512}, timeout=10.0)
        params = r.get("params", []) if isinstance(r, dict) else []
        for p in params:
            if param_name.lower() in str(p.get("name", "")).lower():
                return int(p.get("index", -1))
        return -1

    @mcp.tool()
    def fl_plugin_param_read(channel: int, slot: int, param_index: int) -> dict:
        """Read a single plugin parameter: name, value (0-1), display string."""
        conn = get_connection()
        return conn.send_command("plugins.getParamValue", {"param_index": param_index,
                                                           "plugin_index": channel, "slot_index": slot})

    @mcp.tool()
    def fl_plugin_preset(channel: int, slot: int = -1, direction: str = "next") -> str:
        """Cycle plugin presets. direction: 'next' | 'prev'."""
        conn = get_connection()
        r = conn.send_command("plugins.nextPreset" if direction == "next" else "plugins.prevPreset",
                              {"index": channel, "slot_index": slot})
        if isinstance(r, dict) and "error" in r and r["error"]:
            return f"Error: {r['error']}"
        n = conn.send_command("plugins.getPresetCount", {"index": channel, "slot_index": slot})
        count = n.get("count", "?") if isinstance(n, dict) else "?"
        pn = r.get("plugin_name", "?") if isinstance(r, dict) else "?"
        return f"Preset {direction} on {pn} (count: {count})"

    # ---------------------------------------------------------------
    # Transport / position
    # ---------------------------------------------------------------

    @mcp.tool()
    def fl_transport_state() -> dict:
        """Full transport state: playing/recording, loop mode, song position,
        song length, playback speed."""
        conn = get_connection()
        out = {}
        for field, action, p in (
            ("playing", "transport.isPlaying", {}),
            ("recording", "transport.isRecording", {}),
            ("loop_mode", "transport.getLoopMode", {}),
            ("song_pos", "transport.getSongPos", {"mode": 0}),
            ("song_length", "transport.getSongLength", {"mode": 0}),
            ("hint", "transport.getSongPosHint", {}),
        ):
            r = conn.send_command(action, p, timeout=3.0)
            if isinstance(r, dict) and "value" in r:
                out[field] = r["value"]
        hw = conn.send_command("transport.getHWBeatLEDState")
        if isinstance(hw, dict) and "value" in hw:
            out["hw_beat_led"] = hw["value"]
        return out


    @mcp.tool()
    def fl_transport_song_pos(ticks: int | None = None, bar: int | None = None) -> dict:
        """Get or set the song position.

        Args:
            ticks: Absolute tick position to jump to (if setting).
            bar: Bar number to jump to (1-based; alternative to ticks).
        """
        conn = get_connection()
        if ticks is not None or bar is not None:
            params = {"mode": 0}
            if ticks is not None:
                params["position"] = ticks
            elif bar is not None:
                ppq = conn.send_command("general.getRecPPQ")
                q = ppq.get("value", 96) if isinstance(ppq, dict) else 96
                params["position"] = max(0, (bar - 1) * q * 4)
            conn.send_command("transport.setSongPos", params)
        return conn.send_command("transport.position")

    @mcp.tool()
    def fl_transport_loop_mode(mode: str | int) -> str:
        """Set transport loop mode: 0=off, 1=pattern, 2=song (or use names
        'off'/'pattern'/'song')."""
        names = {"off": 0, "pattern": 1, "song": 2}
        m = names.get(str(mode).lower()) if isinstance(mode, str) else mode
        conn = get_connection()
        r = conn.send_command("transport.setLoopMode", {"mode": m})
        return f"Loop mode: {mode}" if not (isinstance(r, dict) and "error" in r) else f"Error: {r['error']}"

    @mcp.tool()
    def fl_transport_playback_speed(speed: float = 1.0) -> str:
        """Set playback speed multiplier (1.0 = normal)."""
        conn = get_connection()
        r = conn.send_command("transport.setPlaybackSpeed", {"speedMultiplier": speed})
        return f"Playback speed: {speed}x" if not (isinstance(r, dict) and "error" in r) else f"Error: {r['error']}"

    # ---------------------------------------------------------------
    # Patterns surface
    # ---------------------------------------------------------------

    @mcp.tool()
    def fl_patterns_state() -> dict:
        """Current pattern state: count, active pattern info, groups."""
        conn = get_connection()
        out = {}
        for field, action, p in (
            ("count", "patterns.patternCount", {}),
            ("active", "patterns.patternNumber", {}),
            ("max", "patterns.patternMax", {}),
            ("group_count", "patterns.getPatternGroupCount", {}),
            ("active_group", "patterns.getActivePatternGroup", {}),
        ):
            r = conn.send_command(action, p, timeout=3.0)
            if isinstance(r, dict) and "value" in r:
                out[field] = r["value"]
        return out

    @mcp.tool()
    def fl_pattern_select(pattern: int) -> str:
        """Select + jump to a pattern."""
        conn = get_connection()
        conn.send_command("patterns.selectPattern", {"pattern": pattern})
        conn.send_command("patterns.jumpToPattern", {"pattern": pattern})
        return f"Selected pattern {pattern}"

    @mcp.tool()
    def fl_pattern_info(pattern: int) -> dict:
        """Get pattern name/color/length/selected/group status."""
        conn = get_connection()
        out = {"pattern": pattern}
        for field, action, p in (
            ("name", "patterns.getPatternName", {}),
            ("color", "patterns.getPatternColor", {}),
            ("length", "patterns.getPatternLength", {}),
            ("selected", "patterns.isPatternSelected", {}),
            ("default", "patterns.isPatternDefault", {}),
        ):
            r = conn.send_command(action, {"pattern": pattern, **p}, timeout=3.0)
            if isinstance(r, dict) and "value" in r:
                out[field] = r["value"]
        return out

    @mcp.tool()
    def fl_pattern_clone(source: int, dest: int) -> str:
        """Clone pattern 'source' into slot 'dest'."""
        conn = get_connection()
        r = conn.send_command("patterns.clonePattern", {"from": source, "to": dest})
        return f"Cloned pattern {source} -> {dest}" if not (isinstance(r, dict) and "error" in r) else f"Error: {r['error']}"

    @mcp.tool()
    def fl_pattern_rename(pattern: int, name: str) -> str:
        """Rename a pattern."""
        conn = get_connection()
        r = conn.send_command("patterns.setPatternName", {"pattern": pattern, "name": name})
        return f"Pattern {pattern} renamed '{name}'" if not (isinstance(r, dict) and "error" in r) else f"Error: {r['error']}"

    @mcp.tool()
    def fl_pattern_burn_loop(pattern: int) -> str:
        """Convert pattern loop to played notes (burn loop)."""
        conn = get_connection()
        r = conn.send_command("patterns.burnLoop", {"pattern": pattern})
        return "Loop burned" if not (isinstance(r, dict) and "error" in r) else f"Error: {r['error']}"

    # ---------------------------------------------------------------
    # General / project surface
    # ---------------------------------------------------------------


    @mcp.tool()
    def fl_time_signature(numerator: int | None = None, denominator: int | None = None) -> dict:
        """Set the project time signature.

        Args:
            numerator: beats per bar (e.g. 4).
            denominator: beat unit (e.g. 4 = quarter note).
        """
        conn = get_connection()
        set_msg = []
        if numerator is not None:
            r = conn.send_command("general.setNumerator", {"numerator": numerator})
            if not (isinstance(r, dict) and "error" in r):
                set_msg.append(f"num={numerator}")
        if denominator is not None:
            r = conn.send_command("general.setDenominator", {"denominator": denominator})
            if not (isinstance(r, dict) and "error" in r):
                set_msg.append(f"den={denominator}")
        out: dict = {"set": " ".join(set_msg)} if set_msg else {"info": "no change requested"}
        if set_msg:
            conn.send_command("general.saveUndo", {"name": "MCP time signature"})
        return out

    @mcp.tool()
    def fl_undo_manager() -> dict:
        """Undo stack state: count, position, last, level hint.""" 
        conn = get_connection()
        out = {}
        for field, action in (
            ("count", "general.getUndoHistoryCount"),
            ("pos", "general.getUndoHistoryPos"),
            ("last", "general.getUndoHistoryLast"),
            ("level_hint", "general.getUndoLevelHint"),
        ):
            r = conn.send_command(action, {}, timeout=3.0)
            if isinstance(r, dict) and "value" in r:
                out[field] = r["value"]
        return out

    @mcp.tool()
    def fl_undo_save(name: str = "MCP Change") -> str:
        """Save a named undo point."""
        conn = get_connection()
        r = conn.send_command("general.saveUndo", {"name": name})
        return f"Undo saved: {name}" if not (isinstance(r, dict) and "error" in r) else f"Error: {r['error']}"


    @mcp.tool()
    def fl_redo(steps: int = 1) -> str:
        """Redo 'steps' history levels."""
        conn = get_connection()
        r = conn.send_command("general.undoUpDown", {"value": steps})
        return f"Redo {steps} step(s)" if not (isinstance(r, dict) and "error" in r) else f"Error: {r['error']}"

    @mcp.tool()
    def fl_general_event(event_id: int, value: int) -> str:
        """Write a GLOBAL automation event via general.processRECEvent.

        Useful event ids (midi constants):
          REC_MainVol, REC_MainPitch, REC_MainFCut, REC_MainFRes,
          REC_MainShuffle, REC_Tempo, REC_SongPosition, REC_SongLength.
        """
        conn = get_connection()
        r = conn.send_command("general.automateValue", {"event_id": event_id, "value": value})
        return f"Event {event_id} = {value}" if not (isinstance(r, dict) and "error" in r) else f"Error: {r['error']}"

    # ---------------------------------------------------------------
    # Playlist surface
    # ---------------------------------------------------------------

    @mcp.tool()
    def fl_playlist_state() -> dict:
        """Playlist state: track count, song start, performance mode, live status."""
        conn = get_connection()
        out = {}
        for field, action, p in (
            ("track_count", "playlist.trackCount", {}),
            ("song_start_tick", "playlist.getSongStartTickPos", {}),
            ("performance_mode", "playlist.getPerformanceModeState", {}),
            ("live_status", "playlist.getLiveStatus", {}),
            ("live_loop_mode", "playlist.getLiveLoopMode", {}),
            ("live_trigger_mode", "playlist.getLiveTriggerMode", {}),
        ):
            r = conn.send_command(action, p, timeout=3.0)
            if isinstance(r, dict) and "value" in r:
                out[field] = r["value"]
        return out

    @mcp.tool()
    def fl_playlist_track_mute(track: int, muted: bool | None = None, lock: bool | None = None) -> str:
        """Mute/unmute a playlist track (and optionally lock the mute)."""
        conn = get_connection()
        if muted is None:
            r = conn.send_command("playlist.isTrackMuted", {"track": track})
            muted = not (r.get("value") if isinstance(r, dict) else False)
        r = conn.send_command("playlist.muteTrack", {"track": track, "mute": muted})
        if lock is not None:
            conn.send_command("playlist.muteTrackLock", {"track": track, "lock": lock})
        return f"Playlist track {track} {'muted' if muted else 'unmuted'}" if not (isinstance(r, dict) and "error" in r) else f"Error: {r['error']}"

    # ---------------------------------------------------------------
    # UI surface
    # ---------------------------------------------------------------

    @mcp.tool()
    def fl_ui_state() -> dict:
        """UI state: focused form, windows visibility, snap mode, metronome etc."""
        conn = get_connection()
        out = {}
        for field, action, p in (
            ("focused_form", "ui.getFocusedFormID", {}),
            ("focused_caption", "ui.getFocusedFormCaption", {}),
            ("focused_plugin", "ui.getFocusedPluginName", {}),
            ("prog_title", "ui.getProgTitle", {}),
            ("snap_mode", "ui.getSnapMode", {}),
            ("metronome", "ui.isMetronomeEnabled", {}),
            ("precount", "ui.isPrecountEnabled", {}),
            ("loop_rec", "ui.isLoopRecEnabled", {}),
            ("start_on_input", "ui.isStartOnInputEnabled", {}),
            ("hint", "ui.getHintMsg", {}),
        ):
            r = conn.send_command(action, p, timeout=3.0)
            if isinstance(r, dict) and "value" in r:
                out[field] = r["value"]
        return out

    @mcp.tool()
    def fl_ui_window(window: str, show: bool | None = None) -> dict:
        """Show/hide/query FL windows. window: 'piano_roll','playlist','mixer',
        'channel_rack','plugin','plugin_effect','browser'.

        Args:
            window: window name.
            show: True=show, False=hide, None=query only.
        """
        names = {"piano_roll": 260, "playlist": 230, "mixer": 320, "channel_rack": 280,
                 "plugin": 196, "plugin_effect": 197, "browser": 280}
        wid = names.get(window.lower())
        if wid is None:
            return {"error": f"Unknown window '{window}'. Use: {sorted(names)}"}
        conn = get_connection()
        if show is not None:
            conn.send_command("ui.showWindow" if show else "ui.hideWindow", {"windowId": wid})
        r = conn.send_command("ui.getVisible", {"windowId": wid})
        return {"window": window, "visible": r.get("value") if isinstance(r, dict) else None}


    @mcp.tool()
    def fl_ui_notification(text: str) -> str:
        """Show a notification popup in FL."""
        conn = get_connection()
        r = conn.send_command("ui.showNotification", {"message": text})
        return "Notification shown" if not (isinstance(r, dict) and "error" in r) else f"Error: {r['error']}"

    # ---------------------------------------------------------------
    # Arrangement / markers
    # ---------------------------------------------------------------

    @mcp.tool()
    def fl_arrangement_state() -> dict:
        """Arrangement state: time position, hint, selection."""
        conn = get_connection()
        out = {}
        for field, action in (
            ("current_time", "arrangement.currentTime"),
            ("time_hint", "arrangement.currentTimeHint"),
            ("selection_active", "arrangement.selectionIsActive"),
            ("selection_start", "arrangement.selectionStart"),
            ("selection_end", "arrangement.selectionEnd"),
            ("live_selection", "arrangement.liveSelection"),
        ):
            r = conn.send_command(action, {}, timeout=3.0)
            if isinstance(r, dict) and "value" in r:
                out[field] = r["value"]
        return out

    @mcp.tool()
    def fl_marker_jump(index: int) -> str:
        """Jump to a playlist/arrangement marker by index."""
        conn = get_connection()
        r = conn.send_command("arrangement.jumpToMarker", {"index": index})
        return f"Jumped to marker {index}" if not (isinstance(r, dict) and "error" in r) else f"Error: {r['error']}"

    @mcp.tool()
    def fl_marker_add(name: str = "") -> str:
        """Add an auto time marker at current position with an optional name."""
        conn = get_connection()
        r = conn.send_command("arrangement.addAutoTimeMarker", {"name": name})
        return "Marker added" if not (isinstance(r, dict) and "error" in r) else f"Error: {r['error']}"

    @mcp.tool()
    def fl_marker_name(index: int) -> str:
        """Get marker name by index."""
        conn = get_connection()
        r = conn.send_command("arrangement.getMarkerName", {"index": index})
        return str(r.get("value")) if isinstance(r, dict) and "value" in r else "?"

    # ---------------------------------------------------------------
    # Device surface (hardware / MIDI)
    # ---------------------------------------------------------------

    @mcp.tool()
    def fl_device_info() -> dict:
        """Controller device info: name, id, port, assignment, master sync."""
        conn = get_connection()
        out = {}
        for field, action in (
            ("name", "device.getName"),
            ("device_id", "device.getDeviceID"),
            ("port", "device.getPortNumber"),
            ("assigned", "device.isAssigned"),
            ("midi_out_assigned", "device.isMidiOutAssigned"),
            ("master_sync", "device.getMasterSync"),
        ):
            r = conn.send_command(action, {}, timeout=3.0)
            if isinstance(r, dict) and "value" in r:
                out[field] = r["value"]
        return out

    @mcp.tool()
    def fl_device_linked() -> dict:
        """Read the currently linked (last tweaked) control: channel, info,
        value, string, param name."""
        conn = get_connection()
        out = {}
        for field, action in (
            ("channel", "device.getLinkedChannel"),
            ("info", "device.getLinkedInfo"),
            ("value", "device.getLinkedValue"),
            ("value_string", "device.getLinkedValueString"),
            ("param_name", "device.getLinkedParamName"),
        ):
            r = conn.send_command(action, {}, timeout=3.0)
            if isinstance(r, dict) and "value" in r:
                out[field] = r["value"]
        return out

    @mcp.tool()
    def fl_device_link_to_last_tweaked() -> str:
        """Link the controller to the last tweaked plugin/FL control.

        After linking, device.getLinkedValue reflects that control; the
        hardware can then drive it. Useful for full remote-control flows.
        """
        conn = get_connection()
        r = conn.send_command("device.linkToLastTweaked")
        return "Linked to last tweaked" if not (isinstance(r, dict) and "error" in r) else f"Error: {r['error']}"

    @mcp.tool()
    def fl_device_master_sync(enabled: bool) -> str:
        """Enable/disable the device's master sync (transport clock out)."""
        conn = get_connection()
        r = conn.send_command("device.setMasterSync", {"enabled": enabled})
        return f"Master sync {'on' if enabled else 'off'}" if not (isinstance(r, dict) and "error" in r) else f"Error: {r['error']}"

    @mcp.tool()
    def fl_device_midi_out(status: int, data1: int, data2: int) -> str:
        """Send a raw MIDI message out of the controller port."""
        conn = get_connection()
        r = conn.send_command("device.midiOutMsg", {"status": status, "data1": data1, "data2": data2})
        return f"Sent MIDI {status:02X} {data1:02X} {data2:02X}" if not (isinstance(r, dict) and "error" in r) else f"Error: {r['error']}"

    @mcp.tool()
    def fl_device_full_refresh() -> str:
        """Force a full hardware refresh (LEDs/displays of the controller)."""
        conn = get_connection()
        r = conn.send_command("device.fullRefresh")
        return "Full refresh sent" if not (isinstance(r, dict) and "error" in r) else f"Error: {r['error']}"
