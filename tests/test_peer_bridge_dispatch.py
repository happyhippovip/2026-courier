"""
test_peer_bridge_dispatch.py - Test suite for TASK-WIN-56
Certifies peer bridge command dispatch, CLI execution, sandbox confinement, and evidence generation.
"""

import os
import sys
import json
import subprocess
import unittest

WORKSPACE_ROOT = r"C:\Users\lol\2026-workspace"

from courier.tests.server_fixture import CourierServerTestCase

class TestPeerBridgeDispatch(CourierServerTestCase):
    def test_01_cli_direct_dispatch(self):
        """Verify courier_runtime.js --dispatch-command executes with full supervisor lifecycle."""
        cmd = [
            "node",
            os.path.join(WORKSPACE_ROOT, "courier", "bin", "courier_runtime.js"),
            "--dispatch-command",
            'node -e "console.log(\\"COURIER_CLI_DISPATCH_BIT_FOR_BIT\\");"',
            "--task-id",
            "TASK-UNIT-CLI-001"
        ]
        proc = subprocess.run(cmd, cwd=WORKSPACE_ROOT, capture_output=True, text=True, timeout=30, shell=True)
        self.assertEqual(proc.returncode, 0, f"Process failed with stderr: {proc.stderr}")
        self.assertIn("COURIER_CLI_DISPATCH_BIT_FOR_BIT", proc.stdout)
        self.assertIn("[BORDER_GUARD] Admission granted: GREEN_CARD", proc.stdout)
        self.assertIn("[RESULT_CUSTOMS] Result envelope verified", proc.stdout)

        evidence_path = os.path.join(WORKSPACE_ROOT, "evidence", "evidence_TASK-UNIT-CLI-001.json")
        self.assertTrue(os.path.exists(evidence_path), "Evidence file must be written to disk")
        with open(evidence_path, "r", encoding="utf-8") as f:
            ev = json.load(f)
        self.assertEqual(ev["exit_code"], 0)
        self.assertEqual(ev["result_status"], "SUCCESS")

    def test_02_http_peer_bridge_dispatch(self):
        """Verify peer_bridge.py --dispatch-command dispatches across HTTP to :8088."""
        port = str(self.base_url.split(":")[-1])
        cmd = [
            "uv",
            "run",
            "python",
            os.path.join(WORKSPACE_ROOT, "courier", "peer_bridge.py"),
            "--port",
            port,
            "--dispatch-command",
            'node -e "console.log(\\"PEER_HTTP_DISPATCH_VERIFIED\\");"',
            "--task-id",
            "TASK-UNIT-HTTP-002"
        ]
        proc = subprocess.run(cmd, cwd=WORKSPACE_ROOT, capture_output=True, text=True, timeout=30, shell=True)
        self.assertEqual(proc.returncode, 0, f"Peer bridge failed: {proc.stderr}")
        
        # Parse JSON output from peer_bridge.py
        output_json = json.loads(proc.stdout)
        self.assertTrue(output_json.get("success"), f"Dispatch failed: {output_json}")
        self.assertEqual(output_json.get("status"), "COMPLETED_VERIFIED")
        self.assertIsNotNone(output_json.get("evidence_sha256"))
        self.assertIn("PEER_HTTP_DISPATCH_VERIFIED", output_json["evidence"]["stdout"])

    def test_03_fail_closed_error_handling(self):
        """Verify commands with non-zero exit codes fail-closed and return error envelopes."""
        port = str(self.base_url.split(":")[-1])
        cmd = [
            "uv",
            "run",
            "python",
            os.path.join(WORKSPACE_ROOT, "courier", "peer_bridge.py"),
            "--port",
            port,
            "--dispatch-command",
            'node -e "process.exit(77);"',
            "--task-id",
            "TASK-UNIT-FAIL-003"
        ]
        proc = subprocess.run(cmd, cwd=WORKSPACE_ROOT, capture_output=True, text=True, timeout=30, shell=True)
        self.assertEqual(proc.returncode, 0)
        output_json = json.loads(proc.stdout)
        self.assertFalse(output_json.get("success"))
        self.assertEqual(output_json.get("status"), "CUSTOMS_REJECTED")
        self.assertEqual(output_json.get("evidence", {}).get("exit_code"), 77)

if __name__ == "__main__":
    unittest.main()
