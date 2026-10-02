#!/usr/bin/env python3
"""Aggregate soak ``summary.json`` files into a failure trend report.

Usage:
  python3 scripts/soak/failure_trend.py run1/summary.json run2/summary.json --out trend.md

Each input keeps its platform; the report never merges Mac and Windows
evidence into one claim. Exit 0 when every run passes its envelopes,
1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import sys


def _load(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Soak failure trend report")
    ap.add_argument("summaries", nargs="+")
    ap.add_argument("--out", type=str, default="")
    args = ap.parse_args(argv)
    rows = []
    for path in args.summaries:
        data = _load(path)
        verdict = data.get("verdict", {})
        first = data.get("first_sample") or {}
        last = data.get("last_sample") or {}
        rows.append({
            "file": path,
            "platform": (first.get("platform") or "unknown"),
            "cycles": verdict.get("cycles_executed"),
            "pass": verdict.get("pass"),
            "obj_growth": verdict.get("obj_growth"),
            "obj_slope": verdict.get("obj_slope"),
            "rss_growth_kb": verdict.get("rss_growth_kb"),
            "fd_delta": verdict.get("fd_delta"),
            "probes": verdict.get("live_probes"),
        })
    lines = ["# Host Guardian soak failure trend", ""]
    for r in rows:
        lines.append(f"## {r['file']} ({r['platform']})")
        lines.append(f"- PASS: {r['pass']}, cycles: {r['cycles']}")
        lines.append(f"- heap objects growth: {r['obj_growth']}, "
                     f"slope: {r['obj_slope']} obj/cycle")
        lines.append(f"- rss growth (context): {r['rss_growth_kb']} KB")
        lines.append(f"- fd delta: {r['fd_delta']}")
        lines.append(f"- probes: {json.dumps(r['probes'])}")
        lines.append("")
    ok = all(r["pass"] for r in rows)
    lines.append(f"OVERALL: {'PASS' if ok else 'FAIL'} "
                 f"({sum(1 for r in rows if r['pass'])}/{len(rows)} runs)")
    report = "\n".join(lines) + "\n"
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(report)
    else:
        sys.stdout.write(report)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
