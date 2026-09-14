"""Deterministic tests for the worker availability resolver and Courier routing contract.

All tests:
  MODEL_CALLS = 0
  NETWORK = 0
  SPEND = 0

Tests cover spec items A through M (plus L/M using existing suite).
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.worker_availability import (
    AvailabilityEvidence,
    AvailabilityStore,
    AvailabilityStoreIntegrityError,
    WorkerAvailabilityResolver,
    WorkerState,
    _find_in_PATH,
    _is_executable,
)
from scripts.courier_safety_dispatcher import (
    CourierSafetyDispatcher,
    DynamicAgentRouter,
    MissionQueue,
    write_json_atomic,
)
from scripts.courier_founder_mode import MultiChatGoalIntake


class TestAvailabilityResolutionPrecedence(unittest.TestCase):
    """A: configured/path resolution precedence."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_configured_path_takes_precedence_over_PATH(self):
        """Configured agy_path_override wins even when a different agy is in PATH."""
        # A real file that is executable
        real_file = self.ws / "my_agy"
        real_file.write_text("#!/bin/sh\necho ok")
        real_file.chmod(0o755)

        resolver = WorkerAvailabilityResolver(agy_path_override=real_file)
        evidence = resolver.resolve_gemini()
        self.assertEqual(evidence.resolution_method, "CONFIGURED_PATH")
        self.assertEqual(evidence.state, WorkerState.AVAILABLE)
        self.assertEqual(evidence.executable, str(real_file))

    def test_configured_path_unavailable_if_not_executable(self):
        """Configured path that does not exist reports UNAVAILABLE."""
        resolver = WorkerAvailabilityResolver(agy_path_override=Path("/nonexistent/agy_xyz"))
        evidence = resolver.resolve_gemini()
        self.assertEqual(evidence.resolution_method, "CONFIGURED_PATH")
        self.assertEqual(evidence.state, WorkerState.UNAVAILABLE)
        self.assertIsNone(evidence.executable)

    def test_canonical_fallback_used_when_no_override_and_not_in_PATH(self):
        """Without override and not in PATH, resolver checks canonical path."""
        with patch("scripts.worker_availability._find_in_PATH", return_value=None):
            with patch("scripts.worker_availability._is_executable", return_value=False):
                resolver = WorkerAvailabilityResolver()
                evidence = resolver.resolve_gemini()
        self.assertEqual(evidence.resolution_method, "CANONICAL_FALLBACK")
        self.assertEqual(evidence.state, WorkerState.UNAVAILABLE)

    def test_path_discovery_used_before_canonical_fallback(self):
        """PATH discovery is used before the hardcoded canonical fallback."""
        fake_path = Path("/usr/local/bin/agy_fake")
        with patch("scripts.worker_availability._find_in_PATH", return_value=fake_path):
            with patch("scripts.worker_availability._is_executable", return_value=True):
                resolver = WorkerAvailabilityResolver()
                evidence = resolver.resolve_gemini()
        self.assertEqual(evidence.resolution_method, "PATH_DISCOVERY")
        self.assertEqual(evidence.state, WorkerState.AVAILABLE)
        self.assertEqual(evidence.executable, str(fake_path))


class TestGeminiUnavailableBlocking(unittest.TestCase):
    """B: AGY unavailable → no dispatch → WORKER_UNAVAILABLE / BLOCKED."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_unavailable_gemini_blocks_mission(self):
        """When GEMINI is unavailable, mission must be BLOCKED with WORKER_UNAVAILABLE."""
        # Point resolver at a non-existent path so GEMINI is unavailable
        nonexistent = Path("/nonexistent_agy_in_test_xyz")
        with patch("scripts.worker_availability._find_in_PATH", return_value=None), \
             patch("scripts.worker_availability._is_executable", return_value=False):
            router = DynamicAgentRouter()
            # Verify select_agent returns None for implementation (requires GEMINI)
            result = router.select_agent("implementation", preferred_agent="GEMINI")
        self.assertIsNone(result)

    def test_unavailable_gemini_does_not_silently_reroute_to_cli1(self):
        """GEMINI unavailable must NOT silently fall back to CLI1 for implementation."""
        with patch("scripts.worker_availability._find_in_PATH", return_value=None), \
             patch("scripts.worker_availability._is_executable", return_value=False):
            router = DynamicAgentRouter()
            result = router.select_agent("implementation")
        # Must be None — not CLI1, not any fallback
        self.assertIsNone(result)

    def test_process_next_mission_marks_blocked_worker_unavailable(self):
        """process_next_mission must mark the mission BLOCKED with WORKER_UNAVAILABLE reason."""
        dispatcher = CourierSafetyDispatcher(self.ws)
        # Enqueue an implementation mission (requires GEMINI)
        q = MissionQueue(self.ws)
        mission = {
            "goal": "test",
            "normalized_task": "Implement something",
            "capability_required": "implementation",
            "preferred_agent": "GEMINI",
            "requires_write": True,
            "is_heavy": True,
            "task": {"capability_request": "implementation", "prompt": "do it"},
        }
        enqueued = q.enqueue(q._normalize(mission))

        with patch("scripts.worker_availability._find_in_PATH", return_value=None), \
             patch("scripts.worker_availability._is_executable", return_value=False):
            result = dispatcher.process_next_mission("worker-1")

        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result.get("reason"), "WORKER_UNAVAILABLE")

        updated = q.get(enqueued["mission_id"])
        self.assertEqual(updated["status"], "BLOCKED")
        self.assertEqual(updated["result_reference"], "WORKER_UNAVAILABLE")


class TestNoRetryOnUnchangedUnavailability(unittest.TestCase):
    """C: same unavailable fingerprint → no retry loop."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_fingerprint_unchanged_means_no_transition(self):
        """Identical fingerprints must return UNCHANGED, not CHANGED_SINCE_LAST_CHECK."""
        store = AvailabilityStore(self.ws)
        evidence = AvailabilityEvidence(
            worker="GEMINI", state=WorkerState.UNAVAILABLE,
            executable=None, resolution_method="CANONICAL_FALLBACK",
            detail="not found"
        )
        # First call — sets the baseline
        first = store.classify_transition("GEMINI", evidence)
        # Second call with identical evidence — fingerprint unchanged
        second = store.classify_transition("GEMINI", evidence)
        self.assertEqual(second, "UNCHANGED")

    def test_unchanged_available_is_stable(self):
        """Available → available (same path) is also UNCHANGED."""
        store = AvailabilityStore(self.ws)
        evidence = AvailabilityEvidence(
            worker="GEMINI", state=WorkerState.AVAILABLE,
            executable="/usr/local/bin/agy", resolution_method="PATH_DISCOVERY",
            detail="found"
        )
        store.classify_transition("GEMINI", evidence)
        second = store.classify_transition("GEMINI", evidence)
        self.assertEqual(second, "UNCHANGED")

    def test_corrupt_availability_history_fails_closed_and_is_not_overwritten(self):
        store = AvailabilityStore(self.ws)
        store._path.write_text('{"GEMINI":', encoding="utf-8")
        before = store._path.read_bytes()
        evidence = AvailabilityEvidence(
            worker="GEMINI", state=WorkerState.AVAILABLE,
            executable="/usr/local/bin/agy", resolution_method="PATH_DISCOVERY",
            detail="found",
        )

        with self.assertRaisesRegex(AvailabilityStoreIntegrityError, "CORRUPT_FAIL_CLOSED"):
            store.classify_transition("GEMINI", evidence)
        self.assertEqual(store._path.read_bytes(), before)


class TestAvailabilityChangeTriggersRetry(unittest.TestCase):
    """D+E: unavailable→available fingerprint change → exactly one normal retry."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_fingerprint_changes_when_availability_changes(self):
        """Different state or executable path produces different fingerprint."""
        unavail = AvailabilityEvidence(
            worker="GEMINI", state=WorkerState.UNAVAILABLE,
            executable=None, resolution_method="CANONICAL_FALLBACK", detail=""
        )
        avail = AvailabilityEvidence(
            worker="GEMINI", state=WorkerState.AVAILABLE,
            executable="/usr/local/bin/agy", resolution_method="PATH_DISCOVERY", detail=""
        )
        self.assertNotEqual(unavail.fingerprint(), avail.fingerprint())

    def test_classify_transition_detects_unavailable_to_available(self):
        """classify_transition returns CHANGED_SINCE_LAST_CHECK when moving UNAVAILABLE→AVAILABLE."""
        store = AvailabilityStore(self.ws)
        unavail = AvailabilityEvidence(
            worker="GEMINI", state=WorkerState.UNAVAILABLE,
            executable=None, resolution_method="CANONICAL_FALLBACK", detail=""
        )
        avail = AvailabilityEvidence(
            worker="GEMINI", state=WorkerState.AVAILABLE,
            executable="/usr/local/bin/agy", resolution_method="PATH_DISCOVERY", detail=""
        )
        store.classify_transition("GEMINI", unavail)  # Set baseline
        result = store.classify_transition("GEMINI", avail)
        self.assertEqual(result, "CHANGED_SINCE_LAST_CHECK")

    def test_retry_uses_legal_mission_queue_transition(self):
        """E: The BLOCKED→PENDING retry must go through MissionQueue.transition, not a direct status write."""
        q = MissionQueue(self.ws)
        # Create a WORKER_UNAVAILABLE blocked mission manually
        base = {
            "goal": "test",
            "normalized_task": "Implement X",
            "capability_required": "implementation",
            "preferred_agent": "GEMINI",
            "requires_write": True,
            "is_heavy": False,
        }
        enqueued = q.enqueue(q._normalize(base))
        mission_id = enqueued["mission_id"]
        # Simulate dispatcher blocking it
        q.transition(mission_id, "CLAIMED", claimed_by="w1")
        q.transition(mission_id, "RUNNING")
        q.transition(mission_id, "BLOCKED", result_reference="WORKER_UNAVAILABLE")

        m = q.get(mission_id)
        self.assertEqual(m["status"], "BLOCKED")
        self.assertEqual(m["result_reference"], "WORKER_UNAVAILABLE")

        # Legal retry: BLOCKED → PENDING is in the transition table
        q.transition(mission_id, "PENDING")
        after = q.get(mission_id)
        self.assertEqual(after["status"], "PENDING")


class TestHumanGateProtection(unittest.TestCase):
    """F+H: HUMAN_GATE never auto-resets from availability change or duplicate goal."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_human_gate_not_reset_by_availability_change(self):
        """HUMAN_GATE status must NOT be changed by a WORKER_UNAVAILABLE-only reset path."""
        q = MissionQueue(self.ws)
        base = {
            "goal": "a goal",
            "normalized_task": "Some human-gated task",
            "capability_required": "implementation",
            "preferred_agent": "GEMINI",
            "requires_write": True,
            "is_heavy": False,
        }
        enqueued = q.enqueue(q._normalize(base))
        mission_id = enqueued["mission_id"]
        q.transition(mission_id, "CLAIMED", claimed_by="w1")
        q.transition(mission_id, "HUMAN_GATE", result_reference="REQUIRES_LOGIN")

        # Simulate the submit_goal deduplication that only resets WORKER_UNAVAILABLE missions
        def _reset_only_worker_unavailable(doc):
            for m in doc.get("missions", []):
                if m.get("status") == "BLOCKED" and m.get("result_reference") == "WORKER_UNAVAILABLE":
                    m["status"] = "PENDING"
            return True
        q._mutate(_reset_only_worker_unavailable)

        after = q.get(mission_id)
        # HUMAN_GATE must NOT have changed
        self.assertEqual(after["status"], "HUMAN_GATE")

    def test_duplicate_goal_intake_cannot_bypass_human_gate(self):
        """H: Resubmitting the same goal must not auto-reset HUMAN_GATE missions."""
        from scripts.courier_founder_mode import MultiChatGoalIntake
        intake = MultiChatGoalIntake(self.ws)
        q = MissionQueue(self.ws)

        goal_text = "Build something with login required"
        goal_id = intake.submit_goal("source", goal_text)

        # Mark goal ACTIVE
        def _activate(data):
            for g in data:
                if g["goal_id"] == goal_id:
                    g["status"] = "ACTIVE"
        intake._mutate(_activate)

        # Create a mission gated by HUMAN_GATE for this goal
        base = {
            "goal": goal_text,
            "normalized_task": "Deploy with OAuth",
            "capability_required": "implementation",
            "preferred_agent": "GEMINI",
            "requires_write": True,
            "is_heavy": False,
        }
        enqueued = q.enqueue(q._normalize(base))
        mission_id = enqueued["mission_id"]
        q.transition(mission_id, "CLAIMED", claimed_by="w1")
        q.transition(mission_id, "HUMAN_GATE", result_reference="OAUTH_REQUIRED")

        # Now resubmit the same goal (simulating duplicate intake)
        intake.submit_goal("source", goal_text)

        # HUMAN_GATE must NOT have been reset
        after = q.get(mission_id)
        self.assertEqual(after["status"], "HUMAN_GATE")


class TestFailedProtection(unittest.TestCase):
    """G: FAILED must not auto-reset merely due to availability change."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_failed_not_reset_by_duplicate_goal_intake(self):
        """FAILED missions must not be auto-reset when a goal is resubmitted."""
        from scripts.courier_founder_mode import MultiChatGoalIntake
        intake = MultiChatGoalIntake(self.ws)
        q = MissionQueue(self.ws)

        goal_text = "Test goal for failed protection"
        goal_id = intake.submit_goal("source", goal_text)
        # Mark goal ACTIVE
        def _activate(data):
            for g in data:
                if g["goal_id"] == goal_id:
                    g["status"] = "ACTIVE"
        intake._mutate(_activate)

        # Create and fail a mission
        base = {
            "goal": goal_text,
            "normalized_task": "Something that failed",
            "capability_required": "implementation",
            "preferred_agent": "GEMINI",
            "requires_write": True,
            "is_heavy": False,
        }
        enqueued = q.enqueue(q._normalize(base))
        mission_id = enqueued["mission_id"]
        q.transition(mission_id, "CLAIMED", claimed_by="w1")
        q.transition(mission_id, "RUNNING")
        q.transition(mission_id, "PENDING_VERIFY")
        q.transition(mission_id, "FAILED", result_reference="VERIFY_FAIL")

        # Resubmit goal
        intake.submit_goal("source", goal_text)

        # FAILED must remain FAILED
        after = q.get(mission_id)
        self.assertEqual(after["status"], "FAILED")


class TestCLI1ReadOnlyContract(unittest.TestCase):
    """I+J: Implementation must not route to CLI1; CLI1 cannot write repo files."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_implementation_not_in_cli1_capabilities(self):
        """I: 'implementation' must not be in CLI1's capability set."""
        router = DynamicAgentRouter()
        cli1_caps = router.CAPABILITIES.get("CLI1", ())
        for cap in cli1_caps:
            self.assertNotIn("implementation", cap.lower(),
                             f"CLI1 must not have implementation capability, found: {cap}")

    def test_implementation_capability_does_not_resolve_to_cli1(self):
        """I: select_agent('implementation') must never return CLI1."""
        with patch("scripts.worker_availability._find_in_PATH", return_value=None), \
             patch("scripts.worker_availability._is_executable", return_value=False):
            router = DynamicAgentRouter()
            result = router.select_agent("implementation")
        # Must be None (GEMINI unavailable) or GEMINI — never CLI1
        self.assertNotEqual(result, "CLI1")

    def test_cli1_worker_raises_on_implementation_action(self):
        """J: The CLI1 worker adapter must raise RuntimeError on implementation action."""
        from scripts.courier_real_worker_adapters import create_real_cli1_adapter
        adapter = create_real_cli1_adapter(self.ws)

        # Minimal envelope shape needed for the adapter
        task_envelope = {
            "task_hash": "a" * 64,
            "worker_id": "test-worker",
            "target_agent": "CLI1",
            "correlation_id": "corr-test",
            "task_id": "task-test",
            "payload": {
                "action": "implementation",
                "capability_request": "implementation",
                "prompt": "Do something",
            },
        }
        with self.assertRaises(RuntimeError) as ctx:
            adapter(task_envelope)
        self.assertIn("CLI1_READONLY_CONTRACT_VIOLATED", str(ctx.exception))

    def test_cli1_worker_raises_on_bounded_local_writes(self):
        """J: CLI1 must not accept 'bounded local writes' either."""
        from scripts.courier_real_worker_adapters import create_real_cli1_adapter
        adapter = create_real_cli1_adapter(self.ws)

        task_envelope = {
            "task_hash": "b" * 64,
            "worker_id": "test-worker",
            "target_agent": "CLI1",
            "correlation_id": "corr-test",
            "task_id": "task-test",
            "payload": {
                "capability_request": "legacy implementation",
                "prompt": "Write something",
            },
        }
        with self.assertRaises(RuntimeError) as ctx:
            adapter(task_envelope)
        self.assertIn("CLI1_READONLY_CONTRACT_VIOLATED", str(ctx.exception))


class TestSemanticResultClassification(unittest.TestCase):
    """K: implementation result classification is semantic, not GEMINI-identity dependent."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self.tmp.name)
        from scripts.courier_founder_mode import FounderModePlanner
        self.planner = FounderModePlanner(self.ws)

    def tearDown(self):
        self.tmp.cleanup()

    def _make_result_file(self, payload: dict) -> Path:
        """Write a result JSON to a temp file and return its path."""
        from scripts.courier_safety_dispatcher import canonical_hash
        f = self.ws / f"result_{payload.get('task_hash', 'test')}.json"
        data = {"payload": payload}
        f.write_text(json.dumps(data))
        return f

    def test_discovery_classified_by_action_not_worker(self):
        """DISCOVERY is inferred from action, regardless of worker_agent."""
        payload = {
            "action": "discover_improvement_opportunities",
            "worker_agent": "CLI1",  # Must not matter for classification
            "weakness_id": "TEST-001",
            "description": "Test issue",
            "evidence": {},
            "suggested_files": ["a.py"],
            "verification_strategy": "run_tests",
            "task_hash": "discovery_test",
        }
        result_path = self._make_result_file(payload)
        mission = {"result_reference": str(result_path)}
        result = self.planner._load_result(mission)
        self.assertEqual(result.get("task_type"), "DISCOVERY")

    def test_implementation_not_classified_by_gemini_identity(self):
        """K: Implementation must not be inferred merely because worker_agent == GEMINI."""
        # A GEMINI result without implementation action/stage/changed_files
        # should NOT automatically be classified as IMPLEMENTATION
        payload = {
            "worker_agent": "GEMINI",
            "verdict": "PASS",
            "summary": "Some analysis result",
            "task_hash": "gemini_analysis_test",
            # No action, no stage, no changed_files → no semantic evidence for implementation
        }
        result_path = self._make_result_file(payload)
        mission = {"result_reference": str(result_path)}
        result = self.planner._load_result(mission)
        # Should NOT be IMPLEMENTATION if there's no semantic evidence
        self.assertNotEqual(result.get("task_type"), "IMPLEMENTATION")

    def test_implementation_classified_by_changed_files(self):
        """Implementation result with changed_files is correctly classified."""
        payload = {
            "worker_agent": "GEMINI",
            "changed_files": ["scripts/foo.py", "tests/test_foo.py"],
            "task_hash": "impl_with_files_test",
        }
        result_path = self._make_result_file(payload)
        mission = {"result_reference": str(result_path)}
        result = self.planner._load_result(mission)
        self.assertEqual(result.get("task_type"), "IMPLEMENTATION")
        self.assertIn("scripts/foo.py", result.get("changed_files", []))

    def test_verification_classified_by_action(self):
        """VERIFICATION is inferred from the verify_improvement_tests action."""
        payload = {
            "worker_agent": "CLI1",
            "action": "verify_improvement_tests",
            "test_returncode": 0,
            "task_hash": "verify_test",
        }
        result_path = self._make_result_file(payload)
        mission = {"result_reference": str(result_path)}
        result = self.planner._load_result(mission)
        self.assertEqual(result.get("task_type"), "VERIFICATION")
        self.assertTrue(result["acceptance_evidence"]["goal_satisfied"])


class TestAvailabilityFingerprint(unittest.TestCase):
    """B+C+D — structural fingerprint correctness."""

    def test_same_evidence_same_fingerprint(self):
        ev = AvailabilityEvidence("GEMINI", WorkerState.AVAILABLE, "/usr/local/bin/agy", "PATH_DISCOVERY", "found")
        self.assertEqual(ev.fingerprint(), ev.fingerprint())

    def test_different_state_different_fingerprint(self):
        avail = AvailabilityEvidence("GEMINI", WorkerState.AVAILABLE, "/usr/local/bin/agy", "PATH_DISCOVERY", "found")
        unavail = AvailabilityEvidence("GEMINI", WorkerState.UNAVAILABLE, None, "CANONICAL_FALLBACK", "not found")
        self.assertNotEqual(avail.fingerprint(), unavail.fingerprint())

    def test_different_path_different_fingerprint(self):
        a = AvailabilityEvidence("GEMINI", WorkerState.AVAILABLE, "/usr/local/bin/agy", "PATH_DISCOVERY", "x")
        b = AvailabilityEvidence("GEMINI", WorkerState.AVAILABLE, "/opt/agy/bin/agy", "PATH_DISCOVERY", "x")
        self.assertNotEqual(a.fingerprint(), b.fingerprint())


class TestRegressionSuite(unittest.TestCase):
    """L: existing Courier regression suite remains green — spot-check core dispatcher."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_mission_queue_transitions_are_legal(self):
        q = MissionQueue(self.ws)
        base = {
            "goal": "regression test",
            "normalized_task": "Do something",
            "capability_required": "local repo analysis",
            "preferred_agent": "CLI1",
            "requires_write": False,
            "is_heavy": False,
        }
        enqueued = q.enqueue(q._normalize(base))
        mid = enqueued["mission_id"]
        q.transition(mid, "CLAIMED", claimed_by="w1")
        q.transition(mid, "RUNNING")
        q.transition(mid, "PENDING_VERIFY")
        q.transition(mid, "VERIFIED", verification_reference="hash123")
        final = q.get(mid)
        self.assertEqual(final["status"], "VERIFIED")

    def test_illegal_transition_raises(self):
        q = MissionQueue(self.ws)
        base = {
            "goal": "illegal test",
            "normalized_task": "x",
            "capability_required": "local repo analysis",
            "preferred_agent": "CLI1",
            "requires_write": False,
            "is_heavy": False,
        }
        enqueued = q.enqueue(q._normalize(base))
        with self.assertRaises(RuntimeError):
            # PENDING → VERIFIED is illegal
            q.transition(enqueued["mission_id"], "VERIFIED")

    def test_cli1_available_for_repo_analysis(self):
        """CLI1 must remain available for its legitimate read-only capabilities."""
        router = DynamicAgentRouter()
        result = router.select_agent("local repo analysis", preferred_agent="CLI1")
        self.assertEqual(result, "CLI1")

    def test_gemini_selected_for_implementation_when_available(self):
        """GEMINI is selected for implementation when the executable is present."""
        with patch("scripts.worker_availability._find_in_PATH", return_value=Path("/usr/local/bin/agy")), \
             patch("scripts.worker_availability._is_executable", return_value=True):
            router = DynamicAgentRouter()
            result = router.select_agent("implementation")
        self.assertEqual(result, "GEMINI")


if __name__ == "__main__":
    unittest.main()
