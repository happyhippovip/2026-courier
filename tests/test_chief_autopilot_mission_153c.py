#!/usr/bin/env python3
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from scripts.chief_autopilot import BoundedChiefAutopilot, parse_autopilot_command
from scripts.chief_continuation_controller import ChiefContinuationController
from scripts.opportunity_queue import Opportunity, OpportunityQueue


class ChiefAutopilotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        policy = self.repo / "events/policies/resource_policy.json"
        policy.parent.mkdir(parents=True)
        policy.write_text(Path("events/policies/resource_policy.json").read_text(encoding="utf-8"), encoding="utf-8")
        self.queue = OpportunityQueue(self.repo)
        self.autopilot = BoundedChiefAutopilot(self.repo)

    def tearDown(self):
        self.temp.cleanup()

    def add(self, opportunity_id="local-1", **extra):
        values = dict(opportunity_id=opportunity_id, source="TEST", objective_id=opportunity_id, project="test",
                      description="Validate durable local evidence", priority=8, target_agent="local", allowed_scope=[],
                      allowed_actions=["READ"], expected_output="Evidence validation result")
        values.update(extra)
        self.assertTrue(self.queue.add_opportunity(Opportunity(**values)))

    def test_supported_commands_and_invalid_durations(self):
        self.assertEqual(parse_autopilot_command("WEITER 90 MINUTEN"), 90)
        self.assertEqual(parse_autopilot_command("EINKAUFEN 90 MINUTEN"), 90)
        self.assertEqual(parse_autopilot_command("AUTOPILOT 90 MINUTEN"), 90)
        self.assertIsNone(parse_autopilot_command("WEITER 181 MINUTEN"))
        self.assertIsNone(parse_autopilot_command("WEITER 45 MINUTEN"))

    def test_controller_starts_lease_and_persists_heartbeat_and_status(self):
        self.add()
        result = ChiefContinuationController(self.repo).handle("EINKAUFEN 90 MINUTEN")
        self.assertEqual(result["CHIEF_STATUS"], "AUTOPILOT_STARTED")
        self.assertTrue((self.repo / "events/chief-autopilot/lease.json").exists())
        self.assertTrue((self.repo / "events/chief-autopilot/heartbeat.json").exists())
        self.assertTrue((self.repo / "events/chief-autopilot/status.json").exists())
        self.assertEqual(BoundedChiefAutopilot(self.repo).lease()["tasks_completed"], 1)

    def test_successful_local_results_continue_without_second_human_command(self):
        self.add("a", priority=9)
        self.add("b", priority=8)
        self.autopilot.start("AUTOPILOT 90 MINUTEN")
        self.autopilot.run_available()
        lease = self.autopilot.lease()
        self.assertEqual(lease["tasks_completed"], 2)
        self.assertEqual(len(list((self.repo / "events/chief-autopilot/results").glob("*.json"))), 2)

    def test_three_task_acceptance_sequence_needs_no_second_human_command(self):
        for name, priority in (("a", 9), ("b", 8), ("c", 7)):
            self.add(name, priority=priority)
        self.autopilot.start("EINKAUFEN 90 MINUTEN")
        self.autopilot.run_available()
        self.assertEqual(self.autopilot.lease()["tasks_completed"], 3)
        self.assertEqual(len(list((self.repo / "events/chief-autopilot/results").glob("*.json"))), 3)

    def test_task_limit_is_enforced(self):
        for index in range(3):
            self.add(f"t{index}", priority=9 - index)
        self.autopilot.start("WEITER 30 MINUTEN", task_limit=2)
        final = self.autopilot.run_available()
        self.assertEqual(final["CHIEF_STATUS"], "PAUSED")
        self.assertEqual(self.autopilot.lease()["tasks_completed"], 2)

    def test_restart_recovers_without_extending_expiry(self):
        self.autopilot.start("WEITER 90 MINUTEN")
        before = self.autopilot.lease()["expires_at"]
        recovered = BoundedChiefAutopilot(self.repo).recover()
        self.assertTrue(recovered["recovered_after_restart"])
        self.assertEqual(recovered["expires_at"], before)

    def test_expired_lease_dispatches_nothing_and_reports(self):
        self.add()
        self.autopilot.start("WEITER 30 MINUTEN")
        lease = self.autopilot.lease()
        lease["expires_at"] = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=1)).isoformat()
        (self.repo / "events/chief-autopilot/lease.json").write_text(json.dumps(lease), encoding="utf-8")
        result = self.autopilot.step()
        self.assertEqual(result["CHIEF_STATUS"], "EXPIRED")
        self.assertEqual(OpportunityQueue(self.repo).get_opportunity("local-1").status, "READY")
        self.assertTrue(list((self.repo / "events/chief-autopilot/reports").glob("*.json")))

    def test_stop_prevents_new_dispatch_without_terminating_any_process(self):
        self.add()
        self.autopilot.start("WEITER 30 MINUTEN")
        self.assertEqual(self.autopilot.stop()["CHIEF_STATUS"], "STOP_ACCEPTED")
        self.assertEqual(self.autopilot.step()["CHIEF_STATUS"], "STOPPED")
        self.assertEqual(OpportunityQueue(self.repo).get_opportunity("local-1").status, "READY")

    def test_money_and_publication_gates_block_their_branch(self):
        self.add(estimated_cost=1.0)
        self.autopilot.start("WEITER 30 MINUTEN")
        result = self.autopilot.step()
        self.assertEqual(result["CHIEF_STATUS"], "HUMAN_GATE")
        self.assertEqual(result["human_gate"], "PAYMENT_APPROVAL_REQUIRED")

    def test_independent_local_branch_runs_when_provider_transport_is_unavailable(self):
        self.add("remote", priority=10, target_agent="antigravity")
        self.add("local", priority=9)
        self.autopilot.start("WEITER 30 MINUTEN")
        self.assertEqual(self.autopilot.step()["CHIEF_STATUS"], "LOCAL_TASK_COMPLETE")
        refreshed = OpportunityQueue(self.repo)
        self.assertEqual(refreshed.get_opportunity("local").status, "COMPLETED")
        self.assertEqual(refreshed.get_opportunity("remote").status, "READY")

    def test_only_remote_work_pauses_without_fake_provider_execution(self):
        self.add(target_agent="codex")
        self.autopilot.start("WEITER 30 MINUTEN")
        result = self.autopilot.step()
        self.assertEqual(result["CHIEF_STATUS"], "RESOURCE_WAIT")
        self.assertEqual(self.autopilot.lease()["stop_reason"], "PROVIDER_TRANSPORT_UNAVAILABLE")

    def test_existing_chief_provider_task_is_preserved_not_redispatched(self):
        state = self.repo / "events/chief-continuation/state.json"
        state.parent.mkdir(parents=True)
        state.write_text(json.dumps({"current": {"task_id": "TASK-REMOTE", "status": "PREPARED_NOT_EXECUTED", "provider": "chatgpt_plus_codex"}}), encoding="utf-8")
        self.autopilot.start("WEITER 30 MINUTEN")
        result = self.autopilot.step()
        self.assertEqual(result["CHIEF_STATUS"], "RESOURCE_WAIT")
        self.assertIn("TASK-REMOTE", result["unavailable_provider_tasks"])

    def test_explicit_lease_runner_processes_only_local_work_and_exits_on_wait(self):
        self.add("local", priority=9)
        self.add("remote", priority=8, target_agent="antigravity")
        self.autopilot.start("AUTOPILOT 30 MINUTEN")
        result = self.autopilot.run_lease(poll_seconds=0.1, max_cycles=3)
        self.assertEqual(result["CHIEF_STATUS"], "RESOURCE_WAIT")
        self.assertEqual(result["cycles"], 2)
        self.assertEqual(OpportunityQueue(self.repo).get_opportunity("local").status, "COMPLETED")

    def test_duplicate_lease_task_is_suppressed_by_queue_claim(self):
        self.add()
        self.autopilot.start("WEITER 30 MINUTEN")
        claimed, _, _ = self.queue.claim_opportunity("local-1", "other-owner")
        self.assertTrue(claimed)
        result = self.autopilot.step()
        self.assertEqual(result["CHIEF_STATUS"], "PAUSED")
        self.assertEqual(OpportunityQueue(self.repo).get_opportunity("local-1").status, "RUNNING")

    def test_heartbeat_is_zero_model_and_persistent_service_is_not_a_task(self):
        self.autopilot.start("WEITER 30 MINUTEN")
        heartbeat = json.loads((self.repo / "events/chief-autopilot/heartbeat.json").read_text(encoding="utf-8"))
        self.assertEqual(heartbeat["model_calls"], 0)
        self.assertNotIn("run_visual_studio_server.py", json.dumps(heartbeat))

    def test_failed_local_task_is_bounded_at_three_attempts(self):
        missing = "events/evidence/does-not-exist.json"
        self.add(evidence={"source_path": missing})
        self.autopilot.start("WEITER 30 MINUTEN")
        for _ in range(3):
            self.autopilot.step()
        final = OpportunityQueue(self.repo).get_opportunity("local-1")
        self.assertEqual(final.status, "BLOCKED")
        self.assertEqual(final.evidence["autopilot_attempts"], 3)


if __name__ == "__main__":
    unittest.main()
