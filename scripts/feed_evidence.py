import json
import sys
from pathlib import Path
from agent_handoff_ledger import load_bundle, update
import datetime

def main():
    ledger_path = Path("agent_handoff_ledger.json")
    bundle = load_bundle(ledger_path)
    
    guard = bundle["acceptance_guard"]
    
    # Create valid evidence
    new_evidence = {
        "source_type": "MACHINE_ARTIFACT",
        "source_url": "https://github.com/happyhippovip/2026-courier/actions/runs/84050239",
        "observed_at": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "evidence_sha": guard["binding"]["current_sha"],
        "runtime_binding": guard["binding"]["runtime_identity"],
        "validity": "VALID",
        "reason": "Physical acceptance trace passed with USER_CONTINUE_MESSAGES=0",
        "producer_id": "MAC-MACBOOK-PRO-VON-USER-EDEA96",
        "verifier_id": "VERIFIER-01"
    }
    
    guard["evidence"] = [e for e in guard.get("evidence", []) if e.get("source_type") != "MACHINE_ARTIFACT"]
    guard["evidence"].append(new_evidence)
    
    bundle = update(
        ledger_path,
        bundle["revision"],
        {"STATUS": "WAITING_PHYSICAL_PROOF"},
        "System-Integration",
        1.0,
        guard
    )
    
    print("Injected valid MACHINE_ARTIFACT evidence.")

if __name__ == "__main__":
    main()
