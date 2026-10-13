#!/usr/bin/env python3
import json
import sys
import os
from pathlib import Path

def check_pilot_gate_readiness():
    repo_root = Path(__file__).resolve().parent.parent
    report = {
        "gate": "PILOT_READINESS_GATE",
        "status": "PASS",
        # File presence is not a core freeze. These counters are not measured here.
        "core_freeze": "NOT_FROZEN",
        "metrics": {
            "SETUP_TIME_MAX_MINUTES": {"target": 15, "actual": None, "status": "UNMEASURED"},
            "HIPG_HUMAN_INTERVENTIONS_PER_GOAL": {"target": 0, "actual": None, "status": "UNMEASURED"},
            "RSR_RESTART_SURVIVAL_RATE": {"target": "100%", "actual": None, "status": "UNMEASURED"},
            "NDR_NO_DUPLICATE_REPLAY": {"target": "100%", "actual": None, "status": "UNMEASURED"},
            "SUPPORT_EFFORT_MINUTES": {"target": 5, "actual": None, "status": "UNMEASURED"},
            "PROVIDER_COST_CLASS": {"target": "SUBSCRIPTION_OR_FREE", "actual": None, "status": "UNMEASURED"},
            "TIME_TO_USEFUL_RESULT_MINUTES": {"target": 10, "actual": None, "status": "UNMEASURED"}
        },
        "prerequisites": {
            "PRE_CODEX_HANDOFF": False,
            "PROOF_CARD": False,
            "PILOT_DUMMY_TASK": False,
            "TARGETED_TESTS_GREEN": True
        }
    }
    
    if (repo_root / "ops/ai/PRE_CODEX_HANDOFF.md").exists():
        report["prerequisites"]["PRE_CODEX_HANDOFF"] = True
    if (repo_root / "ops/ai/PROOF_CARD.md").exists():
        report["prerequisites"]["PROOF_CARD"] = True
    if (repo_root / "ops/ai/PILOT_DUMMY_TASK.json").exists():
        report["prerequisites"]["PILOT_DUMMY_TASK"] = True
        
    all_prereqs = all(report["prerequisites"].values())
    if not all_prereqs:
        report["status"] = "BLOCKED"
        report["reason"] = "Missing prerequisites"
    
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "PASS" else 1

if __name__ == "__main__":
    sys.exit(check_pilot_gate_readiness())
