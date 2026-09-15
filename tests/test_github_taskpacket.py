"""Tests for the bounded GitHub TaskPacket contract."""

from __future__ import annotations

import unittest
import json
import os
import tempfile
from pathlib import Path

from scripts.run_github_taskpacket import terminal_result, validate_taskpacket
from scripts.verify_github_taskpacket_result import main as verify_main


def valid_packet() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "task_id": "task-123",
        "attempt_id": "attempt-1",
        "dispatch_id": "dispatch-123",
        "result_id": "result-123",
        "operation": "repository-metadata-v1",
        "github_run_id": "123456789",
        "github_run_attempt": 1,
        "repository": "happyhippovip/2026-courier",
        "ref": "refs/heads/main",
        "sha": "a" * 40,
    }


class GitHubTaskPacketTests(unittest.TestCase):
    def test_valid_packet_produces_machine_readable_terminal_result(self):
        packet = valid_packet()
        self.assertIsNone(validate_taskpacket(packet))
        result = terminal_result(packet, None)
        self.assertEqual(result["status"], "SUCCEEDED")
        self.assertTrue(result["terminal"])
        self.assertEqual(result["dispatch_id"], packet["dispatch_id"])
        self.assertEqual(result["github_run_id"], packet["github_run_id"])

    def test_unapproved_operation_is_rejected_without_execution(self):
        packet = valid_packet()
        packet["operation"] = "run-arbitrary-payload"
        error = validate_taskpacket(packet)
        self.assertEqual(error, "unsupported operation")
        result = terminal_result(packet, error)
        self.assertEqual(result["status"], "REJECTED")
        self.assertNotIn("result", result)

    def test_identity_must_be_stable_schema_value(self):
        packet = valid_packet()
        packet["dispatch_id"] = "contains space"
        self.assertEqual(validate_taskpacket(packet), "invalid dispatch_id")

    def test_independent_verifier_records_exact_result_provenance(self):
        packet = valid_packet()
        result = terminal_result(packet, None)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            result_path = root / "result.json"
            output_path = root / "verification.json"
            result_path.write_text(json.dumps(result), encoding="utf-8")
            original_environ = os.environ.copy()
            original_argv = __import__("sys").argv
            try:
                os.environ.update({
                    "TASK_ID": "task-123",
                    "ATTEMPT_ID": "attempt-1",
                    "DISPATCH_ID": "dispatch-123",
                    "RESULT_ID": "result-123",
                    "GITHUB_RUN_ID": "123456789",
                    "GITHUB_RUN_ATTEMPT": "1",
                })
                __import__("sys").argv = [
                    "verify_github_taskpacket_result.py", "--result", str(result_path),
                    "--output", str(output_path),
                ]
                verify_main()
            finally:
                os.environ.clear()
                os.environ.update(original_environ)
                __import__("sys").argv = original_argv
            verification = json.loads(output_path.read_text(encoding="utf-8"))
        self.assertEqual(verification["verifier_id"], "github-actions-taskpacket-verifier-v1")
        self.assertEqual(verification["result_path"], "result.json")


if __name__ == "__main__":
    unittest.main()
