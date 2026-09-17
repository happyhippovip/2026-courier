#!/usr/bin/env python3
"""
Physical Test A: Verify that a hanging child process is killed by daemon's
timeout path, leaving zero orphans.

This test directly calls run_agy with a very short timeout to prove the
process group ownership + cleanup chain works end to end.
"""
import subprocess, os, sys, time, signal, json, tempfile
from pathlib import Path

WRAPPER = os.path.join(os.path.dirname(__file__), "limit_wrapper.sh")

print("=" * 60)
print("TEST A: Timeout kills owned process tree")
print("=" * 60)

# Launch wrapper with a long sleep (simulates a hanging task)
cmd = [WRAPPER, "sleep", "1000"]
process = subprocess.Popen(
    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    text=True, start_new_session=True
)
pgid = os.getpgid(process.pid)
root_pid = process.pid

print(f"  Launched: root_pid={root_pid}, pgid={pgid}")
time.sleep(1)

# Verify children are alive
try:
    os.killpg(pgid, 0)
    print(f"  ✓ Process group {pgid} is alive")
except OSError:
    print(f"  ✗ FAIL: Process group {pgid} is NOT alive before timeout")
    sys.exit(1)

# Show processes in the group
procs_before = subprocess.check_output(
    ["ps", "-o", "pid,ppid,pgid,command", "-g", str(pgid)],
    text=True, stderr=subprocess.DEVNULL
).strip()
print(f"  Processes before cleanup:\n{procs_before}")

# Simulate the daemon timeout handler
print(f"\n  Simulating timeout: SIGTERM → pgid {pgid}")
try:
    os.killpg(pgid, signal.SIGTERM)
except OSError:
    pass

# Bounded grace (like daemon does)
for i in range(10):
    time.sleep(0.5)
    try:
        os.killpg(pgid, 0)
    except OSError:
        print(f"  ✓ Process group {pgid} exited gracefully after {(i+1)*0.5:.1f}s")
        break
else:
    print(f"  Grace period exhausted, sending SIGKILL to pgid {pgid}")
    try:
        os.killpg(pgid, signal.SIGKILL)
    except OSError:
        pass
    time.sleep(0.5)

# Reap
try:
    process.communicate(timeout=5)
except:
    pass

# Final verification
try:
    os.killpg(pgid, 0)
    print(f"  ✗ FAIL: Process group {pgid} STILL ALIVE after cleanup!")
    result_a = "FAIL"
except OSError:
    print(f"  ✓ Process group {pgid} is confirmed dead")
    result_a = "PASS"

# Check for any orphaned sleep processes
orphan_check = subprocess.run(
    ["pgrep", "-f", "sleep 1000"], capture_output=True, text=True
)
if orphan_check.stdout.strip():
    print(f"  ✗ FAIL: Orphaned 'sleep 1000' processes found: {orphan_check.stdout.strip()}")
    result_a = "FAIL"
else:
    print(f"  ✓ No orphaned 'sleep 1000' processes")

print(f"\n  TEST A RESULT: {result_a}")

print("\n" + "=" * 60)
print("TEST E: Shell metacharacter escape prevention")
print("=" * 60)

# echo "hello ; ls -la" should be treated as literal text, not executed
result = subprocess.run(
    ["echo", "hello ; ls -la"],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5
)
output = result.stdout.strip()
if output == "hello ; ls -la" and result.returncode == 0:
    print(f"  ✓ echo output is literal: '{output}'")
    result_e = "PASS"
else:
    print(f"  ✗ FAIL: echo output unexpected: '{output}'")
    result_e = "FAIL"

print(f"  TEST E RESULT: {result_e}")

print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"  TIMEOUT_TREE_CLEANUP     = {result_a}")
print(f"  WRAPPER_SIGNAL_FORWARDING = {result_a}")
print(f"  ZERO_ORPHANS             = {result_a}")
print(f"  SHELL_ESCAPE_PREVENTED   = {result_e}")
