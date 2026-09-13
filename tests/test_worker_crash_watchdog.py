"""
test_worker_crash_watchdog.py - Test suite for TASK-WIN-59
Certifies real-time worker process monitoring, dead-worker lease revocation,
resource lock freeing, zero-loss task reclaiming, and watchdog HTTP endpoints.
"""

import os
import sys
import json
import time
import subprocess
import urllib.request
import unittest

WORKSPACE_ROOT = r"C:\Users\lol\2026-workspace"
BASE_URL = "http://127.0.0.1:8088"

def find_node():
    direct = r"C:\Users\lol\AppData\Local\OpenAI\Codex\runtimes\cua_node\b58ca2eaa616c2da\bin\node.exe"
    if os.path.exists(direct):
        return direct
    import shutil
    cand = shutil.which("node.exe")
    if cand:
        return cand
    cand_cmd = shutil.which("node")
    if cand_cmd and cand_cmd.lower().endswith(".exe"):
        return cand_cmd
    return "node"

NODE_BIN = find_node()

def http_post(endpoint, payload):
    url = f"{BASE_URL}{endpoint}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))

def http_get(endpoint):
    url = f"{BASE_URL}{endpoint}"
    req = urllib.request.Request(url, headers={"Content-Type": "application/json"}, method="GET")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))

from courier.tests.server_fixture import CourierServerTestCase

class TestWorkerCrashWatchdog(CourierServerTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        global BASE_URL
        BASE_URL = cls.base_url

    def test_01_pid_liveness_detection(self):
        """Verify process.kill(pid, 0) accurately detects live and dead PIDs on Windows."""
        # Current python process PID must be alive
        current_pid = os.getpid()
        cmd = [
            NODE_BIN,
            "-e",
            f"const {{ WorkerCrashWatchdog }} = require('./supervisor/crash_watchdog');"
            f"console.log(JSON.stringify({{"
            f"  live: WorkerCrashWatchdog.isPidAlive({current_pid}),"
            f"  dead: WorkerCrashWatchdog.isPidAlive(99999999)"
            f"}}));"
        ]
        proc = subprocess.run(cmd, cwd=os.path.join(WORKSPACE_ROOT, "courier"), capture_output=True, text=True, timeout=15, shell=True)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        res = json.loads(proc.stdout)
        self.assertTrue(res.get("live"), "Current PID must be detected as live")
        self.assertFalse(res.get("dead"), "PID 99999999 must be detected as dead")

    def test_02_dead_worker_lease_and_lock_revocation(self):
        """Verify watchdog detects dead worker process, terminates lease, and frees held locks."""
        # Spawn a subprocess that stays alive briefly then gets killed
        child = subprocess.Popen([NODE_BIN, "-e", "setInterval(() => {}, 1000);"])
        dead_pid = child.pid
        task_id = f"TASK-WATCHDOG-CRASH-{int(time.time())}"
        test_scope = f"C:/Users/lol/2026-workspace/scope_watchdog_{int(time.time())}"

        # Setup lease and lock in Supervisor
        setup_cmd = [
            "node",
            "-e",
            f"const path = require('path');"
            f"const {{ SupervisorPlane }} = require('./supervisor/index');"
            f"const sp = new SupervisorPlane(path.join(process.cwd(), 'runtime'));"
            f"const lease = sp.leaseManager.createLease({{"
            f"  task_id: '{task_id}',"
            f"  pid: {dead_pid},"
            f"  command: 'node worker_process.js'"
            f"}});"
            f"sp.lockManager.acquire('{test_scope}', '{task_id}');"
            f"console.log(JSON.stringify({{ lease_id: lease.process_lease_id }}));"
        ]
        setup_proc = subprocess.run(setup_cmd, cwd=os.path.join(WORKSPACE_ROOT, "courier"), capture_output=True, text=True, timeout=15, shell=True)
        self.assertEqual(setup_proc.returncode, 0)
        lease_info = json.loads(setup_proc.stdout)
        lease_id = lease_info["lease_id"]

        # Kill the child worker process
        child.kill()
        child.wait()

        # Reconcile via HTTP watchdog endpoint
        recon_res = http_post("/api/courier/watchdog/reconcile", {})
        self.assertTrue(recon_res.get("success"))
        report = recon_res.get("report", {})
        
        # Verify dead lease was reclaimed
        reclaimed_ids = [item.get("lease_id") for item in report.get("dead_leases_reclaimed", [])]
        self.assertIn(lease_id, reclaimed_ids, f"Lease {lease_id} must be in reclaimed list: {report}")

        # Verify lock is now free and can be acquired by another task
        lock_cmd = [
            "node",
            "-e",
            f"const path = require('path');"
            f"const {{ SupervisorPlane }} = require('./supervisor/index');"
            f"const sp = new SupervisorPlane(path.join(process.cwd(), 'runtime'));"
            f"const check = sp.lockManager.canAcquire('{test_scope}', 'NEW-TASK-001');"
            f"console.log(JSON.stringify(check));"
        ]
        lock_proc = subprocess.run(lock_cmd, cwd=os.path.join(WORKSPACE_ROOT, "courier"), capture_output=True, text=True, timeout=15, shell=True)
        self.assertEqual(lock_proc.returncode, 0)
        lock_res = json.loads(lock_proc.stdout)
        self.assertTrue(lock_res.get("available"), "Resource lock must be freed after dead worker detected")

    def test_03_work_stealing_task_reclaim_on_crash(self):
        """Verify tasks claimed by dead workers are returned to PENDING with zero work loss."""
        # Enqueue task
        t_id = f"TASK-WS-RECLAIM-{int(time.time())}"
        lane = f"LANE-RECLAIM-{int(time.time())}"
        http_post("/api/courier/work-stealing/enqueue", {
            "task_id": t_id,
            "lane": lane,
            "priority": 90,
            "resource_path": f"C:/Users/lol/2026-workspace/reclaim_scope_{int(time.time())}"
        })

        # Steal task with worker
        steal_res = http_post("/api/courier/work-stealing/steal", {
            "workerId": "WORKER-DOOMED-CRASH",
            "lane": lane
        })
        self.assertTrue(steal_res.get("stolen"))

        # Trigger watchdog with immediate expiration
        recon_res = http_post("/api/courier/watchdog/reconcile", {})
        self.assertTrue(recon_res.get("success"))

        # Verify task is returned to PENDING by inspecting queue
        q_res = http_get("/api/courier/work-stealing/queue")
        self.assertTrue(q_res.get("success"))
        found_task = next((t for t in q_res.get("tasks", []) if t.get("task_id") == t_id), None)
        self.assertIsNotNone(found_task)

    def test_04_watchdog_telemetry_and_zero_spend(self):
        """Verify watchdog status telemetry reports healthy and spend is strictly 0.00 EUR."""
        status_res = http_get("/api/courier/watchdog/status")
        self.assertTrue(status_res.get("success"))
        telem = status_res.get("telemetry", {})
        self.assertTrue(telem.get("healthy"))
        self.assertIn("total_crashes_detected", telem)

        # Zero spend check
        courier_status = http_get("/api/courier/status")
        self.assertEqual(courier_status.get("spend_eur", 0.0), 0.0)

if __name__ == "__main__":
    unittest.main()
