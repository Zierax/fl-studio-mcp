# logs — Run artifacts

Output of real sessions, kept as evidence rather than as documentation.

| File | What it is |
|------|------------|
| `execution_log_2026-08-17.txt` | Per-call log of a production session (tool, params, latency, error) |
| `execution_log_2026-08-18_compose.txt` | Per-call log of the full composition scenario |
| `scenario_report_2026-08-18.json` | The scenario report: snapshot before/after, per-call log, verification results |
| `benchmark_report_2026-08-17.json` | Bridge benchmark: success rate and latency percentiles (p50/p90/p95) |

These are **generated**, not hand-written. They are committed because they
are the evidence behind the claims in the docs — how fast the bridge is,
what the failure modes look like in practice, and what a full session
actually does.

## Regenerating them

```bash
# bridge benchmark
uv run python scripts/benchmark.py --rounds 50 --json logs/benchmark_report.json

# full composition scenario (needs FL Studio running with the controller)
uv run python scripts/scenario_compose.py --out logs
```

Both scripts write into this folder by default. They are session
artifacts, not part of the API surface — do not depend on their exact
shape.
