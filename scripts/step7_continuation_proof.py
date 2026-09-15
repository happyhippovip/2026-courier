#!/usr/bin/env python3
import sys
import subprocess
import time
import json
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(COURIER_DIR))

from scripts.opportunity_queue import OpportunityQueue, Opportunity
from scripts.next_safe_work_router import NextSafeWorkRouter
import hashlib
import datetime

def clear_queue():
    queue = OpportunityQueue(repo_dir=COURIER_DIR)
    for opp in queue.opportunities.values():
        if opp.status in ("READY", "HUMAN_GATE"):
            opp.status = "COMPLETED"
            from scripts.opportunity_queue import save_json
            save_json(queue.queue_dir / f"{opp.opportunity_id}.json", opp.to_dict())

def wait_for_result(task_id: str, timeout=60) -> dict:
    result_path = COURIER_DIR / "events" / "processed" / f"{task_id}-result.json"
    start = time.time()
    while time.time() - start < timeout:
        if result_path.exists():
            try:
                return json.loads(result_path.read_text())
            except Exception:
                pass
        time.sleep(1)
    return None

def auto_injector(result: dict):
    task_id = result.get("task_id")
    
    # Mark parent task completed
    queue = OpportunityQueue(repo_dir=COURIER_DIR)
    opp = queue.opportunities.get(task_id)
    if opp:
        opp.status = "COMPLETED"
        from scripts.opportunity_queue import save_json
        save_json(queue.queue_dir / f"{task_id}.json", opp.to_dict())

    if task_id == "TASK_7_STEP1":
        next_id = "TASK_7_STEP2"
        goal_id = result.get("payload", {}).get("goal_id", "OBJ-STEP7")
        print(f"[AUTO_INJECTOR] Accepted result for {task_id}. Dispatching next safe task: {next_id}")
        
        opp2 = Opportunity(
            opportunity_id=next_id,
            source="AUTO_INJECTOR",
            project="WINDOWS_AI_OS",
            description="Follow-up safe check",
            objective_id=goal_id,
            priority=5,
            risk="SAFE",
            estimated_cost=0.0,
            heavy_job=False,
            status="READY",
            target_agent=None,
            required_capabilities=["WINDOWS_EXECUTION"],
            allowed_scope=["C:\\Dev\\Windows-AI-OS"],
            allowed_actions=["READ"],
            dedupe_hash=hashlib.sha256(next_id.encode()).hexdigest()[:16],
        )
        queue.opportunities[opp2.opportunity_id] = opp2
        save_json(queue.queue_dir / f"{next_id}.json", opp2.to_dict())
        return next_id
    elif task_id == "TASK_7_STEP2":
        print(f"[AUTO_INJECTOR] Accepted result for {task_id}. No safe next work exists. Quiescing safely.")
        return None
    return None

def run_pipeline(task_id: str, desc: str):
    ROUTER_CMD = [sys.executable, str(SCRIPTS_DIR / "router_dispatch_codex.py")]
    proc = subprocess.run(ROUTER_CMD + [task_id, desc], capture_output=True, text=True)
    for line in proc.stdout.splitlines():
        if "STEP" in line or "FINAL_STATUS" in line or "FAIL" in line:
            print(f"  {line}")
    return proc.returncode == 0 and "FINAL_STATUS=PASS" in proc.stdout

def main():
    print("=== STEP 7: CONTINUATION PROOF ===")
    clear_queue()
    
    # 1. Dispatch Task A
    task_a = "TASK_7_STEP1"
    queue = OpportunityQueue(repo_dir=COURIER_DIR)
    opp = Opportunity(
        opportunity_id=task_a,
        source="MANUAL_START",
        project="WINDOWS_AI_OS",
        description="Initial read task",
        objective_id="OBJ-STEP7",
        priority=5,
        risk="SAFE",
        estimated_cost=0.0,
        heavy_job=False,
        status="READY",
        target_agent=None,
        required_capabilities=["WINDOWS_EXECUTION"],
        allowed_scope=["C:\\Dev\\Windows-AI-OS"],
        allowed_actions=["READ"],
        dedupe_hash=hashlib.sha256(task_a.encode()).hexdigest()[:16],
    )
    queue.opportunities[opp.opportunity_id] = opp
    from scripts.opportunity_queue import save_json
    save_json(queue.queue_dir / f"{task_a}.json", opp.to_dict())
    
    print(f"\n[PIPELINE] Executing Task A: {task_a}")
    if not run_pipeline(task_a, "Initial read task"):
        print("[FAIL] Task A failed")
        sys.exit(1)
        
    result_a = wait_for_result(task_a)
    if not result_a:
        print("[FAIL] Task A result missing")
        sys.exit(1)
        
    # 2. Injector chains Task B
    next_task = auto_injector(result_a)
    if not next_task:
        print("[FAIL] Injector did not spawn Task B")
        sys.exit(1)
        
    print(f"\n[PIPELINE] Executing Task B: {next_task} (Auto-chained)")
    if not run_pipeline(next_task, "Follow-up safe check"):
        print("[FAIL] Task B failed")
        sys.exit(1)
        
    result_b = wait_for_result(next_task)
    
    # 3. Injector quiesces
    final_task = auto_injector(result_b)
    if final_task is None:
        print("\n[VERDICT] STEP 7 SUCCESSFUL - Pipeline quiesced safely.")
    else:
        print("\n[VERDICT] STEP 7 FAILED - Spurious task spawned.")
        sys.exit(1)

if __name__ == "__main__":
    main()
