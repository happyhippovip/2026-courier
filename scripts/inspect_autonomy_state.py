#!/usr/bin/env python3
"""Mission: Autonomy Control Plane V2 - Bounded State Inspection Utility.

Standard repository command for routine observation (replacing arbitrary inline python3 -c).
Provides JSON and human-readable summaries of runtime sessions, worker states, and readiness.
"""

import argparse
import json
import sys
from pathlib import Path

COURIER_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(COURIER_DIR))

from scripts.snitch_observer import SnitchObserver


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect Autonomy Control Plane State & Worker Health")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    parser.add_argument("--reconcile", action="store_true", help="Reconcile dead orphan processes")
    args = parser.parse_args()

    observer = SnitchObserver(repo_dir=COURIER_DIR)

    if args.reconcile:
        reconciled = observer.reconcile_orphans()
        if not args.json:
            print(f"[RECONCILE] Reconciled {reconciled} orphaned session records to STALE_RUNNING_OFFLINE")

    readiness = observer.compute_operational_readiness()
    observations = observer.inspect_workspace()

    if args.json:
        payload = {
            "readiness": readiness.to_dict(),
            "workers": [obs.to_dict() for obs in observations],
        }
        print(json.dumps(payload, indent=2))
        return 0

    print("=================================================================")
    print("  AUTONOMY CONTROL PLANE V2 - LIVE STATE INSPECTION")
    print("=================================================================")
    print(f"  Readiness Status:               {readiness.readiness.value}")
    print(f"  Safe for Unattended Operation:  {'YES' if readiness.safe_for_unattended_operation else 'NO'}")
    print(f"  Crash Safety Oracle:            {'PASSED' if readiness.crash_safety_oracle_passed else 'FAILED'}")
    print(f"  Active Workers (Alive):         {readiness.active_workers_count}")
    print(f"  Permission Blocked:             {readiness.permission_blocked_count}")
    print(f"  Hung Workers:                   {readiness.hung_workers_count}")
    print(f"  Stale Orphans:                  {readiness.stale_orphans_count}")
    print(f"  Autonomous Spend Limit:         {readiness.autonomous_spend_limit_eur:.2f} EUR")
    print(f"  Publication Authorization:      {readiness.publication_auth_inference}")
    print("-----------------------------------------------------------------")
    if readiness.reasons:
        print("  BLOCKING REASONS / WARNINGS:")
        for r in readiness.reasons:
            print(f"    - {r}")
    else:
        print("  All safety gates satisfied: SYSTEM LIVE & READY.")
    print("=================================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
