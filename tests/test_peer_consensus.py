"""
test_peer_consensus.py - Test Suite for TASK-WIN-66: Cross-Host Autonomous Peer Consensus & Handoff Inbox Ingestion
Certifies:
1. Valid inbound request ingestion, atomic fenced claim, and two-level closure sealing
2. Corrupted & malformed request quarantine and archive isolation
3. Strict idempotency & duplicate suppression (TASKS_DUPLICATED = 0)
4. Border Guard Mac-reserved scope defense
5. Fenced Mutex split-brain preemption
6. Zero Spend Firewall enforcement (0.00 EUR)
7. Handoff candidate metadata synchronization
"""

import os
import sys
import json
import time
import shutil
import unittest

WORKSPACE_ROOT = r"C:\Users\lol\2026-workspace"
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from courier.chief.control_plane import ControlPlane
from courier.chief.fenced_mutex import FencedMutexManager
from courier.chief.peer_consensus import PeerConsensusEngine, MAC_RESERVED_SCOPES

class TestPeerConsensus(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workspace_root = WORKSPACE_ROOT
        cls.cp = ControlPlane()
        cls.engine = PeerConsensusEngine(cp=cls.cp, workspace_root=cls.workspace_root)
        cls.inbox = cls.engine.inbox_dir
        cls.archive = cls.engine.archive_dir
        cls.claims = cls.engine.claims_dir
        cls.results = cls.engine.results_dir
        cls.receipts = cls.engine.receipts_dir

    def test_01_valid_inbound_request_ingestion_and_fenced_claim(self):
        """Verify valid request is ingested, claimed with epoch token, executed, sealed, and archived."""
        req_id = f"REQ-TEST-CONSENSUS-{int(time.time() * 1000)}"
        req_data = {
            "schema_version": "1.0",
            "mission_id": "MISSION-AUTONOMY",
            "windows_validation_request_id": req_id,
            "assignment_id": f"ASSIGN-{req_id}",
            "target_runner": "WINDOWS",
            "validation_type": "WINDOWS_COMPATIBILITY",
            "artifact": "project-memory/data/autonomy_cycle_state.json",
            "artifact_reference": "project-memory/data/autonomy_cycle_state.json",
            "exact_question": "Validate peer consensus ingestion pipeline",
            "expected_evidence": "Process execution and closure receipt",
            "allowed_scope": "C:\\Users\\lol\\2026-workspace",
            "created_by": "MAC_CHIEF",
            "timestamp_utc": "2026-09-13T04:20:00Z",
            "host_os": "WINDOWS"
        }
        req_path = os.path.join(self.inbox, f"REQUEST_{req_id}.json")
        with open(req_path, "w", encoding="utf-8") as f:
            json.dump(req_data, f, indent=2)

        # Run reconciliation
        res = self.engine.reconcile_peer_inbox()
        self.assertEqual(res["status"], "PASS")
        self.assertGreaterEqual(res["processed_count"], 1)

        # Check claim file was generated with epoch token
        claim_file = os.path.join(self.claims, f"{req_id}.json")
        self.assertTrue(os.path.exists(claim_file), "Claim file must exist")
        with open(claim_file, "r", encoding="utf-8") as f:
            claim_data = json.load(f)
        self.assertEqual(claim_data.get("claim_state"), "CLAIMED")
        self.assertIn("fencing_epoch", claim_data)
        self.assertIn("fencing_token", claim_data)

        # Check result file was written
        result_file = os.path.join(self.results, f"{req_id}.json")
        self.assertTrue(os.path.exists(result_file), "Result file must exist")
        with open(result_file, "r", encoding="utf-8") as f:
            result_data = json.load(f)
        self.assertEqual(result_data.get("status"), "PASS")
        self.assertEqual(result_data.get("decision"), "ACCEPTED_VERIFIED")
        self.assertIn("receipt_id", result_data)

        # Check receipt file was generated
        receipt_id = result_data["receipt_id"]
        receipt_file = os.path.join(self.receipts, f"{receipt_id}.json")
        self.assertTrue(os.path.exists(receipt_file), "Closure receipt must exist")

        # Check request file was moved to archive
        self.assertFalse(os.path.exists(req_path), "Inbound request must be archived")
        archived_file = os.path.join(self.archive, f"REQUEST_{req_id}.json")
        self.assertTrue(os.path.exists(archived_file), "Archived request must exist in archive dir")

    def test_02_corrupted_and_malformed_request_quarantine(self):
        """Verify invalid/corrupted payloads are quarantined and archived without crashing."""
        malformed_id = f"REQ-TEST-MALFORMED-{int(time.time() * 1000)}"
        schema_fail_id = f"REQ-TEST-SCHEMAFAIL-{int(time.time() * 1000)}"

        # File 1: Completely invalid JSON
        f1_path = os.path.join(self.inbox, f"REQUEST_{malformed_id}.json")
        with open(f1_path, "w", encoding="utf-8") as f:
            f.write("{{{ NOT VALID JSON :::")

        # File 2: JSON missing required schema fields
        f2_path = os.path.join(self.inbox, f"REQUEST_{schema_fail_id}.json")
        with open(f2_path, "w", encoding="utf-8") as f:
            json.dump({"random_key": "unrecognized_value"}, f)

        res = self.engine.reconcile_peer_inbox()
        self.assertEqual(res["status"], "PASS")
        self.assertGreaterEqual(res["rejected_count"], 2)

        # Both files must have been removed from inbox
        self.assertFalse(os.path.exists(f1_path))
        self.assertFalse(os.path.exists(f2_path))

        # Rejection results must be logged
        res2_file = os.path.join(self.results, f"{schema_fail_id}.json")
        self.assertTrue(os.path.exists(res2_file))
        with open(res2_file, "r", encoding="utf-8") as f:
            res_data = json.load(f)
        self.assertEqual(res_data.get("status"), "REJECTED")

    def test_03_strict_idempotency_and_duplicate_suppression(self):
        """Verify duplicate requests or repeated 'weiter' signals never repeat completed work."""
        req_id = f"REQ-TEST-IDEMPOTENT-{int(time.time() * 1000)}"
        req_data = {
            "schema_version": "1.0",
            "mission_id": "MISSION-AUTONOMY",
            "windows_validation_request_id": req_id,
            "assignment_id": f"ASSIGN-{req_id}",
            "target_runner": "WINDOWS",
            "validation_type": "WINDOWS_COMPATIBILITY",
            "artifact": "project-memory/data/autonomy_cycle_state.json",
            "artifact_reference": "project-memory/data/autonomy_cycle_state.json",
            "exact_question": "Validate idempotency suppression",
            "expected_evidence": "Strict single execution",
            "allowed_scope": "C:\\Users\\lol\\2026-workspace",
            "created_by": "MAC_CHIEF",
            "timestamp_utc": "2026-09-13T04:20:00Z",
            "host_os": "WINDOWS"
        }
        # First execution
        req_path = os.path.join(self.inbox, f"REQUEST_{req_id}.json")
        with open(req_path, "w", encoding="utf-8") as f:
            json.dump(req_data, f, indent=2)

        res1 = self.engine.reconcile_peer_inbox()
        self.assertEqual(res1["status"], "PASS")
        self.assertIn(req_id, [p.get("windows_validation_request_id") for p in res1["processed"]])

        # Simulate 5 duplicate replays of the exact same request
        for i in range(5):
            dup_path = os.path.join(self.inbox, f"REQUEST_{req_id}_dup{i}.json")
            with open(dup_path, "w", encoding="utf-8") as f:
                json.dump(req_data, f, indent=2)

        res2 = self.engine.reconcile_peer_inbox()
        self.assertEqual(res2["status"], "PASS")
        self.assertEqual(res2["processed_count"], 0, "No duplicate tasks should be executed")
        self.assertGreaterEqual(res2["deduplicated_count"], 5, "All duplicates must be suppressed")

    def test_04_border_guard_mac_scope_protection(self):
        """Verify attempts to target Mac-reserved scopes are rejected immediately."""
        req_id = f"REQ-TEST-BORDERGUARD-{int(time.time() * 1000)}"
        req_data = {
            "schema_version": "1.0",
            "mission_id": "MISSION-AUTONOMY",
            "windows_validation_request_id": req_id,
            "assignment_id": f"ASSIGN-{req_id}",
            "target_runner": "WINDOWS",
            "validation_type": "WINDOWS_COMPATIBILITY",
            "artifact": "supervisor_standalone.py",
            "artifact_reference": "supervisor_standalone.py",
            "exact_question": "Attempt modification of Mac-reserved supervisor",
            "expected_evidence": "Rejection by Border Guard",
            "allowed_scope": "C:\\Users\\lol\\2026-workspace\\coordination\\mac_to_windows",
            "created_by": "MAC_CHIEF",
            "timestamp_utc": "2026-09-13T04:20:00Z",
            "host_os": "WINDOWS"
        }
        req_path = os.path.join(self.inbox, f"REQUEST_{req_id}.json")
        with open(req_path, "w", encoding="utf-8") as f:
            json.dump(req_data, f, indent=2)

        res = self.engine.reconcile_peer_inbox()
        self.assertEqual(res["status"], "PASS")

        # Result must be REJECTED with BORDER_GUARD_VIOLATION
        res_file = os.path.join(self.results, f"{req_id}.json")
        self.assertTrue(os.path.exists(res_file))
        with open(res_file, "r", encoding="utf-8") as f:
            res_data = json.load(f)
        self.assertEqual(res_data.get("status"), "REJECTED")
        self.assertEqual(res_data.get("decision"), "REJECTED_BORDER_GUARD_VIOLATION")

    def test_05_spend_firewall_enforcement(self):
        """Verify requests requesting spend > 0.00 EUR are rejected by the financial firewall."""
        req_id = f"REQ-TEST-SPEND-{int(time.time() * 1000)}"
        req_data = {
            "schema_version": "1.0",
            "mission_id": "MISSION-AUTONOMY",
            "windows_validation_request_id": req_id,
            "assignment_id": f"ASSIGN-{req_id}",
            "target_runner": "WINDOWS",
            "validation_type": "WINDOWS_COMPATIBILITY",
            "artifact": "project-memory/data/autonomy_cycle_state.json",
            "artifact_reference": "project-memory/data/autonomy_cycle_state.json",
            "exact_question": "Attempt spend authorization",
            "expected_evidence": "Spend firewall rejection",
            "allowed_scope": "C:\\Users\\lol\\2026-workspace",
            "spend_eur": 50.00,
            "created_by": "MAC_CHIEF",
            "timestamp_utc": "2026-09-13T04:20:00Z",
            "host_os": "WINDOWS"
        }
        req_path = os.path.join(self.inbox, f"REQUEST_{req_id}.json")
        with open(req_path, "w", encoding="utf-8") as f:
            json.dump(req_data, f, indent=2)

        res = self.engine.reconcile_peer_inbox()
        self.assertEqual(res["status"], "PASS")

        # Result must be REJECTED with SPEND_FIREWALL_VIOLATION
        res_file = os.path.join(self.results, f"{req_id}.json")
        self.assertTrue(os.path.exists(res_file))
        with open(res_file, "r", encoding="utf-8") as f:
            res_data = json.load(f)
        self.assertEqual(res_data.get("status"), "REJECTED")
        self.assertEqual(res_data.get("decision"), "REJECTED_SPEND_FIREWALL_VIOLATION")

    def test_06_fenced_mutex_split_brain_preemption(self):
        """Verify conflicting locks prevent concurrent double-writing."""
        req_id = f"REQ-TEST-SPLITBRAIN-{int(time.time() * 1000)}"
        resource_id = f"REQUEST_CLAIM_{req_id}"

        # Pre-lock resource under a different worker
        fenced_mgr = FencedMutexManager()
        acq_res = fenced_mgr.acquire(resource_id=resource_id, holder_id="OTHER_MAC_WORKER", holder_host="MAC", ttl_seconds=300)
        self.assertTrue(acq_res.get("acquired"))

        # Attempt claim from Windows peer consensus engine
        claimed, info = self.engine.claim_request(req_id, {"windows_validation_request_id": req_id})
        self.assertFalse(claimed, "Should fail to acquire lock when already held by another worker")
        self.assertEqual(info.get("error"), "FAILED_TO_ACQUIRE_FENCED_MUTEX")

        # Cleanup lock
        fenced_mgr.release(resource_id, "OTHER_MAC_WORKER", acq_res["lease_token"])

    def test_07_handoff_candidate_synchronization(self):
        """Verify MAC_HANDOFF_CANDIDATE.json maintains monotonic certified tasks count."""
        cand_path = self.engine.handoff_candidate_path
        self.assertTrue(os.path.exists(cand_path))
        with open(cand_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertGreaterEqual(data["evidence"]["certified_tasks_count"], 65)
        self.assertEqual(data["evidence"]["spend_eur"], 0.00)
        self.assertEqual(data["evidence"]["proof_debt"], 0.00)

if __name__ == "__main__":
    unittest.main()
