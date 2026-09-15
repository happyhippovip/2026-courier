import json
import time
from pathlib import Path

opp = {
  "opportunity_id": f"TASK_FOUNDATION_{int(time.time())}",
  "source": "MAC_CHIEF",
  "objective_id": "OBJ-COMPOUND-INTELLIGENCE",
  "project": "COURIER",
  "description": "Create a python script `analytics_agent_performance.py` in the root that parses the events in `events/worker-events` to identify which workers have the highest failure rates.",
  "priority": 10,
  "expected_value": "New capability for continuous agent improvement",
  "evidence": {},
  "required_capabilities": [
    "MAC_LOCAL"
  ],
  "risk": "SAFE",
  "heavy_job": False,
  "status": "READY",
  "target_agent": "CODEX",
  "allowed_scope": [
    "GLOBAL"
  ],
  "allowed_actions": [
    "WRITE"
  ]
}

p = Path(f"events/opportunity-queue/{opp['opportunity_id']}.json")
p.write_text(json.dumps(opp, indent=2))
print(opp['opportunity_id'])
