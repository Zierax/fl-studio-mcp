"""Choose the right MIDI port for the FL Studio bridge.

Picking the first available MIDI output port is not good enough: a machine
usually exposes a dozen of them (sound synths, virtual instruments, DAW
ports) and the bridge has to talk to the *virtual port that FL Studio is
listening on*.  Selecting the wrong port -- for example
``Microsoft GS Wavetable Synth 0`` -- makes every call time out even though
the server, the controller script and the virtual port are all fine.

The scoring below prefers ports that are obviously meant for the bridge and
penalises the well known software synths, so the best candidate wins while
an explicit user choice always takes precedence.
"""

from __future__ import annotations

import re

#: Normalised names that strongly indicate the FL Studio MCP bridge.
_BRIDGE_MARKERS = ("flstudiomcp",)

#: Normalised names that indicate a MIDI bridge of some kind.
_MCP_MARKERS = ("mcp",)

#: Normalised names of well known software synths and virtual instruments.
#: These are never the port FL Studio listens on.
_SYNTH_MARKERS = (
    "gswavetable",
    "microsoftmidi",
    "microsoftgs",
    "gs synth",
    "synth",
    "wavetable",
    "timidity",
    "fluid",
    "soundfont",
    "microsoftgswavetable",
)

#: Normalised names of virtual MIDI drivers that are commonly used to
#: create the bridge port.
_VIRTUAL_MARKERS = ("loopmidi", "loopback", "iac", "vb", "midi")

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalize_port_name(name: str) -> str:
    """Normalise a MIDI port name for comparison.

    ``"FL Studio MCP 1"`` and ``"FLStudioMCP 1"`` both become
    ``"flstudiomcp1"``.
    """
    return _NON_ALNUM.sub("", (name or "").lower())


def score_port(name: str) -> int:
    """Score a MIDI port name; higher is better.

    A score of ``0`` means "never pick this port automatically".
    """
    normalized = normalize_port_name(name)
    if not normalized:
        return 0

    score = 0

    if any(marker in normalized for marker in _BRIDGE_MARKERS):
        # The dedicated FL Studio MCP port.
        score += 100
    elif any(marker in normalized for marker in _MCP_MARKERS):
        # Some other MCP bridge port.
        score += 40
    elif any(marker in normalized for marker in _VIRTUAL_MARKERS):
        # A virtual MIDI driver, but not named after the bridge.
        score += 10

    if any(marker in normalized for marker in _SYNTH_MARKERS):
        score -= 50

    return score


def find_port(port_names: list[str], preferred: str | None = None) -> str | None:
    """Return the best MIDI port for the FL Studio bridge.

    Args:
        port_names: All MIDI output ports reported by the system.
        preferred: An explicitly requested port name. It wins over the
            automatic scoring whenever it matches (exactly or as a
            case-insensitive substring).

    Returns:
        The chosen port name, or ``None`` when nothing suitable exists.
    """
    if not port_names:
        return None

    if preferred:
        wanted = preferred.strip().lower()
        for name in port_names:
            if name.lower() == wanted:
                return name
        for name in port_names:
            if wanted in name.lower():
                return name
        return None

    best_score = None
    best_name: str | None = None
    for name in port_names:
        score = score_port(name)
        # Strict comparison keeps the earliest port on ties.
        if best_score is None or score > best_score:
            best_score = score
            best_name = name

    if best_name is None:
        return None

    if best_score is not None and best_score <= 0:
        # Nothing looked like the bridge: fall back to the first port so the
        # connection still has a chance, but the caller is told it was a
        # guess (see ``is_guess``).
        return port_names[0]

    return best_name


def describe_choice(port_names: list[str], chosen: str | None) -> dict[str, object]:
    """Describe how a port was selected (used by the status tools)."""
    scores = {name: score_port(name) for name in port_names}
    guess = False
    if chosen is not None:
        guess = scores.get(chosen, 0) <= 0
    return {
        "chosen": chosen,
        "score": scores.get(chosen, 0) if chosen else 0,
        "is_guess": guess,
        "scores": scores,
    }
