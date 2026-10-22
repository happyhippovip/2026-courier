#!/usr/bin/env python3
import json
import sys
from pathlib import Path


# Declared targets only. Actuals stay empty until a run measures them.
_METRIC_TARGETS = {
    "SETUP_TIME_MAX_MINUTES": 15,
    "HIPG_HUMAN_INTERVENTIONS_PER_GOAL": 0,
    "RSR_RESTART_SURVIVAL_RATE": "100%",
    "NDR_NO_DUPLICATE_REPLAY": "100%",
    "SUPPORT_EFFORT_MINUTES": 5,
    "PROVIDER_COST_CLASS": "SUBSCRIPTION_OR_FREE",
    "TIME_TO_USEFUL_RESULT_MINUTES": 10,
}


def _unmeasured_metrics() -> dict:
    return {
        name: {
            "target": target,
            "actual": None,
            "status": "NOT_MEASURED",
            "measured": False,
        }
        for name, target in _METRIC_TARGETS.items()
    }


def check_pilot_gate_readiness():
    repo_root = Path(__file__).resolve().parent.parent
    file_flags = {
        "PRE_CODEX_HANDOFF": (repo_root / "ops/ai/PRE_CODEX_HANDOFF.md").exists(),
        "PROOF_CARD": (repo_root / "ops/ai/PROOF_CARD.md").exists(),
        "PILOT_DUMMY_TASK": (repo_root / "ops/ai/PILOT_DUMMY_TASK.json").exists(),
    }
    report = {
        "gate": "PILOT_READINESS_GATE",
        "status": "NOT_MEASURED",
        "metrics": _unmeasured_metrics(),
        "prerequisites": {
            **file_flags,
            # File presence is not a test run.
            "TARGETED_TESTS_GREEN": False,
        },
    }

    if not all(file_flags.values()):
        report["status"] = "BLOCKED"
        report["reason"] = "Missing prerequisites"
    else:
        report["status"] = "NOT_MEASURED"
        report["reason"] = "Prerequisite files exist. Readiness metrics were not measured."

    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(check_pilot_gate_readiness())
