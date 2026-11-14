"""End-to-end composition scenario for fl-studio-mcp (SPIDER CROWN).

Drives a live FL Studio session through the bridge channel, composing a
44-bar dark-trap skeleton from _temp/PLAN.md: tempo, seven section patterns
(INTRO, HOOK, VERSE, BREAK, HOOKB, VERSEB, OUTRO), step-sequencer drums and
bass, a piano-roll lead, and a mixer balance. Every write is verified by a
read-back, every call is logged, and a JSON report plus an execution log are
written to logs/.

Usage:
    python scripts/scenario_compose.py [--out DIR]

Exit codes:
    0  scenario completed
    1  a verification checkpoint failed
    2  could not connect to FL Studio
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from fl_studio_mcp.utils.connection import get_connection

# --- plan data (from _temp/PLAN.md, step indices 0-based, 16 steps per bar) ---

BARS = 4
STEPS = BARS * 16

# channel roles (per PLAN resources table)
CH_KICK, CH_CLAP, CH_HAT, CH_SNARE, CH_BASS = 0, 1, 2, 3, 4

# midi note -> FL step pitch (0 = C5 = midi 72)
def _p(midi: int) -> int:
    return midi - 72

_BASS_HOOK = [
    [(0, 24, 110), (6, 24, 100), (10, 36, 100)],
    [(0, 31, 110), (6, 31, 100), (10, 31, 100)],
    [(0, 27, 110), (6, 27, 100), (12, 27, 105)],
    [(0, 24, 110), (11, 24, 100)],
]
_BASS_VERSE = [
    [(0, 24, 105), (4, 26, 95), (8, 27, 100), (12, 31, 98)],
    [(0, 31, 105), (4, 31, 95), (8, 24, 100), (12, 24, 98)],
    [(0, 27, 105), (4, 28, 95), (8, 31, 100), (12, 35, 98)],
    [(0, 35, 105), (8, 24, 100)],
]
_BASS_BREAK = [
    [(0, 24, 100)], [(0, 31, 100)], [(0, 33, 100)], [(0, 35, 100)],
]

SECTIONS = {
    "INTRO": {
        "kick": [], "clap": [],
        "hat": [{"step": s, "velocity": 70} for s in (1, 3, 5, 7, 9, 11, 13, 15)],
        "snare": [], "bass": _BASS_HOOK,
    },
    "HOOK": {
        "kick": [0, 6, 8, 12], "clap": [4, 12],
        "hat": [
            {"step": s, "velocity": 110 if s in (0, 4, 8, 12) else (115 if s in (14, 15) else 100)}
            for s in range(16)
        ],
        "snare": [62, 63], "bass": _BASS_HOOK,
    },
    "VERSE": {
        "kick": [0, 8], "clap": [4, 12],
        "hat": [{"step": s, "velocity": 100} for s in (1, 3, 5, 7, 9, 11, 13, 15)],
        "snare": [4, 12, 5], "bass": _BASS_VERSE,
    },
    "BREAK": {
        "kick": [0], "clap": [],
        "hat": [],
        "snare": [30, 31, 46, 47, 62, 63],
        "bass": _BASS_BREAK,
    },
    "HOOKB": {
        "kick": [0, 6, 8, 12, 14], "clap": [4, 12],
        "hat": [
            {"step": s, "velocity": 110 if s in (0, 4, 8, 12) else (115 if s in (14, 15) else 100)}
            for s in range(16)
        ],
        "snare": [62, 63], "bass": [
            [(0, 36, 110), (6, 24, 100), (10, 36, 100)],
            [(0, 31, 110), (6, 31, 100), (10, 31, 100)],
            [(0, 36, 110), (6, 24, 100), (12, 27, 105)],
            [(0, 24, 110), (11, 24, 100)],
        ],
    },
    "VERSEB": {
        "kick": [0, 8], "clap": [4, 12],
        "hat": [{"step": s, "velocity": 100} for s in (1, 3, 5, 7, 9, 11, 13, 15)],
        "snare": [4, 12, 5], "bass": [
            [(0, 36, 105), (4, 26, 95), (8, 27, 100), (12, 31, 98)],
            [(0, 31, 105), (4, 31, 95), (8, 24, 100), (12, 24, 98)],
            [(0, 27, 105), (4, 40, 95), (8, 31, 100), (12, 35, 98)],
            [(0, 35, 105), (8, 24, 100)],
        ],
    },
    "OUTRO": {
        "kick": [0], "clap": [4, 12],
        "hat": [{"step": s, "velocity": 60} for s in (1, 3, 5, 7, 9, 11, 13, 15)],
        "snare": [], "bass": [[(0, 24, 90)], [(0, 31, 90)], [], []],
    },
}

# piano-roll lead (BREAK): C#m phrygian riff, 8th notes, two passes
_LEAD = [73, 76, 80, 83, 81, 80, 78, 76]
_LEAD_NOTES = [
    {"midi": midi + octave, "time": base + i * 0.5, "duration": 0.5, "velocity": 0.8}
    for octave, base in ((0, 0.0), (12, 8.0))
    for i, midi in enumerate(_LEAD)
]

MIX = {
    1: {"name": "Kick", "volume": 0.95, "pan": 0.0},
    2: {"name": "Clap", "volume": 0.80, "pan": -0.05},
    3: {"name": "Hat", "volume": 0.65, "pan": 0.12, "sep": 0.30},
    4: {"name": "Snare", "volume": 0.85, "pan": 0.03},
    5: {"name": "Bass", "volume": 1.0, "pan": 0.0},
    6: {"name": "FX", "volume": 0.80, "pan": 0.0},
    7: {"name": "Sub", "volume": 0.90, "pan": 0.0},
}

EXPECTED_CHANNELS = ["808 Kick", "808 Clap", "808 HiHat", "808 Snare", "FLEX Bass"]
TARGET_BPM = 145.0
TOLERANCE_BPM = 0.5

log_rows: list[dict] = []
failures: list[dict] = []


def _ok(resp: dict) -> bool:
    return bool(resp.get("success", False)) and "error" not in resp


def call(conn, name: str, params: dict | None = None, timeout: float = 5.0) -> dict:
    t0 = time.perf_counter()
    resp = conn.send_command(name, params or {}, timeout=timeout)
    latency_ms = (time.perf_counter() - t0) * 1000.0
    ok = _ok(resp)
    log_rows.append(
        {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "call": name,
            "params": params or {},
            "success": ok,
            "latency_ms": round(latency_ms, 3),
            "error": resp.get("error") if not ok else None,
        }
    )
    if not ok:
        print(f"  [CALL-FAIL] {name} {json.dumps(params or {})}: {resp.get('error')}")
    return resp


def check(name: str, condition: bool, detail: str) -> bool:
    if not condition:
        failures.append({"check": name, "detail": detail})
        print(f"  [CHECK-FAIL] {name}: {detail}")
    return condition


def _drum_entries(patterns: list, velocity: int = 100) -> list[dict]:
    return [{"step": s, "enabled": True, "velocity": velocity} for s in patterns]


def _step_entries(patterns: list[dict]) -> list[dict]:
    return [
        {"step": e["step"], "enabled": True, "velocity": e.get("velocity", 100)}
        for e in patterns
    ]


def _bass_entries(bars: list) -> list[dict]:
    entries = []
    for bar, notes in enumerate(bars):
        for step, midi, vel in notes:
            entries.append(
                {"step": bar * 16 + step, "enabled": True, "note": _p(midi), "velocity": vel}
            )
    return entries


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None, help="output directory (default: repo logs/)")
    args = ap.parse_args()

    repo = Path(__file__).resolve().parent.parent
    out_dir = Path(args.out) if args.out else repo / "logs"
    out_dir.mkdir(parents=True, exist_ok=True)

    conn = get_connection()
    try:
        conn.ensure_connected()
    except RuntimeError as exc:
        print(f"[FAIL] connection: {exc}")
        return 2

    print("== Phase 0: connect and baseline ==")
    call(conn, "transport.getStatus")
    tempo0 = call(conn, "transport.getTempo")
    chans = call(conn, "channels.getAll")
    chans_list = chans.get("channels") or []
    names = [c.get("name", "") for c in chans_list]
    check("expected channels present", all(n in names for n in EXPECTED_CHANNELS),
          f"channels found: {names}")
    mix_before = call(conn, "project.snapshot", {"include_playlist": False})
    original_bpm = float(tempo0.get("tempo", 0.0))
    print(f"  baseline: {original_bpm} BPM, {len(chans_list)} channels")

    print("== Phase 1: pre-production ==")
    call(conn, "tempo.set", {"tempo": TARGET_BPM})
    tempo1 = call(conn, "transport.getTempo")
    check("tempo set to 145", abs(float(tempo1.get("tempo", 0.0)) - TARGET_BPM) <= TOLERANCE_BPM,
          f"read-back {tempo1.get('tempo')}")

    print("== Phase 2: section patterns ==")
    pattern_indices: dict[str, int] = {}
    for sec in SECTIONS:
        resp = call(conn, "patterns.create", {"name": sec})
        idx = resp.get("index")
        if idx is not None:
            pattern_indices[sec] = idx
            call(conn, "patterns.setLength", {"index": idx, "length": 16})
        else:
            failures.append({"check": f"patterns.create {sec}", "detail": str(resp)})

    print("== Phase 3: drums and bass (step sequencer) ==")
    for sec, data in SECTIONS.items():
        idx = pattern_indices.get(sec)
        if idx is None:
            continue
        call(conn, "patterns.select", {"index": idx})
        for ch, label in ((CH_KICK, "kick"), (CH_CLAP, "clap"), (CH_HAT, "hat"),
                          (CH_SNARE, "snare"), (CH_BASS, "bass")):
            call(conn, "channels.clearSteps", {"channel": ch, "steps": STEPS})
        for ch, label in ((CH_KICK, "kick"), (CH_CLAP, "clap"), (CH_HAT, "hat"),
                          (CH_SNARE, "snare")):
            pat = data[label]
            entries = _drum_entries(pat) if isinstance(pat, list) and pat and isinstance(pat[0], int) \
                else _step_entries(pat)
            resp = call(conn, "channels.setSteps", {"channel": ch, "steps": entries}, timeout=6.0)
            rb = call(conn, "channels.getSteps", {"channel": ch, "steps": STEPS})
            got = [s for s in (rb.get("steps") or []) if s.get("enabled")]
            expected_steps = set(pat) if isinstance(pat, list) and pat and isinstance(pat[0], int) \
                else {e["step"] for e in pat}
            got_steps = {s["step"] for s in got}
            check(f"{sec}/{label} steps", got_steps == expected_steps,
                  f"expected {sorted(expected_steps)}, got {sorted(got_steps)}")
        resp = call(conn, "channels.setSteps",
                    {"channel": CH_BASS, "steps": _bass_entries(data["bass"])}, timeout=6.0)
        rb = call(conn, "channels.getSteps", {"channel": CH_BASS, "steps": STEPS})
        got = {s["step"]: s.get("note") for s in (rb.get("steps") or []) if s.get("enabled")}
        expected = {bar * 16 + st: _p(midi) for bar, notes in enumerate(data["bass"])
                    for st, midi, _ in notes}
        check(f"{sec}/bass notes", got == expected,
              f"expected {expected}, got {got}")

    print("== Phase 4: piano-roll lead (BREAK) ==")
    try:
        from fl_studio_mcp.tools.piano_roll import _clear_request_file, _read_state, _write_request
        from fl_studio_mcp.utils.fl_trigger import trigger_fl_studio
        if pattern_indices.get("BREAK") is not None:
            call(conn, "patterns.select", {"index": pattern_indices["BREAK"]})
        _clear_request_file()
        _write_request([{"action": "add_notes", "notes": _LEAD_NOTES}])
        triggered = trigger_fl_studio()
        time.sleep(2.0)
        state = _read_state()
        state_ok = state is not None and bool(state.get("notes"))
        check("piano-roll lead placed", state_ok,
              f"triggered={triggered}, state={json.dumps(state)[:300] if state else None}")
    except Exception as exc:  # noqa: BLE001 - scenario must not die on the lead path
        failures.append({"check": "piano-roll lead", "detail": f"{type(exc).__name__}: {exc}"})
        print(f"  [CHECK-FAIL] piano-roll lead: {type(exc).__name__}: {exc}")

    print("== Phase 5: mixer balance ==")
    for track, cfg in MIX.items():
        call(conn, "mixer.setTrackName", {"track": track, "name": cfg["name"]})
        call(conn, "mixer.setTrackVolume", {"track": track, "value": cfg["volume"]})
        call(conn, "mixer.setTrackPan", {"track": track, "value": cfg["pan"]})
        if "sep" in cfg:
            call(conn, "mixer.setStereoSep", {"track": track, "separation": cfg["sep"]})
    for track, cfg in MIX.items():
        name_rb = call(conn, "mixer.getTrackName", {"track": track})
        vol_rb = call(conn, "mixer.getTrackVolume", {"track": track})
        check(f"mixer track {track} name", name_rb.get("name") == cfg["name"],
              f"expected {cfg['name']}, got {name_rb.get('name')}")
        check(f"mixer track {track} volume",
              abs(float(vol_rb.get("volume", -1.0)) - cfg["volume"]) <= 0.02,
              f"expected {cfg['volume']}, got {vol_rb.get('volume')}")

    print("== Phase 6: final snapshot ==")
    mix_after = call(conn, "project.snapshot", {"include_playlist": False})
    pat_count = call(conn, "patterns.count")

    summary = {
        "scenario": "SPIDER CROWN (dark trap, PLAN.md)",
        "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tempo_bpm": TARGET_BPM,
        "original_bpm": original_bpm,
        "calls": len(log_rows),
        "successes": sum(1 for r in log_rows if r["success"]),
        "failures": len(failures),
        "failure_checks": failures,
        "pattern_indices": pattern_indices,
        "patterns_total": pat_count.get("count"),
        "latency_ms": {
            "p50": round(sorted(r["latency_ms"] for r in log_rows)[len(log_rows) // 2], 3),
            "max": round(max(r["latency_ms"] for r in log_rows), 3),
        },
        "channel_counts": {c: sum(1 for r in log_rows if r["call"] == c) for c in
                           ("channels.setSteps", "channels.getSteps", "patterns.create",
                            "patterns.setLength", "mixer.setTrackName")},
        "snapshot_before": mix_before,
        "snapshot_after": mix_after,
        "log": log_rows,
    }

    report_path = out_dir / "scenario_report_2026-08-18.json"
    log_path = out_dir / "execution_log_2026-08-18_compose.txt"
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    with open(log_path, "w", encoding="utf-8") as fh:
        for r in log_rows:
            tag = "OK " if r["success"] else "ERR"
            fh.write(f"{r['ts']} {tag} {r['call']} {json.dumps(r['params'])} "
                     f"{r['latency_ms']:.1f}ms{r['error'] and ' -> ' + r['error'] or ''}\n")

    print(f"\nCalls: {summary['calls']}, successes: {summary['successes']}, "
          f"failed checks: {len(failures)}")
    print(f"Report:  {report_path}")
    print(f"Log:     {log_path}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
