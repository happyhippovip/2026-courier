"""
test_closure_gate.py - Test suite for TASK-WIN-63
Certifies Autonomous Two-Level Done Verification & Multi-Host Closure Gate:
- Level 1 pass + remote pending (local_step_erledigt=True, gesamtaufgabe_erledigt=False, blocker=PEER_SYNC_PENDING)
- Level 1 + Level 2 complete (local_step_erledigt=True, gesamtaufgabe_erledigt=True, blocker=NONE, signed receipt)
- Human Gate Isolation (requires_human_gate=True, blocker=HUMAN_GATE_APPROVAL_REQUIRED, local progress preserved)
- Spend Firewall Strict Enforcement (spend_eur > 0.00 rejected with zero proof debt)
- HTTP closure evaluation and receipt retrieval (/api/courier/closure/evaluate & /api/courier/closure/receipt/:id)
- CLI stdin/stdout runner (courier.chief.closure_evaluator)
"""

import os
import sys
import json
import time
import hashlib
import unittest
import subprocess
import urllib.request
import urllib.error

WORKSPACE_ROOT = r"C:\Users\lol\2026-workspace"
BASE_URL = "http://127.0.0.1:8088"

if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from courier.chief.closure_gate import TwoLevelClosureGate
from courier.chief.control_plane import ControlPlane

class TestClosureGate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gate = TwoLevelClosureGate(workspace_root=WORKSPACE_ROOT)
        cls.cp = ControlPlane()

    @classmethod
    def tearDownClass(cls):
        with cls.cp.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM tasks WHERE task_id LIKE ?", ("TEST-%",))
            cur.execute("DELETE FROM checkpoints WHERE checkpoint_key LIKE ?", ("CLOSURE_RECEIPT_TEST-%",))
            conn.commit()

    def test_01_level1_pass_level2_peer_pending(self):
        """Local step passes but remote sync is pending: local done, overall open."""
        task_id = f"TEST-CG-01-{int(time.time() * 1000)}"
        evidence = {
            "returncode": 0,
            "success": True,
            "stdout": "Local step executed perfectly."
        }
        res = self.gate.evaluate_task_closure(
            task_id=task_id,
            execution_evidence=evidence,
            remote_peer_synced=False,
            requires_human_gate=False,
            spend_eur=0.00
        )
        self.assertTrue(res["success"])
        self.assertTrue(res["two_level_done"]["local_step_erledigt"])
        self.assertFalse(res["two_level_done"]["gesamtaufgabe_erledigt"])
        self.assertEqual(res["two_level_done"]["blocker"], "PEER_SYNC_PENDING")
        self.assertEqual(res["two_level_done"]["next_step"], "TRANSMIT_TO_PEER")
        self.assertIsNotNone(res["receipt"])
        self.assertEqual(res["receipt"]["spend_eur"], 0.00)
        self.assertTrue(os.path.exists(res["receipt_path"]))

    def test_02_level1_and_level2_complete(self):
        """Both local execution and remote sync succeed: both levels done."""
        task_id = f"TEST-CG-02-{int(time.time() * 1000)}"
        evidence = {
            "returncode": 0,
            "success": True,
            "stdout": "Local build complete and verified."
        }
        res = self.gate.evaluate_task_closure(
            task_id=task_id,
            execution_evidence=evidence,
            remote_peer_synced=True,
            requires_human_gate=False,
            spend_eur=0.00
        )
        self.assertTrue(res["success"])
        self.assertTrue(res["two_level_done"]["local_step_erledigt"])
        self.assertTrue(res["two_level_done"]["gesamtaufgabe_erledigt"])
        self.assertEqual(res["two_level_done"]["blocker"], "NONE")
        self.assertEqual(res["two_level_done"]["next_step"], "TASK_FULLY_CLOSED")
        
        # Verify receipt signature
        receipt = res["receipt"]
        expected_content = f"{receipt['receipt_id']}:{task_id}:True:True:NONE:0.0:{receipt['timestamp_utc']}"
        expected_sig = hashlib.sha256(expected_content.encode("utf-8")).hexdigest()
        self.assertEqual(receipt["signature_sha256"], expected_sig)

    def test_03_human_gate_isolation(self):
        """Human gate required: local progress completes, Level 2 safely paused without aborting."""
        task_id = f"TEST-CG-03-{int(time.time() * 1000)}"
        evidence = {
            "returncode": 0,
            "success": True,
            "stdout": "Candidate ready for production deployment."
        }
        res = self.gate.evaluate_task_closure(
            task_id=task_id,
            execution_evidence=evidence,
            remote_peer_synced=True,
            requires_human_gate=True,
            spend_eur=0.00
        )
        self.assertTrue(res["success"])
        self.assertTrue(res["two_level_done"]["local_step_erledigt"])
        self.assertFalse(res["two_level_done"]["gesamtaufgabe_erledigt"])
        self.assertEqual(res["two_level_done"]["blocker"], "HUMAN_GATE_APPROVAL_REQUIRED")
        self.assertEqual(res["two_level_done"]["next_step"], "WAIT_FOR_HUMAN_GATE")

    def test_04_spend_firewall_rejection(self):
        """Spend greater than 0.00 EUR is immediately rejected by the firewall."""
        task_id = f"TEST-CG-04-{int(time.time() * 1000)}"
        res = self.gate.evaluate_task_closure(
            task_id=task_id,
            execution_evidence={"returncode": 0, "success": True},
            remote_peer_synced=True,
            requires_human_gate=False,
            spend_eur=0.50
        )
        self.assertFalse(res["success"])
        self.assertEqual(res["decision"], "REJECTED_SPEND_VIOLATION")
        self.assertFalse(res["two_level_done"]["local_step_erledigt"])
        self.assertFalse(res["two_level_done"]["gesamtaufgabe_erledigt"])
        self.assertEqual(res["two_level_done"]["blocker"], "SPEND_FIREWALL_VIOLATION")
        self.assertIsNone(res["receipt"])

    def test_05_closure_evaluator_cli_pipe(self):
        """CLI runner accepts stdin JSON and outputs structured closure report."""
        task_id = f"TEST-CG-05-{int(time.time() * 1000)}"
        payload = {
            "task_id": task_id,
            "execution_evidence": {"returncode": 0, "success": True, "stdout": "CLI test run"},
            "remote_peer_synced": True,
            "requires_human_gate": False,
            "spend_eur": 0.00
        }
        proc = subprocess.run(
            ["uv", "run", "python", "-m", "courier.chief.closure_evaluator"],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            cwd=WORKSPACE_ROOT
        )
        self.assertEqual(proc.returncode, 0, f"Stderr: {proc.stderr}")
        data = json.loads(proc.stdout)
        self.assertTrue(data["success"])
        self.assertEqual(data["task_id"], task_id)
        self.assertTrue(data["two_level_done"]["gesamtaufgabe_erledigt"])

    def test_06_http_closure_api_and_receipt_retrieval(self):
        """Studio REST API POST /api/courier/closure/evaluate and GET /api/courier/closure/receipt/:id."""
        task_id = f"TEST-CG-06-{int(time.time() * 1000)}"
        payload = {
            "task_id": task_id,
            "execution_evidence": {"returncode": 0, "success": True, "stdout": "HTTP test run"},
            "remote_peer_synced": True,
            "requires_human_gate": False,
            "spend_eur": 0.00
        }
        req = urllib.request.Request(
            f"{BASE_URL}/api/courier/closure/evaluate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                self.assertEqual(resp.status, 200)
                eval_data = json.loads(resp.read().decode("utf-8"))
                self.assertTrue(eval_data["success"])
                receipt_id = eval_data["receipt_id"]
                sig = eval_data["signature_sha256"]
        except urllib.error.URLError as e:
            self.skipTest(f"Studio server not reachable: {e}")
            return

        # Fetch receipt via GET /api/courier/closure/receipt/:id
        get_req = urllib.request.Request(f"{BASE_URL}/api/courier/closure/receipt/{receipt_id}", method="GET")
        with urllib.request.urlopen(get_req, timeout=10) as resp:
            self.assertEqual(resp.status, 200)
            receipt_data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(receipt_data["receipt_id"], receipt_id)
            self.assertEqual(receipt_data["signature_sha256"], sig)
            self.assertEqual(receipt_data["spend_eur"], 0.00)

if __name__ == "__main__":
    unittest.main()
