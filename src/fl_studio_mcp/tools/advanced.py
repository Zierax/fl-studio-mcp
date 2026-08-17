"""Advanced control tools for FL Studio (V4 controller).

Wraps the V4 controller capabilities: raw API passthrough, automation,
project info, transport actions (globalTransport), tempo (FL25 real API),
mixer routing/sends, built-in EQ, metering, FX chain info, channel events,
swing (shuffle), step parameter access, playlist control, and undo.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastmcp import FastMCP


def register_advanced_tools(mcp: FastMCP) -> None:
    """Register advanced control tools with the MCP server."""
    from fl_studio_mcp.utils.connection import get_connection

    @mcp.tool()
    def fl_raw_command(module: str, function: str, args: list | None = None) -> dict:
        """Execute an arbitrary FL Studio API call directly (raw passthrough).

        This is the ultimate escape hatch: it calls `module.function(*args)`
        inside FL Studio's Python scripting environment.

        Allowed modules: channels, mixer, transport, plugins, patterns,
        playlist, general, ui, arrangement.

        Args:
            module: FL Studio API module name (e.g. "mixer", "channels")
            function: Function name inside the module (e.g. "getTrackCount")
            args: Positional arguments for the function (numbers/strings/bools)

        Returns:
            JSON-serializable result of the call (or an error dict).
        """
        conn = get_connection()
        result = conn.send_command("raw.call", {
            "module": module,
            "function": function,
            "args": args or [],
        }, timeout=4.0)
        if not result.get("success", False) and "error" in result:
            return {"error": result["error"]}
        return {
            "result": result.get("result"),
            "error": result.get("error"),
            "meta": result.get("meta"),
        }

    @mcp.tool()
    def fl_api_list_functions(module: str, prefix: str = "") -> list:
        """List the callable functions of an FL Studio API module (API discovery).

        Use this to discover what this specific FL Studio version really
        supports before calling fl_raw_command.

        Args:
            module: API module name (channels, mixer, transport, patterns,
                    playlist, general, ui, arrangement, plugins, midi)
            prefix: Optional name prefix filter (e.g. "Eq", "getTrack")

        Returns:
            List of function names.
        """
        conn = get_connection()
        result = conn.send_command("raw.list", {"module": module, "prefix": prefix}, timeout=4.0)
        if not result.get("success", False) and "error" in result:
            return []
        return result.get("functions", [])

    @mcp.tool()
    def fl_api_list_constants(prefix: str = "FPT_") -> list:
        """List midi module constants (FPT_, REC_*, etc.) for API discovery.

        Args:
            prefix: Constant name prefix, e.g. "FPT_", "REC_", "REC_Chan_"

        Returns:
            List of {"name": ..., "value": ...} dicts.
        """
        conn = get_connection()
        result = conn.send_command("raw.consts", {"prefix": prefix}, timeout=4.0)
        if not result.get("success", False) and "error" in result:
            return []
        return result.get("constants", [])

    @mcp.tool()
    def fl_project_info() -> dict:
        """Get project-wide information (title, author, genre, PPQ, time signature, version)."""
        conn = get_connection()
        result = conn.send_command("project.info")
        return result if result.get("success", False) else {"error": result.get("error", "unknown")}

    @mcp.tool()
    def fl_set_time_signature(numerator: int, denominator: int) -> str:
        """Set the project time signature.

        Args:
            numerator: beats per bar (e.g. 4)
            denominator: note value of one beat (e.g. 4)
        """
        conn = get_connection()
        result = conn.send_command("project.setTimeSig", {
            "numerator": numerator,
            "denominator": denominator,
        })
        if not result.get("success", False) and "error" in result:
            return f"Error: {result['error']}"
        return f"Time signature set to {result.get('numerator')}/{result.get('denominator')}"

    @mcp.tool()
    def fl_set_ppq(ppq: int) -> str:
        """Set the resolution of the project in pulses per quarter note.

        Args:
            ppq: Resolution (e.g. 96, 192, 384, 768, 960)
        """
        conn = get_connection()
        result = conn.send_command("project.setPPQ", {"ppq": ppq})
        if not result.get("success", False) and "error" in result:
            return f"Error: {result['error']}"
        return f"PPQ set to {result.get('ppq')}"

    @mcp.tool()
    def fl_transport_action(action: str) -> str:
        """Trigger a global FL Studio action via transport.globalTransport.

        Common actions: 'start' (play), 'stop', 'record', 'save', 'saveas',
        'saveloopproject', 'new', 'open', 'toggle_play', 'toggle_record',
        'undo', 'redo', 'stop_and_rewind', 'goto_next_position',
        'goto_previous_position', 'scroll_begin', 'scroll_end',
        'hide_mixer', 'hide_playlist', 'hide_piano_roll', 'f8', 'f12',
        'prev_pattern', 'next_pattern', 'stretch_and_fit', 'paste', 'cut',
        'copy', 'delete', 'insert', 'merge', 'toggle_value_mode',
        'toggle_value_link', 'cut_mixer_track', 'copy_mixer_track',
        'rename_mixer_track', 'edit_mixer_track_events', 'hybridize_mixer_track',
        'zoom_to_selection', 'zoom_out', 'update_playlist_and_editor',
        'swap_left_right', 'toggle_notes_as_drum_pads', 'quick_quantize',
        'stretch_notes', 'show_performance_mode',
        'snap_on_off', 'snap_next', 'snap_previous',
        'move_note_to_previous_position', 'move_note_to_next_position',
        'select_all_notes', 'toggle_editor_plugin', 'deselect_all_notes',
        'undo_history', 'count_down', 'toggle_drum_mode',
        'toggle_drum_mode_window', 'jump_begin', 'fast_forward',
        'set_recording_options', 'set_recording_delay', 'toggle_rover',
        'plugins_presets', 'mixer_plugins', 'channels_rack',
        'show_ui_focus_floating_mini_editors', 'duplicate_focused_plugin_window',
        'select_previous_channel_button', 'select_next_channel_button',
        'toggle_browser', 'toggle_instruments', 'toggle_playlist_scroll',
        'toggle_mixer_scroll', 'toggle_channel_rack_scroll', 'toggle_effects',
        'toggle_waveforms', 'toggle_individual_mixer', 'show_all_channel_rack',
        'show_toolbar', 'show_browser', 'show_transport', 'show_instruments',
        'show_plugin_window', 'show_mixer_into_rack', 'show_mixer_tracks',
        'show_status_line', 'show_playlist_toolbar', 'show_backup',
        'show_on_top', 'show_wrapped_music_notes', 'execute_plugin_key',
        'set_mixer_track_current_position', 'clear_active_undo',
        'hide_all_plugin_windows', 'hide_current_plugin_window',
        'unhide_current_plugin_window', 'hide_plugin_window',
        'show_current_plugin_window', 'minimize_current_plugin_window',
        'hide_current_plugin_window2', 'move_current_plugin_window',
        'enable_current_plugin_warp', 'enable_fruity_envelope_controller',
        'move_all_plugin_windows', 'alt_flip_current_plugin_window',
        'unhide_all_plugin_windows', 'show_mixer', 'show_playlist',
        'preview_notes_into_active_pattern', 'toggle_metronome',
        'toggle_main_piano_roll_quantize', 'toggle_snapping',
        'show_mixer_carousel', 'toggle_track_selector',
        'toggle_pattern_selector', 'toggle_playlist_track_carousel',
        'toggle_channel_rack_carousel', 'toggle_mixer_carousel',
        'toggle_playlist_editor_carousel', 'toggle_piano_roll_carousel',
        'toggle_pattern_editor_carousel', 'ignore_shortcuts',
        'mute_all_key_input', 'enable_key_down_propagation',
        'enable_key_up_propagation', 'enable_mouse_propagation',
        'show_help', 'show_document_center', 'show_support_documents',
        'global_privacy', 'bring_all_to_front' etc.

        Args:
            action: The action name (matches transport.globalTransport commands).
        """
        conn = get_connection()
        result = conn.send_command("transport.action", {"action": action})
        if not result.get("success", False) and "error" in result:
            return f"Error: {result['error']}"
        return f"Action '{action}' triggered"

    @mcp.tool()
    def fl_tempo_get() -> float:
        """Get the current project tempo in BPM (mixer.setCurrentTempo EPB API)."""
        conn = get_connection()
        result = conn.send_command("tempo.get")
        if not result.get("success", False) and "error" in result:
            return -1.0
        return result.get("tempo", -1.0)

    @mcp.tool()
    def fl_tempo_set(bpm: float) -> str:
        """Set the project tempo in BPM (FL25 real API: mixer.setCurrentTempo, takes EPB=BPM*1000).

        Args:
            bpm: Tempo in beats per minute (e.g. 140.0)
        """
        conn = get_connection()
        result = conn.send_command("tempo.set", {"bpm": bpm})
        if not result.get("success", False) and "error" in result:
            return f"Error: {result['error']}"
        raw = result.get("tempo")
        if isinstance(raw, (int, float)) and raw > 1000:
            raw = raw / 1000.0
        return f"Tempo set to {raw} BPM"

    @mcp.tool()
    def fl_general_info() -> dict:
        """Get general FL Studio API info (api version, undo state, changed flag, rec PPQ/PPB)."""
        conn = get_connection()
        result = conn.send_command("general.info")
        if not result.get("success", False) and "error" in result:
            return {"error": result["error"]}
        return {
            "api_version": result.get("api_version"),
            "changed": result.get("changed"),
            "rec_ppq": result.get("rec_ppq"),
            "rec_ppb": result.get("rec_ppb"),
            "undo_count": result.get("undo_count"),
            "undo_pos": result.get("undo_pos"),
        }

    @mcp.tool()
    def fl_save_undo(undo_name: str = "MCP Action") -> str:
        """Create a named undo step in FL Studio.

        Args:
            undo_name: Label for the undo point
        """
        conn = get_connection()
        result = conn.send_command("general.saveUndo", {"name": undo_name})
        if not result.get("success", False) and "error" in result:
            return f"Error: {result['error']}"
        return f"Undo point '{result.get('name', undo_name)}' saved"

    @mcp.tool()
    def fl_undo() -> str:
        """Undo the last action in FL Studio."""
        conn = get_connection()
        result = conn.send_command("general.undo")
        if not result.get("success", False) and "error" in result:
            return f"Error: {result['error']}"
        return "Undo applied"

    @mcp.tool()
    def fl_undo_updown(steps: int) -> str:
        """Move through the undo history.

        Args:
            steps: Positive = redo, negative = undo
        """
        conn = get_connection()
        result = conn.send_command("general.undoUpDown", {"steps": steps})
        if not result.get("success", False) and "error" in result:
            return f"Error: {result['error']}"
        return f"Undo history moved by {steps}"

    @mcp.tool()
    def fl_safe_to_edit() -> bool:
        """Check whether it's the right time to edit the project (safe state)."""
        conn = get_connection()
        result = conn.send_command("general.safeToEdit")
        if not result.get("success", False) and "error" in result:
            return False
        return result.get("safe", False)

    @mcp.tool()
    def fl_mixer_route(track: int, dest: int, value: float, width: float = 1.0) -> str:
        """Route a mixer track to another track (bus/send).

        Args:
            track: Source track
            dest: Destination track (e.g. a bus track)
            value: 0.0 (no send) to 1.0 (full send)
            width: Stereo width of the send (default 1.0)
        """
        conn = get_connection()
        result = conn.send_command("mixer.route", {
            "track": track,
            "dest": dest,
            "value": value,
            "width": width,
        })
        if not result.get("success", False) and "error" in result:
            return f"Error: {result['error']}"
        return f"Track {track} routed to track {dest} at level {value}"

    @mcp.tool()
    def fl_mixer_route_level(track: int, dest: int, value: float) -> str:
        """Set the send level of an existing route.

        Args:
            track: Source track
            dest: Destination track
            value: 0.0 to 1.0
        """
        conn = get_connection()
        result = conn.send_command("mixer.routeLevel", {
            "track": track,
            "dest": dest,
            "value": value,
        })
        if not result.get("success", False) and "error" in result:
            return f"Error: {result['error']}"
        return f"Route {track}->{dest} level set to {value}"

    @mcp.tool()
    def fl_mixer_route_send_active(track: int, dest: int, active: bool) -> str:
        """Enable/disable a route (send) between tracks.

        Args:
            track: Source track
            dest: Destination track
            active: True to activate the send
        """
        conn = get_connection()
        result = conn.send_command("mixer.routeSendActive", {
            "track": track,
            "dest": dest,
            "active": active,
        })
        if not result.get("success", False) and "error" in result:
            return f"Error: {result['error']}"
        return f"Send {track}->{dest} {'active' if active else 'inactive'}"

    @mcp.tool()
    def fl_mixer_equalizer(track: int, mode: str = "get", band: int = 0, gain: float | None = None, freq: float | None = None, q: float | None = None) -> dict:
        """Control the built-in mixer track EQ (3 bands in this FL version).

        NOTE: values are normalized 0-1, not dB/Hz (0.5 = unity gain).

        Args:
            track: Mixer track
            mode: 'get' (one band) | 'set' (write gain/freq/q) | 'bands' (all bands)
            band: EQ band index (0-2)
            gain: Normalized gain 0-1 (0.5 = 0dB)
            freq: Normalized center frequency 0-1
            q: Normalized bandwidth 0-1
        """
        conn = get_connection()
        params: dict = {"track": track, "mode": mode, "band": band}
        if gain is not None:
            params["gain"] = gain
        if freq is not None:
            params["freq"] = freq
        if q is not None:
            params["q"] = q
        result = conn.send_command("mixer.equalizer", params)
        if not result.get("success", False) and "error" in result:
            return {"error": result["error"]}
        return result

    @mcp.tool()
    def fl_mixer_peaks(track: int) -> dict:
        """Get the current metering peaks of a mixer track.

        Args:
            track: Mixer track
        """
        conn = get_connection()
        result = conn.send_command("mixer.peaks", {"track": track})
        if not result.get("success", False) and "error" in result:
            return {"error": result["error"]}
        return result

    @mcp.tool()
    def fl_mixer_fx_info(track: int, slots: int = 4) -> dict:
        """Get the FX plugin chain of a mixer track.

        Args:
            track: Mixer track
            slots: Max number of FX slots to check
        """
        conn = get_connection()
        result = conn.send_command("mixer.fxInfo", {"track": track, "slots": slots})
        if not result.get("success", False) and "error" in result:
            return {"error": result["error"]}
        return result

    @mcp.tool()
    def fl_mixer_fx_mix_level(track: int, slot: int, level: float) -> str:
        """Set the mix level of an FX slot on a track.

        Args:
            track: Mixer track
            slot: FX slot index
            level: 0.0 (bypass) to 1.0 (full)
        """
        conn = get_connection()
        result = conn.send_command("mixer.fxMixLevel", {
            "track": track,
            "slot": slot,
            "level": level,
        })
        if not result.get("success", False) and "error" in result:
            return f"Error: {result['error']}"
        return f"FX slot {slot} on track {track} level set to {level}"

    @mcp.tool()
    def fl_mixer_link_channel(track: int, channel: int, link: bool) -> str:
        """Link/unlink a channel to a mixer track.

        Args:
            track: Mixer track
            channel: Channel index
            link: True to link, False to unlink
        """
        conn = get_connection()
        result = conn.send_command("mixer.linkChannel", {
            "track": track,
            "channel": channel,
            "link": link,
        })
        if not result.get("success", False) and "error" in result:
            return f"Error: {result['error']}"
        return f"Channel {channel} {'linked to' if link else 'unlinked from'} track {track}"

    @mcp.tool()
    def fl_mixer_automate(track: int, value: float, rec_event_id: int | None = None, flags: int | None = None) -> str:
        """Write an automation event for a mixer track (fader rides).

        Args:
            track: Mixer track
            value: New value (0-1)
            rec_event_id: Optional REC event ID (defaults to track volume event)
            flags: Optional REC_* flags
        """
        params: dict = {"track": track, "value": value}
        if rec_event_id is not None:
            params["rec_event_id"] = rec_event_id
        if flags is not None:
            params["flags"] = flags
        conn = get_connection()
        result = conn.send_command("mixer.automate", params)
        if not result.get("success", False) and "error" in result:
            return f"Error: {result['error']}"
        return f"Automation written for track {track} (event {result.get('event_id')})"

    @mcp.tool()
    def fl_channel_shuffle(channel: int, shuffle: float) -> str:
        """Set swing (shuffle) amount for a channel.

        Args:
            channel: Channel index
            shuffle: 0.0 to 1.0 (e.g. 0.5 = 50%% swing)
        """
        conn = get_connection()
        result = conn.send_command("channels.shuffle", {
            "channel": channel,
            "shuffle": shuffle,
        })
        if not result.get("success", False) and "error" in result:
            return f"Error: {result['error']}"
        return f"Channel {channel} shuffle set to {result.get('shuffle')}"

    @mcp.tool()
    def fl_channel_event(channel: int, event: str, value: float | None = None) -> dict:
        """Read or write a REC automation event on a channel.

        Args:
            channel: Channel index
            event: one of the real event names for this FL version:
                   'volume', 'pan', 'pitch', 'fcut'/'cut', 'fres'/'res',
                   'ftype', 'mute', 'fx', 'offset_vol', 'offset_pan',
                   'offset_pitch', 'offset_fcut', 'offset_fres',
                   'swing_mix' (0-1), 'gate_time', 'porta_time',
                   'smp_ofs', 'stretch_time', 'time_ofs', 'piano_roll',
                   'arpeggio_time/gate/repeat', 'delay_time', 'crossfade', 'clip'
                   (NOT available: slider_1-5, knob_1-6, mod_x/mod_y, formant, boost)
            value: If provided, write this value; otherwise read current.
                   volume: 0-1, pan: -1..1, pitch: semitones -24..24

        Returns:
            The current (or written) value of the event.
        """
        params: dict = {"channel": channel, "event": event}
        if value is not None:
            params["value"] = value
        conn = get_connection()
        result = conn.send_command("channels.event", params)
        if not result.get("success", False) and "error" in result:
            return {"error": result["error"]}
        return result

    @mcp.tool()
    def fl_channel_loop(channel: int, loop: int | None = None, pattern: int = -1) -> dict:
        """Get or set the loop style of a channel.

        Args:
            channel: Channel index
            loop: Loop style (only when setting):
                  0 = loop off, 1 = loop new, 2 = loop all, -1 = toggle.
                  Omit to only read the current style.
            pattern: Pattern index (default -1 = active pattern)

        Returns:
            dict with the resulting loop style.
        """
        params: dict = {"channel": channel, "pattern": pattern}
        if loop is not None:
            params["loop"] = loop
        conn = get_connection()
        result = conn.send_command("channels.loop", params)
        if not result.get("success", False) and "error" in result:
            return {"error": result["error"]}
        return result

    @mcp.tool()
    def fl_channel_step_param(channel: int, step: int, param: str, value: int | None = None) -> dict:
        """Read or write a step sequencer parameter for a channel's step.

        Args:
            channel: Channel index
            step: Step index
            param: Step parameter: 'note'/'pitch', 'velocity', 'release',
                   'fine_pitch', 'pan', 'mod_x', 'mod_y', 'shift', 'repeat'
            value: If provided, write this value; otherwise read current.

        Returns:
            The current (or written) value of the parameter.
        """
        params: dict = {"channel": channel, "step": step, "param": param}
        if value is not None:
            params["value"] = value
        conn = get_connection()
        result = conn.send_command("channels.stepParam", params)
        if not result.get("success", False) and "error" in result:
            return {"error": result["error"]}
        return result

    @mcp.tool()
    def fl_playlist_info(include_empty: bool = False) -> dict:
        """Get playlist track info (compact: skips default 'Track N' tracks).

        Args:
            include_empty: True to also include default/empty tracks

        Returns:
            {"track_count", "shown", "tracks": [{index, name, color, muted, solo}]}
        """
        conn = get_connection()
        result = conn.send_command("playlist.info", {"include_empty": include_empty})
        if not result.get("success", False) and "error" in result:
            return {"error": result["error"]}
        return result

    @mcp.tool()
    def fl_playlist_set_track_name(track: int, name: str) -> str:
        """Set the name of a playlist track.

        Args:
            track: Playlist track index
            name: New name
        """
        conn = get_connection()
        result = conn.send_command("playlist.setTrackName", {"track": track, "name": name})
        if not result.get("success", False) and "error" in result:
            return f"Error: {result['error']}"
        return f"Playlist track {track} renamed to '{name}'"

    @mcp.tool()
    def fl_playlist_set_track_color(track: int, red: int, green: int, blue: int) -> str:
        """Set the color of a playlist track.

        Args:
            track: Playlist track index
            red, green, blue: RGB components (0-255)
        """
        conn = get_connection()
        result = conn.send_command("playlist.setTrackColor", {
            "track": track,
            "r": red,
            "g": green,
            "b": blue,
        })
        if not result.get("success", False) and "error" in result:
            return f"Error: {result['error']}"
        return f"Playlist track {track} color set"

    @mcp.tool()
    def fl_playlist_mute(track: int, muted: bool | None = None) -> str:
        """Mute/unmute a playlist track.

        Args:
            track: Playlist track index
            muted: True=mut, False=unmut, None=toggle
        """
        conn = get_connection()
        result = conn.send_command("playlist.mute", {"track": track, "muted": muted})
        if not result.get("success", False) and "error" in result:
            return f"Error: {result['error']}"
        return f"Playlist track {track} {'muted' if result.get('muted', muted) else 'unmuted'}"

    @mcp.tool()
    def fl_playlist_solo(track: int, solo: bool | None = None) -> str:
        """Solo/unsolo a playlist track.

        Args:
            track: Playlist track index
            solo: True=solo, False=unsolo, None=toggle
        """
        conn = get_connection()
        result = conn.send_command("playlist.solo", {"track": track, "solo": solo})
        if not result.get("success", False) and "error" in result:
            return f"Error: {result['error']}"
        return f"Playlist track {track} {'soloed' if result.get('solo', solo) else 'unsoloed'}"

    @mcp.tool()
    def fl_playlist_select(track: int, select: bool = True) -> str:
        """Select/deselect a playlist track.

        Args:
            track: Playlist track index
            select: True to select, False to deselect
        """
        conn = get_connection()
        result = conn.send_command("playlist.select", {"track": track, "select": select})
        if not result.get("success", False) and "error" in result:
            return f"Error: {result['error']}"
        return f"Playlist track {track} {'selected' if select else 'deselected'}"

    @mcp.tool()
    def fl_ui_hint(text: str) -> str:
        """Show a hint message in the FL Studio status bar.

        Args:
            text: Message to display
        """
        conn = get_connection()
        result = conn.send_command("ui.hint", {"text": text})
        if not result.get("success", False) and "error" in result:
            return f"Error: {result['error']}"
        return "Hint shown"

    @mcp.tool()
    def fl_piano_dump_score_log(time: int = 10, silent: bool = True) -> str:
        """Dump the played MIDI score into the piano roll of the SELECTED channel.

        This writes whatever MIDI was played (e.g. via fl_trigger_note)
        into the currently selected channel's score as persistent notes.
        Select the channel first (fl_select_channel) and make sure the
        target pattern is active.

        Args:
            time: Number of seconds of score to dump
            silent: True to suppress note preview sounds
        """
        conn = get_connection()
        result = conn.send_command("piano.dumpScoreLog", {
            "time": time,
            "silent": 1 if silent else 0,
        })
        if not result.get("success", False) and "error" in result:
            return f"Error: {result['error']}"
        return f"Score log dumped ({time}s) into selected channel's piano roll"

    @mcp.tool()
    def fl_project_snapshot(include_playlist: bool = False) -> dict:
        """Get a compact snapshot of the whole project state in ONE round-trip.

        Combines channels, patterns, mixer names, transport, tempo, and
        project info into a single response for quick context building.

        Args:
            include_playlist: also include non-default playlist tracks
        """
        conn = get_connection()
        result = conn.send_command("project.snapshot", {"include_playlist": include_playlist})
        if not result.get("success", False) and "error" in result:
            return {"error": result["error"]}
        return result

    @mcp.tool()
    def fl_transport_position() -> dict:
        """Get current playback position (human text, recent beat index, ticks)."""
        conn = get_connection()
        result = conn.send_command("transport.position")
        if not result.get("success", False) and "error" in result:
            return {"error": result["error"]}
        return result

    @mcp.tool()
    def fl_arrangement_info() -> dict:
        """Get arrangement info: time signature events, song end position."""
        conn = get_connection()
        result = conn.send_command("arrangement.info")
        if not result.get("success", False) and "error" in result:
            return {"error": result["error"]}
        return result