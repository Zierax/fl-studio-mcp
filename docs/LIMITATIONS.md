# Limitations

This is the honest list of what FL Studio's scripting API allows — and
crucially, what it does **not**. Read it once, and you will not waste prompts
on things the server can never do.

## Cannot do (by design of the FL API — no workaround exists)

### Create channels or load audio files

There is no FL API function to:

- add a new channel to the channel rack,
- load a sample / audio file into a channel,
- instantiate a plugin.

The server can only control channels that **already exist** in the open
project. Loading an acapella: open the **browser**, click the file, drag it
into the rack/playlist manually — the server will then happily program and
mix that channel.

### Place clips on the playlist timeline

`playlist` API functions cover track names, colors, mute/solo and state
reads. There is no call to drop a pattern clip or audio clip onto the
timeline. Pattern *management* (create/select/rename/clone/clear) is fully
automated; **arranging** is a manual step in FL Studio.

### Load or instantiate plugins

Plugins already present in the project can be fully controlled (params,
presets, colors) — but nothing can be added. Also, some 3rd-party VSTs don't
report parameter names; `fl_get_plugin_params` will return indices/values,
and `fl_plugin_param_name_to_index` is your friend.

### Persist live note triggers

`fl_trigger_note` plays audio through the channel as a preview. Unless FL
recording is active, this is **not** written into the pattern — consistent
with FL's own behavior. For written music, use the step sequencer or piano
roll tools.

### Read audio waveform / render the mix

The API is control-plane only. There is no "get audio samples" or "render to
file" call. (For arranging + rendering, use FL Studio's own export.)

## Partial / version-dependent

| Area | Reality |
|------|---------|
| API surface | FL's Python API has grown over versions; some functions exist only in newer builds. Use `fl_api_list_functions` to discover what *your* FL Studio exposes. |
| Plugin params | Names, ranges, and units are plugin-provided; not all plugins cooperate. |
| UI automation | `ui.*` functions (focus forms, browser navigation, popup menus) exist and are exposed via raw access, but they depend on the window being open (e.g. browser must be visible and focused). |
| Preview = state change | Some `ui.*`/transport functions mutate FL's visible state — the server always reads back and returns the authoritative value. |

## Performance & safety

- One JSON round-trip per call; each takes a few ms inside FL Studio. Batch
  heavy work (e.g. whole patterns) into single calls rather than many small
  ones.
- The controller executes commands synchronously in FL's script thread — do
  not run thousands of calls in a tight loop while playback is active.
- Undo: the server can save/restore undo points (`fl_save_undo`, `fl_undo`),
  but FL's undo count/stack depends on its own "undoable" model — big
  scripted edits may coalesce. Save the project (Ctrl+S) before risky
  experiments, or snapshot with `fl_project_snapshot`.