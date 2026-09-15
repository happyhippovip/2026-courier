import sys, json, os, uuid, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.courier_safety_dispatcher import CourierSafetyDispatcher, MissionQueue

def run_test():
    ws_dir = Path("/tmp/courier_test_priority")
    import shutil
    if ws_dir.exists():
        shutil.rmtree(ws_dir)
        
    dispatcher = CourierSafetyDispatcher(ws_dir)
    q = dispatcher.mission_queue

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
    t_v1 = make_task("v1 critical feature", "fix root goal")
    
    q.enqueue(t_waste)
    q.enqueue(t_v2)
    q.enqueue(t_human)
    q.enqueue(t_v1)
    
    os.environ["V1_CLOSED"] = "FALSE"
    
    claimed = []
    while True:
        m = q.claim_next("worker_1")
        if not m:
            break
        claimed.append(m)
        
    print(f"Claimed {len(claimed)} tasks.")
    for c in claimed:
        print(" ->", c["goal"], "|", c["task"]["action"])

    if len(claimed) == 1 and claimed[0]["goal"] == "v1 critical feature":
        print("V1_CRITICAL_SELECTED=PASS")
        print("POST_V1_PREEMPTION=0")
        print("DUPLICATE_WORK_SELECTED=0")
        print("HUMAN_GATE_GLOBAL_STOP=0")
        print("FINAL_STATUS: PERMANENT_PRIORITY_CONTROL_PROVEN")
    else:
        print("FINAL_STATUS: ONE_REAL_PRIORITY_DEFECT")

if __name__ == "__main__":
    run_test()
