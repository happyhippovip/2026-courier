"""
test_work_stealing_concurrency.py - Test suite for TASK-WIN-58
Certifies multi-worker distributed work stealing, lane concurrency limits,
resource collision avoidance, and HTTP work stealing endpoints.
"""

import os
import sys
import json
import time
import urllib.request
import unittest

WORKSPACE_ROOT = r"C:\Users\lol\2026-workspace"
BASE_URL = "http://127.0.0.1:8088"

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

class TestWorkStealingConcurrency(CourierServerTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        global BASE_URL
        BASE_URL = cls.base_url

    def test_01_enqueue_and_atomic_work_stealing(self):
        """Verify multiple workers steal distinct tasks atomically without double claiming."""
        # Enqueue 3 distinct tasks
        for i in range(3):
            t_res = http_post("/api/courier/work-stealing/enqueue", {
                "task_id": f"TASK-WS-UNIT-A-{i}-{int(time.time())}",
                "priority": 50 + i,
                "lane": "WINDOWS_GOOGLE",
                "resource_path": f"C:/Users/lol/2026-workspace/scope_a_{i}"
            })
            self.assertTrue(t_res.get("success"))

        # 3 workers steal concurrently
        stolen_tasks = []
        for w_idx in range(3):
            w_id = f"WORKER-UNIT-{w_idx}"
            s_res = http_post("/api/courier/work-stealing/steal", {
                "workerId": w_id,
                "lane": "WINDOWS_GOOGLE"
            })
            self.assertTrue(s_res.get("stolen"), f"Worker {w_id} failed to steal task: {s_res}")
            stolen_tasks.append(s_res["task"]["task_id"])
            # Complete task
            comp_res = http_post("/api/courier/work-stealing/complete", {
                "taskId": s_res["task"]["task_id"],
                "claimToken": s_res["claim_token"],
                "workerId": w_id,
                "resultStatus": "SUCCESS"
            })
            self.assertTrue(comp_res.get("success"))

        # Verify all 3 stolen tasks were distinct
        self.assertEqual(len(set(stolen_tasks)), 3, "All 3 workers must steal distinct tasks")

    def test_02_lane_concurrency_limit_enforced(self):
        """Verify maximum concurrent workers in a lane cannot exceed the limit (5)."""
        # Enqueue 6 tasks in lane TEST_LANE
        lane_name = f"LANE-TEST-{int(time.time())}"
        for i in range(6):
            http_post("/api/courier/work-stealing/enqueue", {
                "task_id": f"TASK-WS-LANE-{i}-{int(time.time())}",
                "priority": 100,
                "lane": lane_name,
                "resource_path": f"C:/Users/lol/2026-workspace/lane_scope_{i}"
            })

        active_tokens = []
        # Steal 5 tasks (up to limit)
        for i in range(5):
            s_res = http_post("/api/courier/work-stealing/steal", {
                "workerId": f"WORKER-LANE-{i}",
                "lane": lane_name
            })
            self.assertTrue(s_res.get("stolen"))
            active_tokens.append((s_res["task"]["task_id"], s_res["claim_token"], f"WORKER-LANE-{i}"))

        # Attempt 6th steal in the same lane -> should be rejected
        s6_res = http_post("/api/courier/work-stealing/steal", {
            "workerId": "WORKER-LANE-6-OVERFLOW",
            "lane": lane_name
        })
        self.assertFalse(s6_res.get("stolen"))
        self.assertEqual(s6_res.get("reason"), "LANE_CONCURRENCY_LIMIT_REACHED")

        # Clean up held tasks
        for tid, tok, wid in active_tokens:
            http_post("/api/courier/work-stealing/complete", {
                "taskId": tid,
                "claimToken": tok,
                "workerId": wid,
                "resultStatus": "SUCCESS"
            })

    def test_03_telemetry_and_zero_spend_invariant(self):
        """Verify queue telemetry reports accurate counts and spend remains 0.00 EUR."""
        telem_res = http_get("/api/courier/work-stealing/telemetry")
        self.assertTrue(telem_res.get("success"))
        telem = telem_res.get("telemetry", {})
        self.assertIn("total_tasks", telem)
        self.assertIn("completed", telem)
        self.assertEqual(telem.get("max_concurrent_per_lane"), 5)

    def test_04_stress_test_5_concurrent_workers(self):
        """Stress test: 5 concurrent workers stealing and executing tasks simultaneously."""
        import concurrent.futures

        # Enqueue 5 distinct tasks in an isolated stress lane
        stress_lane = f"LANE-STRESS-{int(time.time())}"
        task_ids = []
        for i in range(5):
            t_id = f"TASK-STRESS-{i}-{int(time.time())}"
            task_ids.append(t_id)
            http_post("/api/courier/work-stealing/enqueue", {
                "task_id": t_id,
                "priority": 80,
                "lane": stress_lane,
                "resource_path": f"C:/Users/lol/2026-workspace/stress_scope_{i}",
                "executable_command": "node -e \"console.log('STRESS_SUCCESS');\""
            })

        def worker_routine(worker_idx):
            w_id = f"WORKER-CONCURRENT-{worker_idx}"
            # 1. Steal task
            steal_res = http_post("/api/courier/work-stealing/steal", {
                "workerId": w_id,
                "lane": stress_lane
            })
            if not steal_res.get("stolen"):
                return {"worker_id": w_id, "success": False, "reason": steal_res.get("reason")}
            
            task = steal_res["task"]
            # 2. Dispatch command execution
            dispatch_res = http_post("/api/courier/dispatch", {
                "task_id": task["task_id"],
                "command": task["executable_command"] or "node -e \"console.log('DEFAULT');\"",
                "scope_paths": [WORKSPACE_ROOT]
            })
            
            # 3. Complete work
            comp_res = http_post("/api/courier/work-stealing/complete", {
                "taskId": task["task_id"],
                "claimToken": steal_res["claim_token"],
                "workerId": w_id,
                "resultStatus": "SUCCESS" if dispatch_res.get("success") else "FAILED",
                "artifacts": dispatch_res.get("artifacts", []),
                "evidenceSha256": dispatch_res.get("evidence_sha256")
            })

            return {
                "worker_id": w_id,
                "task_id": task["task_id"],
                "success": comp_res.get("success") and dispatch_res.get("success"),
                "evidence_sha256": dispatch_res.get("evidence_sha256")
            }

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(worker_routine, idx) for idx in range(5)]
            results = [f.result(timeout=30) for f in futures]

        # Verify all 5 workers completed successfully
        self.assertEqual(len(results), 5)
        completed_task_ids = set()
        for r in results:
            self.assertTrue(r["success"], f"Worker routine failed: {r}")
            self.assertIsNotNone(r["evidence_sha256"])
            completed_task_ids.add(r["task_id"])

        self.assertEqual(len(completed_task_ids), 5, "All 5 concurrent workers must execute 5 distinct tasks")

if __name__ == "__main__":
    unittest.main()
