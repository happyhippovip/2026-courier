#!/usr/bin/env python3
"""Adversarial local tests for Mission 119B four-hour autonomy safety gates."""

import concurrent.futures
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.opportunity_queue import Opportunity, OpportunityQueue
from scripts.run_autonomous_supervisor import (
    AutonomousSupervisor,
    DecisionContinuationStore,
    SessionBudgetLedger,
    SessionWorkBudget,
)
from scripts.run_chief_commander import ChiefDecisionContract


def _claim_worker(repo_dir: str, opportunity_id: str, owner: str):
    queue = OpportunityQueue(repo_dir=Path(repo_dir))
    return queue.claim_opportunity(opportunity_id, owner)


def _supervisor_contender(repo_dir: str, session_id: str):
    supervisor = AutonomousSupervisor(repo_dir=Path(repo_dir))
    return supervisor.run_long_run_session(
        budget=SessionWorkBudget(max_wall_clock_seconds=15),
        session_id=session_id,
        enable_bundling=False,
        max_operations=1,
        idle_exit_after_empty_checks=1,
    )


def _recovery_contender(repo_dir: str, decision_id: str):
    return DecisionContinuationStore(Path(repo_dir)).reconcile_intent(decision_id)


class HumanGateFixtureSupervisor(AutonomousSupervisor):
    """Local deterministic worker fixture; it never invokes a model or external service."""

    def dispatch_and_execute_task(self, task_info, workflow_id, correlation_id, **_kwargs):
        task_id = task_info["task_id"]
        result_file = self.processed_dir / f"{task_id}-result.json"
        needs_human = "HUMAN" in task_info["instruction"]
        payload = {
            "verdict": "HUMAN_APPROVAL_REQUIRED" if needs_human else "PASS",
            "human_gate_required": needs_human,
            "summary": "fixture result",
        }
        result_file.write_text(json.dumps({
            "task_id": task_id,
            "source": "antigravity",
            "payload": payload,
        }), encoding="utf-8")
        return result_file


class TestMission119BAutonomySafety(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="courier_test_m119b_"))
        for directory in ("events/opportunity-queue", "events/processed", "events/dispatch", "events/chief-decisions", "events/consumed-decisions", "events/locks"):
            (self.temp_dir / directory).mkdir(parents=True, exist_ok=True)
        (self.temp_dir / "config").mkdir(exist_ok=True)
        (self.temp_dir / "config/local_tools.json").write_text("{}", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _opportunity(self, identifier, description, priority=5):
        return Opportunity(
            opportunity_id=identifier,
            source="TEST",
            objective_id="KEEP_PRODUCTION_PIPELINE_HEALTHY",
            project="2026-courier",
            description=description,
            priority=priority,
            allowed_scope=["config/local_tools.json"],
        )

    def test_atomic_opportunity_claim_has_one_winner_and_safe_release(self):
        queue = OpportunityQueue(repo_dir=self.temp_dir)
        queue.add_opportunity(self._opportunity("OPP-119B-CLAIM", "Shared READY opportunity"))
        with concurrent.futures.ProcessPoolExecutor(max_workers=2) as executor:
            first = executor.submit(_claim_worker, str(self.temp_dir), "OPP-119B-CLAIM", "supervisor-a")
            second = executor.submit(_claim_worker, str(self.temp_dir), "OPP-119B-CLAIM", "supervisor-b")
            results = [first.result(), second.result()]
        winners = [result for result in results if result[0]]
        losers = [result for result in results if not result[0]]
        self.assertEqual(len(winners), 1)
        self.assertEqual(len(losers), 1)
        self.assertEqual(losers[0][1], "ALREADY_CLAIMED")
        winner_claim = winners[0][2]
        self.assertFalse(queue.release_opportunity_claim("OPP-119B-CLAIM", "old-owner-must-not-release"))
        self.assertTrue(queue.release_opportunity_claim("OPP-119B-CLAIM", winner_claim["claim_id"]))

    def test_two_supervisors_dispatch_one_shared_opportunity_once(self):
        queue = OpportunityQueue(repo_dir=self.temp_dir)
        queue.add_opportunity(self._opportunity("OPP-119B-SHARED", "Shared supervisor operation"))
        with concurrent.futures.ProcessPoolExecutor(max_workers=2) as executor:
            first = executor.submit(_supervisor_contender, str(self.temp_dir), "m119b-supervisor-a")
            second = executor.submit(_supervisor_contender, str(self.temp_dir), "m119b-supervisor-b")
            results = [first.result(), second.result()]
        dispatches = list((self.temp_dir / "events/dispatch").glob("*-worker-job.json"))
        self.assertEqual(len(dispatches), 1)
        self.assertEqual(sum(result["total_builder_jobs_executed"] for result in results), 1)

    def test_human_gate_parks_only_affected_branch_and_independent_branch_completes(self):
        supervisor = HumanGateFixtureSupervisor(repo_dir=self.temp_dir)
        supervisor.opportunity_queue.add_opportunity(self._opportunity("OPP-119B-HUMAN", "HUMAN approval required", priority=10))
        supervisor.opportunity_queue.add_opportunity(self._opportunity("OPP-119B-SAFE", "Safe independent work", priority=9))
        result = supervisor.run_long_run_session(
            budget=SessionWorkBudget(max_wall_clock_seconds=20),
            session_id="m119b-human-gate",
            enable_bundling=False,
            max_operations=2,
            idle_exit_after_empty_checks=1,
        )
        fresh_queue = OpportunityQueue(repo_dir=self.temp_dir)
        self.assertEqual(fresh_queue.get_opportunity("OPP-119B-HUMAN").status, "WAITING_FOR_HUMAN")
        self.assertEqual(fresh_queue.get_opportunity("OPP-119B-SAFE").status, "COMPLETED")
        human_ops = [entry for entry in result["operations"] if entry["opportunity_id"] == "OPP-119B-HUMAN"]
        self.assertEqual(len(human_ops), 1)
        self.assertEqual(human_ops[0]["status"], "WAITING_FOR_HUMAN")
        self.assertEqual(result["stop_reason"], "IDLE_MONITORING_NO_WORK")

    def test_decision_intents_recover_across_three_crash_windows(self):
        workflow_id = "WF-119B-CRASH"
        decision = ChiefDecisionContract(
            chief_decision_id="dec-119b-crash",
            workflow_id=workflow_id,
            task_id="SOURCE-119B",
            result_id="SOURCE-RESULT-119B",
            correlation_id="corr-119b",
            decision="CONTINUE",
            next_task={"task_id": "NEXT-119B", "instruction": "Resume safely", "target_agent": "antigravity"},
        )
        supervisor = AutonomousSupervisor(repo_dir=self.temp_dir)
        supervisor.chief._persist_decision(decision.task_id, decision)  # A: crash after decision only
        restarted_a = AutonomousSupervisor(repo_dir=self.temp_dir)
        self.assertEqual(restarted_a.continuations.recover_pending(workflow_id)[0]["next_task"]["task_id"], "NEXT-119B")

        store = DecisionContinuationStore(self.temp_dir)
        intent = store.persist_intent(decision)  # B: crash after intent, before dispatch
        restarted_b = AutonomousSupervisor(repo_dir=self.temp_dir)
        self.assertEqual(restarted_b.continuations.recover_pending(workflow_id)[0]["dispatch_state"], "NEXT_TASK_INTENT_PERSISTED")

        dispatch = self.temp_dir / "events/dispatch/NEXT-119B-worker-job.json"
        dispatch.write_text(json.dumps({
            "task_id": "NEXT-119B",
            "workflow_id": workflow_id,
            "correlation_id": "corr-119b",
            "dispatch_id": intent["dispatch_id"],
        }), encoding="utf-8")  # C: crash after durable dispatch, before finalization
        restarted_c = AutonomousSupervisor(repo_dir=self.temp_dir)
        recovered = restarted_c.continuations.recover_pending(workflow_id)
        self.assertEqual(recovered, [])
        finalized = json.loads((self.temp_dir / "events/decision-continuations/dec-119b-crash.json").read_text(encoding="utf-8"))
        self.assertEqual(finalized["dispatch_state"], "NEXT_TASK_DISPATCHED")
        self.assertTrue((self.temp_dir / "events/consumed-decisions/dec-119b-crash.json").exists())
        self.assertEqual(restarted_c.continuations.recover_pending(workflow_id), [])  # second restart is idempotent

    def test_case_c_concurrent_recovery_finalizes_one_existing_dispatch_without_redispatch(self):
        workflow_id = "WF-119B-CASE-C-CONCURRENT"
        decision = ChiefDecisionContract(
            chief_decision_id="dec-119b-case-c-concurrent",
            workflow_id=workflow_id,
            task_id="SOURCE-119B-CASE-C",
            result_id="SOURCE-RESULT-119B-CASE-C",
            correlation_id="corr-119b-case-c",
            decision="CONTINUE",
            next_task={"task_id": "NEXT-119B-CASE-C", "instruction": "Resume existing dispatch", "target_agent": "antigravity"},
        )
        supervisor = AutonomousSupervisor(repo_dir=self.temp_dir)
        supervisor.chief._persist_decision(decision.task_id, decision)
        intent = DecisionContinuationStore(self.temp_dir).persist_intent(decision)
        dispatch = self.temp_dir / "events/dispatch/NEXT-119B-CASE-C-worker-job.json"
        dispatch.write_text(json.dumps({
            "task_id": "NEXT-119B-CASE-C",
            "workflow_id": workflow_id,
            "correlation_id": "corr-119b-case-c",
            "dispatch_id": intent["dispatch_id"],
            "builder_execution_count": 1,
        }), encoding="utf-8")

        with concurrent.futures.ProcessPoolExecutor(max_workers=2) as executor:
            attempts = [
                executor.submit(_recovery_contender, str(self.temp_dir), decision.chief_decision_id)
                for _ in range(2)
            ]
            outcomes = [attempt.result() for attempt in attempts]
        self.assertEqual(outcomes.count("DURABLE_DISPATCH_FOUND"), 1)
        self.assertEqual(outcomes.count("CONSUMED"), 1)
        self.assertEqual(len(list((self.temp_dir / "events/dispatch").glob("*-worker-job.json"))), 1)
        self.assertEqual(AutonomousSupervisor(repo_dir=self.temp_dir).continuations.recover_pending(workflow_id), [])

    def test_budget_reservations_are_persisted_and_fail_closed(self):
        external = SessionBudgetLedger(self.temp_dir, "m119b-external", SessionWorkBudget(max_external_actions=1))
        self.assertTrue(external.reserve("external", 1)[0])
        self.assertEqual(external.reserve("external", 1)[1], "EXTERNAL_ACTION_BUDGET_EXHAUSTED")
        model = SessionBudgetLedger(self.temp_dir, "m119b-model", SessionWorkBudget(max_model_work_budget=1))
        self.assertTrue(model.reserve("model", 1)[0])
        self.assertEqual(model.reserve("model", 1)[1], "MODEL_WORK_BUDGET_EXHAUSTED")

    def test_adversarial_canary_preserves_all_four_hour_guards(self):
        """One local, zero-spend canary combines the four safety boundaries.

        It deliberately creates a claim race, parks one human-gated branch while
        completing an independent branch, recovers a persisted Chief decision,
        and proves both model/external reservations fail closed.  The fixture has
        no model, network, or external-action implementation.
        """
        queue = OpportunityQueue(repo_dir=self.temp_dir)
        queue.add_opportunity(self._opportunity("OPP-119B-CANARY-RACE", "Shared READY opportunity"))
        with concurrent.futures.ProcessPoolExecutor(max_workers=2) as executor:
            attempts = [
                executor.submit(_claim_worker, str(self.temp_dir), "OPP-119B-CANARY-RACE", owner)
                for owner in ("canary-a", "canary-b")
            ]
            claim_results = [attempt.result() for attempt in attempts]
        self.assertEqual(sum(1 for won, _reason, _claim in claim_results if won), 1)
        self.assertEqual(sum(1 for won, _reason, _claim in claim_results if not won), 1)

        supervisor = HumanGateFixtureSupervisor(repo_dir=self.temp_dir)
        supervisor.opportunity_queue.add_opportunity(self._opportunity("OPP-119B-CANARY-HUMAN", "HUMAN approval required", priority=10))
        supervisor.opportunity_queue.add_opportunity(self._opportunity("OPP-119B-CANARY-SAFE", "Safe independent work", priority=9))
        session = supervisor.run_long_run_session(
            budget=SessionWorkBudget(max_wall_clock_seconds=20, max_external_actions=1, max_model_work_budget=1),
            session_id="m119b-adversarial-canary",
            enable_bundling=False,
            max_operations=2,
            idle_exit_after_empty_checks=1,
        )
        current = OpportunityQueue(repo_dir=self.temp_dir)
        self.assertEqual(current.get_opportunity("OPP-119B-CANARY-HUMAN").status, "WAITING_FOR_HUMAN")
        self.assertEqual(current.get_opportunity("OPP-119B-CANARY-SAFE").status, "COMPLETED")
        self.assertEqual(session["stop_reason"], "IDLE_MONITORING_NO_WORK")

        decision = ChiefDecisionContract(
            chief_decision_id="dec-119b-canary",
            workflow_id="WF-119B-CANARY",
            task_id="SOURCE-119B-CANARY",
            result_id="SOURCE-RESULT-119B-CANARY",
            correlation_id="corr-119b-canary",
            decision="CONTINUE",
            next_task={"task_id": "NEXT-119B-CANARY", "instruction": "Recover safely", "target_agent": "antigravity"},
        )
        supervisor.chief._persist_decision(decision.task_id, decision)
        recovered = AutonomousSupervisor(repo_dir=self.temp_dir).continuations.recover_pending(decision.workflow_id)
        self.assertEqual([item["next_task"]["task_id"] for item in recovered], ["NEXT-119B-CANARY"])

        ledger = SessionBudgetLedger(self.temp_dir, "m119b-canary-budget", SessionWorkBudget(max_external_actions=1, max_model_work_budget=1))
        self.assertTrue(ledger.reserve("external", 1)[0])
        self.assertFalse(ledger.reserve("external", 1)[0])
        self.assertTrue(ledger.reserve("model", 1)[0])
        self.assertFalse(ledger.reserve("model", 1)[0])


if __name__ == "__main__":
    unittest.main()
