"""Heartbeat liveness prober with progressive quiet, slow, probing and lease revocation states.

Lane L3. Evaluates worker heartbeat freshness across progressive silence states:
- WORKING: heartbeat received recently (< warning_s)
- QUIET: slight silence, within normal bounds (warning_s..slow_s)
- SLOW: elevated silence, active ping recommended (slow_s..probe_s)
- PROBING: extended silence, actively probing worker (probe_s..timeout_s)
- FAILED: hard deadline exceeded (> timeout_s), triggers fail-closed lease revocation
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class LivenessPolicy:
    warning_s: float = 5.0
    slow_s: float = 10.0
    probe_s: float = 20.0
    timeout_s: float = 30.0


@dataclass
class LivenessReport:
    state: str  # "WORKING", "QUIET", "SLOW", "PROBING", "FAILED"
    elapsed_s: float
    should_ping: bool
    should_revoke: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def probe_liveness(
    last_heartbeat_at: float,
    current_time: Optional[float] = None,
    policy: Optional[LivenessPolicy] = None,
) -> LivenessReport:
    pol = policy or LivenessPolicy()
    now = current_time if current_time is not None else time.time()
    if (
        isinstance(last_heartbeat_at, bool)
        or not isinstance(last_heartbeat_at, (int, float))
        or math.isnan(last_heartbeat_at)
        or math.isinf(last_heartbeat_at)
        or last_heartbeat_at <= 0
        or math.isnan(now)
    ):
        return LivenessReport(
            state="FAILED",
            elapsed_s=float(pol.timeout_s + 1.0),
            should_ping=False,
            should_revoke=True,
        )
    elapsed = max(0.0, round(now - last_heartbeat_at, 3))

    if elapsed <= pol.warning_s:
        state = "WORKING"
        should_ping = False
        should_revoke = False
    elif elapsed <= pol.slow_s:
        state = "QUIET"
        should_ping = False
        should_revoke = False
    elif elapsed <= pol.probe_s:
        state = "SLOW"
        should_ping = True
        should_revoke = False
    elif elapsed <= pol.timeout_s:
        state = "PROBING"
        should_ping = True
        should_revoke = False
    else:
        state = "FAILED"
        should_ping = False
        should_revoke = True

    return LivenessReport(
        state=state,
        elapsed_s=elapsed,
        should_ping=should_ping,
        should_revoke=should_revoke,
    )


def inspect_workers_liveness(
    workers_heartbeats: dict[str, float],
    current_time: Optional[float] = None,
    policy: Optional[LivenessPolicy] = None,
) -> dict[str, LivenessReport]:
    now = current_time if current_time is not None else time.time()
    reports = {}
    for wid, last_hb in workers_heartbeats.items():
        reports[wid] = probe_liveness(float(last_hb), current_time=now, policy=policy)
    return reports


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="courier_core.liveness_prober",
        description="Probe worker heartbeat liveness and determine lease revocation.",
    )
    parser.add_argument("heartbeats_json", help="Path to JSON file with {'workers': {<wid>: <timestamp>}}")
    parser.add_argument("--warning-s", type=float, default=5.0)
    parser.add_argument("--slow-s", type=float, default=10.0)
    parser.add_argument("--probe-s", type=float, default=20.0)
    parser.add_argument("--timeout-s", type=float, default=30.0)
    args = parser.parse_args(argv)

    try:
        with open(args.heartbeats_json, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        print(json.dumps({"error": f"failed to read {args.heartbeats_json}: {exc}"}))
        return 1

    policy = LivenessPolicy(
        warning_s=args.warning_s,
        slow_s=args.slow_s,
        probe_s=args.probe_s,
        timeout_s=args.timeout_s,
    )

    workers = data.get("workers") or {}
    reports = inspect_workers_liveness(workers, policy=policy)

    revocations = [wid for wid, r in reports.items() if r.should_revoke]
    all_healthy = len(revocations) == 0

    out = {
        "all_healthy": all_healthy,
        "revocations_needed": revocations,
        "reports": {wid: r.to_dict() for wid, r in reports.items()},
    }
    print(json.dumps(out, indent=2))
    return 0 if all_healthy else 1


if __name__ == "__main__":
    sys.exit(main())
