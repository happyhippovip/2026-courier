"""Targeted unit tests for Courier Worker Adapters using injected process doubles and deterministic fixtures.

Guarantees:
- UNIT_TEST_MODEL_CALLS = 0
- UNIT_TEST_NETWORK_REQUESTS = 0
- Fail-closed security validations across all edge cases.
"""
import hashlib
import json
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from scripts.worker_availability import WorkerState, AvailabilityEvidence

class MockResolver:
    def resolve_gemini(self):
        return AvailabilityEvidence(worker='GEMINI', state=WorkerState.AVAILABLE, executable='/agy', resolution_method='MOCK', detail='mock')
    def resolve_codex(self):
        return AvailabilityEvidence(worker='CODEX', state=WorkerState.AVAILABLE, executable='/codex', resolution_method='MOCK', detail='mock')
    def resolve_cli1(self):
        return AvailabilityEvidence(worker='CLI1', state=WorkerState.AVAILABLE, executable='/cli1', resolution_method='MOCK', detail='mock')
from pathlib import Path
from typing import Any, Optional
from unittest.mock import MagicMock, patch

from scripts.courier_real_worker_adapters import (
    create_real_cli1_adapter,
    create_real_codex_adapter,
    create_real_gemini_adapter,
    get_real_worker_adapters,
)
from scripts.courier_safety_dispatcher import (
    CourierSafetyDispatcher,
    LocalWorkerAdapterBoundary,
    TaskEnvelope,
    canonical_hash,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


@patch('scripts.worker_availability.WorkerAvailabilityResolver', new=MockResolver)
class TestCourierRealWorkerAdapters(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace_dir = Path(self.temp_dir.name)
        self.boundary = LocalWorkerAdapterBoundary(self.workspace_dir)
        self.boundary.attach_real_worker_adapters(REPO_ROOT)
        self.dispatcher = CourierSafetyDispatcher(self.workspace_dir, adapter_boundary=self.boundary)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_real_cli1_adapter_execution(self) -> None:
        """Verify truthful CLI1 deterministic local adapter execution (0 model calls)."""
        adapter = create_real_cli1_adapter(REPO_ROOT)
        envelope = {
            "task_hash": "cli1_task_hash_123",
            "worker_id": "worker_cli1_01",
            "target_agent": "CLI1",
            "correlation_id": "corr-cli1-001",
            "task_id": "task-cli1-001",
            "payload": {"action": "inspect_repo"},
        }
        res = adapter(envelope)
        self.assertEqual(res["ack"]["status"], "ACCEPTED")
        self.assertEqual(res["ack"]["task_hash"], "cli1_task_hash_123")
        self.assertEqual(res["ack"]["worker_id"], "worker_cli1_01")
        self.assertEqual(res["ack"]["target_agent"], "CLI1")
        self.assertEqual(res["ack"]["correlation_id"], "corr-cli1-001")
        self.assertEqual(res["ack"]["task_id"], "task-cli1-001")
        self.assertEqual(res["ack"]["ack_mode"], "SYNCHRONOUS_COMPLETION_VALIDATED")

        self.assertEqual(res["result"]["status"], "COMPLETED")
        self.assertEqual(res["result"]["task_hash"], "cli1_task_hash_123")
        self.assertEqual(res["result"]["correlation_id"], "corr-cli1-001")
        self.assertEqual(res["result"]["task_id"], "task-cli1-001")
        payload = res["result"]["payload"]
        self.assertEqual(payload["worker_agent"], "CLI1")
        self.assertEqual(payload["worker_type"], "DETERMINISTIC_LOCAL")
        self.assertFalse(payload["real_model_call"])
        self.assertFalse(payload["separate_process"])
        self.assertEqual(payload["entrypoint"], "scripts/cli_operations_autopilot.py")
        self.assertEqual(payload["execution_mode"], "REAL_CLI1_LOCAL_EXECUTION")
        self.assertIn("organization_observation", payload)
        self.assertEqual(res["result"]["result_fingerprint"], canonical_hash(payload))

    @patch("scripts.run_codex_bridge.subprocess.run")
    def test_real_codex_adapter_execution(self, mock_run: MagicMock) -> None:
        """Verify CODEX adapter executes with full identity binding and returns valid ACK + RESULT."""
        def mock_subprocess_exec(cmd, **kwargs):
            if "--version" in cmd:
                return MagicMock(returncode=0, stdout="codex 0.1.0", stderr="")
            if "-o" in cmd:
                out_file_idx = cmd.index("-o") + 1
                out_file = Path(cmd[out_file_idx])
                out_file.parent.mkdir(parents=True, exist_ok=True)
                prompt_text = cmd[-1]
                mission_id = ""
                corr_id, task_id, task_hash = "corr-codex-001", "task-codex-001", "codex_task_hash_456"
                for line in prompt_text.splitlines():
                    if line.startswith("CORRELATION_ID: "):
                        corr_id = line.split("CORRELATION_ID: ")[1].strip()
                    elif line.startswith("MISSION_ID: "):
                        mission_id = line.split("MISSION_ID: ")[1].strip()
                    elif line.startswith("TASK_ID: "):
                        task_id = line.split("TASK_ID: ")[1].strip()
                    elif line.startswith("TASK_HASH: "):
                        task_hash = line.split("TASK_HASH: ")[1].strip()
                model_payload = {
                    "correlation_id": corr_id,
                    "task_id": task_id,
                    "mission_id": mission_id,
                    "task_hash": task_hash,
                    "target_agent": "CODEX",
                    "verdict": "PASS",
                    "summary": "All schemas verified successfully.",
                }
                out_file.write_text(json.dumps(model_payload), encoding="utf-8")
                return MagicMock(returncode=0, stdout="", stderr="")
            return MagicMock(returncode=0, stdout="", stderr="")

        mock_run.side_effect = mock_subprocess_exec
        adapter = create_real_codex_adapter(REPO_ROOT)
        envelope = {
            "task_hash": "codex_task_hash_456",
            "worker_id": "worker_codex_01",
            "target_agent": "CODEX",
            "correlation_id": "corr-codex-001",
            "task_id": "task-codex-001",
            "requested_model": "codex",
            "payload": {"action": "verify_schemas"},
        }
        res = adapter(envelope)
        self.assertEqual(res["ack"]["status"], "ACCEPTED")
        self.assertEqual(res["ack"]["task_hash"], "codex_task_hash_456")
        self.assertEqual(res["ack"]["target_agent"], "CODEX")
        self.assertEqual(res["ack"]["correlation_id"], "corr-codex-001")
        self.assertEqual(res["ack"]["task_id"], "task-codex-001")
        self.assertEqual(res["ack"]["ack_mode"], "SYNCHRONOUS_COMPLETION_VALIDATED")

        self.assertEqual(res["result"]["status"], "COMPLETED")
        payload = res["result"]["payload"]
        self.assertEqual(payload["worker_agent"], "CODEX")
        self.assertEqual(payload["worker_type"], "NATIVE_MODEL_CLI")
        self.assertTrue(payload["real_model_call"])
        self.assertTrue(payload["separate_process"])
        self.assertEqual(payload["requested_model"], "codex")
        self.assertEqual(payload["entrypoint"], "/Applications/ChatGPT.app/Contents/Resources/codex")
        self.assertEqual(payload["execution_mode"], "REAL_CODEX_CLI_EXECUTION")
        self.assertEqual(payload["verdict"], "PASS")
        self.assertEqual(payload["summary"], "All schemas verified successfully.")
        self.assertEqual(res["result"]["result_fingerprint"], canonical_hash(payload))

    @patch("scripts.native_agy_runner.subprocess.run")
    def test_real_gemini_adapter_execution(self, mock_run: MagicMock) -> None:
        """Verify GEMINI adapter executes native AGY boundary with full identity binding."""
        def mock_agy_exec(cmd, **kwargs):
            if "--version" in cmd:
                return MagicMock(returncode=0, stdout="agy 1.1.25", stderr="")
            prompt_idx = cmd.index("-p") + 1
            prompt_text = cmd[prompt_idx]
            mission_id = ""
            corr_id, task_id, task_hash = "corr-gemini-001", "task-gemini-001", "gemini_task_hash_789"
            for line in prompt_text.splitlines():
                if line.startswith("CORRELATION_ID: "):
                    corr_id = line.split("CORRELATION_ID: ")[1].strip()
                elif line.startswith("MISSION_ID: "):
                    mission_id = line.split("MISSION_ID: ")[1].strip()
                elif line.startswith("TASK_ID: "):
                    task_id = line.split("TASK_ID: ")[1].strip()
                elif line.startswith("TASK_HASH: "):
                    task_hash = line.split("TASK_HASH: ")[1].strip()
            model_inner = {
                "correlation_id": corr_id,
                "task_id": task_id,
                    "mission_id": mission_id,
                "task_hash": task_hash,
                "target_agent": "GEMINI",
                "verdict": "PASS",
                "summary": "Acceptance audit confirmed clean.",
            }
            outer = {
                "status": "SUCCESS",
                "model": "gemini-3.7-flash-medium",
                "conversation_id": "conv-canary-001",
                "duration_seconds": 1.1,
                "response": json.dumps(model_inner),
                "usage": {"input_tokens": 80, "output_tokens": 15, "total_tokens": 95},
            }
            return MagicMock(returncode=0, stdout=json.dumps(outer), stderr="")

        mock_run.side_effect = mock_agy_exec

        adapter = create_real_gemini_adapter(REPO_ROOT, model="gemini-3.7-flash-medium")
        envelope = {
            "task_hash": "gemini_task_hash_789",
            "worker_id": "worker_gemini_01",
            "target_agent": "GEMINI",
            "correlation_id": "corr-gemini-001",
            "task_id": "task-gemini-001",
            "requested_model": "gemini-3.7-flash-medium",
            "payload": {"action": "acceptance_audit"},
        }
        res = adapter(envelope)
        self.assertEqual(res["ack"]["status"], "ACCEPTED")
        self.assertEqual(res["ack"]["target_agent"], "GEMINI")
        self.assertEqual(res["ack"]["correlation_id"], "corr-gemini-001")
        self.assertEqual(res["ack"]["task_id"], "task-gemini-001")
        self.assertEqual(res["ack"]["ack_mode"], "SYNCHRONOUS_COMPLETION_VALIDATED")

        self.assertEqual(res["result"]["status"], "COMPLETED")
        payload = res["result"]["payload"]
        self.assertEqual(payload["worker_agent"], "GEMINI")
        self.assertEqual(payload["worker_type"], "NATIVE_AGY_MODEL")
        self.assertTrue(payload["real_model_call"])
        self.assertTrue(payload["separate_process"])
        self.assertEqual(payload["requested_model"], "gemini-3.7-flash-medium")
        self.assertEqual(payload["confirmed_model"], "gemini-3.7-flash-medium")
        self.assertTrue(payload["model_identity_truthful"])
        self.assertEqual(payload["execution_mode"], "REAL_GEMINI_NATIVE_AGY_EXECUTION")
        self.assertEqual(payload["verdict"], "PASS")
        self.assertEqual(payload["summary"], "Acceptance audit confirmed clean.")
        self.assertEqual(res["result"]["result_fingerprint"], canonical_hash(payload))

    @patch("scripts.native_agy_runner.subprocess.run")
    def test_human_approval_required_becomes_human_gate_and_zero_successors(self, mock_run: MagicMock) -> None:
        """Verify HUMAN_APPROVAL_REQUIRED verdict becomes HUMAN_GATE with zero successors."""
        def mock_agy_gate(cmd, **kwargs):
            if "--version" in cmd:
                return MagicMock(returncode=0, stdout="agy 1.1.25", stderr="")
            prompt_idx = cmd.index("-p") + 1
            prompt_text = cmd[prompt_idx]
            mission_id = ""
            corr_id, task_id, task_hash = "corr-gate-001", "m-gate-001", "hash-gate-001"
            for line in prompt_text.splitlines():
                if line.startswith("CORRELATION_ID: "):
                    corr_id = line.split("CORRELATION_ID: ")[1].strip()
                elif line.startswith("MISSION_ID: "):
                    mission_id = line.split("MISSION_ID: ")[1].strip()
                elif line.startswith("TASK_ID: "):
                    task_id = line.split("TASK_ID: ")[1].strip()
                elif line.startswith("TASK_HASH: "):
                    task_hash = line.split("TASK_HASH: ")[1].strip()
            model_inner = {
                "correlation_id": corr_id,
                "task_id": task_id,
                    "mission_id": mission_id,
                "task_hash": task_hash,
                "target_agent": "GEMINI",
                "verdict": "HUMAN_APPROVAL_REQUIRED",
                "summary": "Manual approval needed before proceeding.",
            }
            outer = {
                "status": "SUCCESS",
                "model": "gemini-3.7-flash-medium",
                "response": json.dumps(model_inner),
            }
            return MagicMock(returncode=0, stdout=json.dumps(outer), stderr="")

        mock_run.side_effect = mock_agy_gate

        self.dispatcher.mission_queue.enqueue({
            "mission_id": "m-gate-001",
            "goal": "Test human gate handling",
            "capability_required": "acceptance review",
            "preferred_agent": "GEMINI",
            "task": {"action": "check_gate", "correlation_id": "corr-gate-001", "task_id": "m-gate-001"},
        })

        deriver = MagicMock(return_value={"mission_id": "m-should-not-exist"})
        res = self.dispatcher.process_next_mission("worker-1", successor_deriver=deriver)

        self.assertEqual(res["status"], "HUMAN_GATE")
        self.assertEqual(res["mission_id"], "m-gate-001")
        self.assertIsNone(res["successor_mission_id"])
        deriver.assert_not_called()

        mission = self.dispatcher.mission_queue.get("m-gate-001")
        self.assertEqual(mission["status"], "HUMAN_GATE")

    @patch("scripts.native_agy_runner.subprocess.run")
    def test_auth_requirement_triggers_human_gate(self, mock_run: MagicMock) -> None:
        """Verify authentication / OAuth requirement triggers HUMAN_GATE."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="Please login required to continue OAuth flow",
            stderr="",
        )
        self.dispatcher.mission_queue.enqueue({
            "mission_id": "m-auth-001",
            "goal": "Test auth requirement",
            "capability_required": "acceptance review",
            "preferred_agent": "GEMINI",
            "task": {"action": "check_auth", "task_id": "m-auth-001"},
        })
        res = self.dispatcher.process_next_mission("worker-1")
        self.assertEqual(res["status"], "HUMAN_GATE")
        self.assertEqual(res["mission_id"], "m-auth-001")

    def test_missing_identity_fails_closed(self) -> None:
        """Verify missing correlation_id/task_id fails closed."""
        self.boundary.register_consumer("CLI1", lambda env: {
            "ack": {
                "schema_version": "1.0",
                "type": "ACK",
                "status": "ACCEPTED",
                "task_hash": env["task_hash"],
                "worker_id": env["worker_id"],
                "target_agent": env["target_agent"],
                # missing correlation_id and task_id
            },
            "result": {
                "schema_version": "1.0",
                "type": "RESULT",
                "status": "COMPLETED",
                "task_hash": env["task_hash"],
                "worker_id": env["worker_id"],
                "target_agent": env["target_agent"],
                "payload": {"data": 1},
                "result_fingerprint": canonical_hash({"data": 1}),
            }
        })
        self.dispatcher.mission_queue.enqueue({
            "mission_id": "m-missing-id",
            "goal": "Missing identity test",
            "capability_required": "local repo analysis",
            "task": {"action": "missing_id", "correlation_id": "corr-missing-1", "task_id": "task-missing-1"},
        })
        res = self.dispatcher.process_next_mission("worker-1")
        self.assertEqual(res["status"], "BLOCKED")

    def test_mismatched_correlation_id_fails_closed(self) -> None:
        """Verify mismatched correlation_id fails closed."""
        self.boundary.register_consumer("CLI1", lambda env: {
            "ack": {
                "schema_version": "1.0",
                "type": "ACK",
                "status": "ACCEPTED",
                "task_hash": env["task_hash"],
                "worker_id": env["worker_id"],
                "target_agent": env["target_agent"],
                "correlation_id": "forged_correlation_id",
                "task_id": env["task_id"],
            },
            "result": {
                "schema_version": "1.0",
                "type": "RESULT",
                "status": "COMPLETED",
                "task_hash": env["task_hash"],
                "worker_id": env["worker_id"],
                "target_agent": env["target_agent"],
                "correlation_id": "forged_correlation_id",
                "task_id": env["task_id"],
                "payload": {"data": 1},
                "result_fingerprint": canonical_hash({"data": 1}),
            }
        })
        self.dispatcher.mission_queue.enqueue({
            "mission_id": "m-mismatched-corr",
            "goal": "Mismatched correlation_id test",
            "capability_required": "local repo analysis",
            "task": {"action": "mismatched_corr", "correlation_id": "expected_corr", "task_id": "task-1"},
        })
        res = self.dispatcher.process_next_mission("worker-1")
        self.assertEqual(res["status"], "BLOCKED")

    def test_mismatched_task_id_fails_closed(self) -> None:
        """Verify mismatched task_id fails closed."""
        self.boundary.register_consumer("CLI1", lambda env: {
            "ack": {
                "schema_version": "1.0",
                "type": "ACK",
                "status": "ACCEPTED",
                "task_hash": env["task_hash"],
                "worker_id": env["worker_id"],
                "target_agent": env["target_agent"],
                "correlation_id": env["correlation_id"],
                "task_id": "forged_task_id",
            },
            "result": {
                "schema_version": "1.0",
                "type": "RESULT",
                "status": "COMPLETED",
                "task_hash": env["task_hash"],
                "worker_id": env["worker_id"],
                "target_agent": env["target_agent"],
                "correlation_id": env["correlation_id"],
                "task_id": "forged_task_id",
                "payload": {"data": 1},
                "result_fingerprint": canonical_hash({"data": 1}),
            }
        })
        self.dispatcher.mission_queue.enqueue({
            "mission_id": "m-mismatched-task-id",
            "goal": "Mismatched task_id test",
            "capability_required": "local repo analysis",
            "task": {"action": "mismatched_task_id", "correlation_id": "corr-1", "task_id": "expected_task_id"},
        })
        res = self.dispatcher.process_next_mission("worker-1")
        self.assertEqual(res["status"], "BLOCKED")

    def test_missing_ack_fails_closed(self) -> None:
        """Verify missing worker ACK fails closed."""
        self.boundary.register_consumer("CLI1", lambda env: {
            "result": {
                "schema_version": "1.0",
                "type": "RESULT",
                "status": "COMPLETED",
                "task_hash": env["task_hash"],
                "worker_id": env["worker_id"],
                "target_agent": env["target_agent"],
                "correlation_id": env["correlation_id"],
                "task_id": env["task_id"],
                "payload": {"data": 1},
                "result_fingerprint": canonical_hash({"data": 1}),
            }
        })
        self.dispatcher.mission_queue.enqueue({
            "mission_id": "m-no-ack",
            "goal": "Missing ACK test",
            "capability_required": "local repo analysis",
            "task": {"action": "no_ack"},
        })
        res = self.dispatcher.process_next_mission("worker-1")
        self.assertEqual(res["status"], "BLOCKED")
        self.assertIn("MISSING_OR_INVALID_ACK", str(res.get("reason", "")))

    def test_invalid_ack_fails_closed(self) -> None:
        """Verify rejected/invalid worker ACK fails closed."""
        self.boundary.register_consumer("CLI1", lambda env: {
            "ack": {
                "schema_version": "1.0",
                "type": "ACK",
                "status": "REJECTED",
                "task_hash": env["task_hash"],
                "worker_id": env["worker_id"],
                "target_agent": env["target_agent"],
                "correlation_id": env["correlation_id"],
                "task_id": env["task_id"],
            },
            "result": {
                "schema_version": "1.0",
                "type": "RESULT",
                "status": "COMPLETED",
                "task_hash": env["task_hash"],
                "worker_id": env["worker_id"],
                "target_agent": env["target_agent"],
                "correlation_id": env["correlation_id"],
                "task_id": env["task_id"],
                "payload": {"data": 2},
                "result_fingerprint": canonical_hash({"data": 2}),
            },
        })
        self.dispatcher.mission_queue.enqueue({
            "mission_id": "m-bad-ack",
            "goal": "Bad ACK test",
            "capability_required": "local repo analysis",
            "task": {"action": "bad_ack"},
        })
        res = self.dispatcher.process_next_mission("worker-1")
        self.assertEqual(res["status"], "BLOCKED")
        self.assertIn("MISSING_OR_INVALID_ACK", str(res.get("reason", "")))

    def test_wrong_task_hash_fails_closed(self) -> None:
        """Verify forged or mismatched task_hash in ACK fails closed."""
        self.boundary.register_consumer("CLI1", lambda env: {
            "ack": {
                "schema_version": "1.0",
                "type": "ACK",
                "status": "ACCEPTED",
                "task_hash": "forged_task_hash",
                "worker_id": env["worker_id"],
                "target_agent": env["target_agent"],
                "correlation_id": env["correlation_id"],
                "task_id": env["task_id"],
            },
            "result": {
                "schema_version": "1.0",
                "type": "RESULT",
                "status": "COMPLETED",
                "task_hash": env["task_hash"],
                "worker_id": env["worker_id"],
                "target_agent": env["target_agent"],
                "correlation_id": env["correlation_id"],
                "task_id": env["task_id"],
                "payload": {"data": 3},
                "result_fingerprint": canonical_hash({"data": 3}),
            },
        })
        self.dispatcher.mission_queue.enqueue({
            "mission_id": "m-wrong-hash",
            "goal": "Wrong task hash test",
            "capability_required": "local repo analysis",
            "task": {"action": "wrong_hash"},
        })
        res = self.dispatcher.process_next_mission("worker-1")
        self.assertEqual(res["status"], "BLOCKED")

    def test_wrong_worker_id_fails_closed(self) -> None:
        """Verify forged or mismatched worker_id fails closed."""
        self.boundary.register_consumer("CLI1", lambda env: {
            "ack": {
                "schema_version": "1.0",
                "type": "ACK",
                "status": "ACCEPTED",
                "task_hash": env["task_hash"],
                "worker_id": "forged_worker_id",
                "target_agent": env["target_agent"],
                "correlation_id": env["correlation_id"],
                "task_id": env["task_id"],
            },
            "result": {
                "schema_version": "1.0",
                "type": "RESULT",
                "status": "COMPLETED",
                "task_hash": env["task_hash"],
                "worker_id": env["worker_id"],
                "target_agent": env["target_agent"],
                "correlation_id": env["correlation_id"],
                "task_id": env["task_id"],
                "payload": {"data": 4},
                "result_fingerprint": canonical_hash({"data": 4}),
            },
        })
        self.dispatcher.mission_queue.enqueue({
            "mission_id": "m-wrong-worker",
            "goal": "Wrong worker id test",
            "capability_required": "local repo analysis",
            "task": {"action": "wrong_worker"},
        })
        res = self.dispatcher.process_next_mission("worker-1")
        self.assertEqual(res["status"], "BLOCKED")

    def test_wrong_target_agent_fails_closed(self) -> None:
        """Verify forged or mismatched target_agent fails closed."""
        self.boundary.register_consumer("CLI1", lambda env: {
            "ack": {
                "schema_version": "1.0",
                "type": "ACK",
                "status": "ACCEPTED",
                "task_hash": env["task_hash"],
                "worker_id": env["worker_id"],
                "target_agent": "CODEX",
                "correlation_id": env["correlation_id"],
                "task_id": env["task_id"],
            },
            "result": {
                "schema_version": "1.0",
                "type": "RESULT",
                "status": "COMPLETED",
                "task_hash": env["task_hash"],
                "worker_id": env["worker_id"],
                "target_agent": env["target_agent"],
                "correlation_id": env["correlation_id"],
                "task_id": env["task_id"],
                "payload": {"data": 5},
                "result_fingerprint": canonical_hash({"data": 5}),
            },
        })
        self.dispatcher.mission_queue.enqueue({
            "mission_id": "m-wrong-target",
            "goal": "Wrong target agent test",
            "capability_required": "local repo analysis",
            "task": {"action": "wrong_target"},
        })
        res = self.dispatcher.process_next_mission("worker-1")
        self.assertEqual(res["status"], "BLOCKED")

    def test_missing_result_fails_closed(self) -> None:
        """Verify missing worker RESULT fails closed."""
        self.boundary.register_consumer("CLI1", lambda env: {
            "ack": {
                "schema_version": "1.0",
                "type": "ACK",
                "status": "ACCEPTED",
                "task_hash": env["task_hash"],
                "worker_id": env["worker_id"],
                "target_agent": env["target_agent"],
                "correlation_id": env["correlation_id"],
                "task_id": env["task_id"],
            }
        })
        self.dispatcher.mission_queue.enqueue({
            "mission_id": "m-missing-res",
            "goal": "Missing result test",
            "capability_required": "local repo analysis",
            "task": {"action": "missing_res"},
        })
        res = self.dispatcher.process_next_mission("worker-1")
        self.assertEqual(res["status"], "BLOCKED")

    def test_invalid_result_fingerprint_fails_closed(self) -> None:
        """Verify tampered result payload fails closed with fingerprint mismatch."""
        self.boundary.register_consumer("CLI1", lambda env: {
            "ack": {
                "schema_version": "1.0",
                "type": "ACK",
                "status": "ACCEPTED",
                "task_hash": env["task_hash"],
                "worker_id": env["worker_id"],
                "target_agent": env["target_agent"],
                "correlation_id": env["correlation_id"],
                "task_id": env["task_id"],
            },
            "result": {
                "schema_version": "1.0",
                "type": "RESULT",
                "status": "COMPLETED",
                "task_hash": env["task_hash"],
                "worker_id": env["worker_id"],
                "target_agent": env["target_agent"],
                "correlation_id": env["correlation_id"],
                "task_id": env["task_id"],
                "payload": {"data": "tampered"},
                "result_fingerprint": "bad_fingerprint_123",
            },
        })
        self.dispatcher.mission_queue.enqueue({
            "mission_id": "m-tampered-res",
            "goal": "Tampered result test",
            "capability_required": "local repo analysis",
            "task": {"action": "tampered_res"},
        })
        res = self.dispatcher.process_next_mission("worker-1")
        self.assertEqual(res["status"], "BLOCKED")

    def test_worker_crash_fails_closed(self) -> None:
        """Verify worker throwing exception fails closed and releases leases."""
        def crash_worker(env: dict[str, Any]) -> dict[str, Any]:
            raise RuntimeError("CRITICAL_WORKER_CRASH")

        self.boundary.register_consumer("CLI1", crash_worker)
        self.dispatcher.mission_queue.enqueue({
            "mission_id": "m-crash",
            "goal": "Worker crash test",
            "capability_required": "local repo analysis",
            "task": {"action": "crash"},
        })
        res = self.dispatcher.process_next_mission("worker-1")
        self.assertEqual(res["status"], "BLOCKED")
        self.assertEqual(self.dispatcher.mission_queue.get("m-crash")["status"], "BLOCKED")

    @patch("subprocess.run")
    def test_codex_adapter_timeout_fails_closed(self, mock_run: MagicMock) -> None:
        """Verify Codex adapter timeout fails closed."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["codex"], timeout=90.0)
        adapter = create_real_codex_adapter(REPO_ROOT)
        envelope = {
            "task_hash": "codex_timeout_hash",
            "worker_id": "worker_codex_01",
            "target_agent": "CODEX",
            "correlation_id": "corr-timeout",
            "task_id": "task-timeout",
            "payload": {"action": "verify_schemas"},
        }
        with self.assertRaises(RuntimeError) as ctx:
            adapter(envelope)
        self.assertIn("CODEX_GENUINE_ENTRYPOINT_FAILED", str(ctx.exception))

    @patch("subprocess.run")
    def test_codex_adapter_nonzero_exit_fails_closed_no_fallback(self, mock_run: MagicMock) -> None:
        """Verify Codex CLI nonzero exit fails closed without deterministic fallback."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Codex execution failed")
        adapter = create_real_codex_adapter(REPO_ROOT)
        envelope = {
            "task_hash": "codex_nonzero_hash",
            "worker_id": "worker_codex_01",
            "target_agent": "CODEX",
            "correlation_id": "corr-nonzero",
            "task_id": "task-nonzero",
            "payload": {"action": "verify_schemas"},
        }
        with self.assertRaises(RuntimeError) as ctx:
            adapter(envelope)
        self.assertIn("CODEX_GENUINE_ENTRYPOINT_FAILED", str(ctx.exception))

    @patch("subprocess.run")
    def test_gemini_adapter_timeout_fails_closed(self, mock_run: MagicMock) -> None:
        """Verify Gemini adapter timeout fails closed."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["agy"], timeout=60.0)
        adapter = create_real_gemini_adapter(REPO_ROOT)
        envelope = {
            "task_hash": "gemini_timeout_hash",
            "worker_id": "worker_gemini_01",
            "target_agent": "GEMINI",
            "correlation_id": "corr-timeout",
            "task_id": "task-timeout",
            "payload": {"action": "acceptance_audit"},
        }
        with self.assertRaises(RuntimeError) as ctx:
            adapter(envelope)
        self.assertIn("GEMINI_NATIVE_AGY_FAILED", str(ctx.exception))

    @patch("subprocess.run")
    def test_gemini_adapter_nonzero_exit_fails_closed(self, mock_run: MagicMock) -> None:
        """Verify Gemini adapter nonzero exit fails closed."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="AGY internal error")
        adapter = create_real_gemini_adapter(REPO_ROOT)
        envelope = {
            "task_hash": "gemini_nonzero_hash",
            "worker_id": "worker_gemini_01",
            "target_agent": "GEMINI",
            "correlation_id": "corr-nonzero",
            "task_id": "task-nonzero",
            "payload": {"action": "acceptance_audit"},
        }
        with self.assertRaises(RuntimeError) as ctx:
            adapter(envelope)
        self.assertIn("GEMINI_NATIVE_AGY_FAILED", str(ctx.exception))

    def test_requested_model_mismatch_fails_closed(self) -> None:
        """Verify requested_model mismatch in result fails closed."""
        self.boundary.register_consumer("GEMINI", lambda env: {
            "ack": {
                "schema_version": "1.0",
                "type": "ACK",
                "status": "ACCEPTED",
                "task_hash": env["task_hash"],
                "worker_id": env["worker_id"],
                "target_agent": env["target_agent"],
                "correlation_id": env["correlation_id"],
                "task_id": env["task_id"],
            },
            "result": {
                "schema_version": "1.0",
                "type": "RESULT",
                "status": "COMPLETED",
                "task_hash": env["task_hash"],
                "worker_id": env["worker_id"],
                "target_agent": env["target_agent"],
                "correlation_id": env["correlation_id"],
                "task_id": env["task_id"],
                "payload": {"requested_model": "wrong-model-name"},
                "result_fingerprint": canonical_hash({"requested_model": "wrong-model-name"}),
            }
        })
        envelope = TaskEnvelope(
            task_hash="hash-mismatch-model",
            worker_id="worker-1",
            target_agent="GEMINI",
            capability="acceptance review",
            requires_write=False,
            is_heavy=False,
            verification_required=True,
            safety_decision="APPROVED_SAFE",
            payload={},
            correlation_id="corr-model",
            task_id="task-model",
            requested_model="gemini-3.7-flash-medium",
        )
        with self.assertRaises(RuntimeError) as ctx:
            self.boundary.dispatch("GEMINI", envelope, {})
        self.assertIn("REQUESTED_MODEL_MISMATCH", str(ctx.exception))

    @patch("subprocess.run")
    def test_three_worker_isolated_canary(self, mock_run: MagicMock) -> None:
        """Verify 3-worker canary with isolated process doubles (0 real model calls, 0 network)."""
        def mock_codex_exec(cmd, **kwargs):
            if "--version" in cmd:
                return MagicMock(returncode=0, stdout="codex 0.1.0", stderr="")
            if "-o" in cmd:
                out_file_idx = cmd.index("-o") + 1
                out_file = Path(cmd[out_file_idx])
                out_file.parent.mkdir(parents=True, exist_ok=True)
                prompt_text = cmd[-1]
                mission_id = ""
                corr_id, task_id, task_hash = "corr-b06r3-m2-verification", "b06r3-m2-verification", "hash_m2_codex"
                for line in prompt_text.splitlines():
                    if line.startswith("CORRELATION_ID: "):
                        corr_id = line.split("CORRELATION_ID: ")[1].strip()
                    elif line.startswith("MISSION_ID: "):
                        mission_id = line.split("MISSION_ID: ")[1].strip()
                    elif line.startswith("TASK_ID: "):
                        task_id = line.split("TASK_ID: ")[1].strip()
                    elif line.startswith("TASK_HASH: "):
                        task_hash = line.split("TASK_HASH: ")[1].strip()
                model_payload = {
                    "correlation_id": corr_id,
                    "task_id": task_id,
                    "mission_id": mission_id,
                    "task_hash": task_hash,
                    "target_agent": "CODEX",
                    "verdict": "PASS",
                    "summary": "Codex verified schemas.",
                }
                out_file.write_text(json.dumps(model_payload), encoding="utf-8")
                return MagicMock(returncode=0, stdout="", stderr="")
            return MagicMock(returncode=0, stdout="", stderr="")

        def mock_agy_exec(cmd, **kwargs):
            if "--version" in cmd:
                return MagicMock(returncode=0, stdout="agy 1.1.25", stderr="")
            prompt_idx = cmd.index("-p") + 1
            prompt_text = cmd[prompt_idx]
            mission_id = ""
            corr_id, task_id, task_hash = "corr-b06r3-m3-acceptance", "b06r3-m3-acceptance", "hash_m3_gemini"
            for line in prompt_text.splitlines():
                if line.startswith("CORRELATION_ID: "):
                    corr_id = line.split("CORRELATION_ID: ")[1].strip()
                elif line.startswith("MISSION_ID: "):
                    mission_id = line.split("MISSION_ID: ")[1].strip()
                elif line.startswith("TASK_ID: "):
                    task_id = line.split("TASK_ID: ")[1].strip()
                elif line.startswith("TASK_HASH: "):
                    task_hash = line.split("TASK_HASH: ")[1].strip()
            model_inner = {
                "correlation_id": corr_id,
                "task_id": task_id,
                    "mission_id": mission_id,
                "task_hash": task_hash,
                "target_agent": "GEMINI",
                "verdict": "PASS",
                "summary": "Gemini AGY acceptance passed.",
            }
            outer = {
                "status": "SUCCESS",
                "model": "gemini-3.7-flash-medium",
                "conversation_id": "conv-canary-isolated",
                "duration_seconds": 0.5,
                "response": json.dumps(model_inner),
                "usage": {"input_tokens": 50, "output_tokens": 10, "total_tokens": 60},
            }
            return MagicMock(returncode=0, stdout=json.dumps(outer), stderr="")

        def mock_unified_run(cmd, **kwargs):
            exe = str(cmd[0])
            if "codex" in exe:
                return mock_codex_exec(cmd, **kwargs)
            elif "agy" in exe:
                return mock_agy_exec(cmd, **kwargs)
            return MagicMock(returncode=0, stdout="", stderr="")

        mock_run.side_effect = mock_unified_run

        # 1. Enqueue Root Mission 1 (CLI1)
        m1 = self.dispatcher.mission_queue.enqueue({
            "mission_id": "b06r3-m1-analysis",
            "goal": "Truthful read-only organizational observation via deterministic CLI1",
            "normalized_task": "Execute observe_organization via cli_operations_autopilot",
            "capability_required": "local repo analysis",
            "preferred_agent": "CLI1",
            "requires_write": False,
            "task": {
                "action": "inspect_repo",
                "requires_write": False,
                "task_id": "b06r3-m1-analysis",
                "correlation_id": "corr-b06r3-m1-analysis",
            },
        })
        self.assertEqual(m1["status"], "PENDING")

        def b06r3_successor_deriver(verified_parent: dict[str, Any]) -> Optional[dict[str, Any]]:
            pid = verified_parent["mission_id"]
            if pid == "b06r3-m1-analysis":
                return {
                    "mission_id": "b06r3-m2-verification",
                    "goal": "Real read-only schema verification via native Codex CLI",
                    "normalized_task": "Execute native Codex CLI inspection",
                    "capability_required": "legacy implementation",
                    "preferred_agent": "CODEX",
                    "requires_write": False,
                    "task": {
                        "action": "verify_schemas",
                        "requires_write": False,
                        "task_id": "b06r3-m2-verification",
                        "correlation_id": "corr-b06r3-m2-verification",
                        "task_hash": "hash_m2_codex",
                    },
                }
            elif pid == "b06r3-m2-verification":
                return {
                    "mission_id": "b06r3-m3-acceptance",
                    "goal": "Real read-only acceptance audit via native Antigravity AGY CLI",
                    "normalized_task": "Execute native agy model execution",
                    "capability_required": "acceptance review",
                    "preferred_agent": "GEMINI",
                    "requires_write": False,
                    "task": {
                        "action": "audit_acceptance",
                        "requires_write": False,
                        "task_id": "b06r3-m3-acceptance",
                        "correlation_id": "corr-b06r3-m3-acceptance",
                        "task_hash": "hash_m3_gemini",
                    },
                }
            return None

        # Step 1: Process Mission 1 (CLI1 - Deterministic Local)
        res1 = self.dispatcher.process_next_mission("operator-1", successor_deriver=b06r3_successor_deriver)
        self.assertEqual(res1["status"], "VERIFIED")
        self.assertEqual(res1["mission_id"], "b06r3-m1-analysis")
        self.assertEqual(res1["successor_mission_id"], "b06r3-m2-verification")

        # Step 2: Process Mission 2 (CODEX - Native CLI)
        res2 = self.dispatcher.process_next_mission("operator-1", successor_deriver=b06r3_successor_deriver)
        self.assertEqual(res2["status"], "VERIFIED")
        self.assertEqual(res2["mission_id"], "b06r3-m2-verification")
        self.assertEqual(res2["successor_mission_id"], "b06r3-m3-acceptance")

        # Step 3: Process Mission 3 (GEMINI - Native AGY Model)
        res3 = self.dispatcher.process_next_mission("operator-1", successor_deriver=b06r3_successor_deriver)
        self.assertEqual(res3["status"], "VERIFIED")
        self.assertEqual(res3["mission_id"], "b06r3-m3-acceptance")
        self.assertIsNone(res3["successor_mission_id"])  # Intentional STOP

        # Step 4: Stop check
        res4 = self.dispatcher.process_next_mission("operator-1", successor_deriver=b06r3_successor_deriver)
        self.assertEqual(res4["status"], "NO_PENDING_MISSION")

        # Verify all 3 missions in queue
        all_missions = self.dispatcher.mission_queue.read_all()
        self.assertEqual(len(all_missions), 3)
        self.assertTrue(all(m["status"] == "VERIFIED" for m in all_missions))
        self.assertEqual(all_missions[0]["preferred_agent"], "CLI1")
        self.assertEqual(all_missions[1]["preferred_agent"], "CODEX")
        self.assertEqual(all_missions[2]["preferred_agent"], "GEMINI")


if __name__ == "__main__":
    unittest.main()

