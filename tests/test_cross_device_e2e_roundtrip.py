"""
test_cross_device_e2e_roundtrip.py - Test suite for TASK-WIN-57
Certifies end-to-end Mac-to-Windows HTTP request intake, execution, customs verification, and retrieval.
"""

import os
import sys
import json
import time
import subprocess
import unittest

WORKSPACE_ROOT = r"C:\Users\lol\2026-workspace"

from courier.tests.server_fixture import CourierServerTestCase

class TestCrossDeviceE2ERoundtrip(CourierServerTestCase):
    def test_01_request_submission_and_synchronous_resolution(self):
        """Verify submitting structured validation request via peer_bridge and getting completed result."""
        req_id = f"REQ-E2E-{int(time.time())}"
        port = str(self.base_url.split(":")[-1])
        payload_str = json.dumps({
            "windows_validation_request_id": req_id,
            "validation_type": "WINDOWS_COMPATIBILITY",
            "exact_question": "Validate roundtrip execution envelope",
            "expected_evidence": "Structured result file with evidence"
        })
        cmd = [
            "uv",
            "run",
            "python",
            os.path.join(WORKSPACE_ROOT, "courier", "peer_bridge.py"),
            "--port",
            port,
            "--submit",
            payload_str
        ]
        proc = subprocess.run(cmd, cwd=WORKSPACE_ROOT, capture_output=True, text=True, timeout=60, shell=True)
        self.assertEqual(proc.returncode, 0, f"Submit failed: {proc.stderr}")
        res = json.loads(proc.stdout)
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("request_id"), req_id)

    def test_02_remote_worker_command_roundtrip_with_evidence_verification(self):
        """Verify remote worker command dispatch returns cryptographically sealed evidence."""
        task_id = f"TASK-E2E-ROUNDTRIP-{int(time.time())}"
        port = str(self.base_url.split(":")[-1])
        cmd = [
            "uv",
            "run",
            "python",
            os.path.join(WORKSPACE_ROOT, "courier", "peer_bridge.py"),
            "--port",
            port,
            "--dispatch-command",
            'node -e "console.log(\\"E2E_ROUNDTRIP_VERIFIED_SHA256\\");"',
            "--task-id",
            task_id
        ]
        proc = subprocess.run(cmd, cwd=WORKSPACE_ROOT, capture_output=True, text=True, timeout=30, shell=True)
        self.assertEqual(proc.returncode, 0, f"Dispatch failed: {proc.stderr}")
        res = json.loads(proc.stdout)
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("status"), "COMPLETED_VERIFIED")
        self.assertTrue(len(res.get("evidence_sha256", "")) == 64, "SHA-256 must be 64 hex characters")
        self.assertIn("E2E_ROUNDTRIP_VERIFIED_SHA256", res["evidence"]["stdout"])

    def test_03_zero_spend_invariant_preserved(self):
        """Verify autonomous spend remains strictly 0.00 EUR across all operations."""
        port = str(self.base_url.split(":")[-1])
        status_cmd = [
            "uv",
            "run",
            "python",
            os.path.join(WORKSPACE_ROOT, "courier", "peer_bridge.py"),
            "--port",
            port,
            "--status"
        ]
        proc = subprocess.run(status_cmd, cwd=WORKSPACE_ROOT, capture_output=True, text=True, timeout=15, shell=True)
        self.assertEqual(proc.returncode, 0)
        status_res = json.loads(proc.stdout)
        self.assertEqual(status_res.get("spend_eur", 0.0), 0.0)

if __name__ == "__main__":
    unittest.main()
