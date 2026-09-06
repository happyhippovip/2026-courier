"""Deterministic, temporary-workspace proof of Courier's normal goal lifecycle."""
from __future__ import annotations

import tempfile
import unittest
import json
from pathlib import Path
from unittest.mock import patch

from scripts.courier_founder_mode import FounderModeMVP
from scripts.courier_safety_dispatcher import (
    CourierSafetyDispatcher,
    LocalWorkerAdapterBoundary,
    canonical_hash,
)
from scripts.worker_availability import AvailabilityEvidence, WorkerState


def _response(task: dict, *, status: str, payload: dict) -> dict:
    """Produce the same identity-bound response shape required at the boundary."""
    identity = {
        "schema_version": "1.0",
        "task_hash": task["task_hash"],
        "worker_id": task["worker_id"],
        "target_agent": task["target_agent"],
        "correlation_id": task.get("correlation_id", ""),
        "task_id": task.get("task_id", ""),
    }
    ack = {"type": "ACK", "status": "ACCEPTED", **identity}
    result = {
        "type": "RESULT",
        "status": status,
        "mission_id": task.get("mission_id", ""),
        "payload": payload,
        "result_fingerprint": canonical_hash(payload),
        **identity,
    }
    return {"ack": ack, "result": result}


class TestCourierCompleteLifecycle(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp.name)
        self.boundary = LocalWorkerAdapterBoundary(self.workspace)
        self.dispatcher = CourierSafetyDispatcher(self.workspace, self.boundary)
        self.implementation_attempts = 0

        self.boundary.register_consumer("CLI1", self._cli1)
        self.boundary.register_consumer("GEMINI", self._gemini)
        self.available = AvailabilityEvidence(
            worker="GEMINI", state=WorkerState.AVAILABLE, executable="/tmp/agy",
            resolution_method="TEST", detail="temporary lifecycle worker",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _cli1(self, task: dict) -> dict:
        action = task["payload"].get("action")
        if action == "verify_improvement_tests":
            payload = {"action": action, "test_returncode": 0, "verdict": "PASS"}
        else:
            self.fail(f"CLI1 received unsupported action: {action}")
        return _response(task, status="COMPLETED", payload=payload)

    def _gemini(self, task: dict) -> dict:
        action = task["payload"].get("action")
        if action == "discover_improvement_opportunities":
            payload = {
                "action": action,
                "weakness_id": "TEMPORARY_EFFECT",
                "description": "Create the requested local workspace effect.",
                "evidence": "temporary deterministic discovery evidence",
                "suggested_files": ["lifecycle_effect.txt"],
                "verification_strategy": "local_file_check",
                "confidence": 1.0,
                "verdict": "PASS",
            }
            return _response(task, status="COMPLETED", payload=payload)
        
        self.implementation_attempts += 1
        if self.implementation_attempts == 2:
            (self.workspace / "lifecycle_effect.txt").write_text("DONE", encoding="utf-8")
        payload = {
            "action": "implementation",
            "changed_files": ["lifecycle_effect.txt"],
            "verification_strategy": "local_file_check",
            "verdict": "PASS",
        }
        return _response(task, status="COMPLETED", payload=payload)

    def _run(self, goal: str):
        runtime = FounderModeMVP(str(self.workspace), self.dispatcher)
        runtime.intake.submit_goal(source="system", goal=goal)
        runtime.run_autonomous_loop()
        return runtime

    def test_complete_lifecycle_retries_once_then_satisfies_goal(self) -> None:
        runtime = self._run("Create a file named lifecycle_effect.txt containing exactly: DONE")
        goals = runtime.intake._read_no_lock()
        self.assertEqual(goals[0]["status"], "SATISFIED")
        self.assertEqual(self.implementation_attempts, 2)
        self.assertEqual((self.workspace / "lifecycle_effect.txt").read_text(encoding="utf-8"), "DONE")

        missions = runtime.queue.read_all()
        self.assertEqual([m["status"] for m in missions], ["VERIFIED", "VERIFIED", "VERIFIED"])
        self.assertEqual([m["preferred_agent"] for m in missions], ["GEMINI", "GEMINI", "CLI1"])
        self.assertEqual(missions[1]["claimed_by"], "founder_loop_1")

        with open(missions[2]["result_reference"], encoding="utf-8") as handle:
            self.assertEqual(json.load(handle)["target_agent"], "CLI1")
        lessons = runtime.memory._read()
        self.assertTrue(lessons and all(item.get("fingerprint") for item in lessons))

        ledger = self.dispatcher.ledger.get_reviewed_entry(missions[1]["task_hash"])
        self.assertEqual(ledger["file_hashes"]["worker_id"], "GEMINI")
        self.assertEqual(ledger["file_hashes"]["coordinator_worker_id"], "founder_loop_1")
        self.assertEqual(ledger["file_hashes"]["native_attempt"], "2")

    def test_human_gate_stops_without_successor_or_effect(self) -> None:
        def gated_gemini(task: dict) -> dict:
            payload = {"verdict": "HUMAN_GATE", "summary": "Login required"}
            return _response(task, status="HUMAN_GATE", payload=payload)

        self.boundary.register_consumer("GEMINI", gated_gemini)
        runtime = self._run("Create a file named lifecycle_effect.txt containing exactly: DONE")
        self.assertEqual(runtime.intake._read_no_lock()[0]["status"], "HUMAN_GATE")
        missions = runtime.queue.read_all()
        self.assertEqual([m["status"] for m in missions], ["VERIFIED", "HUMAN_GATE"])
        self.assertFalse((self.workspace / "lifecycle_effect.txt").exists())

    def test_underdetermined_write_goal_blocks_before_writer_dispatch(self) -> None:
        runtime = self._run("Create a repository-root file, but do not specify its name.")
        goal = runtime.intake._read_no_lock()[0]
        self.assertEqual(goal["status"], "BLOCKED")
        self.assertEqual(goal["blocker_evidence"]["planner_error"], "WRITE_ACCEPTANCE_CRITERIA_UNDERIVABLE")
        self.assertEqual(self.implementation_attempts, 0)
        self.assertEqual([m["status"] for m in runtime.queue.read_all()], ["VERIFIED"])


if __name__ == "__main__":
    unittest.main()
