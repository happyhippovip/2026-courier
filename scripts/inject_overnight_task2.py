import json
from pathlib import Path

COURIER_DIR = Path("/Users/user/Downloads/2026-courier")

task_id = "WINDOWS_OVERNIGHT_TEST_2"
opp = {
    "opportunity_id": task_id,
    "source": "MAC_ANTIGRAVITY",
    "objective_id": "OBJ-OVERNIGHT",
    "project": "Courier",
    "description": "C:\\Dev\\Windows-AI-OS\\scripts\\Test-WindowsAIHost.ps1",
    "priority": 7,
    "expected_value": "Evidence-backed output",
    "status": "READY",
    "target_agent": "WINDOWS",
    "allowed_scope": ["C:\\Dev\\Windows-AI-OS"],
    "allowed_actions": ["RUN_POWERSHELL"],
    "created_at": "2026-09-14T20:20:00.000000+00:00",
    "updated_at": "2026-09-14T20:20:00.000000+00:00",
    "dedupe_hash": "overnighthash2"
}

out = COURIER_DIR / "events" / "opportunity-queue" / f"{task_id}.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(opp, indent=2))
print(f"Added opportunity {task_id} to queue.")
