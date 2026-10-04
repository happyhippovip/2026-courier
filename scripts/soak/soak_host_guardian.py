#!/usr/bin/env python3
"""Optional Host Guardian endurance soak (manual / workflow_dispatch only).

Runs accelerated admission cycles plus checkpoint IO against the Issue #76
``scripts/host_capacity.py`` slice, samples real host baselines, and writes
``summary.json`` + ``summary.md`` into --out. Never writes into the repo
tree; never runs on push/PR/schedule (see
``.github/workflows/host-endurance-soak.yml``).

Examples:
  python3 scripts/soak/soak_host_guardian.py --cycles 5000 --slots 64
  python3 scripts/soak/soak_host_guardian.py --seconds 28800 --cycle-delay-ms 1000 --out /tmp/soak-night
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import random
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from scripts import host_capacity as HC
from scripts.soak import baseline_metrics as BM
from courier_worker import host as H

ENVELOPES = {
    # Product-heap envelopes (gc object counts): the leak signal the harness
    # owns. RSS is reported for context only -- the sampler itself (subprocess
    # pipes, psutil caches, allocator high-water) moves harness RSS by ~1 MB
    # per 20 samples while the pure admission loop grows 0 KB (verified), so
    # gating on harness RSS would false-alarm on measurement noise.
    "obj_growth_max": 500,
    "obj_slope_max": 2.0,  # objects per cycle, post-warmup least-squares
    "fd_delta_max": 8,
    "checkpoint_max_bytes": 64 * 1024,
    "cleanup_wall_max_s": 30.0,
}


def _snapshot(i: int, rng: random.Random) -> HC.HostSnapshot:
    # Mostly healthy; periodic pressure spike (sleep/wake) and rare EMFILE
    # pause (network-loss/provider-quota class). Deterministic per seed.
    if i % 97 == 96:
        return HC.HostSnapshot(recent_emfile=True)
    if i % 23 == 22:
        return HC.HostSnapshot(load_1=24.0, cores=8, memory_pressure="HIGH",
                               swap_paging=True, thermal="NOMINAL")
    return HC.HostSnapshot(load_1=round(rng.uniform(0.5, 4.0), 3), cores=8,
                           memory_pressure="NOMINAL", swap_paging=False,
                           thermal="NOMINAL")


def _live_probe(workdir: str) -> dict:
    home = os.path.join(workdir, "live-probe-home")
    host = H.WorkerHost(home, pressure_probe=lambda: None)
    spec = H.ExecutionSpec(
        task_id="soak-probe", attempt=1, dispatch_id="d-soak-probe",
        worker_id="w-soak", result_id="r-d-soak-probe",
        argv=(sys.executable, "-c", "import time; time.sleep(30)"),
        timeout_s=1.0, lease_ttl_s=30.0,
        artifact_dir=os.path.join(home, "artifacts", "probe"),
        heartbeat_s=0.2)
    start = time.monotonic()
    res = host.run_once(spec)
    wall = time.monotonic() - start
    orphans = H.run_orphan_gate(home)
    return {"outcome": res.outcome, "cleanup_latency_s": round(wall, 3),
            "orphan_records_left": orphans,
            "within_envelope": wall <= ENVELOPES["cleanup_wall_max_s"]
            and res.outcome == H.Outcome.TIMEOUT and orphans == 0}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Host Guardian endurance soak")
    ap.add_argument("--cycles", type=int, default=5000)
    ap.add_argument("--slots", type=int, default=64)
    ap.add_argument("--seconds", type=float, default=0.0,
                    help="timed-soak budget; 0 = cycle-count mode only")
    ap.add_argument("--cycle-delay-ms", type=float, default=0.0,
                    help="coalesced delay between cycles (no busy poll)")
    ap.add_argument("--live-probes", type=int, default=2)
    ap.add_argument("--seed", type=int, default=76)
    ap.add_argument("--out", type=str, default="",
                    help="artifact dir; default: fresh temp dir")
    args = ap.parse_args(argv)
    if args.cycles < 1 or args.cycles > 1_000_000:
        print("cycles must be within [1, 1000000]", file=sys.stderr)
        return 2
    if args.seconds < 0 or args.seconds > 7 * 86400:
        print("seconds budget exceeds the 7-day soak ceiling", file=sys.stderr)
        return 2
    out = args.out or tempfile.mkdtemp(prefix="host-soak-")
    os.makedirs(out, exist_ok=True)
    rng = random.Random(args.seed)
    active = 0
    # Bounded harness memory: scalars and min/max only, never the full
    # per-cycle history, so the harness cannot be the leak it hunts.
    waiting_min = waiting_max = None
    waiting_distinct: set = set()
    rss_series, fd_series, obj_series = [], [], []
    first_sample = last_sample = None
    checkpoint_every = max(1, args.cycles // 20)
    deadline = time.monotonic() + args.seconds if args.seconds else None
    i = 0
    delay_s = max(0.0, args.cycle_delay_ms / 1000.0)
    while i < args.cycles and (deadline is None or time.monotonic() < deadline):
        snap = _snapshot(i, rng)
        adm = HC.admit_capacity(args.slots, active, 0, snap, HC.NORMAL_PROFILE)
        if adm.health == HC.HEALTHY:
            active = adm.admitted_active
        w = adm.waiting_slots
        waiting_distinct.add(w)
        waiting_min = w if waiting_min is None else min(waiting_min, w)
        waiting_max = w if waiting_max is None else max(waiting_max, w)
        if i % checkpoint_every == 0:
            HC.save_checkpoint(out, adm.health, adm, [],
                               last_resource_event="SOAK_CYCLE_%d" % i)
            sample = BM.collect_sample(log_dirs=[out])
            if first_sample is None:
                first_sample = sample
            last_sample = sample
            rss = sample.get("rss_kb")
            if isinstance(rss, int):
                rss_series.append(rss)
            fd = sample.get("fd_count")
            if isinstance(fd, int):
                fd_series.append(fd)
            gc.collect()
            # x-axis in cycles (not sample index) so the slope unit is
            # objects/cycle regardless of checkpoint spacing.
            obj_series.append((i, len(gc.get_objects())))
        if delay_s:
            time.sleep(delay_s)
        i += 1
    probes = [_live_probe(out) for _ in range(max(0, args.live_probes))]
    verdict = {"cycles_executed": i, "live_probes": probes}
    # Warmup discard (standard soak practice): allocator high-water mark and
    # one-time imports settle in the first quarter; the leak verdict uses the
    # post-warmup slope only. Growth is still reported end-to-end honestly.
    cut = len(obj_series) // 4
    steady_obj = obj_series[cut:]
    steady_fd = fd_series[len(fd_series) // 4:] if fd_series else []
    verdict["warmup_samples_discarded"] = cut
    verdict["waiting_min"] = waiting_min
    verdict["waiting_max"] = waiting_max
    if obj_series:
        verdict["obj_growth"] = obj_series[-1][1] - obj_series[0][1]
        verdict["obj_slope"] = BM.slope([x for x, _ in steady_obj],
                                        [y for _, y in steady_obj])
        verdict["obj_within_envelope"] = (
            verdict["obj_growth"] <= ENVELOPES["obj_growth_max"]
            and verdict["obj_slope"] <= ENVELOPES["obj_slope_max"])
    if rss_series:
        verdict["rss_growth_kb"] = rss_series[-1] - rss_series[0]
        verdict["rss_report_only"] = True
    if fd_series:
        verdict["fd_delta"] = steady_fd[-1] - steady_fd[0] if steady_fd else 0
        verdict["fd_within_envelope"] = verdict["fd_delta"] <= ENVELOPES["fd_delta_max"]
    verdict["probes_within_envelope"] = all(p["within_envelope"] for p in probes)
    verdict["pass"] = all([
        verdict.get("obj_within_envelope", True),
        verdict.get("fd_within_envelope", True),
        verdict["probes_within_envelope"],
    ])
    summary = {"envelopes": ENVELOPES, "args": vars(args),
               "first_sample": first_sample,
               "last_sample": last_sample,
               "verdict": verdict}
    with open(os.path.join(out, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, default=str)
    with open(os.path.join(out, "summary.md"), "w", encoding="utf-8") as fh:
        fh.write("# Host Guardian soak summary\n\n")
        fh.write(f"- cycles: {i}, slots: {args.slots}, seed: {args.seed}\n")
        if obj_series:
            fh.write(f"- heap objects growth: {verdict['obj_growth']}, "
                     f"slope: {verdict['obj_slope']:.4f} obj/cycle\n")
        if rss_series:
            fh.write(f"- rss growth (context only): {verdict['rss_growth_kb']} KB\n")
        if fd_series:
            fh.write(f"- fd delta: {verdict['fd_delta']}\n")
        fh.write(f"- live probes: {json.dumps(probes)}\n")
        fh.write(f"- PASS: {verdict['pass']}\n")
    print(f"soak artifacts: {out} PASS={verdict['pass']}")
    return 0 if verdict["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
