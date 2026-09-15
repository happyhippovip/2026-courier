import sys
from pathlib import Path
import hashlib

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(COURIER_DIR) not in sys.path:
    sys.path.insert(0, str(COURIER_DIR))

from scripts.opportunity_queue import Opportunity, OpportunityQueue

queue = OpportunityQueue(repo_dir=COURIER_DIR)
task_id = "MAC_WINDOWS_INTEGRATION_PROOF_2"
desc = "Windows integration test task"
dedupe_hash = hashlib.sha256(f"{task_id}:{desc}".encode()).hexdigest()[:16]

opp = Opportunity(
    opportunity_id=task_id,
    source="MAC_ANTIGRAVITY",
    description=desc,
    objective_id="OBJ-WINDOWS-AI-OS-FOUNDATION",
    project="Windows-AI-OS",
    priority=7,
    risk="LOW",
    estimated_cost=0.0,
    heavy_job=False,
    status="READY",
    target_agent="WINDOWS",
    allowed_scope=[r"C:\Dev\Windows-AI-OS"],
    dedupe_hash=dedupe_hash,
    allowed_actions=["HEALTH_CHECK"]
)

queue.add_opportunity(opp)
print(f"Added opportunity {task_id} to queue.")
