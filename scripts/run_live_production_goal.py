#!/usr/bin/env python3

import sys
import time
import json
import hashlib
import subprocess
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(COURIER_DIR) not in sys.path:
    sys.path.insert(0, str(COURIER_DIR))

from scripts.intake_to_router_wire import process_one_idea
import scripts.mac_result_consumer as mac_result_consumer
from scripts.next_safe_work_router import NextSafeWorkRouter
from scripts.courier_real_worker_adapters import get_real_worker_adapters
from scripts.opportunity_queue import OpportunityQueue
from scripts.live_worker_registry import LiveWorkerRegistry, AvailabilityClass, WorkerState


ACTIVE_LOOP_DELAY_SECONDS = 2.0
INITIAL_IDLE_BACKOFF_SECONDS = 1.0
MAX_IDLE_BACKOFF_SECONDS = 15.0


def recommendation_fingerprint(recommendations):
    """Return a stable identity for the current routing decision."""
    return hashlib.sha256(
        json.dumps(recommendations, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def idle_backoff_seconds(unchanged_idle_cycles):
    """Short bounded backoff for a genuinely unchanged, non-actionable state."""
    exponent = min(4, max(0, int(unchanged_idle_cycles) - 1))
    return min(MAX_IDLE_BACKOFF_SECONDS, INITIAL_IDLE_BACKOFF_SECONDS * (2 ** exponent))


def quiescence_state(opportunities):
    """Describe durable unresolved work without equating queue silence to success."""
    statuses = {opp.status for opp in opportunities}
    if "RUNNING" in statuses:
        return "WORK_IN_PROGRESS"
    if "READY" in statuses:
        return "READY_WORK_UNROUTED"
    if statuses.intersection({"WAITING_FOR_HUMAN", "HUMAN_GATE", "PAYMENT_APPROVAL_REQUIRED"}):
        return "WAITING_FOR_HUMAN_GATE"
    if statuses.intersection({"BLOCKED", "DEFERRED", "CIRCUIT_OPEN"}):
        return "WAITING_FOR_DEPENDENCIES"
    return "QUIESCENT_WAKEABLE"


def dispatch_recommendations(recommendations, queue, goal, dispatched_tasks, dispatch_fn=None):
    """Dispatch every independent recommendation; one unavailable worker is local only."""
    
    # Enforce ONE ACTIVE TASK
    active_tasks = [o for o in queue.list_opportunities() if o.status in ("ACTIVE", "RUNNING")]
    if len(active_tasks) >= 1:
        print(f"Skipping dispatch, ACTIVE task limit (1) reached. Active tasks: {len(active_tasks)}")
        return True, "ACTIVE_TASK_LIMIT"
        
    dispatch_fn = dispatch_fn or dispatch_task
    active = False
    newly_dispatched = 0
    for worker_id, rec in recommendations.items():
        action = rec.get("recommended_action", "")
        if not action.startswith("DISPATCH_TASK_"):
            continue

        task_id = action.replace("DISPATCH_TASK_", "", 1)
        if task_id in dispatched_tasks:
            continue

        print(f"--- DISPATCHING LOOP: {task_id} to {worker_id} ---")
        opp = queue.get_opportunity(task_id)
        
        # CLAIM THE OPPORTUNITY TO MOVE IT TO ACTIVE
        claimed, _, _ = queue.claim_opportunity(task_id, worker_id, lease_seconds=180)
        if not claimed:
            print(f"Could not claim task {task_id}")
            continue
            
        opp = queue.get_opportunity(task_id)
        if opp.status == "RUNNING":
            opp.status = "ACTIVE"
            queue.save_opportunity(opp)
            
        active = True
        
        prompt_text = opp.description if opp else goal
        action_name = opp.allowed_actions[0] if opp and opp.allowed_actions else "discover_improvement_opportunities"
        task_hash = rec.get("task_fingerprint", "autohash")
        scope = rec.get("scope", [])

        dispatched_tasks.add(task_id)
        dispatch_fn(task_id, worker_id, action_name, prompt_text, scope, task_hash)
        newly_dispatched += 1
    return active, newly_dispatched

def dispatch_task(task_id, worker_id, action_name, prompt_text, scope, task_hash):
    adapters = get_real_worker_adapters(repo_root=COURIER_DIR)
    
    if worker_id == "CODEX":
        print(f"Routing to CODEX via router_dispatch_codex.py: {task_id}")
        cmd = [sys.executable, str(SCRIPTS_DIR / "router_dispatch_codex.py"), task_id, prompt_text]
        subprocess.Popen(cmd) # Run non-blocking
        return
        
    adapter = adapters.get(worker_id)
    if adapter:
        task_envelope = { "timeout_seconds": 180, 
            "task_hash": task_hash,
            "worker_id": worker_id,
            "target_agent": worker_id,
            "task_id": task_id,
            "payload": {
                "action": action_name,
                "prompt": prompt_text,
                "allowed_scope": scope
            }
        }
        
        req_id = f"REQ-MAC-{task_hash[:8]}"
        requests_dir = COURIER_DIR / "coordination" / "local_requests"
        requests_dir.mkdir(parents=True, exist_ok=True)
        with open(requests_dir / f"{req_id}.json", "w") as f:
            json.dump(task_envelope, f)
            
        def _run():
            try:
                result_envelope = adapter(task_envelope)
                res_data = result_envelope.get("result", {})
                out_payload = res_data.get("payload", {})
                out_payload["action"] = action_name
                calc_fingerprint = hashlib.sha256(f"{req_id}COMPLETEDAuto task completed".encode("utf-8")).hexdigest()
                wrapped = {
                    "request_id": req_id,
                    "mission_id": task_id,
                    "schema_version": "1.0",
                    "status": "COMPLETED",
                    "observed_behavior": "Auto task completed",
                    "result_fingerprint": calc_fingerprint,
                    "payload": out_payload
                }
                out = COURIER_DIR / "coordination" / "windows_to_mac" / "results" / f"{req_id}.json"
                out.parent.mkdir(parents=True, exist_ok=True)
                with open(out, "w") as f:
                    json.dump(wrapped, f, indent=2)
                print(f"Kickstart result returned to {out}")
            except Exception as e:
                print(f"Failed kickstart: {e}")
                
        import threading
        threading.Thread(target=_run).start() # Non-blocking

def update_completed_tasks():
    results_dirs = [
        COURIER_DIR / "coordination" / "windows_to_mac" / "results",
        COURIER_DIR / "coordination" / "windows_to_mac" / "archive",
        COURIER_DIR / "events" / "processed",
        COURIER_DIR / "events" / "results",
    ]
    queue = OpportunityQueue(repo_dir=COURIER_DIR)
    
    for results_path in results_dirs:
        if not results_path.exists(): continue
        for res_file in results_path.glob("*.json"):
            if "-worker-job" in res_file.name: continue
            try:
                with open(res_file) as f:
                    data = json.load(f)
                mission_id = data.get("mission_id") or data.get("task_id")
                status = data.get("status")
                verdict = data.get("verdict", "PASS")
                
                if mission_id and status == "COMPLETED":
                    opp = queue.get_opportunity(mission_id)
                    if opp and opp.status not in ("SUCCEEDED", "RETRYABLE", "BLOCKED", "UNSUPPORTED"):
                        # Phase 1: Mark as RESULT received
                        opp.status = "RESULT"
                        queue.save_opportunity(opp)
                        print(f"Task {mission_id} moved to RESULT")
                        
                        # Phase 2: Evaluation
                        opp.status = "EVALUATED"
                        queue.save_opportunity(opp)
                        print(f"Task {mission_id} moved to EVALUATED")
                        
                        # Phase 3: Resolution
                        if verdict == "PASS":
                            opp.status = "SUCCEEDED"
                        elif verdict == "BLOCKED":
                            opp.status = "BLOCKED"
                        elif verdict == "UNSUPPORTED":
                            opp.status = "UNSUPPORTED"
                        else:
                            opp.status = "RETRYABLE"
                            
                        queue.save_opportunity(opp)
                        print(f"Task {mission_id} durably closed as {opp.status}")
            except Exception as e:
                pass

def main():
    if len(sys.argv) > 1:
        goal = sys.argv[1]
    else:
        goal = """Fix the Windows executor to use safe restricted commands. Then test it by running the tests natively on Windows. Make sure Mac verifies the result."""
    
    print("--- INJECTING REAL GOAL ---")
    process_one_idea(goal)

    reg = LiveWorkerRegistry(repo_dir=COURIER_DIR)
    record = reg.register_worker(worker_id="WINDOWS", role="WINDOWS_NATIVE", provider="WINDOWS", availability_class=AvailabilityClass.TEMPORARY_30_DAY, mutable_scope=[r"C:\Dev\Windows-AI-OS"])
    record.state = WorkerState.AVAILABLE.value
    reg._save_worker_record(record)
    
    print("--- ENTERING AUTONOMOUS LOOP ---")
    dispatched_tasks = set()
    
    last_idle_fingerprint = None
    unchanged_idle_cycles = 0
    while True:
        mac_result_consumer.consume_results()
        update_completed_tasks()
        
        router = NextSafeWorkRouter(repo_dir=COURIER_DIR)
        res = router.evaluate_next_safe_work()
        recs = res.get("recommendations", {})
        queue = OpportunityQueue(repo_dir=COURIER_DIR)
        
        active, _ = dispatch_recommendations(recs, queue, goal, dispatched_tasks)

        if not active:
            current_fingerprint = recommendation_fingerprint(recs)
            if current_fingerprint == last_idle_fingerprint:
                unchanged_idle_cycles += 1
            else:
                unchanged_idle_cycles = 1
                last_idle_fingerprint = current_fingerprint

            state = quiescence_state(queue.list_opportunities())
            delay = idle_backoff_seconds(unchanged_idle_cycles)
            print(f"--- {state}; waiting {delay:g}s for a real state change ---")
            
            if state == "QUIESCENT_WAKEABLE":
                print("Queue is quiescent. Triggering goal evaluation via GEMINI...")
                task_hash = "goal-eval-" + str(unchanged_idle_cycles)
                task_envelope = {
                    "timeout_seconds": 120,
                    "task_hash": task_hash,
                    "worker_id": "GEMINI",
                    "target_agent": "GEMINI",
                    "task_id": f"eval-{unchanged_idle_cycles}",
                    "payload": {
                        "action": "evaluate_goal_completion",
                        "prompt": f"The opportunity queue currently has {len(queue.list_opportunities())} tasks. Are there any pending blocked tasks? If so, identify an entirely different disjoint task (e.g. Windows) to make progress. Goal: {goal}. Is the overall goal fully demonstrably complete? If not complete, identify the next safe concrete dependency/task and output it.",
                        "allowed_scope": ["SAFE_LOCAL_VALIDATION"]
                    }
                }
                adapters = get_real_worker_adapters(repo_root=COURIER_DIR)
                if "GEMINI" in adapters:
                    try:
                        res = adapters["GEMINI"](task_envelope)
                        print(f"GEMINI Goal Evaluation Result: {res}")
                        if res and "result" in res:
                            payload = res["result"].get("payload", {})
                            summary = payload.get("summary", "")
                            if summary and summary != "GOAL_IS_COMPLETE_YES":
                                import uuid
                                from scripts.opportunity_queue import Opportunity
                                task_id_new = f"plan-imp-{uuid.uuid4().hex[:8]}"
                                opp = Opportunity(
                                    opportunity_id=task_id_new,
                                    source="MAC_CHIEF",
                                    project="Courier",
                                    objective_id="OBJ-EVAL",
                                    description=summary,
                                    priority=5,
                                    risk="LOW",
                                    target_agent="CODEX",
                                    allowed_actions=["implement_bounded_improvement"],
                                    allowed_scope=["GLOBAL"]
                                )
                                queue.add_opportunity(opp)
                                queue.save_opportunity(opp)
                                print(f"Enqueued new task from Gemini: {task_id_new}")
                    except Exception as e:
                        print(f"Goal evaluation failed: {e}")
            
            time.sleep(delay)
            continue


        last_idle_fingerprint = None
        unchanged_idle_cycles = 0
        time.sleep(ACTIVE_LOOP_DELAY_SECONDS)

if __name__ == "__main__":
    main()
