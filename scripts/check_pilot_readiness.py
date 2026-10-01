#!/usr/bin/env python3
import sys
import os

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
