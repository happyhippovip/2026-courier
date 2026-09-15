import sys
from pathlib import Path
import json

sys.path.append(str(Path(__file__).resolve().parent.parent / "scripts"))
from opportunity_queue import OpportunityQueue

queue = OpportunityQueue(repo_dir=Path(__file__).resolve().parent.parent)
opp = queue.get_opportunity("plan-imp-ea791415")
if opp:
    opp.status = "COMPLETED"
    queue.save_opportunity(opp)
    print("Marked plan-imp-ea791415 as COMPLETED")
