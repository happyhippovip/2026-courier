#!/usr/bin/env python3
"""Reviewer-owned fail-closed acceptance tests for Computer-A crash safety.

These tests intentionally fail on the pre-remediation implementation.  They
are a post-builder acceptance gate, not a production test replacement.
"""

from __future__ import annotations

import datetime as dt
import json
import multiprocessing as mp
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.autonomous_opportunity_discovery import CanonicalOpportunity
from scripts.autonomous_single_pc_executor import SinglePCAutonomousExecutor
from scripts.autonomous_work_session_controller import AutonomousWorkSessionController
from scripts.elite_execution_core import EliteExecutionCore
from scripts.opportunity_queue import Opportunity, OpportunityQueue
from scripts.real_autonomy_runtime import RealAutonomyRuntime, SessionStatus


def _heavy_authority_contender(repo_dir: str, task_id: str) -> bool:
    """Independent process contender; no shared Python object is retained."""
    core = EliteExecutionCore(repo_dir=Path(repo_dir))
    acquired, _reason = core.acquire_scope_lock(task_id, ["HEAVY:GOOGLE"])
    return acquired


class CrashSafetyOracle(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="autonomy_crash_oracle_"))
        for rel in ("events/autonomy-runtime", "events/opportunity-queue", "events/chief-brain"):
            (self.root / rel).mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def test_idle_does_not_consume_productive_budget_and_new_work_wakes(self) -> None:
        runtime = RealAutonomyRuntime(repo_dir=self.root)
        runtime.start_night_session("idle-oracle", "idle safety", max_iterations=2)
        for _ in range(20):
            runtime.execute_session_step(deterministic_resolver=lambda _tid: (False, {}))
        session = runtime._load_session()
        self.assertNotEqual(session.status, SessionStatus.STOPPED_SAFELY,
                            "idle observations exhausted the productive iteration limit")

        runtime.opp_queue.add_opportunity(Opportunity(
            opportunity_id="OPP-IDLE-WAKE",
            source="ORACLE", objective_id="IDLE", project="TMP",
            description="new deterministic evidence", priority=1,
        ))
        result = runtime.execute_session_step(deterministic_resolver=lambda tid: (tid == "OPP-IDLE-WAKE", {"ok": True}))
        self.assertEqual(result.get("status"), "PROGRESS_MADE")

    def test_crash_after_effect_is_not_blindly_replayed(self) -> None:
        marker = self.root / "effect-count"
        candidate = CanonicalOpportunity(
            opportunity_id="work-fruitki-inventory-summary",
            description="crash-window oracle", status="READY", priority=9,
        )

        def configure(executor: SinglePCAutonomousExecutor, crash: bool) -> None:
            executor.discovery.discover_opportunities = lambda **_kwargs: [candidate]
            executor.discovery.rank_opportunities = lambda items: items
            def handler() -> dict:
                count = int(marker.read_text()) if marker.exists() else 0
                marker.write_text(str(count + 1))
                if crash:
                    raise RuntimeError("simulated crash after side effect")
                return {"status": "SUCCESS"}
            executor._handlers = {candidate.opportunity_id: handler}

        first = SinglePCAutonomousExecutor(repo_dir=self.root, session_id="effect-oracle")
        configure(first, crash=True)
        with self.assertRaises(RuntimeError):
            first.execute_shift(max_steps=1)

        restarted = SinglePCAutonomousExecutor(repo_dir=self.root, session_id="effect-oracle")
        configure(restarted, crash=False)
        restarted.execute_shift(max_steps=1)
        self.assertEqual(marker.read_text(), "1",
                         "unknown side effect was blindly replayed after restart")

    def test_unapplied_result_is_replayed_after_crash(self) -> None:
        runtime = RealAutonomyRuntime(repo_dir=self.root)
        def crash_apply(**_kwargs):
            raise RuntimeError("simulated crash after dedupe persistence")
        runtime.chief_brain.ingest_worker_result = crash_apply
        with self.assertRaises(RuntimeError):
            runtime.ingest_real_event("RESULT", "LOCAL", "corr-result", {"outcome": "SUCCESS"}, "TASK-RESULT")

        restarted = RealAutonomyRuntime(repo_dir=self.root)
        replay = restarted.ingest_real_event("RESULT", "LOCAL", "corr-result", {"outcome": "SUCCESS"}, "TASK-RESULT")
        self.assertEqual(replay.get("status"), "INGESTED",
                         "dedupe marker permanently suppressed an unapplied valid result")

    def test_stale_cleanup_never_unlinks_a_replacement_claim(self) -> None:
        queue = OpportunityQueue(repo_dir=self.root)
        queue.add_opportunity(Opportunity(
            opportunity_id="OPP-STALE-RACE", source="ORACLE", objective_id="LEASE",
            project="TMP", description="lease race", allowed_scope=[],
        ))
        claim_path = queue._claim_path("OPP-STALE-RACE")
        stale = {
            "opportunity_id": "OPP-STALE-RACE", "claim_owner": "dead",
            "claim_id": "old", "pid": 99999999,
            "lease_expires_at": (dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=1)).isoformat(),
        }
        claim_path.write_text(json.dumps(stale), encoding="utf-8")
        replacement = dict(stale, claim_owner="replacement", claim_id="new",
                           pid=1,
                           lease_expires_at=(dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1)).isoformat())
        original_unlink = Path.unlink
        injected = {"done": False}

        def replace_then_unlink(path: Path, *args, **kwargs):
            if path == claim_path and not injected["done"]:
                injected["done"] = True
                path.write_text(json.dumps(replacement), encoding="utf-8")
            return original_unlink(path, *args, **kwargs)

        Path.unlink = replace_then_unlink
        try:
            queue.claim_opportunity("OPP-STALE-RACE", "reclaimer")
        finally:
            Path.unlink = original_unlink
        surviving = json.loads(claim_path.read_text(encoding="utf-8")) if claim_path.exists() else {}
        self.assertEqual(surviving.get("claim_id"), "new",
                         "stale pathname cleanup removed a replacement claim")

    def test_running_without_fresh_liveness_is_not_live(self) -> None:
        state = {
            "session_id": "stale-running", "status": "RUNNING",
            "updated_at": "2000-01-01T00:00:00+00:00", "accounting": {},
        }
        (self.root / "events/autonomy-runtime/session_controller_state.json").write_text(json.dumps(state), encoding="utf-8")
        controller = AutonomousWorkSessionController(repo_dir=self.root, session_id="stale-running")
        self.assertNotEqual(controller.session.status, "RUNNING",
                            "stale RUNNING state is accepted as live authority without liveness evidence")

    def test_two_independent_policy_cores_cannot_hold_same_heavy_authority(self) -> None:
        with mp.get_context("spawn").Pool(2) as pool:
            got_first, got_second = pool.starmap(
                _heavy_authority_contender,
                [(str(self.root), "heavy-a"), (str(self.root), "heavy-b")],
            )
        self.assertEqual(int(got_first) + int(got_second), 1,
                         "heavy authority is in-memory only and admits two independent contenders")


if __name__ == "__main__":
    unittest.main()
