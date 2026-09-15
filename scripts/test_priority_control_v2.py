import sys, json, os, uuid, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.courier_safety_dispatcher import MissionQueue, write_json_atomic

def run_test():
    ws_dir = Path("/tmp/courier_test_priority2")
    import shutil
    if ws_dir.exists():
        shutil.rmtree(ws_dir)
        
    q = MissionQueue(ws_dir)

    def make_task(goal_desc, action, risk_class="SAFE"):
        return {
            "mission_id": str(uuid.uuid4()),
            "goal": goal_desc,
            "task": {"action": action},
            "risk_class": risk_class,
            "status": "PENDING"
        }
        
    t_waste = make_task("keep busy", "duplicate_waste")
    t_v2 = make_task("v2 invoice system", "post-v1 revenue")
    t_human = make_task("do something", "dangerous", "HUMAN_GATED")
    
    q.enqueue(t_waste)
    q.enqueue(t_v2)
    q.enqueue(t_human)
    
    os.environ["V1_CLOSED"] = "TRUE"
    
    claimed = []
    while True:
        m = q.claim_next("worker_1")
        if not m:
            break
        claimed.append(m)
        
    print(f"Claimed {len(claimed)} tasks.")
    for c in claimed:
        print(c["goal"], c["task"]["action"])

if __name__ == "__main__":
    run_test()
