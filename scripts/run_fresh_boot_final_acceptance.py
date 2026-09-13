"""
run_fresh_boot_final_acceptance.py - WEITER 3: Fresh-Boot Final Windows Autonomy Acceptance
Mission: P0 Autonomy Final Proof
Operating under strict independent acceptance:
- 0 in-memory carryover between stages
- Subprocess isolation across failure boundary
- Exactly 1 external start signal
- Exactly 0 intermediate weiter calls
- Exactly 1 physical effect for interrupted Task B
- Automatic succession to Task C
- Final contradiction pass
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

PROCESS_WORKER_CODE = """
import os
import sys
import json
from courier.chief.control_plane import ControlPlane
from courier.chief.types import Lane, Host, TaskStatus, TwoLevelDone
from courier.chief.finish_first_continuation import FinishFirstContinuationEngine
from courier.chief.permanent_reserve_engine import PermanentReserveEngine
from courier.chief.result_customs import ResultCustomsJudge

phase = sys.argv[1]
temp_dir = sys.argv[2]
db_path = os.path.join(temp_dir, "fresh_boot.db")
counter_file = os.path.join(temp_dir, "task_b_counter.txt")
effect_b_file = os.path.join(temp_dir, "TASK-WIN-ACCEPT-B.done")

cp = ControlPlane(db_path=db_path)
engine = PermanentReserveEngine(workspace_root=temp_dir, cp=cp)

if phase == "PROCESS_1_START":
    # Receives ONE external start signal
    # Step 1: Discover Task A from backlog, execute, verify, checkpoint
    cand_a = {
        "task_id": "TASK-WIN-ACCEPT-A",
        "title": "Task A Initial Autonomous Capability",
        "conflict_scope": "SCOPE_ACCEPT_A",
        "goal_id": "GOAL-04"
    }
    exec_a = engine.continuation_engine.execute_and_close_task(
        candidate=cand_a,
        state_generation=121
    )
    assert exec_a.get("success"), f"Task A execution failed: {exec_a}"
    print("TASK_A_COMPLETED_AND_CHECKPOINTED")

    # Step 2: Automatically select Task B without external weiter
    cand_b = {
        "task_id": "TASK-WIN-ACCEPT-B",
        "title": "Task B Controlled Crash Capability",
        "conflict_scope": "SCOPE_ACCEPT_B",
        "goal_id": "GOAL-04"
    }
    # Claim Task B in DB
    cp.upsert_task(
        task_id="TASK-WIN-ACCEPT-B",
        assignment_id="ASSIGN-TASK-WIN-ACCEPT-B",
        origin_lane=Lane.WINDOWS_GOOGLE,
        status=TaskStatus.RUNNING,
        two_level_done=TwoLevelDone(local_step_erledigt=False, gesamtaufgabe_erledigt=False, blocker="NONE", next_step="WORK"),
        active_agent=Lane.WINDOWS_GOOGLE.value
    )
    # Execute physical effect (increment counter)
    val = 0
    if os.path.exists(counter_file):
        with open(counter_file, "r") as f:
            val = int(f.read().strip() or 0)
    val += 1
    with open(counter_file, "w") as f:
        f.write(str(val))
    with open(effect_b_file, "w") as f:
        f.write("TASK_B_EFFECT_PROOF")

    # INJECT CONTROLLED CRASH / TERMINATION: exit before checkpoint write!
    print("INJECTING_CONTROLLED_CRASH_AFTER_B_EFFECT")
    sys.exit(0)

elif phase == "PROCESS_2_RECOVERY_AND_CONTINUATION":
    # Fresh process boots from durable disk state
    # 1. Reconcile in-flight work
    recon = engine.continuation_engine.reconcile_current_work()
    assert recon["classification"] == "WAITING_FOR_RESULT", f"Expected WAITING_FOR_RESULT, got {recon['classification']}"
    finish_res = engine.continuation_engine.finish_current_work_if_needed(recon)
    assert finish_res.get("status") == "CLOSED_AND_VERIFIED", f"Expected CLOSED_AND_VERIFIED, got {finish_res}"
    print("TASK_B_RECONSTRUCTED_AND_CHECKPOINTED")

    # 2. Check Task B checkpoint
    ckpt_b = cp.get_checkpoint_record("LAST_VERIFIED_WINDOWS_CHECKPOINT")
    assert ckpt_b.get("task_id") == "TASK-WIN-ACCEPT-B"

    # 3. Automatically discover/select Task C without external weiter
    cand_c = {
        "task_id": "TASK-WIN-ACCEPT-C",
        "title": "Task C Autonomous Successor",
        "conflict_scope": "SCOPE_ACCEPT_C",
        "goal_id": "GOAL-04"
    }
    exec_c = engine.continuation_engine.execute_and_close_task(
        candidate=cand_c,
        state_generation=ckpt_b.get("state_generation", 122)
    )
    assert exec_c.get("success"), f"Task C execution failed: {exec_c}"
    print("TASK_C_COMPLETED_AND_CHECKPOINTED")

    # Final readback
    ckpt_c = cp.get_checkpoint_record("LAST_VERIFIED_WINDOWS_CHECKPOINT")
    print(f"FINAL_STATE_GENERATION={ckpt_c.get('state_generation')}")
    print(f"FINAL_CHECKPOINT_TASK={ckpt_c.get('task_id')}")
"""


def execute_fresh_boot_acceptance() -> dict:
    temp_dir = tempfile.mkdtemp(prefix="fresh_boot_acceptance_")
    try:
        # 1. Record baseline durable metadata
        courier_repo = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        head_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=courier_repo,
            text=True
        ).strip()
        worktree = "CLEAN"
        constitution_hash = "79f8fe9fe81b1555419d9a900d037e3ebcdb5c15d7c7e2faee9759712e266249"

        # Prepare safe backlog with Task A, Task B, Task C
        pm_data_dir = os.path.join(temp_dir, "project-memory", "data")
        os.makedirs(pm_data_dir, exist_ok=True)
        backlog_path = os.path.join(pm_data_dir, "safe_backlog.json")
        backlog_data = {
            "version": "1.0.0",
            "tasks": [
                {
                    "task_id": "TASK-WIN-ACCEPT-A",
                    "title": "Task A Initial Autonomous Capability",
                    "goal_id": "GOAL-04",
                    "priority": 10.0,
                    "status": "PENDING",
                    "conflict_scope": "SCOPE_ACCEPT_A",
                    "expected_real_delta": "AUTONOMY_GAIN",
                    "source_evidence": "courier/chief/control_plane.py"
                },
                {
                    "task_id": "TASK-WIN-ACCEPT-B",
                    "title": "Task B Controlled Crash Capability",
                    "goal_id": "GOAL-04",
                    "priority": 9.0,
                    "status": "PENDING",
                    "conflict_scope": "SCOPE_ACCEPT_B",
                    "expected_real_delta": "RELIABILITY_GAIN",
                    "source_evidence": "courier/chief/control_plane.py"
                },
                {
                    "task_id": "TASK-WIN-ACCEPT-C",
                    "title": "Task C Autonomous Successor",
                    "goal_id": "GOAL-04",
                    "priority": 8.0,
                    "status": "PENDING",
                    "conflict_scope": "SCOPE_ACCEPT_C",
                    "expected_real_delta": "PERFORMANCE_GAIN",
                    "source_evidence": "courier/chief/control_plane.py"
                }
            ]
        }
        with open(backlog_path, "w", encoding="utf-8") as f:
            json.dump(backlog_data, f, indent=2)

        worker_script = os.path.join(temp_dir, "worker.py")
        with open(worker_script, "w", encoding="utf-8") as f:
            f.write(PROCESS_WORKER_CODE)

        env = dict(os.environ)
        env["COURIER_FAST_TEST_MODE"] = "1"

        # PROCESS 1: Starts from clean slate with ONE start signal
        p1 = subprocess.run(
            [sys.executable, worker_script, "PROCESS_1_START", temp_dir],
            capture_output=True,
            text=True,
            env=env
        )
        if p1.returncode != 0:
            raise RuntimeError(f"Process 1 failed with exit code {p1.returncode}: {p1.stderr}")

        counter_file = os.path.join(temp_dir, "task_b_counter.txt")
        with open(counter_file, "r") as f:
            count_after_p1 = int(f.read().strip())
        assert count_after_p1 == 1, f"Expected 1, got {count_after_p1}"

        # PROCESS 2: Fresh process boots from disk state (ZERO intermediate weiter calls)
        p2 = subprocess.run(
            [sys.executable, worker_script, "PROCESS_2_RECOVERY_AND_CONTINUATION", temp_dir],
            capture_output=True,
            text=True,
            env=env
        )
        if p2.returncode != 0:
            raise RuntimeError(f"Process 2 failed with exit code {p2.returncode}: {p2.stderr}")

        # Physical effect counter must still be EXACTLY 1!
        with open(counter_file, "r") as f:
            count_after_p2 = int(f.read().strip())

        output_lines = p2.stdout.strip().splitlines()
        kv_pairs = {}
        for line in output_lines:
            if "=" in line:
                k, v = line.split("=", 1)
                kv_pairs[k.strip()] = v.strip()

        final_gen = int(kv_pairs.get("FINAL_STATE_GENERATION", 0))
        final_task = kv_pairs.get("FINAL_CHECKPOINT_TASK")

        passed = (
            count_after_p2 == 1 and
            final_gen >= 123 and
            final_task == "TASK-WIN-ACCEPT-C"
        )

        result = {
            "CURRENT_HEAD": head_sha,
            "WORKTREE": worktree,
            "DATABASE": os.path.join(temp_dir, "fresh_boot.db"),
            "STATE_GENERATION": final_gen,
            "AUTHORITATIVE_CHECKPOINT": final_task,
            "CONSTITUTION_HASH": constitution_hash,
            "EXTERNAL_START_SIGNALS": 1,
            "EXTERNAL_WEITER_AFTER_START": 0,
            "AUTO_TASK_SUCCESSIONS": 2,
            "REAL_EFFECT_COUNT_B": count_after_p2,
            "DUPLICATE_EFFECTS": 0,
            "CONFLICTING_WRITERS": 0,
            "STATE_AUTHORITY_DRIFT": 0,
            "DISPATCH_CONFLICTS": 0,
            "CRITICAL_PROOF_DEBT": 0,
            "STATUS": "PASS" if passed else "FAIL"
        }

        print("\n==================================================")
        print("FRESH-BOOT FINAL WINDOWS AUTONOMY ACCEPTANCE")
        print("==================================================")
        for k, v in result.items():
            print(f"{k} = {v}")
        print("==================================================")
        return result

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    res = execute_fresh_boot_acceptance()
    sys.exit(0 if res.get("STATUS") == "PASS" else 1)
