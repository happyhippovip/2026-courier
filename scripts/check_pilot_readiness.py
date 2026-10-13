#!/usr/bin/env python3
import sys
import os
from pathlib import Path

def check_readiness():
    print("Checking Pilot Readiness...")

    repo_root = Path(__file__).resolve().parent.parent
    expected_files = [
        "ops/ai/PILOT_DUMMY_TASK.json",
        "ops/ai/PILOT_METRICS_AND_CONTRACT.md",
        "ops/ai/PILOT_METRICS_AND_SIGNAL_SPEC.md",
        "ops/ai/PROVIDER_ISOLATION_SPEC.md"
    ]

    for rel in expected_files:
        if not os.path.exists(repo_root / rel):
            print(f"FAILED: Missing {rel}")
            sys.exit(1)
            
    print("ALL PILOT PREREQUISITES PRESENT. GATE REMAINS LOCKED UNTIL EXPLICIT PHYSICAL SIGNAL.")
    sys.exit(0)

if __name__ == "__main__":
    check_readiness()
