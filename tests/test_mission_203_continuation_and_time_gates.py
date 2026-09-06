#!/usr/bin/env python3
"""Focused Mission 203/205 continuation and authority acceptance tests.

All effects below are synthetic local fixtures. No network, provider, mail,
or publication action is invoked by this suite.
"""

import datetime as dt
import json
import multiprocessing
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.evaluate_revenue_conversion_state import RevenueConversionEvaluator
from scripts.opportunity_queue import Opportunity, OpportunityQueue
from scripts.persistent_organization_daemon import PersistentOrganizationDaemon


def _claim_worker(repo_path: str, owner: str, output: multiprocessing.Queue) -> None:
    queue = OpportunityQueue(repo_dir=Path(repo_path))
    claimed, reason, claim = queue.claim_opportunity("RACE", owner)
    output.put({"claimed": claimed, "reason": reason, "generation": claim.get("authority_generation")})


class TestMission203ContinuationAndTimeGates(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="m205_continuation_"))
        for path in (
            self.test_dir / "events" / "runtime-state",
            self.test_dir / "events" / "revenue-opportunities" / "market_intelligence",
            self.test_dir / "events" / "revenue-opportunities" / "offerings" / "b2b_autonomy_audit",
            self.test_dir / "events" / "locks",
        ):
            path.mkdir(parents=True, exist_ok=True)
        self.daemon = PersistentOrganizationDaemon(repo_dir=self.test_dir)
        self.market_intel_dir = self.test_dir / "events" / "revenue-opportunities" / "market_intelligence"

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _spec(self, **overrides):
        spec = {
            "prospect_alias": "P-01",
            "correlation_id": "CORR-P01-TEST",
            "followup_fingerprint": "p01-v1",
            "generation": 1,
            "eligible_at": (dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=1)).isoformat(),
            "current_status": "PREPARED",
        }
        spec.update(overrides)
        path = self.market_intel_dir / "FINAL_P01_FOLLOWUP_SPEC.json"
        path.write_text(json.dumps(spec), encoding="utf-8")
        return path

    def _add_safe(self, opportunity_id="TASK-A", **overrides):
        values = {
            "opportunity_id": opportunity_id,
            "source": "TEST",
            "objective_id": opportunity_id,
            "project": "2026-courier",
            "description": "Synthetic deterministic local validation",
            "risk": "LOW",
            "estimated_cost": 0.0,
            "heavy_job": False,
            "model_need": False,
            "external_action_units": 0,
            "allowed_scope": [],
            "allowed_actions": ["READ"],
            "dedupe_fingerprint": f"fp-{opportunity_id}",
        }
        values.update(overrides)
        queue = OpportunityQueue(repo_dir=self.test_dir)
        self.assertTrue(queue.add_opportunity(Opportunity(**values)))
        return queue

    def _durable_result(self, queue, opportunity_id, claim, **payload):
        result = {
            "schema_version": "1.0",
            "result_type": "LOCAL_VALIDATION_RESULT",
            "task_id": queue.canonical_task_id(opportunity_id, claim["state_version"]),
            "opportunity_id": opportunity_id,
            "claim_id": claim["claim_id"],
            "generation": claim["state_version"],
            "status": "SUCCESS",
            "handler": "DETERMINISTIC_LOCAL_VALIDATION",
            "completed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "metadata": {},
            **payload,
        }
        result["result_fingerprint"] = queue.expected_result_fingerprint(queue.get_opportunity(opportunity_id), claim, result)
        return result

    def test_future_time_gate_is_event_watch_without_mutation(self):
        path = self._spec(eligible_at=(dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=12)).isoformat())
        self.assertIsNone(self.daemon.evaluate_time_gated_followups())
        self.assertIsNotNone(self.daemon.next_time_gate_at)
        self.assertEqual(json.loads(path.read_text())["current_status"], "PREPARED")

    def test_deadline_without_authorization_parks(self):
        path = self._spec()
        result = self.daemon.evaluate_time_gated_followups()
        self.assertIsNone(result)
        stored = json.loads(path.read_text())
        self.assertEqual(stored["current_status"], "WAITING_FOR_HUMAN")
        self.assertNotIn("sent_at", stored)

    def test_confirmed_synthetic_effect_applies_once(self):
        path = self._spec(authorization={"status": "AUTHORIZED", "authorization_id": "AUTH-TEST"}, effect_adapter="SYNTHETIC_CONFIRMED")
        first = self.daemon.evaluate_time_gated_followups()
        second = self.daemon.evaluate_time_gated_followups()
        self.assertEqual(first["status"], "APPLIED")
        self.assertIsNone(second)
        stored = json.loads(path.read_text())
        self.assertEqual(stored["current_status"], "APPLIED")
        self.assertTrue(stored["result"]["result_fingerprint"])
        self.assertIsNone(stored["sent_at"])

    def test_started_effect_becomes_unknown_and_is_not_resent(self):
        path = self._spec(authorization={"status": "AUTHORIZED", "authorization_id": "AUTH-TEST"}, effect_adapter="SYNTHETIC_CONFIRMED", simulate_crash_after_start=True)
        self.assertEqual(self.daemon.evaluate_time_gated_followups()["status"], "EFFECT_STARTED")
        restarted = PersistentOrganizationDaemon(repo_dir=self.test_dir)
        self.assertEqual(restarted.evaluate_time_gated_followups()["status"], "EFFECT_UNKNOWN")
        self.assertIsNone(restarted.evaluate_time_gated_followups())
        self.assertEqual(json.loads(path.read_text())["current_status"], "EFFECT_UNKNOWN")

    def test_persisted_effect_result_is_applied_after_restart_without_replay(self):
        path = self._spec(
            authorization={"status": "AUTHORIZED", "authorization_id": "AUTH-TEST"},
            effect_adapter="SYNTHETIC_CONFIRMED",
            simulate_crash_after_result=True,
        )
        self.assertEqual(self.daemon.evaluate_time_gated_followups()["status"], "RESULT_PERSISTED")
        restarted = PersistentOrganizationDaemon(repo_dir=self.test_dir)
        self.assertEqual(restarted.evaluate_time_gated_followups()["status"], "APPLIED")
        self.assertIsNone(restarted.evaluate_time_gated_followups())
        self.assertEqual(json.loads(path.read_text())["current_status"], "APPLIED")

    def test_early_reply_suppresses_before_effect(self):
        path = self._spec(authorization={"status": "AUTHORIZED", "authorization_id": "AUTH-TEST"}, effect_adapter="SYNTHETIC_CONFIRMED")
        tracker = self.test_dir / "events" / "revenue-opportunities" / "offerings" / "b2b_autonomy_audit" / "outreach_tracker.json"
        tracker.write_text(json.dumps({"prospects": [{"id": "P-01", "response_state": "POSITIVE_INTEREST"}]}), encoding="utf-8")
        self.assertEqual(self.daemon.evaluate_time_gated_followups()["status"], "SUPPRESSED_DUE_TO_INBOUND_REPLY")
        self.assertEqual(json.loads(path.read_text())["current_status"], "SUPPRESSED_DUE_TO_INBOUND_REPLY")

    def test_canonical_queue_claim_result_then_completion(self):
        self._add_safe("TASK-A")
        result = self.daemon.evaluate_opportunity_queue_work()
        self.assertEqual(result["status"], "SUCCESS")
        queue = OpportunityQueue(repo_dir=self.test_dir)
        self.assertEqual(queue.get_opportunity("TASK-A").status, "COMPLETED")
        self.assertTrue((self.test_dir / "events" / "opportunity-queue" / "results" / "TASK-A.result.json").is_file())
        self.assertFalse((self.test_dir / "events" / "opportunity-queue" / "claims" / "TASK-A.claim.json").exists())

    def test_gated_ready_work_is_parked_and_safe_work_continues(self):
        self._add_safe("SAFE")
        self._add_safe("HUMAN", evidence={"human_gate": True})
        self._add_safe("PAYMENT", estimated_cost=1.0)
        self._add_safe("WRITE", allowed_actions=["WRITE"])
        self.assertEqual(self.daemon.evaluate_opportunity_queue_work()["opportunity_id"], "SAFE")
        queue = OpportunityQueue(repo_dir=self.test_dir)
        self.assertEqual(queue.get_opportunity("HUMAN").status, "READY")
        self.assertEqual(queue.get_opportunity("PAYMENT").status, "READY")
        self.assertEqual(queue.get_opportunity("WRITE").status, "READY")

    def test_safe_work_prevents_idle_and_continues_without_manual_relay(self):
        self._add_safe("TASK-A")
        self._add_safe("TASK-B")
        first = self.daemon.execute_next_eligible_work()
        second = self.daemon.execute_next_eligible_work()
        self.assertEqual({first["opportunity_id"], second["opportunity_id"]}, {"TASK-A", "TASK-B"})
        self.assertNotEqual(first["opportunity_id"], second["opportunity_id"])
        self.assertIsNone(self.daemon.execute_next_eligible_work())

    def test_bounded_synthetic_continuation_effect_canary(self):
        self._add_safe("TASK-A")
        self._add_safe("TASK-B")
        completed = [self.daemon.execute_next_eligible_work(), self.daemon.execute_next_eligible_work()]
        self.assertEqual({item["opportunity_id"] for item in completed}, {"TASK-A", "TASK-B"})
        self.assertIsNone(self.daemon.execute_next_eligible_work())

        path = self._spec(eligible_at=(dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1)).isoformat())
        self.assertIsNone(self.daemon.execute_next_eligible_work())
        self.assertIsNotNone(self.daemon.next_time_gate_at)

        eligible = json.loads(path.read_text())
        eligible.update({
            "eligible_at": (dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=1)).isoformat(),
            "authorization": {"status": "AUTHORIZED", "authorization_id": "AUTH-CANARY"},
            "effect_adapter": "SYNTHETIC_CONFIRMED",
        })
        path.write_text(json.dumps(eligible), encoding="utf-8")
        wake = self.daemon.execute_next_eligible_work()
        self.assertEqual(wake["status"], "APPLIED")
        self.assertIsNone(self.daemon.execute_next_eligible_work())

    def test_updated_canary_recovery_park_continue_then_apply(self):
        queue = self._add_safe("CANARY-A")
        self._add_safe("CANARY-B")
        claimed, _, claim = queue.claim_opportunity("CANARY-A", "canary-owner")
        self.assertTrue(claimed)
        result_path = self.test_dir / "events" / "opportunity-queue" / "results" / "CANARY-A.result.json"
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(json.dumps(self._durable_result(queue, "CANARY-A", claim)), encoding="utf-8")

        restarted = PersistentOrganizationDaemon(repo_dir=self.test_dir)
        self.assertEqual(restarted.execute_next_eligible_work()["status"], "RESULT_RECONCILED")
        gate_path = self._spec()
        self.assertEqual(restarted.execute_next_eligible_work()["opportunity_id"], "CANARY-B")
        self.assertEqual(restarted.execute_next_eligible_work()["status"], "WAITING_GATE")

        authorized = json.loads(gate_path.read_text())
        authorized.update({
            "authorization": {"status": "AUTHORIZED", "authorization_id": "AUTH-CANARY-207"},
            "effect_adapter": "SYNTHETIC_CONFIRMED",
        })
        gate_path.write_text(json.dumps(authorized), encoding="utf-8")
        self.assertEqual(restarted.execute_next_eligible_work()["status"], "APPLIED")
        self.assertIsNone(restarted.execute_next_eligible_work())

    def test_result_is_required_and_stale_claim_cannot_complete(self):
        queue = self._add_safe("RESULT")
        claimed, _, claim = queue.claim_opportunity("RESULT", "test-owner")
        self.assertTrue(claimed)
        self.assertFalse(queue.complete_claimed_opportunity("RESULT", claim["claim_id"], claim["state_version"], {}))
        self.assertEqual(queue.get_opportunity("RESULT").status, "RUNNING")
        self.assertFalse(queue.complete_claimed_opportunity("RESULT", "wrong", claim["state_version"], {"result_fingerprint": "x"}))

    def test_durable_result_is_reconciled_after_restart_without_reexecution(self):
        queue = self._add_safe("RECOVER")
        claimed, _, claim = queue.claim_opportunity("RECOVER", "test-owner")
        self.assertTrue(claimed)
        result = self._durable_result(queue, "RECOVER", claim)
        result_path = self.test_dir / "events" / "opportunity-queue" / "results" / "RECOVER.result.json"
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(json.dumps(result), encoding="utf-8")

        restarted = PersistentOrganizationDaemon(repo_dir=self.test_dir)
        recovered = restarted.execute_next_eligible_work()
        self.assertEqual(recovered["status"], "RESULT_RECONCILED")
        after = OpportunityQueue(repo_dir=self.test_dir)
        self.assertEqual(after.get_opportunity("RECOVER").status, "COMPLETED")
        self.assertFalse((self.test_dir / "events" / "opportunity-queue" / "claims" / "RECOVER.claim.json").exists())

    def test_stale_generation_result_cannot_release_replacement_claim(self):
        queue = self._add_safe("STALE")
        first_ok, _, first = queue.claim_opportunity("STALE", "owner-one")
        self.assertTrue(first_ok)
        self.assertTrue(queue.release_opportunity_claim("STALE", first["claim_id"]))
        stale = queue.get_opportunity("STALE")
        stale.status = "READY"
        queue.save_opportunity(stale)
        replacement = OpportunityQueue(repo_dir=self.test_dir)
        second_ok, _, second = replacement.claim_opportunity("STALE", "owner-two")
        self.assertTrue(second_ok)
        result_path = self.test_dir / "events" / "opportunity-queue" / "results" / "STALE.result.json"
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(json.dumps({
            "task_id": "TASK-OLD",
            "opportunity_id": "STALE",
            "claim_id": first["claim_id"],
            "generation": first["state_version"],
            "result_fingerprint": "old-result",
        }), encoding="utf-8")
        outcomes = OpportunityQueue(repo_dir=self.test_dir).reconcile_durable_results()
        self.assertEqual(outcomes[0]["status"], "BLOCKED_STALE_RESULT")
        current_claim = json.loads((self.test_dir / "events" / "opportunity-queue" / "claims" / "STALE.claim.json").read_text())
        self.assertEqual(current_claim["claim_id"], second["claim_id"])

    def _write_result(self, opportunity_id, result):
        path = self.test_dir / "events" / "opportunity-queue" / "results" / f"{opportunity_id}.result.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result), encoding="utf-8")
        return path

    def _refresh_result_fingerprint(self, queue, opportunity_id, claim, result):
        result["result_fingerprint"] = queue.expected_result_fingerprint(
            queue.get_opportunity(opportunity_id), claim, result,
        )

    def _assert_schema_blocked(self, opportunity_id, result, expected_mismatch=None):
        self._write_result(opportunity_id, result)
        outcome = OpportunityQueue(repo_dir=self.test_dir).reconcile_durable_results()[0]
        self.assertEqual(outcome["status"], "BLOCKED_RESULT_SCHEMA_MISMATCH")
        if expected_mismatch:
            self.assertEqual(outcome["mismatch"], expected_mismatch)
        self.assertEqual(OpportunityQueue(repo_dir=self.test_dir).get_opportunity(opportunity_id).status, "RUNNING")
        self.assertTrue((self.test_dir / "events" / "opportunity-queue" / "claims" / f"{opportunity_id}.claim.json").exists())

    def _claimed_identity_fixture(self, opportunity_id="IDENTITY"):
        queue = self._add_safe(opportunity_id)
        claimed, _, claim = queue.claim_opportunity(opportunity_id, "identity-owner")
        self.assertTrue(claimed)
        return queue, claim, self._durable_result(queue, opportunity_id, claim, metadata={"value": "original"})

    def test_forged_task_id_is_rejected_without_mutation(self):
        queue, claim, result = self._claimed_identity_fixture("FORGED-TASK")
        result["task_id"] = "FORGED-TASK-ID"
        self._write_result("FORGED-TASK", result)
        outcomes = OpportunityQueue(repo_dir=self.test_dir).reconcile_durable_results()
        self.assertEqual(outcomes[0]["status"], "BLOCKED_IDENTITY_MISMATCH")
        self.assertEqual(OpportunityQueue(repo_dir=self.test_dir).get_opportunity("FORGED-TASK").status, "RUNNING")
        self.assertTrue((self.test_dir / "events" / "opportunity-queue" / "claims" / "FORGED-TASK.claim.json").exists())

    def test_forged_result_fingerprint_is_rejected(self):
        queue, claim, result = self._claimed_identity_fixture("FORGED-FINGERPRINT")
        result["result_fingerprint"] = "forged"
        self._write_result("FORGED-FINGERPRINT", result)
        outcomes = OpportunityQueue(repo_dir=self.test_dir).reconcile_durable_results()
        self.assertEqual(outcomes[0]["status"], "BLOCKED_IDENTITY_MISMATCH")
        self.assertEqual(OpportunityQueue(repo_dir=self.test_dir).get_opportunity("FORGED-FINGERPRINT").status, "RUNNING")

    def test_forged_task_and_fingerprint_are_rejected(self):
        queue, claim, result = self._claimed_identity_fixture("FORGED-BOTH")
        result.update({"task_id": "FORGED", "result_fingerprint": "forged"})
        self._write_result("FORGED-BOTH", result)
        outcomes = OpportunityQueue(repo_dir=self.test_dir).reconcile_durable_results()
        self.assertEqual(outcomes[0]["status"], "BLOCKED_IDENTITY_MISMATCH")
        self.assertTrue((self.test_dir / "events" / "opportunity-queue" / "claims" / "FORGED-BOTH.claim.json").exists())

    def test_mutated_result_payload_is_rejected(self):
        queue, claim, result = self._claimed_identity_fixture("MUTATED")
        result["metadata"]["value"] = "changed-after-signing"
        self._write_result("MUTATED", result)
        outcomes = OpportunityQueue(repo_dir=self.test_dir).reconcile_durable_results()
        self.assertEqual(outcomes[0]["status"], "BLOCKED_IDENTITY_MISMATCH")
        self.assertEqual(OpportunityQueue(repo_dir=self.test_dir).get_opportunity("MUTATED").status, "RUNNING")

    def test_repeated_blocked_recovery_is_deduplicated(self):
        queue, claim, result = self._claimed_identity_fixture("REPEAT-BLOCK")
        result["result_fingerprint"] = "forged"
        self._write_result("REPEAT-BLOCK", result)
        first = OpportunityQueue(repo_dir=self.test_dir).reconcile_durable_results()
        second = OpportunityQueue(repo_dir=self.test_dir).reconcile_durable_results()
        self.assertEqual(first[0]["status"], "BLOCKED_IDENTITY_MISMATCH")
        self.assertEqual(second[0]["status"], "BLOCKED_IDENTITY_MISMATCH")
        evidence = list((self.test_dir / "events" / "opportunity-queue" / "blocked-recovery").glob("*.json"))
        self.assertEqual(len(evidence), 1)

    def test_blocked_result_does_not_poison_other_safe_work(self):
        queue, claim, result = self._claimed_identity_fixture("BLOCKED-X")
        result["task_id"] = "FORGED"
        self._write_result("BLOCKED-X", result)
        self._add_safe("SAFE-Y")
        work = PersistentOrganizationDaemon(repo_dir=self.test_dir).execute_next_eligible_work()
        self.assertEqual(work["opportunity_id"], "SAFE-Y")
        self.assertEqual(OpportunityQueue(repo_dir=self.test_dir).get_opportunity("BLOCKED-X").status, "RUNNING")

    def test_identity_binding_synthetic_canary(self):
        # Valid durable recovery is reused, not executed again.
        queue, claim, valid = self._claimed_identity_fixture("CANARY-VALID")
        self._write_result("CANARY-VALID", valid)
        self.assertEqual(PersistentOrganizationDaemon(repo_dir=self.test_dir).execute_next_eligible_work()["status"], "RESULT_RECONCILED")

        # A forged identity remains blocked under its authoritative claim.
        queue, claim, forged = self._claimed_identity_fixture("CANARY-FORGED")
        forged.update({"task_id": "FORGED", "result_fingerprint": "FORGED"})
        self._write_result("CANARY-FORGED", forged)
        outcome = OpportunityQueue(repo_dir=self.test_dir).reconcile_durable_results()
        self.assertEqual(outcome[0]["status"], "BLOCKED_IDENTITY_MISMATCH")
        self.assertEqual(OpportunityQueue(repo_dir=self.test_dir).get_opportunity("CANARY-FORGED").status, "RUNNING")

        # A payload mutation invalidates a formerly correct fingerprint.
        queue, claim, mutated = self._claimed_identity_fixture("CANARY-MUTATED")
        mutated["metadata"]["value"] = "tampered"
        self._write_result("CANARY-MUTATED", mutated)
        outcomes = OpportunityQueue(repo_dir=self.test_dir).reconcile_durable_results()
        self.assertTrue(any(item["status"] == "BLOCKED_IDENTITY_MISMATCH" for item in outcomes))

    def _completed_claim_fixture(self, opportunity_id="POST-APPLY"):
        queue, claim, result = self._claimed_identity_fixture(opportunity_id)
        completed = queue.get_opportunity(opportunity_id)
        completed.status = "COMPLETED"
        queue.save_opportunity(completed)
        return queue, claim, result

    def test_completed_forged_task_id_retains_claim(self):
        queue, claim, result = self._completed_claim_fixture("POST-TASK")
        result["task_id"] = "FORGED"
        self._write_result("POST-TASK", result)
        outcome = OpportunityQueue(repo_dir=self.test_dir).reconcile_durable_results()
        self.assertEqual(outcome[0]["status"], "BLOCKED_IDENTITY_MISMATCH")
        self.assertTrue((self.test_dir / "events" / "opportunity-queue" / "claims" / "POST-TASK.claim.json").exists())

    def test_completed_forged_fingerprint_retains_claim(self):
        queue, claim, result = self._completed_claim_fixture("POST-FP")
        result["result_fingerprint"] = "forged"
        self._write_result("POST-FP", result)
        outcome = OpportunityQueue(repo_dir=self.test_dir).reconcile_durable_results()
        self.assertEqual(outcome[0]["status"], "BLOCKED_IDENTITY_MISMATCH")
        self.assertTrue((self.test_dir / "events" / "opportunity-queue" / "claims" / "POST-FP.claim.json").exists())

    def test_completed_mutated_payload_retains_claim(self):
        queue, claim, result = self._completed_claim_fixture("POST-MUTATED")
        result["metadata"]["value"] = "tampered"
        self._write_result("POST-MUTATED", result)
        outcome = OpportunityQueue(repo_dir=self.test_dir).reconcile_durable_results()
        self.assertEqual(outcome[0]["status"], "BLOCKED_IDENTITY_MISMATCH")
        self.assertTrue((self.test_dir / "events" / "opportunity-queue" / "claims" / "POST-MUTATED.claim.json").exists())

    def test_completed_exact_m208_reproduction_is_blocked(self):
        queue, claim, result = self._completed_claim_fixture("POST-BOTH")
        result.update({"task_id": "FORGED", "result_fingerprint": "forged"})
        self._write_result("POST-BOTH", result)
        outcome = OpportunityQueue(repo_dir=self.test_dir).reconcile_durable_results()
        self.assertEqual(outcome[0]["status"], "BLOCKED_IDENTITY_MISMATCH")
        self.assertTrue((self.test_dir / "events" / "opportunity-queue" / "claims" / "POST-BOTH.claim.json").exists())

    def test_completed_valid_result_releases_once(self):
        queue, claim, result = self._completed_claim_fixture("POST-VALID")
        self._write_result("POST-VALID", result)
        outcome = OpportunityQueue(repo_dir=self.test_dir).reconcile_durable_results()
        self.assertEqual(outcome[0]["status"], "RELEASE_RECONCILED")
        self.assertFalse((self.test_dir / "events" / "opportunity-queue" / "claims" / "POST-VALID.claim.json").exists())

    def test_completed_stale_generation_cannot_release_current_claim(self):
        queue = self._add_safe("POST-STALE")
        first_ok, _, first = queue.claim_opportunity("POST-STALE", "old-owner")
        self.assertTrue(first_ok)
        old_result = self._durable_result(queue, "POST-STALE", first, metadata={"value": "old"})
        self.assertTrue(queue.release_opportunity_claim("POST-STALE", first["claim_id"]))
        opp = queue.get_opportunity("POST-STALE")
        opp.status = "READY"
        queue.save_opportunity(opp)
        replacement = OpportunityQueue(repo_dir=self.test_dir)
        second_ok, _, second = replacement.claim_opportunity("POST-STALE", "new-owner")
        self.assertTrue(second_ok)
        current = replacement.get_opportunity("POST-STALE")
        current.status = "COMPLETED"
        replacement.save_opportunity(current)
        self._write_result("POST-STALE", old_result)
        OpportunityQueue(repo_dir=self.test_dir).reconcile_durable_results()
        current_claim = json.loads((self.test_dir / "events" / "opportunity-queue" / "claims" / "POST-STALE.claim.json").read_text())
        self.assertEqual(current_claim["claim_id"], second["claim_id"])

    def test_completed_repeated_invalid_release_is_deduplicated(self):
        queue, claim, result = self._completed_claim_fixture("POST-REPEAT")
        result["result_fingerprint"] = "forged"
        self._write_result("POST-REPEAT", result)
        OpportunityQueue(repo_dir=self.test_dir).reconcile_durable_results()
        OpportunityQueue(repo_dir=self.test_dir).reconcile_durable_results()
        evidence = list((self.test_dir / "events" / "opportunity-queue" / "blocked-recovery").glob("*.json"))
        self.assertEqual(len(evidence), 1)

    def test_shared_validator_rejects_same_forgery_before_and_after_application(self):
        queue, claim, running = self._claimed_identity_fixture("PARITY-RUN")
        running["task_id"] = "FORGED"
        self._write_result("PARITY-RUN", running)
        before = OpportunityQueue(repo_dir=self.test_dir).reconcile_durable_results()[0]
        queue, claim, completed = self._completed_claim_fixture("PARITY-DONE")
        completed["task_id"] = "FORGED"
        self._write_result("PARITY-DONE", completed)
        after = OpportunityQueue(repo_dir=self.test_dir).reconcile_durable_results()[0]
        self.assertEqual(before["status"], after["status"])
        self.assertEqual(before["mismatch"], after["mismatch"])

    def test_release_reconciliation_synthetic_canary(self):
        # Valid post-application crash recovery releases exactly one claim.
        queue, claim, valid = self._completed_claim_fixture("RELEASE-VALID")
        self._write_result("RELEASE-VALID", valid)
        valid_outcome = OpportunityQueue(repo_dir=self.test_dir).reconcile_durable_results()
        self.assertEqual(valid_outcome[0]["status"], "RELEASE_RECONCILED")

        # Forged identity and altered payload must retain their respective claims.
        queue, claim, forged = self._completed_claim_fixture("RELEASE-FORGED")
        forged.update({"task_id": "FORGED", "result_fingerprint": "FORGED"})
        self._write_result("RELEASE-FORGED", forged)
        forged_outcome = OpportunityQueue(repo_dir=self.test_dir).reconcile_durable_results()
        self.assertEqual(forged_outcome[0]["status"], "BLOCKED_IDENTITY_MISMATCH")
        self.assertTrue((self.test_dir / "events" / "opportunity-queue" / "claims" / "RELEASE-FORGED.claim.json").exists())

        queue, claim, mutated = self._completed_claim_fixture("RELEASE-MUTATED")
        mutated["metadata"]["value"] = "tampered"
        self._write_result("RELEASE-MUTATED", mutated)
        mutated_outcomes = OpportunityQueue(repo_dir=self.test_dir).reconcile_durable_results()
        self.assertTrue(any(item["status"] == "BLOCKED_IDENTITY_MISMATCH" for item in mutated_outcomes))
        self.assertTrue((self.test_dir / "events" / "opportunity-queue" / "claims" / "RELEASE-MUTATED.claim.json").exists())

    def test_result_schema_unknown_handler_is_rejected_with_valid_fingerprint(self):
        queue, claim, result = self._claimed_identity_fixture("SCHEMA-HANDLER")
        result["handler"] = "UNAPPROVED_HANDLER"
        self._refresh_result_fingerprint(queue, "SCHEMA-HANDLER", claim, result)
        self._assert_schema_blocked("SCHEMA-HANDLER", result, "RESULT_SCHEMA_HANDLER_UNAPPROVED")

    def test_result_schema_unapproved_status_is_rejected_with_valid_fingerprint(self):
        queue, claim, result = self._claimed_identity_fixture("SCHEMA-STATUS")
        result["status"] = "COMPLETED_OK"
        self._refresh_result_fingerprint(queue, "SCHEMA-STATUS", claim, result)
        self._assert_schema_blocked("SCHEMA-STATUS", result, "RESULT_SCHEMA_STATUS_UNAPPROVED")

    def test_result_schema_invalid_status_handler_pair_is_rejected(self):
        queue, claim, result = self._claimed_identity_fixture("SCHEMA-PAIR")
        result["handler"] = "DETERMINISTIC_LOCAL_NOOP"
        result["status"] = "SUCCESS"
        self._refresh_result_fingerprint(queue, "SCHEMA-PAIR", claim, result)
        self._assert_schema_blocked("SCHEMA-PAIR", result, "RESULT_SCHEMA_STATUS_HANDLER_MISMATCH")

    def test_result_schema_wrong_result_type_is_rejected(self):
        queue, claim, result = self._claimed_identity_fixture("SCHEMA-TYPE")
        result["result_type"] = "FOREIGN_RESULT"
        self._refresh_result_fingerprint(queue, "SCHEMA-TYPE", claim, result)
        self._assert_schema_blocked("SCHEMA-TYPE", result, "RESULT_SCHEMA_TYPE_UNAPPROVED")

    def test_result_schema_unsupported_version_is_rejected(self):
        queue, claim, result = self._claimed_identity_fixture("SCHEMA-VERSION")
        result["schema_version"] = "999.0"
        self._refresh_result_fingerprint(queue, "SCHEMA-VERSION", claim, result)
        self._assert_schema_blocked("SCHEMA-VERSION", result, "RESULT_SCHEMA_VERSION_UNSUPPORTED")

    def test_result_schema_missing_required_field_is_rejected(self):
        queue, claim, result = self._claimed_identity_fixture("SCHEMA-MISSING")
        del result["metadata"]
        self._refresh_result_fingerprint(queue, "SCHEMA-MISSING", claim, result)
        self._assert_schema_blocked("SCHEMA-MISSING", result, "RESULT_SCHEMA_REQUIRED_FIELDS_MISMATCH")

    def test_result_schema_wrong_field_type_is_rejected(self):
        queue, claim, result = self._claimed_identity_fixture("SCHEMA-FIELD-TYPE")
        result["metadata"] = []
        self._refresh_result_fingerprint(queue, "SCHEMA-FIELD-TYPE", claim, result)
        self._assert_schema_blocked("SCHEMA-FIELD-TYPE", result, "RESULT_SCHEMA_METADATA_INVALID")

    def test_exact_m212_reproduction_cannot_release_claim(self):
        queue, claim, result = self._completed_claim_fixture("M212-EXACT")
        result["status"] = "FORGED_RESULT_TYPE"
        result["handler"] = "FORGED_HANDLER"
        self._refresh_result_fingerprint(queue, "M212-EXACT", claim, result)
        self._write_result("M212-EXACT", result)
        outcome = OpportunityQueue(repo_dir=self.test_dir).reconcile_durable_results()[0]
        self.assertEqual(outcome["status"], "BLOCKED_RESULT_SCHEMA_MISMATCH")
        self.assertTrue((self.test_dir / "events" / "opportunity-queue" / "claims" / "M212-EXACT.claim.json").exists())

    def test_valid_canonical_result_schema_reconciles_once(self):
        queue, claim, result = self._claimed_identity_fixture("SCHEMA-VALID")
        valid, mismatch, _ = queue.validate_durable_result(queue.get_opportunity("SCHEMA-VALID"), claim, result)
        self.assertTrue(valid, mismatch)
        self._write_result("SCHEMA-VALID", result)
        self.assertEqual(OpportunityQueue(repo_dir=self.test_dir).reconcile_durable_results()[0]["status"], "RESULT_RECONCILED")
        self.assertFalse((self.test_dir / "events" / "opportunity-queue" / "claims" / "SCHEMA-VALID.claim.json").exists())

    def test_result_schema_protects_application_and_release_paths_equally(self):
        queue, claim, running = self._claimed_identity_fixture("SCHEMA-PARITY-RUN")
        running["result_type"] = "FOREIGN_RESULT"
        self._refresh_result_fingerprint(queue, "SCHEMA-PARITY-RUN", claim, running)
        self._write_result("SCHEMA-PARITY-RUN", running)
        before = OpportunityQueue(repo_dir=self.test_dir).reconcile_durable_results()[0]
        queue, claim, completed = self._completed_claim_fixture("SCHEMA-PARITY-DONE")
        completed["result_type"] = "FOREIGN_RESULT"
        self._refresh_result_fingerprint(queue, "SCHEMA-PARITY-DONE", claim, completed)
        self._write_result("SCHEMA-PARITY-DONE", completed)
        after = OpportunityQueue(repo_dir=self.test_dir).reconcile_durable_results()[0]
        self.assertEqual(before["status"], "BLOCKED_RESULT_SCHEMA_MISMATCH")
        self.assertEqual(before["status"], after["status"])
        self.assertEqual(before["mismatch"], after["mismatch"])

    def test_repeated_identical_schema_mismatch_evidence_is_deduplicated(self):
        queue, claim, result = self._completed_claim_fixture("SCHEMA-REPEAT")
        result["result_type"] = "FOREIGN_RESULT"
        self._refresh_result_fingerprint(queue, "SCHEMA-REPEAT", claim, result)
        self._write_result("SCHEMA-REPEAT", result)
        first = OpportunityQueue(repo_dir=self.test_dir).reconcile_durable_results()[0]
        second = OpportunityQueue(repo_dir=self.test_dir).reconcile_durable_results()[0]
        self.assertEqual(first["status"], "BLOCKED_RESULT_SCHEMA_MISMATCH")
        self.assertEqual(second["status"], "BLOCKED_RESULT_SCHEMA_MISMATCH")
        evidence = list((self.test_dir / "events" / "opportunity-queue" / "blocked-recovery").glob("*.json"))
        self.assertEqual(len(evidence), 1)

    def test_result_schema_synthetic_canary_distinguishes_valid_and_invalid_candidates(self):
        queue, claim, valid = self._claimed_identity_fixture("SCHEMA-CANARY-VALID")
        self._write_result("SCHEMA-CANARY-VALID", valid)
        self.assertEqual(OpportunityQueue(repo_dir=self.test_dir).reconcile_durable_results()[0]["status"], "RESULT_RECONCILED")
        queue, claim, invalid = self._claimed_identity_fixture("SCHEMA-CANARY-INVALID")
        invalid["handler"] = "DETERMINISTIC_LOCAL_NOOP"
        invalid["status"] = "SUCCESS"
        self._refresh_result_fingerprint(queue, "SCHEMA-CANARY-INVALID", claim, invalid)
        self._assert_schema_blocked("SCHEMA-CANARY-INVALID", invalid, "RESULT_SCHEMA_STATUS_HANDLER_MISMATCH")

    def test_parked_gate_does_not_block_safe_work(self):
        path = self._spec()
        self._add_safe("SAFE-AROUND-GATE")
        result = self.daemon.execute_next_eligible_work()
        self.assertEqual(result["opportunity_id"], "SAFE-AROUND-GATE")
        self.assertEqual(json.loads(path.read_text())["current_status"], "WAITING_FOR_HUMAN")

    def test_parked_gate_only_returns_waiting_gate_and_is_deduplicated(self):
        path = self._spec()
        first = self.daemon.execute_next_eligible_work()
        before = path.read_text()
        second = self.daemon.execute_next_eligible_work()
        self.assertEqual(first["status"], "WAITING_GATE")
        self.assertEqual(second["status"], "WAITING_GATE")
        self.assertEqual(path.read_text(), before)

    def test_result_recovery_then_next_safe_work(self):
        queue = self._add_safe("RECOVER-A")
        self._add_safe("NEXT-B")
        claimed, _, claim = queue.claim_opportunity("RECOVER-A", "test-owner")
        self.assertTrue(claimed)
        result_path = self.test_dir / "events" / "opportunity-queue" / "results" / "RECOVER-A.result.json"
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(json.dumps(self._durable_result(queue, "RECOVER-A", claim)), encoding="utf-8")
        restarted = PersistentOrganizationDaemon(repo_dir=self.test_dir)
        self.assertEqual(restarted.execute_next_eligible_work()["status"], "RESULT_RECONCILED")
        self.assertEqual(restarted.execute_next_eligible_work()["opportunity_id"], "NEXT-B")

    def test_canonical_fenced_claim_has_exactly_one_concurrent_winner(self):
        self._add_safe("RACE")
        output: multiprocessing.Queue = multiprocessing.Queue()
        workers = [
            multiprocessing.Process(target=_claim_worker, args=(str(self.test_dir), f"owner-{i}", output))
            for i in range(2)
        ]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(10)
            self.assertFalse(worker.is_alive())
        outcomes = [output.get(timeout=2) for _ in workers]
        winners = [item for item in outcomes if item["claimed"]]
        self.assertEqual(len(winners), 1, outcomes)
        self.assertIsInstance(winners[0]["generation"], int)

    def test_read_only_evaluator_needs_explicit_write_flag(self):
        evaluator = RevenueConversionEvaluator(repo_dir=self.test_dir)
        playbook = self.test_dir / "events" / "revenue-opportunities" / "RESPONSE_CONVERSION_PLAYBOOK.md"
        evaluator.evaluate_all_exposures()
        self.assertFalse(playbook.exists())


if __name__ == "__main__":
    unittest.main()
