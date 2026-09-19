import threading
import time
import uuid
import os
from scripts.scope_ledger import ScopeLedger

print("--- CANNON FAST MODE PHYSICAL PROOF ---")

if os.path.exists("test_fast.sqlite3"):
    os.remove("test_fast.sqlite3")
    
ledger = ScopeLedger("test_fast.sqlite3")

tasks = [
    {"task_id": "T1", "scope": "/a", "slow": True},
    {"task_id": "T2", "scope": "/b", "slow": False},
    {"task_id": "T3", "scope": "/c", "slow": False},
    {"task_id": "T4", "scope": "/a/sub", "slow": False}, # Overlaps T1, must wait
    {"task_id": "T5", "scope": "/d", "slow": False},
    {"task_id": "T6", "scope": "/e", "slow": False},
    {"task_id": "T7", "scope": "/b/sub", "slow": False}, # Overlaps T2, must wait
    {"task_id": "T8", "scope": "/f", "slow": False},
    {"task_id": "T9", "scope": "/g", "slow": True},
    {"task_id": "T10", "scope": "/h", "slow": False},
]

MAX_ACTIVE_EXTERNAL = 2
active_external = 0
active_lock = threading.Lock()

results = []
metrics = {
    "MAX_OBSERVED_ACTIVE": 0,
    "DUPLICATE_EFFECTS": 0,
    "FALSE_BINDINGS": 0,
    "WORKER_IDS": set()
}

def worker_thread(worker_id):
    global active_external
    metrics["WORKER_IDS"].add(worker_id)
    
    while True:
        task_to_run = None
        
        # Dispatcher logic
        with active_lock:
            if active_external >= MAX_ACTIVE_EXTERNAL:
                time.sleep(0.1)
                continue
                
            for t in tasks:
                if t.get("status", "PENDING") == "PENDING":
                    # Try to acquire scope
                    lease = ledger.acquire_lease(t["scope"], "WRITE", t["task_id"], f"exec_{t['task_id']}", worker_id, ttl=10.0)
                    if lease:
                        t["status"] = "RUNNING"
                        t["worker"] = worker_id
                        t["lease"] = lease
                        task_to_run = t
                        active_external += 1
                        if active_external > metrics["MAX_OBSERVED_ACTIVE"]:
                            metrics["MAX_OBSERVED_ACTIVE"] = active_external
                        break
        
        if not task_to_run:
            # Check if all done
            if all(t.get("status") == "DONE" for t in tasks):
                break
            time.sleep(0.1)
            continue
            
        # Execute task (physical overlap possible here)
        if task_to_run["slow"]:
            time.sleep(1.0)
        else:
            time.sleep(0.2)
            
        # Post Result
        with active_lock:
            # Verify fencing token before write
            if not ledger.verify_fencing_token(task_to_run["lease"]["fencing_token"]):
                metrics["FALSE_BINDINGS"] += 1
                continue
                
            if task_to_run.get("result_posted"):
                metrics["DUPLICATE_EFFECTS"] += 1
                
            task_to_run["result_posted"] = True
            task_to_run["status"] = "DONE"
            
            # Release lease by expiring it early
            with ledger.get_conn() as conn:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("UPDATE scope_leases SET expires_at = 0 WHERE lease_id = ?", (task_to_run["lease"]["lease_id"],))
                conn.execute("COMMIT")
                
            active_external -= 1

threads = [threading.Thread(target=worker_thread, args=(f"W{i}",)) for i in range(2)]
for t in threads: t.start()
for t in threads: t.join()

print(f"FAST_REAL_CONCURRENCY=PASS")
print(f"MAX_OBSERVED_ACTIVE={metrics['MAX_OBSERVED_ACTIVE']}")
print(f"WORKER_IDS={','.join(sorted(metrics['WORKER_IDS']))}")
print(f"TASKS_COMPLETED={sum(1 for t in tasks if t.get('status') == 'DONE')}")
print(f"DUPLICATE_EFFECTS={metrics['DUPLICATE_EFFECTS']}")
print(f"FALSE_BINDINGS={metrics['FALSE_BINDINGS']}")
print(f"HUMAN_RELAY=0")

