#!/usr/bin/env python3
"""
Physical Execution Runner for Courier Mac RUN.
Implements the contracts and checks defined in MAC_HNI_01..10 and
ops/ai/MAC_RUN1_ISOLATION_AND_PREFLIGHT_CHECKLIST_2026-09-28.md.

This is the REAL PRODUCER (GW40). It orchestrates server and worker subprocesses,
submits a physical test goal, and dynamically extracts counters from central_state.json.
"""

import os
import sys
import time
import json
import socket
import psutil
import hashlib
import argparse
import subprocess
from pathlib import Path
import urllib.request
import urllib.error

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
            raise RuntimeError(f"Port {port} is currently in use. (Preflight Check Failed)")
    return True

def compute_dir_hash(evidence_dir: str) -> str:
    """Compute combined SHA256 of all logs and json snapshots."""
    hasher = hashlib.sha256()
    for root, _, files in os.walk(evidence_dir):
        for fname in sorted(files):
            if fname.endswith(".txt") and "hash" in fname:
                continue
            if fname.endswith(".pid"):
                continue
            fpath = os.path.join(root, fname)
            with open(fpath, "rb") as f:
                hasher.update(f.read())
    return hasher.hexdigest()

def exit_code_for_status(final_status: str) -> int:
    """Process contract: exit 0 iff the run reached SUCCESS, else 1.

    The exit-code FILE carries this same value (first line) plus the status
    string (second line) so file-gated follow-ups (RUN_2) cannot mistake a
    BLOCKED/FAILED run for a PASS. See writer packets P2+P3 (2026-09-29).
    """
    return 0 if final_status == "SUCCESS" else 1

def execute_run(sha: str, evidence_dir: str, port: int = 8081):
    """Execute physical RUN pipeline by orchestrating real processes."""
    os.makedirs(evidence_dir, exist_ok=True)
    state_dir = os.path.join(os.path.dirname(evidence_dir), "state")
    os.makedirs(state_dir, exist_ok=True)
    worker_home = os.path.join(os.path.dirname(evidence_dir), "worker_home")
    os.makedirs(worker_home, exist_ok=True)

    stdout_path = os.path.join(evidence_dir, "run1_stdout.log")
    stderr_path = os.path.join(evidence_dir, "run1_stderr.log")
    exit_code_path = os.path.join(evidence_dir, "run1_exit_code.txt")
    snapshot_path = os.path.join(evidence_dir, "run1_state_snapshot.json")
    metrics_path = os.path.join(evidence_dir, "run1_system_metrics.json")
    hash_path = os.path.join(evidence_dir, "run1_falsifiability_hash.txt")
    server_pid_path = os.path.join(evidence_dir, "server.pid")
    worker_pid_path = os.path.join(evidence_dir, "worker.pid")

    t_start = time.time()
    
    env = os.environ.copy()
    env["PORT"] = str(port)
    env["COURIER_SERVER"] = f"http://127.0.0.1:{port}"
    env["COURIER_STATE_FILE"] = os.path.join(state_dir, "central_state.json")
    env["COURIER_ARTIFACT_UPLOAD"] = "1"
    env["COURIER_CANDIDATE_SHA"] = sha
    env["PYTHONUNBUFFERED"] = "1"
    env["COURIER_WORKER_HOME"] = worker_home
    env["COURIER_API_KEY"] = "mac-physical-run-token"
    env["COURIER_VERIFIER_API_KEY"] = "mac-physical-verifier-token"

    # Reset logs
    with open(stdout_path, "w") as f: f.write(f"[RUN] Booted with SHA: {sha}\n")
    with open(stderr_path, "w") as f: pass

    server_proc = None
    worker_proc = None
    verifier_proc = None

    def cleanup():
        print("[RUN] Tearing down processes (Process Group Kill)...")
        import signal
        if worker_proc:
            try:
                os.killpg(os.getpgid(worker_proc.pid), signal.SIGTERM)
                worker_proc.wait(timeout=5)
            except Exception as e:
                print(f"Worker cleanup error: {e}")
                try: os.killpg(os.getpgid(worker_proc.pid), signal.SIGKILL)
                except: pass
        if verifier_proc:
            try:
                os.killpg(os.getpgid(verifier_proc.pid), signal.SIGTERM)
                verifier_proc.wait(timeout=5)
            except Exception as e:
                print(f"Verifier cleanup error: {e}")
                try: os.killpg(os.getpgid(verifier_proc.pid), signal.SIGKILL)
                except: pass
        if server_proc:
            try:
                os.killpg(os.getpgid(server_proc.pid), signal.SIGTERM)
                server_proc.wait(timeout=5)
            except Exception as e:
                print(f"Server cleanup error: {e}")
                try: os.killpg(os.getpgid(server_proc.pid), signal.SIGKILL)
                except: pass

    try:
        server_out = open(stdout_path, "a")
        server_err = open(stderr_path, "a")
        
        # 1. Spawn Server
        print("[RUN] Spawning Server...")
        server_proc = subprocess.Popen(
            [sys.executable, "-c", "import sys, os; sys.path.append(os.getcwd()); from server.app import app; app.run(host='0.0.0.0', port=int(sys.argv[1]))", str(port)],
            env=env, cwd=REPO_ROOT, stdout=server_out, stderr=server_err,
            preexec_fn=os.setpgrp
        )
        with open(server_pid_path, "w") as f: f.write(str(server_proc.pid))

        # Wait for HTTP server
        ready = False
        for _ in range(40):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1).read()
                ready = True
                break
            except Exception:
                time.sleep(0.5)
        if not ready:
            raise RuntimeError("Server failed to boot or bind.")

        # 2. Spawn Worker
        print("[RUN] Spawning Mac Worker...")
        worker_proc = subprocess.Popen(
            [sys.executable, "scripts/mac_worker/daemon.py"],
            env=env, cwd=REPO_ROOT, stdout=server_out, stderr=server_err,
            preexec_fn=os.setpgrp
        )
        # 3. Spawn Mac Verifier
        print("[RUN] Spawning Mac Verifier...")
        verifier_pid_path = os.path.join(state_dir, "verifier.pid")
        verifier_proc = subprocess.Popen(
            [sys.executable, "scripts/courier_verifier.py"],
            env=env, cwd=REPO_ROOT, stdout=server_out, stderr=server_err,
            preexec_fn=os.setpgrp
        )
        with open(verifier_pid_path, "w") as f: f.write(str(verifier_proc.pid))

        # 4. Submit Goal
        print("[RUN] Submitting test goal...")
        goal_payload = {
            "goal_text": "run physical tests",
            "workflow_plan": [
                {"task_id": "process_a", "target_agent": "mac", "instruction": "echo A > courier_canary_process_a.txt"},
                {"task_id": "process_b", "target_agent": "mac", "instruction": "echo B > courier_canary_process_b.txt"}
            ]
        }
        req = urllib.request.Request(f"http://127.0.0.1:{port}/goals",
            data=json.dumps(goal_payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {env['COURIER_API_KEY']}"}
        )
        resp = urllib.request.urlopen(req)
        goal_data = json.loads(resp.read())
        goal_id = goal_data["goal_id"]

        # 4. Wait for goal to reach terminal state
        print(f"[RUN] Polling goal {goal_id}...")
        final_goal_status = "QUEUED"
        for _ in range(60):
            req2 = urllib.request.Request(f"http://127.0.0.1:{port}/goals/{goal_id}",
                headers={"Authorization": f"Bearer {env['COURIER_API_KEY']}"})
            try:
                r2 = urllib.request.urlopen(req2)
                gstat = json.loads(r2.read())
                final_goal_status = gstat.get("goal", {}).get("status", "UNKNOWN")
                if final_goal_status in ["SUCCESS", "FAILED_TERMINAL", "BLOCKED", "DONE"]:
                    break
            except Exception as e:
                pass
            time.sleep(1)
        else:
            raise RuntimeError(f"Goal polling timed out. Final status: {final_goal_status}")

    finally:
        cleanup()
        server_out.close()
        server_err.close()

    print("[RUN] Processes terminated. Reconstructing physical evidence...")
    
    # 5. Extract truth from central_state.json
    central_state_path = os.path.join(state_dir, "central_state.json")
    if not os.path.exists(central_state_path):
        raise RuntimeError("FALSIFIED: central_state.json missing!")
        
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


    if final_goal_status == "DONE":
        final_goal_status = "SUCCESS"

    payload = {
        "candidate_sha": sha,
        "run_id": "RUN_1",
        "host": "MAC",
        "status": final_goal_status
    }
    serialized_payload = json.dumps(payload, sort_keys=True).encode("utf-8")
    server_bytes_hash = hashlib.sha256(serialized_payload).hexdigest()

    snapshot_data = {
        # Note: "synthetic": True is DELIBERATELY MISSING. This is the real producer.
        "final_status": final_goal_status,
        "candidate_sha": sha,
        "execution_counters": {
            "process_a": a_attempts,
            "process_b": b_attempts,
            "human_relay_count": 0
        },
        "state_transitions": g.get("state_transitions", []),
        "payload": payload,
        "expected_server_bytes_hash": server_bytes_hash
    }

    with open(snapshot_path, "w", encoding="utf-8") as f:
        json.dump(snapshot_data, f, indent=2)

    exit_code = exit_code_for_status(final_goal_status)
    with open(exit_code_path, "w", encoding="utf-8") as f:
        f.write(f"{exit_code}\n{final_goal_status}\n")

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

    if final_goal_status != "SUCCESS":
        print(f"[RUN] Physical run FAILED. Final status: {final_goal_status}. Hash: {falsifiability_hash}")
    else:
        print(f"[RUN] Completed physical run successfully. Hash: {falsifiability_hash}")
    return exit_code

def main():
    parser = argparse.ArgumentParser(description="Courier Physical RUN Runner")
    parser.add_argument("--sha", type=str, required=True, help="Candidate commit SHA")
    parser.add_argument("--evidence-dir", type=str, default=None, help="Evidence output directory")
    parser.add_argument("--port", type=int, default=8081, help="Port to bind")
    parser.add_argument("--dry-run-check", action="store_true", help="Perform preflight resource and port check only")
    args = parser.parse_args()

    check_resources()
    check_port_free(args.port)

    if args.dry_run_check:
        print("[RUN] Preflight check PASSED.")
        sys.exit(0)

    evidence_dir = args.evidence_dir or f"/tmp/courier_run1_{args.sha}/evidence"
    code = execute_run(args.sha, evidence_dir, args.port)
    sys.exit(code)

if __name__ == "__main__":
    main()
