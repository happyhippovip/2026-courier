#!/usr/bin/env python3
"""
Physical Execution Runner for Courier Mac RUN 2 (Restart & No-Replay).
Implements the contracts and checks defined in MAC_HNI_11..15 and
ops/ai/MAC_RUN2_RESTART_EXECUTION_HARNESS_2026-09-28.md.

DO NOT EXECUTE RUN_2 PHYSICALLY BEFORE RUN_1 PASS.
"""

import os
import sys
import json
import socket
import psutil
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

def capture_spawn_identity(proc) -> dict:
    """Record pid and create_time at spawn. Call this on the Popen before it can exit."""
    pid = getattr(proc, "pid", None)
    if type(pid) is not int or pid <= 0:
        raise RuntimeError("Spawned process has no pid.")
    try:
        process = psutil.Process(pid)
        if process.status() == psutil.STATUS_ZOMBIE or not process.is_running():
            raise RuntimeError(f"Spawned process {pid} is not running.")
        create_time = process.create_time()
    except psutil.Error as exc:
        raise RuntimeError(f"Could not capture spawn identity for pid {pid}.") from exc
    return {"pid": pid, "create_time": create_time}

def spawn_identity_verified(identity) -> bool:
    """True only when the live process is still the one captured at spawn."""
    if not isinstance(identity, dict):
        return False
    pid = identity.get("pid")
    create_time = identity.get("create_time")
    if type(pid) is not int or pid <= 0:
        return False
    if isinstance(create_time, bool) or not isinstance(create_time, (int, float)):
        return False
    try:
        process = psutil.Process(pid)
        if process.status() == psutil.STATUS_ZOMBIE or not process.is_running():
            return False
        return process.create_time() == create_time
    except (psutil.Error, OSError):
        return False

def execute_run2(sha: str, run1_dir: str, evidence_dir: str, port: int = 8081, spawn_identity=None):
    """Pass the RUN 1 gate, then report success only for a verified restarted process.

    ``port`` is retained for callers. This function does not bind it and does not
    spawn a process of its own.
    """
    del port
    # 1. Verify RUN 1 PASS
    run1_evidence = os.path.join(run1_dir, "evidence")
    exit_file = os.path.join(run1_evidence, "run1_exit_code.txt")
    snap_file = os.path.join(run1_evidence, "run1_state_snapshot.json")

    if not os.path.isfile(exit_file):
        raise RuntimeError(f"RUN 1 exit code file missing: {exit_file}")
    with open(exit_file, "r") as f:
        exit_lines = f.read().strip().splitlines()
    if not exit_lines:
        raise RuntimeError(f"RUN 1 exit code file empty: {exit_file}")
    try:
        run1_exit_code = int(exit_lines[0].strip())
    except ValueError:
        raise RuntimeError(f"RUN 1 exit code file unreadable: {exit_file}")
    if run1_exit_code != 0:
        raise RuntimeError("RUN 1 did not PASS cleanly (non-zero exit code). Contamination guard triggered.")

    if not os.path.isfile(snap_file):
        raise RuntimeError(f"RUN 1 snapshot missing: {snap_file}")
    with open(snap_file, "r") as f:
        run1_snap = json.load(f)
    if run1_snap.get("final_status") != "SUCCESS":
        raise RuntimeError("RUN 1 snapshot status is not SUCCESS.")
    if run1_snap.get("candidate_sha") != sha:
        raise RuntimeError(
            f"RUN 1 snapshot candidate_sha mismatch: expected {sha}, "
            f"found {run1_snap.get('candidate_sha')}. Refusing stale bundle."
        )

    if not spawn_identity_verified(spawn_identity):
        print("[RUN_2] No restarted process verified. Not reporting success.")
        return 1

    os.makedirs(evidence_dir, exist_ok=True)
    record = {
        "restart_process_verified": True,
        "pid": spawn_identity["pid"],
        "create_time": spawn_identity["create_time"],
        "candidate_sha": sha,
    }
    with open(os.path.join(evidence_dir, "run2_restart_identity.json"), "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)
    with open(os.path.join(evidence_dir, "run2_exit_code.txt"), "w", encoding="utf-8") as f:
        f.write("0\n")

    print(f"[RUN_2] Restart completed successfully. pid={spawn_identity['pid']}")
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
