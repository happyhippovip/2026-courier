"""
test_windows_symphony_assurance.py - Comprehensive Windows Symphony Endgame Assurance Court
Verifies:
1. ResultCustoms path traversal rejection (task_id and target_files).
2. ResultCustoms Mac-reserved scope rejection (no Windows worker can certify Mac scopes).
3. HandoffValidator boundary & traversal rejection.
4. ChiefIngestor and ChiefCoordinator parameter alias compatibility.
5. ConstitutionLoader convenience aliases and discovery.
6. ControlPlane single-writer lock exclusivity against competing lanes.
7. ChiefRequestValidator convenience validate API.
8. Clean-room recovery and state memory resilience.
"""

import os
import json
import unittest
import tempfile
import shutil

from courier.chief.control_plane import ControlPlane
from courier.chief.types import Lane, Host
from courier.chief.ingestor import ChiefIngestor
from courier.chief.coordinator import ChiefCoordinator
from courier.chief.validator import ChiefRequestValidator, HandoffValidator
from courier.chief.result_customs import ResultCustomsJudge, MAC_RESERVED_PATTERNS
from courier.chief.constitution import ConstitutionLoader
from courier.chief.crash_proof_recovery import CrashProofMemoryEngine


class TestWindowsSymphonyAssurance(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="symphony_test_")
        self.db_path = os.path.join(self.test_dir, "test_cp.db")
        self.cp = ControlPlane(db_path=self.db_path)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_result_customs_rejects_path_traversal(self):
        """ResultCustomsJudge must reject task_id or target_files with directory traversal (..)."""
        cand_bad_id = {"task_id": "../../etc/passwd"}
        ev_ok = {"exit_code": 0, "stdout": "test passed", "command": "run"}
        res1 = ResultCustomsJudge.evaluate(cand_bad_id, ev_ok)
        self.assertFalse(res1["passed"])
        self.assertIn("SECURITY_PATH_TRAVERSAL_DISALLOWED", res1["reason"])

        cand_bad_files = {"task_id": "TASK-SAFE-01", "target_files": ["../../windows/system32/evil.dll"]}
        res2 = ResultCustomsJudge.evaluate(cand_bad_files, ev_ok)
        self.assertFalse(res2["passed"])
        self.assertIn("SECURITY_PATH_TRAVERSAL_DISALLOWED", res2["reason"])

        cand_ok = {"task_id": "TASK-SAFE-02"}
        ev_bad_files = {"exit_code": 0, "stdout": "test passed", "command": "run", "modified_files": ["dir/../../secret.key"]}
        res3 = ResultCustomsJudge.evaluate(cand_ok, ev_bad_files)
        self.assertFalse(res3["passed"])
        self.assertIn("SECURITY_PATH_TRAVERSAL_DISALLOWED", res3["reason"])

    def test_02_result_customs_rejects_mac_reserved_scopes(self):
        """ResultCustomsJudge must reject any target/modified file in Mac-reserved scopes."""
        cand_ok = {"task_id": "TASK-SAFE-03"}
        for scope in MAC_RESERVED_PATTERNS:
            ev_mac = {"exit_code": 0, "stdout": "test passed", "command": "run", "target_files": [scope]}
            res = ResultCustomsJudge.evaluate(cand_ok, ev_mac)
            self.assertFalse(res["passed"], f"Expected rejection for Mac scope '{scope}'")
            self.assertIn("MAC_RESERVED_SCOPE_VIOLATION", res["reason"])

    def test_03_handoff_validator_rejects_traversal_and_mac_scopes(self):
        """HandoffValidator must reject handoffs targeting Mac scopes or using path traversal."""
        payload_traversal = {
            "assignment_id": "ASSIGN-01",
            "origin": "WINDOWS_GOOGLE",
            "role": "RUNNER",
            "timestamp_utc": "2026-09-13T10:00:00Z",
            "host_os": "WINDOWS",
            "mac_host_access": False,
            "production_write_authority": False,
            "target_files": ["../../system32/calc.exe"]
        }
        valid, errors = HandoffValidator.validate_handoff_payload(payload_traversal)
        self.assertFalse(valid)
        self.assertTrue(any("PATH_TRAVERSAL_VIOLATION" in e for e in errors))

        payload_mac = {
            "assignment_id": "ASSIGN-02",
            "origin": "WINDOWS_GOOGLE",
            "role": "RUNNER",
            "timestamp_utc": "2026-09-13T10:00:00Z",
            "host_os": "WINDOWS",
            "mac_host_access": False,
            "production_write_authority": False,
            "target_files": ["coordination/mac_to_windows/state.json"]
        }
        valid2, errors2 = HandoffValidator.validate_handoff_payload(payload_mac)
        self.assertFalse(valid2)
        self.assertTrue(any("MAC_RESERVED_SCOPE_VIOLATION" in e for e in errors2))

    def test_04_constructor_aliases_ingestor_and_coordinator(self):
        """ChiefIngestor and ChiefCoordinator must support cp and handoffs_dir aliases without error."""
        ingestor = ChiefIngestor(cp=self.cp, handoffs_dir=self.test_dir)
        self.assertIsNotNone(ingestor.control_plane)
        self.assertEqual(ingestor.handoffs_dir, os.path.abspath(self.test_dir))

        coord = ChiefCoordinator(cp=self.cp, handoffs_dir=self.test_dir)
        self.assertIsNotNone(coord.control_plane)
        self.assertEqual(coord.dispatch_base_dir, os.path.abspath(self.test_dir))

    def test_05_constitution_loader_aliases(self):
        """ConstitutionLoader must provide load_constitution and get_constitution aliases."""
        success, data, path, h = ConstitutionLoader.load_constitution()
        self.assertTrue(success)
        self.assertIn("articles", data)
        self.assertTrue(len(h) > 0)

        summary = ConstitutionLoader.get_constitution()
        self.assertEqual(summary.get("status"), "ACTIVE")

    def test_06_lock_exclusivity_against_competing_workers(self):
        """Resource locks must guarantee single-writer exclusivity across competing workers."""
        ok1, msg1 = self.cp.acquire_lock("EXCLUSIVE_RESOURCE_ALPHA", Lane.WINDOWS_GOOGLE, Host.WINDOWS, ttl_seconds=60)
        self.assertTrue(ok1)

        ok2, msg2 = self.cp.acquire_lock("EXCLUSIVE_RESOURCE_ALPHA", Lane.WINDOWS_CLI_1, Host.WINDOWS, ttl_seconds=60)
        self.assertFalse(ok2)
        self.assertIn("SINGLE_WRITER_CONFLICT", msg2)

        ok3, msg3 = self.cp.acquire_lock("EXCLUSIVE_RESOURCE_ALPHA", Lane.WINDOWS_GOOGLE, Host.WINDOWS, ttl_seconds=60, allow_renewal=False)
        self.assertFalse(ok3)
        self.assertIn("LOCK_ALREADY_HELD", msg3)

        released = self.cp.release_lock("EXCLUSIVE_RESOURCE_ALPHA", Lane.WINDOWS_GOOGLE)
        self.assertTrue(released)
        ok4, _ = self.cp.acquire_lock("EXCLUSIVE_RESOURCE_ALPHA", Lane.WINDOWS_CLI_1, Host.WINDOWS, ttl_seconds=60)
        self.assertTrue(ok4)

    def test_07_chief_request_validator_validate_alias(self):
        """ChiefRequestValidator.validate returns dict with boolean valid and error list."""
        valid_req = {
            "mission_id": "MISSION-01",
            "windows_validation_request_id": "REQ-01",
            "artifact_reference": "ref.txt",
            "exact_question": "Does it pass?",
            "expected_evidence": "Pass log",
            "allowed_scope": "courier/tests"
        }
        res = ChiefRequestValidator.validate(valid_req)
        self.assertTrue(res["valid"])
        self.assertEqual(len(res["errors"]), 0)

        invalid_req = {"mission_id": "MISSION-02"}
        res2 = ChiefRequestValidator.validate(invalid_req)
        self.assertFalse(res2["valid"])
        self.assertTrue(len(res2["errors"]) > 0)

    def test_08_clean_room_crash_proof_bootstrap(self):
        """CrashProofMemoryEngine bootstraps cleanly in fresh directory without prior state."""
        fresh_db = os.path.join(self.test_dir, "fresh.db")
        fresh_state = os.path.join(self.test_dir, "fresh_state.json")
        engine = CrashProofMemoryEngine(db_path=fresh_db, state_file=fresh_state)
        state = engine.load_durable_state()
        self.assertIsNotNone(state.get("mission_id"))
        self.assertEqual(state.get("task_status"), "IDLE")


if __name__ == "__main__":
    unittest.main()