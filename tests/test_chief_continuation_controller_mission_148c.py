#!/usr/bin/env python3
import tempfile
import unittest
import json
from pathlib import Path

from scripts.chief_continuation_controller import AutonomousBacklogPlanner, ChiefContinuationController
from scripts.opportunity_queue import Opportunity, OpportunityQueue


class ChiefContinuationControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        policy = self.repo / "events/policies/resource_policy.json"
        policy.parent.mkdir(parents=True)
        policy.write_text(Path("events/policies/resource_policy.json").read_text(encoding="utf-8"), encoding="utf-8")
        self.queue = OpportunityQueue(self.repo)
        self.controller = ChiefContinuationController(self.repo)

    def tearDown(self):
        self.temp.cleanup()

    def add(self, **extra):
        base = dict(opportunity_id="opp-1", source="TEST", objective_id="obj", project="test", description="Run local QC", priority=9, allowed_scope=[], target_agent="antigravity")
        base.update(extra)
        self.assertTrue(self.queue.add_opportunity(Opportunity(**base)))

    def write_evidence(self, relative, value):
        path = self.repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def test_weiter_creates_exactly_one_prepared_task_and_reuses_it(self):
        self.add()
        first = self.controller.handle("WEITER")
        second = ChiefContinuationController(self.repo).handle("WEITER")
        self.assertEqual(first["CHIEF_STATUS"], "WEITER_ACCEPTED")
        self.assertEqual(second["CHIEF_STATUS"], "ALREADY_RUNNING")
        self.assertEqual(len(list((self.repo / "events/chief-continuation/tasks").glob("*.json"))), 1)

    def test_status_has_no_model_call_and_stop_prevents_dispatch(self):
        self.add()
        self.assertEqual(self.controller.handle("STATUS")["model_calls"], 0)
        stopped = self.controller.handle("STOP")
        self.assertEqual(stopped["STATE"], "STOPPED")
        self.assertEqual(self.controller.handle("WEITER")["CHIEF_STATUS"], "STOPPED_NO_NEW_DISPATCH")

    def test_durable_result_is_ingested_not_provider_chat_history(self):
        self.add()
        accepted = self.controller.handle("WEITER")
        task_id = accepted["CURRENT_TASK"]
        result_dir = self.repo / "events/processed"
        result_dir.mkdir(parents=True)
        (result_dir / "result.json").write_text('{"task_id": "' + task_id + '", "payload": {"verdict": "PASS"}}', encoding="utf-8")
        next_result = ChiefContinuationController(self.repo).handle("WEITER")
        self.assertNotEqual(next_result["CHIEF_STATUS"], "ALREADY_RUNNING")

    def test_money_and_publication_are_human_gates(self):
        self.add(estimated_cost=1.0)
        result = self.controller.handle("WEITER")
        self.assertEqual(result["CHIEF_STATUS"], "HUMAN_GATE_REQUIRED")
        self.assertEqual(result["HUMAN_GATE"], "PAYMENT_APPROVAL_REQUIRED")

    def test_unavailable_provider_blocks_and_unknown_command_fails_closed(self):
        self.add(target_agent="unknown-provider")
        self.assertEqual(self.controller.handle("WEITER")["CHIEF_STATUS"], "PROVIDER_UNAVAILABLE")
        self.assertFalse(self.controller.handle("anything else")["COMMAND_ACCEPTED"])

    def test_no_provider_chat_or_secret_material_in_task(self):
        self.add()
        self.controller.handle("WEITER")
        task = next((self.repo / "events/chief-continuation/tasks").glob("*.json")).read_text(encoding="utf-8")
        self.assertIn('"provider_chat_history_included": false', task)
        self.assertNotIn("refresh_token", task.lower())
        self.assertNotIn("api_key", task.lower())

    def test_prepared_pool_switch_blocks_new_task_until_human_auth(self):
        state_path = self.repo / "events/resource-intelligence/google_pool_switch_state.json"
        state_path.parent.mkdir(parents=True)
        state_path.write_text('{"state":"HUMAN_AUTH_REQUIRED","from_pool":"GOOGLE_PRO_POOL_1","to_pool":"GOOGLE_PRO_POOL_2","checkpoint":{"checkpoint_id":"x"}}')
        result = self.controller.handle("WEITER")
        self.assertEqual(result["CHIEF_STATUS"], "ACCOUNT_SWITCH_REQUIRED")
        self.assertTrue(result["WORK_CHECKPOINTED"])

    def test_continue_aliases_are_equivalent_and_status_is_read_only(self):
        self.add()
        for command in ("WEITERMACHEN", "WEITER MACHEN", "FORTSETZEN", "CONTINUE"):
            fresh = ChiefContinuationController(self.repo)
            result = fresh.handle(command)
            self.assertIn(result["CHIEF_STATUS"], {"WEITER_ACCEPTED", "ALREADY_RUNNING"})
        before = (self.repo / "events/chief-continuation/state.json").read_text(encoding="utf-8")
        self.assertEqual(self.controller.handle("STATUS")["CHIEF_STATUS"], "STATUS")
        self.assertEqual((self.repo / "events/chief-continuation/state.json").read_text(encoding="utf-8"), before)

    def test_empty_queue_discovers_unfinished_mission_and_persists_one_task(self):
        self.write_evidence("events/unfinished-missions/mission.json", {
            "mission_id": "M-LOCAL", "title": "Finish local deterministic validator",
            "description": "Complete the bounded local validator from its durable mission artifact.",
            "status": "UNFINISHED", "priority": 9, "target_agent": "antigravity",
            "completion_criteria": ["Validator result is persisted"],
        })
        result = self.controller.handle("WEITER")
        self.assertEqual(result["CHIEF_STATUS"], "WEITER_ACCEPTED")
        task = next((self.repo / "events/chief-continuation/tasks").glob("*.json"))
        payload = json.loads(task.read_text(encoding="utf-8"))
        self.assertEqual(payload["planner_metadata"]["category"], "UNFINISHED")
        self.assertEqual(payload["max_iterations"], 1)
        self.assertFalse(payload["provider_chat_history_included"])

    def test_backlog_ranking_and_busywork_rejection(self):
        self.write_evidence("events/backlog/items.json", {"items": [
            {"task_id": "LOW", "title": "Cosmetic refactor", "description": "Cosmetic refactor of unchanged labels", "status": "READY", "priority": 99},
            {"task_id": "HIGH", "title": "Repair deterministic blocker", "description": "Fix the durable local recovery blocker", "status": "READY", "priority": 9, "target_agent": "antigravity"},
        ]})
        plan = AutonomousBacklogPlanner(self.repo).choose()
        self.assertEqual(plan["task_id"], "HIGH")
        self.assertNotIn("cosmetic", plan["title"].lower())

    def test_human_money_and_publication_backlog_items_fail_closed(self):
        self.write_evidence("events/backlog/protected.json", {"items": [
            {"task_id": "PUB", "title": "Publish a video", "description": "Publish locally prepared video", "status": "READY", "priority": 10, "publication_gate": True},
        ]})
        response = self.controller.handle("WEITER")
        self.assertEqual(response["CHIEF_STATUS"], "HUMAN_GATE_REQUIRED")
        self.assertEqual(response["STATE"], "WAITING_FOR_HUMAN")

    def test_malformed_cost_metadata_fails_closed(self):
        self.write_evidence("events/backlog/cost.json", {"task_id": "COST", "title": "Malformed cost", "description": "Safe local action", "status": "READY", "estimated_cost": "unknown"})
        response = self.controller.handle("WEITER")
        self.assertEqual(response["CHIEF_STATUS"], "HUMAN_GATE_REQUIRED")

    def test_result_ingestion_completes_claim_before_next_planning(self):
        self.add()
        accepted = self.controller.handle("WEITER")
        task_id = accepted["CURRENT_TASK"]
        self.write_evidence("events/processed/result.json", {"task_id": task_id, "correlation_id": "ignored"})
        response = ChiefContinuationController(self.repo).handle("WEITER")
        self.assertEqual(response["CHIEF_STATUS"], "NO_READY_ACTION")
        self.assertEqual(OpportunityQueue(self.repo).get_opportunity("opp-1").status, "COMPLETED")

    def test_interrupted_task_and_heavy_limit_prevent_second_dispatch(self):
        self.add()
        accepted = self.controller.handle("WEITER")
        state = json.loads((self.repo / "events/chief-continuation/state.json").read_text(encoding="utf-8"))
        state["current"]["status"] = "RUNNING"
        (self.repo / "events/chief-continuation/state.json").write_text(json.dumps(state), encoding="utf-8")
        second = ChiefContinuationController(self.repo).handle("WEITER")
        self.assertEqual(second["CHIEF_STATUS"], "ALREADY_RUNNING")
        self.assertEqual(second["CURRENT_TASK"], accepted["CURRENT_TASK"])

    def test_true_no_work_remains_no_ready_action(self):
        result = self.controller.handle("WEITER")
        self.assertEqual(result["CHIEF_STATUS"], "NO_READY_ACTION")
        self.assertIn("EVIDENCE", result)

    def test_pool_four_is_never_selected_by_local_planner(self):
        self.write_evidence("events/backlog/pool4.json", {"task_id": "POOL4", "title": "Use unconfigured pool", "description": "Prepare task", "status": "READY", "priority": 10, "target_agent": "GOOGLE_PRO_POOL_4"})
        response = self.controller.handle("WEITER")
        self.assertEqual(response["CHIEF_STATUS"], "HUMAN_GATE_REQUIRED")
        self.assertEqual(response["HUMAN_GATE"], "PAYMENT_APPROVAL_REQUIRED")

    def test_exhausted_verified_google_pool_checkpoints_same_task_then_resumes(self):
        self.write_evidence("events/resource-intelligence/three_pool_registry.json", {
            "GOOGLE_PRO_POOL_1": {"authorization_state": "AUTHORIZED", "verification_state": "VERIFIED", "capacity_state": "EXHAUSTED"},
            "GOOGLE_PRO_POOL_2": {"authorization_state": "AUTHORIZED", "verification_state": "VERIFIED", "capacity_state": "AVAILABLE"},
            "GOOGLE_PRO_POOL_3": {"authorization_state": "READY_FOR_VERIFICATION", "verification_state": "READY_FOR_VERIFICATION", "capacity_state": "UNKNOWN"},
            "GOOGLE_PRO_POOL_4": {"authorization_state": "NOT_CONFIGURED", "verification_state": "NOT_CONFIGURED", "capacity_state": "NOT_CONFIGURED"},
        })
        self.add(target_agent="GOOGLE_PRO_POOL_1")
        switched = self.controller.handle("WEITER")
        self.assertEqual(switched["CHIEF_STATUS"], "ACCOUNT_SWITCH_REQUIRED")
        task_id = switched["CURRENT_TASK"]
        from scripts.google_pool_controller import GooglePoolController
        self.assertEqual(GooglePoolController(self.repo).verify_switch("GOOGLE_PRO_POOL_2", human_auth_confirmed=True)["status"], "CONTINUATION_READY")
        resumed = ChiefContinuationController(self.repo).handle("WEITER")
        self.assertEqual(resumed["CHIEF_STATUS"], "ALREADY_RUNNING")
        self.assertEqual(resumed["CURRENT_TASK"], task_id)

    def test_oversized_shared_review_scope_is_blocked_not_dispatched(self):
        self.add()
        claimed, _, claim = self.queue.claim_opportunity("opp-1", "review-owner")
        self.assertTrue(claimed)
        state_path = self.repo / "events/chief-continuation/state.json"
        state_path.parent.mkdir(parents=True)
        state_path.write_text(json.dumps({"stopped": False, "current": {
            "task_id": "TASK-BROAD-REVIEW", "status": "PREPARED_NOT_EXECUTED", "opportunity_id": "opp-1",
            "claim_id": claim["claim_id"], "planner_metadata": {"category": "REVIEW"},
            "context_package": {"scope_files": [f"scripts/file_{index}.py" for index in range(13)]},
        }}), encoding="utf-8")
        result = ChiefContinuationController(self.repo).handle("WEITER")
        self.assertEqual(result["CHIEF_STATUS"], "NO_READY_ACTION")
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["last_blocked"]["reason"], "REVIEW_SCOPE_EXCEEDS_AUTONOMOUS_BOUND")
        self.assertEqual(OpportunityQueue(self.repo).get_opportunity("opp-1").status, "BLOCKED")

    def test_nested_creator_plan_routes_existing_local_qc_not_human_content(self):
        master = self.repo / "runtime/content/short/render.mp4"
        master.parent.mkdir(parents=True)
        master.write_bytes(b"not-probed-in-this-planner-test")
        self.write_evidence("events/ready-work/plan.json", {"plans": [
            {"task_id": "HUMAN", "content_id": "golden", "action_type": "HUMAN_AUDIENCE_DECISION", "status": "WAITING_HUMAN", "requires_human": True},
            {"task_id": "QC", "content_id": "magnifying", "action_type": "LOCAL_QC_EXECUTION", "status": "READY_TO_EXECUTE", "execution_class": "DETERMINISTIC_LOCAL", "preferred_worker_class": "LOCAL_DETERMINISTIC_RUNNER", "evidence_references": ["runtime/content/short/render.mp4"]},
        ]})
        plan = AutonomousBacklogPlanner(self.repo).choose()
        self.assertEqual(plan["task_id"], "QC")
        self.assertEqual(plan["provider_suitability"], "local")


if __name__ == "__main__":
    unittest.main()
