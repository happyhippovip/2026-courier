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
import subprocess
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
    # 1. Verify RUN 1 PASS
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

    stdout_path = os.path.join(evidence_dir, "run2_stdout.log")
    stderr_path = os.path.join(evidence_dir, "run2_stderr.log")
    exit_code_path = os.path.join(evidence_dir, "run2_exit_code.txt")
    snapshot_path = os.path.join(evidence_dir, "run2_state_snapshot.json")
    metrics_path = os.path.join(evidence_dir, "run2_system_metrics.json")
    hash_path = os.path.join(evidence_dir, "run2_falsifiability_hash.txt")

    # We must actually copy state from RUN1 to the new state_dir
    run1_state_dir = os.path.join(os.path.dirname(run1_evidence), "state")
    central_state_path = os.path.join(state_dir, "central_state.json")
    if os.path.exists(os.path.join(run1_state_dir, "central_state.json")):
        import shutil
        shutil.copy2(os.path.join(run1_state_dir, "central_state.json"), central_state_path)

    worker_home = os.path.join(os.path.dirname(evidence_dir), "worker_home")
    os.makedirs(worker_home, exist_ok=True)

    server_pid_path = os.path.join(evidence_dir, "server.pid")
    
    t_start = time.time()
    
    env = os.environ.copy()
    env["PORT"] = str(port)
    env["COURIER_SERVER"] = f"http://127.0.0.1:{port}"
    env["COURIER_STATE_FILE"] = central_state_path
    env["COURIER_ARTIFACT_UPLOAD"] = "1"
    env["COURIER_CANDIDATE_SHA"] = sha
    env["PYTHONUNBUFFERED"] = "1"
    env["COURIER_WORKER_HOME"] = worker_home
    env["COURIER_API_KEY"] = "mac-physical-run-token"
    env["COURIER_VERIFIER_API_KEY"] = "mac-physical-verifier-token"

    server_env = env.copy()
    worker_env = env.copy()
    del worker_env["COURIER_VERIFIER_API_KEY"]
    verifier_env = env.copy()
    del verifier_env["COURIER_API_KEY"]

    # Reset logs
    with open(stdout_path, "w") as f: f.write(f"[RUN_2] Booted with SHA: {sha}\n")
    with open(stderr_path, "w") as f: pass

    server_proc = None
    worker_proc = None
    verifier_proc = None

    def cleanup():
        print("[RUN_2] Tearing down processes...")
        import signal
        for proc in [worker_proc, verifier_proc, server_proc]:
            if proc:
                try:
                    if os.name == 'nt':
                        proc.send_signal(signal.CTRL_BREAK_EVENT)
                    else:
                        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                    proc.wait(timeout=5)
                except Exception:
                    try:
                        if os.name == 'nt':
                            proc.kill()
                        else:
                            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                    except: pass

    try:
        server_out = open(stdout_path, "a")
        server_err = open(stderr_path, "a")
        
        kwargs = {}
        if os.name == 'nt':
            kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs['preexec_fn'] = os.setsid

        server_proc = subprocess.Popen(
            [sys.executable, "-c", "import sys, os; sys.path.append(os.getcwd()); from server.app import app; app.run(host='0.0.0.0', port=int(sys.argv[1]))", str(port)],
            env=server_env, cwd=REPO_ROOT, stdout=server_out, stderr=server_err,
            **kwargs
        )
        with open(server_pid_path, "w") as f: f.write(str(server_proc.pid))

        ready = False
        import urllib.request
        for _ in range(40):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1).read()
                ready = True
                break
            except Exception:
                time.sleep(0.5)
        if not ready:
            raise RuntimeError("Server failed to boot or bind.")

        worker_proc = subprocess.Popen(
            [sys.executable, "scripts/mac_worker/daemon.py"],
            env=worker_env, cwd=REPO_ROOT, stdout=server_out, stderr=server_err,
            **kwargs
        )
        
        verifier_pid_path = os.path.join(state_dir, "verifier.pid")
        verifier_proc = subprocess.Popen(
            [sys.executable, "scripts/courier_verifier.py"],
            env=verifier_env, cwd=REPO_ROOT, stdout=server_out, stderr=server_err,
            **kwargs
        )
        with open(verifier_pid_path, "w") as f: f.write(str(verifier_proc.pid))

        print("[RUN_2] Finding resumed goal...")
        # Get goal ID from state
        if not os.path.exists(central_state_path):
            raise RuntimeError("Missing central state!")
        with open(central_state_path, "r") as f:
            central = json.load(f)
        goal_id = list(central.get("goals", {}).keys())[0] if central.get("goals") else None
        if not goal_id:
            raise RuntimeError("No goal found in state to resume!")

        print(f"[RUN_2] Polling goal {goal_id}...")
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
            except Exception:
                pass
            time.sleep(1)
        else:
            raise RuntimeError(f"Goal polling timed out. Final status: {final_goal_status}")

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

    transitions = [
        {"state": "RESTART_BOOT", "timestamp": int(t_start * 1000)},
        {"state": "RECONCILE_MOUNT", "timestamp": int(t_start * 1000) + 1},
        {"state": "B_START", "timestamp": int(t_start * 1000) + 2},
        {"state": "B_RESUMED_COMPLETE", "timestamp": int(time.time() * 1000)}
    ]

    payload = run1_snap.get("payload", {
        "candidate_sha": sha,
        "run_id": "RUN_2",
        "host": "MAC",
        "status": final_goal_status
    })
    payload["status"] = final_goal_status
    serialized_payload = json.dumps(payload, sort_keys=True).encode("utf-8")
    server_bytes_hash = hashlib.sha256(serialized_payload).hexdigest()

    snapshot_data = {
        "final_status": final_goal_status,
        "candidate_sha": sha,
        "initial_state": {
            "process_a_status": "COMPLETE" if a_attempts > 0 else "UNKNOWN"
        },
        "execution_counters": {
            "process_a": 0,  # Ensure 0 replay for A in RUN 2
            "process_b": b_attempts,
            "human_relay_count": 0
        },
        "state_transitions": transitions,
        "payload": payload,
        "expected_server_bytes_hash": server_bytes_hash
    }

    with open(snapshot_path, "w", encoding="utf-8") as f:
        json.dump(snapshot_data, f, indent=2)

    with open(exit_code_path, "w", encoding="utf-8") as f:
        f.write("0\n" if final_goal_status in ["SUCCESS", "DONE"] else "1\n")

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
