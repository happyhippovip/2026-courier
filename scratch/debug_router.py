import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "scripts"))
from opportunity_queue import OpportunityQueue, Opportunity
from next_safe_work_router import NextSafeWorkRouter
import json

queue = OpportunityQueue(repo_dir=Path(__file__).resolve().parent.parent)
tasks = queue.list_opportunities()
for o in tasks:
    if o.opportunity_id == "task-a-proof":
        print(f"Task found! target_agent={o.target_agent}, status={o.status}")
