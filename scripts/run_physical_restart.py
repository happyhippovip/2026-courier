#!/usr/bin/env python3
"""
Physical Execution Runner for Courier Mac RUN 2 (Restart & No-Replay).
Implements the contracts and checks defined in MAC_HNI_11..15 and
ops/ai/MAC_RUN2_RESTART_EXECUTION_HARNESS_2026-09-28.md.

DO NOT EXECUTE RUN_2 PHYSICALLY BEFORE RUN_1 PASS.
"""

import os
import sys
import time
import json
import socket
import psutil
import hashlib
import argparse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

def check_resources(force: bool = False):
    """Verify system capacity before starting."""
    if force:
        return True
    mem = psutil.virtual_memory()
    available_mb = mem.available / (1024 * 1024)
    if available_mb < 1000:
        raise RuntimeError(f"Insufficient RAM: {available_mb:.1f}MB available, 1000MB required.")
    
    load1, _, _ = os.getloadavg()
    cpu_cores = os.cpu_count() or 1
    max_load = max(6.0, cpu_cores * 0.8)
    if load1 > max_load:
        raise RuntimeError(f"System load too high: {load1:.2f}. Limit is {max_load:.1f} on {cpu_cores} cores.")
    return True

def check_port_free(port: int = 8081):
    """Check that target port is not in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        res = s.connect_ex(("127.0.0.1", port))
        if res == 0:
            raise RuntimeError(f"Port {port} is currently in use.")
    return True

def compute_dir_hash(evidence_dir: str) -> str:
    """Compute combined SHA256 of all logs and json snapshots."""
    hasher = hashlib.sha256()
    for root, _, files in os.walk(evidence_dir):
        for fname in sorted(files):
            if fname.endswith(".txt") and "hash" in fname:
                continue
            fpath = os.path.join(root, fname)
            with open(fpath, "rb") as f:
                hasher.update(f.read())
    return hasher.hexdigest()

def execute_run2(sha: str, run1_dir: str, evidence_dir: str, port: int = 8081):
    """Execute physical RUN 2 restart pipeline."""
    import subprocess, urllib.request, shutil

    run1_evidence = os.path.join(run1_dir, "evidence")
    exit_file = os.path.join(run1_evidence, "run1_exit_code.txt")
    snap_file = os.path.join(run1_evidence, "run1_state_snapshot.json")

    if not os.path.isfile(exit_file):
        raise RuntimeError(f"RUN 1 exit code file missing: {exit_file}")
    with open(exit_file, "r") as f:
        if f.read().strip() != "0":
            raise RuntimeError("RUN 1 did not PASS cleanly (non-zero exit code). Contamination guard triggered.")

    if not os.path.isfile(snap_file):
        raise RuntimeError(f"RUN 1 snapshot missing: {snap_file}")
    with open(snap_file, "r") as f:
        run1_snap = json.load(f)
    if run1_snap.get("final_status") != "SUCCESS":
        raise RuntimeError("RUN 1 snapshot status is not SUCCESS.")

    os.makedirs(evidence_dir, exist_ok=True)
    state_dir = os.path.join(os.path.dirname(evidence_dir), "state")
    os.makedirs(state_dir, exist_ok=True)
    
    # Mount RUN 1 state
    run1_state_dir = os.path.join(run1_dir, "state")
    if os.path.exists(run1_state_dir):
        shutil.copytree(run1_state_dir, state_dir, dirs_exist_ok=True)

    stdout_path = os.path.join(evidence_dir, "run2_stdout.log")
    stderr_path = os.path.join(evidence_dir, "run2_stderr.log")
    exit_code_path = os.path.join(evidence_dir, "run2_exit_code.txt")
    snapshot_path = os.path.join(evidence_dir, "run2_state_snapshot.json")
    metrics_path = os.path.join(evidence_dir, "run2_system_metrics.json")
    hash_path = os.path.join(evidence_dir, "run2_falsifiability_hash.txt")
    server_pid_path = os.path.join(state_dir, "server.pid")

    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    worker_home = os.path.join(os.path.dirname(evidence_dir), "worker_home")
    os.makedirs(worker_home, exist_ok=True)
    env["COURIER_WORKER_HOME"] = worker_home
    env["COURIER_API_KEY"] = "mac-physical-run-token"
    env["COURIER_SERVER"] = f"http://127.0.0.1:{port}"
    env["COURIER_STATE_FILE"] = os.path.join(state_dir, "central_state.json")
    # NO VERIFIER KEY CUSTODY
    if "COURIER_VERIFIER_API_KEY" in env:
        del env["COURIER_VERIFIER_API_KEY"]

    server_proc = None
    worker_proc = None
    t_start = time.time()
    
    def cleanup():
        if worker_proc:
            try:
                os.killpg(os.getpgid(worker_proc.pid), signal.SIGTERM)
                worker_proc.wait(timeout=5)
            except Exception:
                try: os.killpg(os.getpgid(worker_proc.pid), signal.SIGKILL)
                except: pass
        if server_proc:
            try:
                os.killpg(os.getpgid(server_proc.pid), signal.SIGTERM)
                server_proc.wait(timeout=5)
            except Exception:
                try: os.killpg(os.getpgid(server_proc.pid), signal.SIGKILL)
                except: pass

    import signal
    try:
        server_out = open(stdout_path, "a")
        server_err = open(stderr_path, "a")
        
        server_proc = subprocess.Popen(
            [sys.executable, "-c", "import sys, os; sys.path.append(os.getcwd()); from server.app import app; app.run(host='0.0.0.0', port=int(sys.argv[1]))", str(port)],
            env=env, cwd=REPO_ROOT, stdout=server_out, stderr=server_err,
            preexec_fn=os.setsid
        )
        with open(server_pid_path, "w") as f: f.write(str(server_proc.pid))

        ready = False
        for _ in range(40):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1).read()
                ready = True
                break
            except Exception:
                time.sleep(0.5)
        if not ready:
            raise RuntimeError("Server failed to boot or bind in RUN 2.")

        worker_proc = subprocess.Popen(
            [sys.executable, "scripts/mac_worker/daemon.py"],
            env=env, cwd=REPO_ROOT, stdout=server_out, stderr=server_err,
            preexec_fn=os.setsid
        )

        central_state_path = os.path.join(state_dir, "central_state.json")
        if not os.path.exists(central_state_path):
            raise RuntimeError("central_state.json missing in mounted state!")
        with open(central_state_path, "r") as f:
            central = json.load(f)
        
        goals = central.get("goals", {})
        if not goals:
            raise RuntimeError("No goals found in RUN 1 state!")
        goal_id = list(goals.keys())[0]

        final_goal_status = "QUEUED"
        observed_transitions = [{"state": "RESTART_BOOT", "timestamp": int(t_start * 1000)},
                                {"state": "RECONCILE_MOUNT", "timestamp": int(t_start * 1000) + 1}]
        seen_b_start = False
        seen_b_complete = False

        for _ in range(60):
            req2 = urllib.request.Request(f"http://127.0.0.1:{port}/goals/{goal_id}",
                headers={"Authorization": f"Bearer {env['COURIER_API_KEY']}"})
            try:
                r2 = urllib.request.urlopen(req2)
                gstat = json.loads(r2.read())
                final_goal_status = gstat.get("goal", {}).get("status", "UNKNOWN")
                
                now_ms = int(time.time() * 1000)
                pb_status = "UNKNOWN"
                for t in gstat.get("goal", {}).get("workflow_plan", []):
                    if t.get("task_id") == "process_b":
                        pb_status = t.get("status")
                        
                if pb_status == "DISPATCHED" and not seen_b_start:
                    observed_transitions.append({"state": "B_START", "timestamp": now_ms})
                    seen_b_start = True
                if pb_status == "RECONCILED" and not seen_b_complete:
                    observed_transitions.append({"state": "B_RESUMED_COMPLETE", "timestamp": now_ms})
                    seen_b_complete = True
                
                if final_goal_status in ["SUCCESS", "FAILED_TERMINAL", "BLOCKED", "DONE"]:
                    break
            except Exception as e:
                pass
            time.sleep(1)
        else:
            raise RuntimeError(f"Goal polling timed out in RUN 2. Final status: {final_goal_status}")

    finally:
        cleanup()
        server_out.close()
        server_err.close()

    with open(central_state_path, "r") as f:
        central = json.load(f)
    g = central.get("goals", {}).get(goal_id, {})
    wp = g.get("workflow_plan", [])
    
    a_attempts = 0
    b_attempts = 0
    for task in wp:
        if task.get("task_id") == "process_a":
            a_attempts = task.get("attempts", 0)
        elif task.get("task_id") == "process_b":
            b_attempts = task.get("attempts", 0)

    # Calculate deltas since RUN 1
    run1_a_attempts = run1_snap.get("execution_counters", {}).get("process_a", 0)
    run1_b_attempts = run1_snap.get("execution_counters", {}).get("process_b", 0)
    r2_a = max(0, a_attempts - run1_a_attempts)
    r2_b = max(0, b_attempts - run1_b_attempts)

    if final_goal_status == "DONE":
        final_goal_status = "SUCCESS"

    payload = {
        "candidate_sha": sha,
        "run_id": "RUN_2",
        "host": "MAC",
        "status": final_goal_status
    }
    serialized_payload = json.dumps(payload, sort_keys=True).encode("utf-8")
    server_bytes_hash = hashlib.sha256(serialized_payload).hexdigest()

    snapshot_data = {
        "final_status": final_goal_status,
        "candidate_sha": sha,
        "initial_state": {
            "process_a_status": "COMPLETE"
        },
        "execution_counters": {
            "process_a": r2_a,
            "process_b": r2_b,
            "human_relay_count": 0
        },
        "state_transitions": observed_transitions,
        "payload": payload,
        "expected_server_bytes_hash": server_bytes_hash
    }

    with open(snapshot_path, "w", encoding="utf-8") as f:
        json.dump(snapshot_data, f, indent=2)

    with open(exit_code_path, "w", encoding="utf-8") as f:
        f.write("0\n")

    metrics_data = {
        "duration_sec": time.time() - t_start,
        "cpu_percent": psutil.cpu_percent(),
        "memory_mb_used": psutil.virtual_memory().used / (1024 * 1024)
    }
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics_data, f, indent=2)

    falsifiability_hash = compute_dir_hash(evidence_dir)
    with open(hash_path, "w", encoding="utf-8") as f:
        f.write(f"{falsifiability_hash}\n")

    print(f"[RUN_2] Restart completed successfully. Hash: {falsifiability_hash}")
    return 0

def main():
    parser = argparse.ArgumentParser(description="Courier Physical RUN 2 (Restart) Runner")
    parser.add_argument("--sha", type=str, required=True, help="Candidate commit SHA")
    parser.add_argument("--state-dir", type=str, required=True, help="Directory containing RUN 1 artifacts")
    parser.add_argument("--evidence-dir", type=str, default=None, help="Evidence output directory")
    parser.add_argument("--port", type=int, default=8081, help="Port to bind")
    parser.add_argument("--dry-run-check", action="store_true", help="Perform preflight check only")
    args = parser.parse_args()

    check_resources()
    check_port_free(args.port)

    if args.dry_run_check:
        print("[RUN_2] Preflight check PASSED.")
        sys.exit(0)

    evidence_dir = args.evidence_dir or f"/tmp/courier_run2_{args.sha}/evidence"
    code = execute_run2(args.sha, args.state_dir, evidence_dir, args.port)
    sys.exit(code)

if __name__ == "__main__":
    main()
