"""Tests for the MIDI port selection logic.

Picking the first available MIDI port makes the bridge talk to a software
synth instead of the virtual port FL Studio listens on, which is the exact
symptom reported in GitHub issue #2.
"""

from __future__ import annotations

import pytest

from fl_studio_mcp.utils.ports import describe_choice, find_port, normalize_port_name, score_port


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("FLStudioMCP 1", "flstudiomcp1"),
        ("FL Studio MCP 1", "flstudiomcp1"),
        ("fl-studio-mcp", "flstudiomcp"),
        ("  FLStudioMCP  ", "flstudiomcp"),
        ("", ""),
    ],
)
def test_normalize_port_name(name, expected):
    assert normalize_port_name(name) == expected


def test_bridge_port_outranks_a_software_synth():
    ports = ["Microsoft GS Wavetable Synth 0", "FL Studio MCP 1"]
    assert find_port(ports) == "FL Studio MCP 1"


def test_bridge_port_outranks_other_virtual_ports():
    ports = ["loopMIDI Port 1", "FLStudioMCP 1", "IAC Driver Bus 1"]
    assert find_port(ports) == "FLStudioMCP 1"


def test_software_synth_is_never_chosen_automatically():
    ports = ["Microsoft GS Wavetable Synth 0", "Microsoft MIDI Synth 1"]
    # Nothing looks like the bridge, so the first port is used as a last
    # resort -- but the choice is reported as a guess.
    chosen = find_port(ports)
    assert chosen == ports[0]
    assert describe_choice(ports, chosen)["is_guess"] is True


def test_explicit_port_wins():
    ports = ["Microsoft GS Wavetable Synth 0", "FL Studio MCP 1"]
    assert find_port(ports, preferred="FL Studio MCP 1") == "FL Studio MCP 1"


def test_explicit_port_matches_case_insensitively():
    ports = ["fl studio mcp 1"]
    assert find_port(ports, preferred="FL Studio MCP 1") == "fl studio mcp 1"


def test_explicit_port_matches_as_a_substring():
    ports = ["FLStudioMCP 1", "other"]
    assert find_port(ports, preferred="flstudiomcp") == "FLStudioMCP 1"


def test_unknown_explicit_port_returns_none():
    ports = ["FLStudioMCP 1"]
    assert find_port(ports, preferred="does not exist") is None


def test_no_ports_returns_none():
    assert find_port([]) is None


def test_score_prefers_the_bridge():
    assert score_port("FLStudioMCP 1") > score_port("loopMIDI 1")
    assert score_port("loopMIDI 1") > score_port("Microsoft GS Wavetable Synth 0")
    assert score_port("Microsoft GS Wavetable Synth 0") <= 0


def test_describe_choice_reports_the_score():
    ports = ["Microsoft GS Wavetable Synth 0", "FLStudioMCP 1"]
    chosen = find_port(ports)
    description = describe_choice(ports, chosen)
    assert description["chosen"] == "FLStudioMCP 1"
    assert description["is_guess"] is False
    assert description["score"] > 0
    assert set(description["scores"]) == set(ports)
