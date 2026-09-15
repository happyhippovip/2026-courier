import os
import sys
from pathlib import Path
from shutil import rmtree
import json

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.courier_safety_dispatcher import CourierSafetyDispatcher, TaskEnvelope, LocalWorkerAdapterBoundary

def dummy_consumer(task_payload):
    pass

def run_test():
    ws_dir = Path(".").resolve()
    boundary = LocalWorkerAdapterBoundary(workspace_dir=ws_dir)
    boundary.register_consumer("GEMINI", dummy_consumer)
    class MyDispatcher(CourierSafetyDispatcher):
        def verify_result(self, worker_id, task_hash, verification_status, result_data=None):
            print("VERIFY CALLED FOR", task_hash)
            state = self._inflight.get(task_hash)
            print("STATE MATCHES:", result_data == state["result"])
            task = state.get("task", {})
            mission_id = state.get("mission_id", "unknown")
            can = self.canonical_validate_result(mission_id, task, result_data, state.get("route"))
            print("CANONICAL:", can)
            prestate = state.get("prestate")
            if state.get("requires_write"):
                if not prestate or "exists" not in prestate:
                    print("NO PRESTATE", prestate)
                else:
                    print("PRESTATE OK")
            
            from scripts.courier_safety_dispatcher import canonical_hash
            criteria = task.get("acceptance_criteria", {})
            fpath = self.workspace_dir / criteria["file_exists"]
            print("FPATH EXISTS:", fpath.exists())
            post_content = fpath.read_text(encoding="utf-8").strip() if fpath.exists() else None
            computed_hash = canonical_hash({"path": str(fpath), "content": post_content})
            print("MY ENVELOPE FINGERPRINT:", result_data.get("result_fingerprint"))
            print("COMPUTED FINGERPRINT:", computed_hash)
            print("PAYLOAD FINGERPRINT:", result_data.get("payload", {}).get("result_fingerprint"))
            
            print("LAST RESULT STATUS BEFORE SUPER:", self.last_result_status)
            res = super().verify_result(worker_id, task_hash, verification_status, result_data)
            print("LAST RESULT STATUS AFTER SUPER:", self.last_result_status)
            print("RESULT:", res)
            return res

    dispatcher = MyDispatcher(workspace_dir=ws_dir, adapter_boundary=boundary)

    # 1. Clean up
    if (ws_dir / "events" / "task-envelopes").exists():
        rmtree(ws_dir / "events" / "task-envelopes")
    if (ws_dir / "events" / "mission-queue").exists():
        rmtree(ws_dir / "events" / "mission-queue")
    os.makedirs(ws_dir / "events" / "mission-queue", exist_ok=True)
    os.makedirs(ws_dir / "events" / "task-envelopes", exist_ok=True)
    (ws_dir / "events" / "mission-queue" / "queue.json").write_text('{"schema_version": "1.0", "missions": []}')
    
    from scripts.courier_safety_dispatcher import canonical_task_hash, canonical_hash
    
    q = dispatcher.mission_queue
    
    task1 = {"action": "implement_bounded_improvement", "preferred_agent": "GEMINI", "nonce": "1"}
    m1 = q.enqueue({"task": task1, "goal_id": "g1"})
    q.transition(m1["mission_id"], "CLAIMED", claimed_by="dead_worker_1")
    q.transition(m1["mission_id"], "RUNNING", claimed_by="dead_worker_1")
    
    task2 = {"action": "implement_bounded_improvement", "preferred_agent": "GEMINI", "nonce": "2", "acceptance_criteria": {"file_exists": "genuine_effect.txt", "content_matches": "genuine_content"}}
    m2 = q.enqueue({"task": task2, "goal_id": "g1", "requires_write": True})
    (ws_dir / "events" / "task-envelopes" / f"prestate_{m2['task_hash']}.json").write_text('{"exists": false}')
    q.transition(m2["mission_id"], "CLAIMED", claimed_by="dead_worker_2")
    q.transition(m2["mission_id"], "RUNNING", claimed_by="dead_worker_2")
    
    task3 = {"action": "implement_bounded_improvement", "preferred_agent": "GEMINI", "nonce": "3"}
    m3 = q.enqueue({"task": task3, "goal_id": "g1"})
    q.transition(m3["mission_id"], "CLAIMED", claimed_by="dead_worker_3")
    q.transition(m3["mission_id"], "RUNNING", claimed_by="dead_worker_3")
    
    # write confirmed effect
    (ws_dir / "genuine_effect.txt").write_text("genuine_content")
    payload2 = {"status": "COMPLETED", "result_fingerprint": canonical_hash({"path": str(ws_dir / "genuine_effect.txt"), "content": "genuine_content"})}
    res2 = {"payload": payload2, "status": "COMPLETED", "mission_id": m2["mission_id"], "task_hash": m2["task_hash"], "result_fingerprint": payload2["result_fingerprint"], "target_agent": "GEMINI"} # added fields so canonical_validate_result passes
    (ws_dir / "events" / "task-envelopes" / f"result__{m2['task_hash']}.json").write_text(json.dumps(res2))

    # write ambiguous effect
    res3 = {"payload": {"status": "UNKNOWN"}, "status": "UNKNOWN"}
    (ws_dir / "events" / "task-envelopes" / f"result__{m3['task_hash']}.json").write_text(json.dumps(res3))

    # RUN RECOVERY
    print("Running reconcile_orphans...")
    try:
        dispatcher.reconcile_orphans()
    except Exception as e:
        print("EXC", e)

    docs = q.read_all()
    d1 = next(d for d in docs if d["mission_id"] == m1["mission_id"])
    d2 = next(d for d in docs if d["mission_id"] == m2["mission_id"])
    d3 = next(d for d in docs if d["mission_id"] == m3["mission_id"])

    print("M1 (No effect):", d1["status"])
    print("M2 (Confirmed):", d2["status"])
    print("M3 (Ambiguous):", d3["status"])

if __name__ == "__main__":
    run_test()
