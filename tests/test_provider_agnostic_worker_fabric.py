#!/usr/bin/env python3
"""Test suite for ProviderAgnosticWorkerFabric (Chief Architecture Acceptance Suite).

Verifies:
A. CLI1 registered and routable.
B. ANTIGRAVITY registered and routable.
C. CHATGPT registered but CONSERVE/RESERVE.
D. Suitable routine task routes to Google when Google capacity exists.
E. ChatGPT can become routable by policy change without code redesign.
F. Worker offline causes safe rerouting/recovery.
G. Hypothetical new worker registers without changing router core.
H. Two workers cannot claim conflicting task authority.
I. Result releases claim and produces next-work decision.
J. No human WEITER required in the continuation path.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.provider_agnostic_worker_fabric import (
    AvailabilityState,
    GenericResultEnvelope,
    GenericWorkerSlot,
    ProviderAgnosticWorkerFabric,
    ProviderType,
    RoutingPreference,
    SurfaceType,
)


class TestProviderAgnosticWorkerFabric(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="fabric_test_"))
        self.fabric = ProviderAgnosticWorkerFabric(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_default_3_slots_registered(self):
        """A, B, C: Verifies CLI1, ANTIGRAVITY_PRIMARY, and CHATGPT_CHIEF initial state."""
        self.assertIn("CLI1", self.fabric.workers)
        self.assertIn("ANTIGRAVITY_PRIMARY", self.fabric.workers)
        self.assertIn("CHATGPT_CHIEF", self.fabric.workers)

        cli1 = self.fabric.workers["CLI1"]
        self.assertEqual(cli1.provider, ProviderType.GOOGLE.value)
        self.assertEqual(cli1.availability_state, AvailabilityState.ACTIVE.value)

        antigravity = self.fabric.workers["ANTIGRAVITY_PRIMARY"]
        self.assertEqual(antigravity.provider, ProviderType.GOOGLE.value)
        self.assertEqual(antigravity.availability_state, AvailabilityState.ACTIVE.value)

        chatgpt = self.fabric.workers["CHATGPT_CHIEF"]
        self.assertEqual(chatgpt.provider, ProviderType.OPENAI.value)
        self.assertEqual(chatgpt.availability_state, AvailabilityState.RESERVE.value)
        self.assertEqual(chatgpt.routing_preference, RoutingPreference.CONSERVE.value)

    def test_02_routine_task_routes_to_google(self):
        """D: Routine build task routes to Google capacity."""
        dec = self.fabric.route_task(
            task_id="TASK-BUILD-01",
            task_class="ROUTINE_BUILD",
            required_capabilities=["ROUTINE_BUILD", "CODE_GENERATION"],
            required_scope="src/build",
        )
        self.assertEqual(dec.routing_verdict, "ROUTED_SUCCESS")
        self.assertEqual(dec.assigned_provider, ProviderType.GOOGLE.value)
        self.assertIn(dec.assigned_worker_id, ["CLI1", "ANTIGRAVITY_PRIMARY"])

    def test_03_chatgpt_routable_by_policy_change_or_strategic_task(self):
        """E: Strategic task or dynamic policy adjustment routes to ChatGPT without code redesign."""
        # 1. Strategic task routes to ChatGPT Chief
        dec_strat = self.fabric.route_task(
            task_id="TASK-STRAT-01",
            task_class="STRATEGIC_JUDGMENT",
            required_capabilities=["STRATEGIC_JUDGMENT", "CHIEF_AMBIGUITY"],
            required_scope="events/governance",
        )
        self.assertEqual(dec_strat.routing_verdict, "ROUTED_SUCCESS")
        self.assertEqual(dec_strat.assigned_worker_id, "CHATGPT_CHIEF")

        # 2. Dynamic policy adjustment
        self.fabric.set_routing_policy("CHATGPT_CHIEF", RoutingPreference.PREFERRED_ROUTINE, AvailabilityState.ACTIVE)
        cg = self.fabric.workers["CHATGPT_CHIEF"]
        self.assertEqual(cg.routing_preference, RoutingPreference.PREFERRED_ROUTINE.value)
        self.assertEqual(cg.availability_state, AvailabilityState.ACTIVE.value)

    def test_04_worker_offline_causes_safe_fallback(self):
        """F: Worker offline transitions gracefully without crash."""
        self.fabric.update_heartbeat("CLI1", state="BUSY")
        self.fabric.workers["CLI1"].availability_state = AvailabilityState.OFFLINE.value

        # Routing falls back to Antigravity
        dec = self.fabric.route_task(
            task_id="TASK-FALLBACK-01",
            task_class="ROUTINE_BUILD",
            required_capabilities=["CODE_GENERATION"],
            required_scope="src/core",
        )
        self.assertEqual(dec.routing_verdict, "ROUTED_SUCCESS")
        self.assertEqual(dec.assigned_worker_id, "ANTIGRAVITY_PRIMARY")

    def test_05_hot_plug_new_worker_on_computer_b(self):
        """G: Hot-plugs a new worker on COMPUTER_B without changing router core."""
        new_slot = GenericWorkerSlot(
            worker_id="COMPUTER_B_WORKER_01",
            provider=ProviderType.LOCAL.value,
            surface=SurfaceType.CLI.value,
            account_id="ACCOUNT_LOCAL_01",
            host="COMPUTER_B",
            role="HIGH_VOLUME_BUILDER",
            capabilities=["LOCAL_TEST", "ASSET_PACKAGING"],
            availability_state=AvailabilityState.ACTIVE.value,
            routing_preference=RoutingPreference.PREFERRED_ROUTINE.value,
        )
        self.fabric.register_worker(new_slot)
        self.assertIn("COMPUTER_B_WORKER_01", self.fabric.workers)

        # Route task requiring LOCAL_TEST
        dec = self.fabric.route_task(
            task_id="TASK-LOCAL-01",
            task_class="LOCAL_TEST",
            required_capabilities=["LOCAL_TEST"],
            required_scope="tests/local",
        )
        self.assertEqual(dec.routing_verdict, "ROUTED_SUCCESS")
        self.assertEqual(dec.assigned_worker_id, "COMPUTER_B_WORKER_01")
        self.assertEqual(dec.assigned_host, "COMPUTER_B")

    def test_06_collision_fencing_prevents_overlapping_scope(self):
        """H: Two workers cannot claim conflicting scope authority."""
        # First worker claims scope
        dec1 = self.fabric.route_task(
            task_id="TASK-SCOPE-A",
            task_class="BUILD",
            required_capabilities=["ROUTINE_BUILD"],
            required_scope="src/exclusive_engine",
        )
        self.assertEqual(dec1.routing_verdict, "ROUTED_SUCCESS")

        # Second worker attempts same scope
        dec2 = self.fabric.route_task(
            task_id="TASK-SCOPE-B",
            task_class="BUILD",
            required_capabilities=["PRIMARY_EXECUTION"],
            required_scope="src/exclusive_engine",
        )
        self.assertEqual(dec2.routing_verdict, "BLOCKED_COLLISION")

    def test_07_result_submission_releases_claim_and_continues(self):
        """I, J: Envelope submission releases claim and produces decision without WEITER."""
        dec = self.fabric.route_task(
            task_id="TASK-SUBMIT-01",
            task_class="BUILD",
            required_capabilities=["ROUTINE_BUILD"],
            required_scope="src/module_a",
        )
        self.assertEqual(dec.routing_verdict, "ROUTED_SUCCESS")

        envelope = GenericResultEnvelope(
            task_id="TASK-SUBMIT-01",
            worker_id=dec.assigned_worker_id,
            provider=dec.assigned_provider,
            surface=dec.assigned_surface,
            host=dec.assigned_host,
            started_at="2026-09-01T15:00:00+00:00",
            completed_at="2026-09-01T15:01:00+00:00",
            result_state="SUCCESS",
            artifacts_changed=["src/module_a.py"],
            verification={"tests_passed": 10},
            evidence={"capital_spent_eur": 0.0},
            economic_delta={"expected_value_eur": 49.0},
            blockers=[],
            next_candidate_actions=["DEPLOY_MODULE_A"],
            fingerprint="abc123fingerprint",
        )

        res = self.fabric.submit_result_and_continue(envelope=envelope, released_scope="src/module_a")
        self.assertEqual(res["status"], "RESULT_PROCESSED_AND_CHAIN_CONTINUED")
        self.assertFalse(res["human_weiter_required"])

        # Proves scope was released and can be claimed again
        dec_next = self.fabric.route_task(
            task_id="TASK-SUBMIT-02",
            task_class="BUILD",
            required_capabilities=["ROUTINE_BUILD"],
            required_scope="src/module_a",
        )
        self.assertEqual(dec_next.routing_verdict, "ROUTED_SUCCESS")


if __name__ == "__main__":
    unittest.main()
