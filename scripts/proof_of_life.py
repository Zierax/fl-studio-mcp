"""Proof-of-life check for fl-studio-mcp.

Runs a minimal write -> read-back -> assert scenario against a live FL
Studio instance to verify the bridge end-to-end:

1. Connect to FL Studio through the MIDI + JSON transport.
2. Read the current tempo, write a known tempo, read it back, and assert
   the read-back matches the write (within tolerance).
3. Read channel count and the first channel name as read-only sanity.
4. Restore the original tempo and verify the restore.

Usage:
    python scripts/proof_of_life.py

Exit codes:
    0  all assertions passed
    1  an assertion failed or the bridge returned an error
    2  could not connect to FL Studio (is it running with the
       FLStudioMCP controller enabled?)
"""

from __future__ import annotations

import sys

from fl_studio_mcp.utils.connection import get_connection

TOLERANCE_BPM = 0.5
TEST_TEMPO = 146.0


def _ok(resp: dict) -> bool:
    return bool(resp.get("success", False)) and "error" not in resp


def main() -> int:
    conn = get_connection()
    try:
        conn.ensure_connected()
    except RuntimeError as exc:
        print(f"[FAIL] connection: {exc}")
        return 2

    base = conn.send_command("transport.getTempo")
    if not _ok(base):
        print(f"[FAIL] transport.getTempo: {base.get('error', base)}")
        return 1
    original = float(base.get("tempo", 0.0))
    print(f"[OK] baseline tempo: {original:.2f} BPM")

    written = conn.send_command("transport.setTempo", {"tempo": TEST_TEMPO})
    if not _ok(written):
        print(f"[FAIL] transport.setTempo: {written.get('error', written)}")
        return 1

    back = conn.send_command("transport.getTempo")
    if not _ok(back):
        print(f"[FAIL] read-back transport.getTempo: {back.get('error', back)}")
        return 1
    got = float(back.get("tempo", 0.0))
    if abs(got - TEST_TEMPO) <= TOLERANCE_BPM:
        print(f"[OK] tempo write/read-back: wrote {TEST_TEMPO:.2f} BPM, read back {got:.2f} BPM")
    else:
        print(f"[FAIL] tempo mismatch: wrote {TEST_TEMPO:.2f} BPM, read back {got:.2f} BPM")
        return 1

    restored = conn.send_command("transport.setTempo", {"tempo": original})
    if not _ok(restored):
        print(f"[FAIL] restore transport.setTempo: {restored.get('error', restored)}")
        return 1
    check = conn.send_command("transport.getTempo")
    if not _ok(check) or abs(float(check.get("tempo", 0.0)) - original) > TOLERANCE_BPM:
        print(f"[FAIL] tempo not restored to {original:.2f} BPM")
        return 1
    print(f"[OK] tempo restored to {original:.2f} BPM")

    count = conn.send_command("channels.getCount")
    if not _ok(count):
        print(f"[FAIL] channels.getCount: {count.get('error', count)}")
        return 1
    n = int(count.get("count", 0))
    print(f"[OK] channel count: {n}")

    if n > 0:
        info = conn.send_command("channels.getInfo", {"channel": 0})
        if not _ok(info):
            print(f"[FAIL] channels.getInfo: {info.get('error', info)}")
            return 1
        name = info.get("name", "<none>")
        print(f"[OK] first channel: {name}")

    print("[PASS] proof of life OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())