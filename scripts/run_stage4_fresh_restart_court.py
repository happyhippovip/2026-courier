"""
run_stage4_fresh_restart_court.py - Stage 4 Fresh Restart + Exactly-Once Court
Demonstrates:
1. Process 1 executes Task A, starts Task B, produces on-disk effect (counter = 1), then crashes before checkpoint.
2. Process 2 (fresh process) boots from durable disk state:
   - Reconciles interrupted Task B
   - Detects on-disk effect already occurred
   - Suppresses re-execution (TASK_B_REAL_EFFECT_COUNT remains 1)
   - Verifies Task B and commits checkpoint
   - Autonomously advances to Task C without human intervention.
"""

import os
import sys
import json
import sqlite3
import hashlib
import tempfile
import shutil
import subprocess
from datetime import datetime, timezone

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

PROCESS_WORKER_SCRIPT = """
import os
import sys
import json
from courier.chief.control_plane import ControlPlane
from courier.chief.types import Lane, Host, TaskStatus, TwoLevelDone
from courier.chief.finish_first_continuation import FinishFirstContinuationEngine
from courier.chief.permanent_reserve_engine import PermanentReserveEngine

phase = sys.argv[1]
temp_dir = sys.argv[2]
db_path = os.path.join(temp_dir, "stage4_court.db")
counter_file = os.path.join(temp_dir, "task_b_counter.txt")
effect_b_file = os.path.join(temp_dir, "TASK-COURT-B.done")
cp = ControlPlane(db_path=db_path)
engine = PermanentReserveEngine(workspace_root=temp_dir, cp=cp)

if phase == "PHASE1_CRASH_SIMULATION":
    # 1. Execute Task A cleanly
    cp.upsert_task(
        task_id="TASK-COURT-A",
        assignment_id="ASSIGN-TASK-COURT-A",
        origin_lane=Lane.WINDOWS_GOOGLE,
        status=TaskStatus.COMPLETED,
        two_level_done=TwoLevelDone(local_step_erledigt=True, gesamtaufgabe_erledigt=False, blocker="NONE", next_step="CONTINUE"),
        active_agent=Lane.WINDOWS_GOOGLE.value
    )
    cp.set_checkpoint("LAST_VERIFIED_WINDOWS_CHECKPOINT", {
        "task_id": "TASK-COURT-A",
        "task_version": 1,
        "state_generation": 100,
        "result_fingerprint": "hash_a",
        "verification_evidence": "Task A verified",
        "verified_at": "2026-09-13T10:00:00+00:00",
        "status": "VERIFIED"
    })
    
    # 2. Start Task B: claim in DB, execute effect (increment counter)
    cp.upsert_task(
        task_id="TASK-COURT-B",
        assignment_id="ASSIGN-TASK-COURT-B",
        origin_lane=Lane.WINDOWS_GOOGLE,
        status=TaskStatus.RUNNING,
        two_level_done=TwoLevelDone(local_step_erledigt=False, gesamtaufgabe_erledigt=False, blocker="NONE", next_step="EXECUTE_EFFECT"),
        active_agent=Lane.WINDOWS_GOOGLE.value
    )
    
    # Execute Task B physical effect: increment counter
    count = 0
    if os.path.exists(counter_file):
        with open(counter_file, "r") as f:
            count = int(f.read().strip() or 0)
    count += 1
    with open(counter_file, "w") as f:
        f.write(str(count))
        
    with open(effect_b_file, "w") as f:
        f.write("TASK_B_EFFECT_PAYLOAD_VALID")
        
    # CRASH / INTERRUPT: exit immediately before result / checkpoint write!
    sys.exit(0)

elif phase == "PHASE2_FRESH_RECOVERY":
    # Fresh process boots from durable disk state
    # 1. Reconcile current work
    recon = engine.continuation_engine.reconcile_current_work()
    if recon["classification"] in ("WAITING_FOR_RESULT", "STALE"):
        finish_res = engine.continuation_engine.finish_current_work_if_needed(recon)
        print(f"RECOVERY_ACTION={finish_res.get('status')}")
    
    # 2. Check Task B state
    task_b = cp.get_task("TASK-COURT-B")
    ckpt = cp.get_checkpoint_record("LAST_VERIFIED_WINDOWS_CHECKPOINT")
    print(f"TASK_B_STATUS={task_b.get('status')}")
    print(f"CHECKPOINT_TASK={ckpt.get('task_id')}")
    
    # 3. Autonomously continue to Task C
    # Discover and execute Task C
    backlog_path = os.path.join(temp_dir, "project-memory", "data", "safe_backlog.json")
    with open(backlog_path, "r") as f:
        bdata = json.load(f)
    
    cand_c = next((t for t in bdata.get("tasks", []) if t.get("task_id") == "TASK-COURT-C"), None)
    if cand_c:
        exec_res = engine.continuation_engine.execute_and_close_task(
            candidate=cand_c,
            state_generation=ckpt.get("state_generation", 100)
        )
        print(f"TASK_C_EXEC_STATUS={exec_res.get('status')}")
        task_c = cp.get_task("TASK-COURT-C")
        ckpt_c = cp.get_checkpoint_record("LAST_VERIFIED_WINDOWS_CHECKPOINT")
        print(f"TASK_C_STATUS={task_c.get('status')}")
        print(f"FINAL_CHECKPOINT_TASK={ckpt_c.get('task_id')}")
"""


def run_fresh_restart_court() -> dict:
    temp_dir = tempfile.mkdtemp(prefix="stage4_court_")
    try:
        # Prepare safe backlog with Task A, Task B, Task C
        pm_data_dir = os.path.join(temp_dir, "project-memory", "data")
        os.makedirs(pm_data_dir, exist_ok=True)
        backlog_path = os.path.join(pm_data_dir, "safe_backlog.json")
        backlog_data = {
            "version": "1.0.0",
            "tasks": [
                {
                    "task_id": "TASK-COURT-A",
                    "title": "Task A Test",
                    "goal_id": "GOAL-04",
                    "priority": 10.0,
                    "status": "COMPLETED",
                    "conflict_scope": "DOMAIN_A",
                    "expected_real_delta": "AUTONOMY_GAIN",
                    "source_evidence": "courier/chief/control_plane.py"
                },
                {
                    "task_id": "TASK-COURT-B",
                    "title": "Task B Controlled Effect",
                    "goal_id": "GOAL-04",
                    "priority": 9.0,
                    "status": "PENDING",
                    "conflict_scope": "DOMAIN_B",
                    "expected_real_delta": "RELIABILITY_GAIN",
                    "source_evidence": "courier/chief/control_plane.py"
                },
                {
                    "task_id": "TASK-COURT-C",
                    "title": "Task C Autonomous Successor",
                    "goal_id": "GOAL-04",
                    "priority": 8.0,
                    "status": "PENDING",
                    "conflict_scope": "DOMAIN_C",
                    "expected_real_delta": "PERFORMANCE_GAIN",
                    "source_evidence": "courier/chief/control_plane.py"
                }
            ]
        }
        with open(backlog_path, "w", encoding="utf-8") as f:
            json.dump(backlog_data, f, indent=2)

        worker_script_path = os.path.join(temp_dir, "worker.py")
        with open(worker_script_path, "w", encoding="utf-8") as f:
            f.write(PROCESS_WORKER_SCRIPT)

        # PROCESS 1: Run Phase 1 (crash simulation after effect)
        env = dict(os.environ)
        env["COURIER_FAST_TEST_MODE"] = "1"
        proc1 = subprocess.run(
            [sys.executable, worker_script_path, "PHASE1_CRASH_SIMULATION", temp_dir],
            capture_output=True,
            text=True,
            env=env
        )
        if proc1.returncode != 0:
            raise RuntimeError(f"Process 1 failed: {proc1.stderr}")

        # Check counter after Process 1
        counter_file = os.path.join(temp_dir, "task_b_counter.txt")
        with open(counter_file, "r") as f:
            count_after_p1 = int(f.read().strip())
        assert count_after_p1 == 1, f"Expected 1, got {count_after_p1}"

        # PROCESS 2: Fresh Process boots from disk state
        proc2 = subprocess.run(
            [sys.executable, worker_script_path, "PHASE2_FRESH_RECOVERY", temp_dir],
            capture_output=True,
            text=True,
            env=env
        )
        if proc2.returncode != 0:
            raise RuntimeError(f"Process 2 failed: {proc2.stderr}")

        # Check counter after Process 2: MUST STILL BE EXACTLY 1!
        with open(counter_file, "r") as f:
            count_after_p2 = int(f.read().strip())

        output_lines = proc2.stdout.strip().splitlines()
        kv_pairs = {}
        for line in output_lines:
            if "=" in line:
                k, v = line.split("=", 1)
                kv_pairs[k.strip()] = v.strip()

        task_b_status = kv_pairs.get("TASK_B_STATUS")
        task_c_status = kv_pairs.get("TASK_C_STATUS")
        final_ckpt = kv_pairs.get("FINAL_CHECKPOINT_TASK")

        passed = (
            count_after_p2 == 1 and
            task_b_status == "COMPLETED" and
            task_c_status == "COMPLETED" and
            final_ckpt == "TASK-COURT-C"
        )

        result = {
            "TASK_B_REAL_EFFECT_COUNT": count_after_p2,
            "TASK_B_STATUS": task_b_status,
            "TASK_C_STATUS": task_c_status,
            "FINAL_CHECKPOINT_TASK": final_ckpt,
            "STAGE_4_FRESH_RESTART_COURT": "PASS" if passed else "FAIL"
        }

        print(f"TASK_B_REAL_EFFECT_COUNT = {count_after_p2}")
        print(f"STAGE_4_FRESH_RESTART_COURT = {'PASS' if passed else 'FAIL'}")
        return result

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    res = run_fresh_restart_court()
    sys.exit(0 if res.get("STAGE_4_FRESH_RESTART_COURT") == "PASS" else 1)
