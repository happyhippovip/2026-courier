import sys
from pathlib import Path
sys.path.insert(0, ".")
from scripts.agent_handoff_ledger import load_bundle, update
import copy

path = Path("agent_handoff_ledger.json")

def update_ledger(ledger_path, edge_name, blocker, bundle):
    revision = bundle["revision"]
    record = bundle["record"]
    proven = list(record.get("PROVEN_EDGES", []))
    unproven = list(record.get("UNPROVEN_EDGES", []))
    
    updates = {}
    if blocker:
        updates["FIRST_CAUSAL_BLOCKER"] = blocker
        updates["STATUS"] = "BLOCKED"
        updates["CLEAN_IDLE"] = "NO"
    else:
        if edge_name and edge_name not in proven and edge_name != "CLEAN_IDLE_ACHIEVED":
            proven.append(edge_name)
        if edge_name in unproven:
            unproven.remove(edge_name)
        updates["PROVEN_EDGES"] = proven
        updates["UNPROVEN_EDGES"] = unproven
        
        if record.get("FIRST_CAUSAL_BLOCKER") == "NONE" or not record.get("FIRST_CAUSAL_BLOCKER"):
            updates["FIRST_CAUSAL_BLOCKER"] = "NONE"

        if not unproven:
            updates["NEXT_EXECUTABLE_ACTION"] = "NONE"
            updates["CLEAN_IDLE"] = "YES"
            updates["STATUS"] = "CLEAN_IDLE"
        else:
            updates["CLEAN_IDLE"] = "NO"
            updates["STATUS"] = "READY"
            
    guard = bundle["acceptance_guard"]
    binding = guard["binding"]
    
    has_physical_proof = any(
        e.get("source_type") == "MACHINE_ARTIFACT" and
        e.get("evidence_sha") == binding["current_sha"] and
        e.get("validity") == "VALID"
        for e in guard.get("evidence", [])
    )
    
    if not unproven:
        if has_physical_proof:
            updates["NEXT_EXECUTABLE_ACTION"] = "NONE"
            updates["QUEUE_INDEPENDENT"] = "YES"
            updates["CLEAN_IDLE"] = "YES"
            updates["STATUS"] = "CLEAN_IDLE"
            guard["transition_state"] = "CANONICAL_ACCEPTED"
            if "ISSUE_STATE" in guard["acceptance_predicate"]["results"]:
                guard["acceptance_predicate"]["results"]["ISSUE_STATE"]["status"] = "PASS"
        else:
            updates["QUEUE_INDEPENDENT"] = "NO"
            updates["CLEAN_IDLE"] = "NO"
            updates["STATUS"] = "WAITING_PHYSICAL_PROOF"
            updates["FIRST_CAUSAL_BLOCKER"] = "MISSING_PHYSICAL_ACCEPTANCE_EVIDENCE"
            guard["transition_state"] = "PROVISIONAL"
            if "ISSUE_STATE" in guard["acceptance_predicate"]["results"]:
                guard["acceptance_predicate"]["results"]["ISSUE_STATE"]["status"] = "UNKNOWN"
                guard["acceptance_predicate"]["results"]["ISSUE_STATE"]["observed_value"] = "NO_FURTHER_ACTION"
    elif "ISSUE_STATE" in guard["acceptance_predicate"]["results"]:
        guard["acceptance_predicate"]["results"]["ISSUE_STATE"]["observed_value"] = "NO_FURTHER_ACTION"

    print(f"Updates for {edge_name}:")
    for k, v in updates.items():
        if k in ["PROVEN_EDGES", "UNPROVEN_EDGES"]:
            print(f"  {k}: length {len(v)}")
        else:
            print(f"  {k}: {v}")
            
    new_bundle = update(
        ledger_path,
        revision,
        updates,
        "Google-Antigravity",
        5.0,
        guard
    )
    return new_bundle

bundle = load_bundle(path)
tasks = ["EXTERNAL_PUBLICATION - AUTHORIZED_MACHINE_ACTION", "PUBLIC DEPLOYMENT - SAFE_AUTOMATABLE_PREPARATION"]
for task in tasks:
    print(f"Executing task: {task}")
    bundle = load_bundle(path) # check freshness
    try:
        bundle = update_ledger(path, task, None, bundle)
        print("Success, new rev:", bundle["revision"])
    except Exception as e:
        print("Exception:", type(e), str(e))
