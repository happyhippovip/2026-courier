#!/usr/bin/env python3
import sys
import subprocess
import time
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(COURIER_DIR))

from scripts.canonical_authority import CanonicalAuthority

PRIMARY_TASK_ID = "TASK_PRIMARY_5E"
COMPETING_TASK_ID = "TASK_COMPETING_5E"
SCOPE = "C:\\Dev\\Windows-AI-OS"
ROUTER_CMD = [sys.executable, str(SCRIPTS_DIR / "router_dispatch_codex.py")]

print(f"=== STEP 5: CONTENTION PROOF ===")

print(f"\n[PRIMARY] Attempting to acquire lease for {PRIMARY_TASK_ID}...")
authority = CanonicalAuthority()
success, gen, err = authority.acquire_scopes("agent-codex-bridge", PRIMARY_TASK_ID, [SCOPE], ttl_seconds=300)
if not success:
    print(f"[FAIL] Primary task failed to acquire lease: {err}")
    sys.exit(1)
print(f"[PRIMARY] Lease acquired (gen {gen}). Simulating long-running execution...")

print(f"\n[COMPETING] Dispatching {COMPETING_TASK_ID} for the SAME scope...")
competing_proc = subprocess.run(
    ROUTER_CMD + [COMPETING_TASK_ID, "Compete for Windows-AI-OS"],
    capture_output=True, text=True
)

print("[COMPETING] Output:")
for line in competing_proc.stdout.splitlines():
    print(f"  {line}")
if competing_proc.stderr:
    for line in competing_proc.stderr.splitlines():
        print(f"  [ERR] {line}")

competing_failed_correctly = False
if competing_proc.returncode == 2 and "checkpointed due to lease contention" in competing_proc.stdout:
    print("[COMPETING] Task correctly failed closed and was denied the lease.")
    competing_failed_correctly = True
else:
    print("[COMPETING] ERROR: Task did not fail closed on lease contention as expected!")

print(f"\n[PRIMARY] Releasing lease...")
authority.release_scopes(owner_id="agent-codex-bridge", scopes=[SCOPE], generation=gen, task_id=PRIMARY_TASK_ID)

print(f"\n[PRIMARY] Dispatching {PRIMARY_TASK_ID} through the pipeline...")
primary_proc = subprocess.run(
    ROUTER_CMD + [PRIMARY_TASK_ID, "Execute primary task on Windows-AI-OS"],
    capture_output=True, text=True
)

print("[PRIMARY] Output:")
for line in primary_proc.stdout.splitlines():
    if "RESULT VERIFICATION" in line or "FINAL_STATUS" in line or "STEP" in line:
        print(f"  {line}")

primary_executed = False
if primary_proc.returncode == 0 and "FINAL_STATUS=PASS" in primary_proc.stdout:
    print("[PRIMARY] Task successfully executed.")
    primary_executed = True

if competing_failed_correctly and primary_executed:
    print("\n[VERDICT] CONTENTION PROOF SUCCESSFUL - ONE WRITER ENFORCED")
else:
    print("\n[VERDICT] CONTENTION PROOF FAILED")
    sys.exit(1)
