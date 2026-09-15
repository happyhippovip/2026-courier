import json
import time
from pathlib import Path

COURIER_DIR = Path("/Users/user/Downloads/2026-courier")

task_id = "CODEX_INTEGRATION_PROOF_1"
opp = {
    "opportunity_id": task_id,
    "source": "MAC_ANTIGRAVITY",
    "objective_id": "OBJ-CODEX-FOUNDATION",
    "project": "Courier",
    "description": "Echo test for Codex integration proof",
    "priority": 7,
    "expected_value": "Evidence-backed output",
    "evidence": {},
    "required_capabilities": [],
    "risk": "LOW",
    "estimated_cost": 0.0,
    "model_need": False,
    "external_action_units": 0,
    "project_id": "",
    "source_artifact": "",
    "source_hash": "",
    "evidence_type": "",
    "production_stage": "",
    "problem_or_goal": "",
    "expected_output": "",
    "risk_class": "LOW",
    "cost_class": "ZERO_COST_LOCAL",
    "dedupe_fingerprint": "codexhash1",
    "heavy_job": False,
    "status": "READY",
    "target_agent": "CODEX",
    "allowed_scope": ["./"],
    "allowed_actions": ["HEALTH_CHECK"],
    "created_at": "2026-09-14T19:58:15.443662+00:00",
    "updated_at": "2026-09-14T20:03:47.568271+00:00",
    "dedupe_hash": "codexhash1"
}

out = COURIER_DIR / "events" / "opportunity-queue" / f"{task_id}.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(opp, indent=2))
print(f"Added opportunity {task_id} to queue.")
