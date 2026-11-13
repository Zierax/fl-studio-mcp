"""Benchmark fl-studio-mcp against a live FL Studio instance.

Runs a fixed suite of read calls and write/read-back cycles through the
bridge and reports success rate and latency statistics (p50, p90, p95,
max) per call type and overall. The results are the numbers quoted in
the UIST 2026 workshop position paper (paper/main.tex).

Usage:
    python scripts/benchmark.py [--rounds N] [--json out.json]

Exit codes:
    0  benchmark completed
    2  could not connect to FL Studio
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time

from fl_studio_mcp.utils.connection import get_connection

READ_CALLS = [
    ("transport.getStatus", None),
    ("transport.getTempo", None),
    ("channels.getCount", None),
    ("channels.getInfo", {"channel": 0}),
    ("mixer.getTrackCount", None),
    ("mixer.getTrackInfo", {"track": 0}),
]

WRITE_CALL = ("transport.setTempo", {"tempo": 128.0})
WRITE_READBACK = "transport.getTempo"
WRITE_EXPECTED = 128.0
TOLERANCE_BPM = 0.5


def _ok(resp: dict) -> bool:
    return bool(resp.get("success", False)) and "error" not in resp


def _percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    idx = (len(ordered) - 1) * p
    lo = int(idx)
    hi = min(lo + 1, len(ordered) - 1)
    if lo == hi:
        return ordered[lo]
    frac = idx - lo
    return ordered[lo] * (1 - frac) + ordered[hi] * frac


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=5)
    ap.add_argument("--json", default=None, help="path to write the JSON report")
    args = ap.parse_args()

    conn = get_connection()
    try:
        conn.ensure_connected()
    except RuntimeError as exc:
        print(f"[FAIL] connection: {exc}")
        return 2

    base = conn.send_command("transport.getTempo")
    if not _ok(base):
        print(f"[FAIL] baseline transport.getTempo: {base.get('error', base)}")
        return 1
    original = float(base.get("tempo", 0.0))

    rows: list[dict] = []
    for _ in range(args.rounds):
        for name, params in READ_CALLS:
            t0 = time.perf_counter()
            resp = conn.send_command(name, params or {})
            latency_ms = (time.perf_counter() - t0) * 1000.0
            rows.append(
                {
                    "call": name,
                    "kind": "read",
                    "success": _ok(resp),
                    "latency_ms": round(latency_ms, 3),
                }
            )

        t0 = time.perf_counter()
        written = conn.send_command(WRITE_CALL[0], WRITE_CALL[1])
        write_ms = (time.perf_counter() - t0) * 1000.0
        rows.append(
            {
                "call": f"{WRITE_CALL[0]}({WRITE_CALL[1]['tempo']})",
                "kind": "write",
                "success": _ok(written),
                "latency_ms": round(write_ms, 3),
            }
        )

        t0 = time.perf_counter()
        back = conn.send_command(WRITE_READBACK)
        rb_ms = (time.perf_counter() - t0) * 1000.0
        ok_rb = _ok(back) and abs(float(back.get("tempo", 0.0)) - WRITE_EXPECTED) <= TOLERANCE_BPM
        rows.append(
            {
                "call": f"{WRITE_READBACK}(read-back)",
                "kind": "readback",
                "success": ok_rb,
                "latency_ms": round(rb_ms, 3),
            }
        )

    conn.send_command("transport.setTempo", {"tempo": original})
    check = conn.send_command("transport.getTempo")
    restored = _ok(check) and abs(float(check.get("tempo", 0.0)) - original) <= TOLERANCE_BPM
    if not restored:
        print(f"[WARN] tempo not restored to {original:.2f} BPM")

    def summarize(rows_subset: list[dict]) -> dict:
        lat = [r["latency_ms"] for r in rows_subset]
        ok = sum(1 for r in rows_subset if r["success"])
        return {
            "calls": len(rows_subset),
            "successes": ok,
            "success_rate": round(ok / len(rows_subset), 4) if rows_subset else None,
            "latency_ms": {
                "p50": round(_percentile(lat, 0.50), 3),
                "p90": round(_percentile(lat, 0.90), 3),
                "p95": round(_percentile(lat, 0.95), 3),
                "max": round(max(lat), 3),
                "mean": round(statistics.fmean(lat), 3),
            },
        }

    per_call: dict[str, dict] = {}
    for row in rows:
        per_call[row["call"]] = summarize([r for r in rows if r["call"] == row["call"]])

    report = {
        "rounds": args.rounds,
        "total_calls": len(rows),
        "overall": summarize(rows),
        "reads": summarize([r for r in rows if r["kind"] == "read"]),
        "writes": summarize([r for r in rows if r["kind"] == "write"]),
        "readbacks": summarize([r for r in rows if r["kind"] == "readback"]),
        "tempo_restored": restored,
        "per_call": per_call,
        "raw": rows,
    }

    print(json.dumps(report, indent=2))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
        print(f"report written to {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
