import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "scripts"))
from opportunity_queue import OpportunityQueue, Opportunity

queue = OpportunityQueue(repo_dir=Path(__file__).resolve().parent.parent)

opp = Opportunity(
    opportunity_id="task-a-real-proof",
    source="MAC_CHIEF",
    project="Courier",
    objective_id="OBJ-CHAIN",
    description="Initial task A for integration proof (real)",
    priority=10,
    target_agent="WINDOWS",
    allowed_actions=["WRITE_PROOF"],
    allowed_scope=["C:\\Dev\\Windows-AI-OS"]
)
opp.status = "READY"
queue.add_opportunity(opp)
queue.save_opportunity(opp)
print("Created task-a-real-proof in queue")
