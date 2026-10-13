#!/usr/bin/env python3
import sys
import os

def _whole_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, float) and not value.is_integer():
        return None
    return int(value)


def pilot_failure_aborts(record):
    """Halt a pilot on the negative signal from the metrics spec.

    Required counts are hipg and ndr_pct. A human intervention or a duplicate
    execution aborts. A missing or non-numeric count aborts. An explicit
    out-of-scope verifier accept or an unrecovered daemon crash aborts.
    hipg 0 and ndr_pct 100 do not abort: that is not the negative signal.
    """
    if not isinstance(record, dict):
        return True
    if "hipg" not in record or "ndr_pct" not in record:
        return True
    hipg = _whole_number(record.get("hipg"))
    ndr_pct = _whole_number(record.get("ndr_pct"))
    if hipg is None or ndr_pct is None:
        return True
    if hipg < 0 or ndr_pct < 0 or ndr_pct > 100:
        return True
    if hipg > 0 or ndr_pct < 100:
        return True
    if record.get("verifier_accepted_out_of_scope") is True:
        return True
    if record.get("daemon_failed_to_recover") is True:
        return True
    return False


def check_readiness():
    print("Checking Pilot Readiness...")
    
    expected_files = [
        "ops/ai/PILOT_DUMMY_TASK.json",
        "ops/ai/PILOT_METRICS_AND_CONTRACT.md",
        "ops/ai/PILOT_METRICS_AND_SIGNAL_SPEC.md",
        "ops/ai/PROVIDER_ISOLATION_SPEC.md"
    ]
    
    for f in expected_files:
        if not os.path.exists(f):
            print(f"FAILED: Missing {f}")
            sys.exit(1)
            
    print("ALL PILOT PREREQUISITES PRESENT. GATE REMAINS LOCKED UNTIL EXPLICIT PHYSICAL SIGNAL.")
    sys.exit(0)

if __name__ == "__main__":
    check_readiness()
