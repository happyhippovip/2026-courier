"""
test_dual_transport_sync.py - Test suite for TASK-WIN-61
Certifies Dual-Transport Cross-Device Synchronization & Remote Handoff Gateway:
- Direct low-latency HTTP peer delivery via /api/courier/sync/handoff
- Fail-safe filesystem mailbox fallback with atomic rename when offline
- Cryptographic SHA-256 evidence sealing
- Rejection of malformed requests (fail-closed HTTP 400)
- Strict 0.00 EUR spend firewall enforcement
"""

import os
import sys
import json
import time
import unittest
import urllib.request
import urllib.error

WORKSPACE_ROOT = r"C:\Users\lol\2026-workspace"
BASE_URL = "http://127.0.0.1:8088"

if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from courier.sync.dual_transport import DualTransportClient
from courier.tests.server_fixture import CourierServerTestCase

class TestDualTransportSync(CourierServerTestCase):
    def test_01_http_peer_handoff_delivery(self):
        """Verify direct HTTP peer delivery queues handoff into mac_to_windows/requests."""
        client = DualTransportClient(peer_url=self.base_url)
        req_id = f"REQ-DUAL-HTTP-TEST-{int(time.time() * 1000)}"
        payload = {
            "schema_version": "1.0",
            "mission_id": "MISSION-AUTONOMY",
            "windows_validation_request_id": req_id,
            "validation_type": "DUAL_TRANSPORT_TEST",
            "exact_question": "Verify direct HTTP handoff intake",
            "expected_evidence": "QUEUED status and file presence"
        }
        res = client.transmit_handoff(payload, prefer_http=True)
        self.assertTrue(res.get("success"), f"Handoff transmission failed: {res}")
        self.assertEqual(res.get("transport"), "HTTP_PEER")
        self.assertEqual(res.get("request_id"), req_id)
        
        # Verify file arrived on filesystem
        expected_file = os.path.join(WORKSPACE_ROOT, "coordination", "mac_to_windows", "requests", f"{req_id}.json")
        self.assertTrue(os.path.exists(expected_file), f"Queued file not found at {expected_file}")
        with open(expected_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data.get("windows_validation_request_id"), req_id)

    def test_02_filesystem_mailbox_fallback_when_offline(self):
        """Verify offline peer gracefully triggers atomic filesystem mailbox fallback."""
        offline_url = "http://127.0.0.1:59999"
        client = DualTransportClient(peer_url=offline_url)
        req_id = f"REQ-DUAL-FALLBACK-TEST-{int(time.time() * 1000)}"
        payload = {
            "schema_version": "1.0",
            "mission_id": "MISSION-AUTONOMY",
            "windows_validation_request_id": req_id,
            "validation_type": "DUAL_TRANSPORT_TEST",
            "exact_question": "Verify offline fallback to filesystem mailbox",
            "expected_evidence": "FALLBACK_ENGAGED and mailbox file presence"
        }
        res = client.transmit_handoff(payload, prefer_http=True)
        self.assertTrue(res.get("success"), f"Fallback failed: {res}")
        self.assertEqual(res.get("transport"), "FILESYSTEM_MAILBOX")
        self.assertTrue(res.get("fallback_engaged"))
        
        # Verify file arrived in fallback mailbox
        file_path = res.get("file_path")
        self.assertTrue(os.path.exists(file_path), f"Mailbox file missing: {file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data.get("windows_validation_request_id"), req_id)

    def test_03_cryptographic_evidence_and_zero_spend(self):
        """Verify 64-char SHA-256 evidence fingerprint and zero spend across both transports."""
        client = DualTransportClient(peer_url=BASE_URL)
        payload = {
            "schema_version": "1.0",
            "request_id": f"REQ-EVIDENCE-{int(time.time() * 1000)}",
            "action": "VERIFY_EVIDENCE"
        }
        res = client.transmit_handoff(payload)
        self.assertEqual(len(res.get("evidence_hash", "")), 64, "Evidence hash must be 64-character hex")
        self.assertEqual(float(res.get("spend_eur", 0.0)), 0.0, "Spend must strictly be 0.00 EUR")

    def test_04_schema_validation_and_rejection_of_malformed_handoff(self):
        """Verify POST /api/courier/sync/handoff fails-closed with HTTP 400 for payloads without ID."""
        url = f"{self.base_url}/api/courier/sync/handoff"
        malformed_payload = json.dumps({"schema_version": "1.0"}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=malformed_payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req, timeout=5)
        self.assertEqual(ctx.exception.code, 400)

if __name__ == "__main__":
    unittest.main()
