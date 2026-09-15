import sys
import time
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent / "scripts"))
from run_live_production_goal import update_completed_tasks, dispatch_recommendations, COURIER_DIR
from next_safe_work_router import NextSafeWorkRouter
from opportunity_queue import OpportunityQueue

update_completed_tasks()
router = NextSafeWorkRouter(repo_dir=COURIER_DIR)
res = router.evaluate_next_safe_work()
recs = res.get("recommendations", {})
queue = OpportunityQueue(repo_dir=COURIER_DIR)
goal = "Run Step 8"
dispatched = set()
active, block = dispatch_recommendations(recs, queue, goal, dispatched)
print(f"Active tasks dispatched: {active}")
