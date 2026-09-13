"""
bootstrap.py - New Agent Deterministic Bootstrap Entrypoint
Runs via `uv run python -m courier.chief.bootstrap`
Discovers and prints exact durable Courier mission state from disk.
"""

import sys
import json
from courier.chief.crash_proof_recovery import CrashProofMemoryEngine

def main():
    engine = CrashProofMemoryEngine()
    reconcile = engine.reconcile_on_startup()
    summary = engine.get_bootstrap_summary()
    state = engine.load_durable_state()
    diag = engine.get_resource_diagnostics()

    if "--json" in sys.argv:
        print(json.dumps({
            "summary": summary,
            "reconciliation": reconcile,
            "durable_state": state,
            "diagnostics": diag
        }, indent=2))
    else:
        print(summary)
        print(f"STARTUP RECONCILIATION: {reconcile['reconciliation_case']} -> {reconcile['action_required']}")
        thermal = diag.get("thermal_status") or diag.get("thermal_cause") or "UNPROVEN"
        print(f"SYSTEM: Memory {diag.get('memory_load_pct')}%, Available RAM {diag.get('ram_available_gb')} GB, Thermal {thermal}")

if __name__ == "__main__":
    main()
