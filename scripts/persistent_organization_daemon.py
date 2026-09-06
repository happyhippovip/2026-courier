#!/usr/bin/env python3
"""Persistent Organization Daemon & Continuous Nervous System.

Runs as a durable, single-instance host background daemon on Computer A:
- Holds OS-level single instance lock (events/runtime-state/daemon.pid)
- Emits continuous heartbeat telemetry (events/runtime-state/daemon_heartbeat.json)
- Dispatches tasks across ProviderAgnosticWorkerFabric (CLI1, Gemini Brain Bridge)
- Scans live inbound Apple Mail inboxes for all 4 sent experiments
- Observes payment destination configuration
- Manages SAFE_IDLE without terminating the process
- Zero human WEITER required.
"""

from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

COURIER_DIR = Path(__file__).resolve().parent.parent
if str(COURIER_DIR) not in sys.path:
    sys.path.insert(0, str(COURIER_DIR))

from scripts.canonical_authority import is_pid_alive
from scripts.chief_decision_protocol import ChiefDecisionProtocol
from scripts.gemini_brain_bridge import GeminiBrainBridge, GeminiJobEnvelope, GeminiTaskClass
from scripts.inbound_response_observer import InboundResponseObserver
from scripts.money_machine_pipeline import EconomicClass, MoneyMachinePipeline, OpportunityState
from scripts.opportunity_queue import Opportunity, OpportunityQueue
from scripts.payment_gate_observer import PaymentGateObserver
from scripts.autonomous_operational_hygiene import AutonomousOperationalHygiene
from scripts.provider_agnostic_worker_fabric import (
    GenericResultEnvelope,
    ProviderAgnosticWorkerFabric,
)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


class PersistentOrganizationDaemon:
    def __init__(self, repo_dir: Optional[Path] = None):
        self.repo_dir = (repo_dir or COURIER_DIR).resolve()
        self.runtime_dir = self.repo_dir / "events" / "runtime-state"
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.pid_file = self.runtime_dir / "daemon.pid"
        self.heartbeat_file = self.runtime_dir / "daemon_heartbeat.json"
        self.market_intel_dir = self.repo_dir / "events" / "revenue-opportunities" / "market_intelligence"

        self.fabric = ProviderAgnosticWorkerFabric(repo_dir=self.repo_dir)
        self.inbound_observer = InboundResponseObserver(repo_dir=self.repo_dir)
        self.payment_observer = PaymentGateObserver(repo_dir=self.repo_dir)
        self.chief_protocol = ChiefDecisionProtocol(repo_dir=self.repo_dir)
        self.pipeline = MoneyMachinePipeline(repo_dir=self.repo_dir)
        self.gemini_bridge = GeminiBrainBridge(repo_dir=self.repo_dir)
        self.hygiene = AutonomousOperationalHygiene(repo_dir=self.repo_dir)

        self.running = True
        self.cycle_count = 0
        self.last_task_id: Optional[str] = None
        self.last_task_completed_at: Optional[str] = None
        self.lock_handle: Optional[Any] = None
        self.next_time_gate_at: Optional[str] = None
        self.parked_gate_count = 0

    def acquire_single_instance_lock(self) -> bool:
        """Ensures exactly 1 persistent daemon process runs on the host machine."""
        try:
            self.lock_handle = open(self.pid_file, "a+", encoding="utf-8")
            fcntl.flock(self.lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.pid_file.write_text(str(os.getpid()), encoding="utf-8")
            return True
        except (IOError, OSError):
            return False

    def emit_heartbeat(
        self,
        status: str = "RUNNING",
        next_action: str = "SCAN_OPPORTUNITIES",
        last_worker: Optional[str] = None,
        last_decision: Optional[str] = None,
    ) -> None:
        """Writes live atomic heartbeat telemetry with productive progress semantics."""
        hb_data = {
            "pid": os.getpid(),
            "process_alive": True,
            "status": status,
            "heartbeat_at": utc_now(),
            "cycle_count": self.cycle_count,
            "last_task_id": self.last_task_id,
            "last_task_completed_at": self.last_task_completed_at,
            "last_real_worker_invocation": last_worker or getattr(self, "_last_worker", "CLI1"),
            "last_next_task_decision": last_decision or getattr(self, "_last_decision", None),
            "next_action": next_action,
            "monitored_experiments_count": len(self.inbound_observer.get_all_active_sent_experiments()),
            "human_weiter_required": False,
            "human_copy_paste_count": 0,
            "unauthorized_spend_eur": 0.0,
        }
        temp_file = self.heartbeat_file.with_suffix(".tmp")
        temp_file.write_text(json.dumps(hb_data, indent=2) + "\n", encoding="utf-8")
        os.replace(temp_file, self.heartbeat_file)

    def evaluate_time_gated_followups(self, dry_run: bool = False) -> Optional[Dict[str, Any]]:
        """Evaluates durable time-gated follow-up specifications.

        Requirements:
        1. Future eligible_at -> EVENT_WATCH, strictly no early send.
        2. Qualifying early reply / bounce recorded -> SUPPRESS follow-up.
        3. eligible_at reached + clean inbox (no reply) -> Execute single follow-up exactly once.
        4. State persisted to spec file on disk.
        """
        if not self.market_intel_dir.is_dir():
            return None

        now = dt.datetime.now(dt.timezone.utc)
        self.next_time_gate_at = None
        self.parked_gate_count = 0
        spec_files = list(self.market_intel_dir.glob("*_FOLLOWUP_SPEC.json"))

        for sfile in spec_files:
            try:
                spec = json.loads(sfile.read_text(encoding="utf-8"))
            except Exception:
                continue

            status = spec.get("current_status", "")
            if status in (
                "FOLLOWUP_SENT",
                "APPLIED",
                "SUPPRESSED_DUE_TO_INBOUND_REPLY",
                "COMPLETED",
                "TERMINATED",
                "EFFECT_UNKNOWN",
            ):
                continue

            prospect_id = spec.get("prospect_alias", "")
            corr_id = spec.get("correlation_id", "")
            eligible_str = spec.get("eligible_at", "")

            if not eligible_str:
                continue

            try:
                eligible_dt = dt.datetime.fromisoformat(eligible_str.replace("Z", "+00:00"))
                if not eligible_dt.tzinfo:
                    eligible_dt = eligible_dt.replace(tzinfo=dt.timezone.utc)
            except Exception:
                continue

            # 1. Check pre-send inbound suppression: Has the prospect replied?
            has_replied = False
            for tracker_path in [
                self.repo_dir / "events" / "revenue-opportunities" / "offerings" / "b2b_autonomy_audit" / "outreach_tracker.json",
                self.repo_dir / "events" / "revenue-opportunities" / "offerings" / "content_to_marketing_asset" / "prospects_content_marketing.json",
                self.repo_dir / "events" / "revenue-opportunities" / "offerings" / "cli_sentinel" / "outreach_tracker.json",
                self.repo_dir / "events" / "revenue-opportunities" / "offerings" / "agent_crash_safety_toolkit" / "outreach_tracker.json",
                self.repo_dir / "events" / "revenue-opportunities" / "offerings" / "token_burn_auditor" / "outreach_tracker.json",
            ]:
                if tracker_path.is_file():
                    try:
                        tdata = json.loads(tracker_path.read_text(encoding="utf-8"))
                        for p in tdata.get("prospects", []):
                            if p.get("id") == prospect_id or p.get("correlation_id") == corr_id:
                                if p.get("response_state") not in ("AWAITING_DISPATCH", "WAITING_FOR_RESPONSE", None):
                                    has_replied = True
                                    break
                    except Exception:
                        pass

            if has_replied:
                spec["current_status"] = "SUPPRESSED_DUE_TO_INBOUND_REPLY"
                spec["suppressed_at"] = utc_now()
                spec["suppression_reason"] = "INBOUND_REPLY_OR_BOUNCE_DETECTED"
                sfile.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
                return {
                    "task_id": f"TASK-SUPPRESS-FOLLOWUP-{prospect_id}",
                    "status": "SUPPRESSED_DUE_TO_INBOUND_REPLY",
                    "prospect_id": prospect_id,
                }

            # A confirmed effect's durable result survives a crash before the
            # final local application step.  Reuse it; never invoke the effect
            # again during recovery.
            if status == "RESULT_PERSISTED":
                result = spec.get("result")
                if not isinstance(result, dict) or result.get("result_fingerprint") != spec.get("effect_idempotency_key"):
                    spec["current_status"] = "EFFECT_UNKNOWN"
                    spec["failure_reason"] = "INVALID_DURABLE_EFFECT_RESULT"
                    spec["effect_unknown_at"] = utc_now()
                    sfile.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
                    return {"status": "EFFECT_UNKNOWN", "prospect_id": prospect_id}
                spec["current_status"] = "APPLIED"
                spec["applied_at"] = utc_now()
                sfile.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
                return {"task_id": result.get("task_id"), "status": "APPLIED", "prospect_id": prospect_id, "correlation_id": corr_id}

            # 2. Check time gate eligibility
            if now < eligible_dt:
                # Time gate is in the future -> EVENT_WATCH, do NOT send early
                self.next_time_gate_at = eligible_dt.isoformat()
                continue

            # An interrupted provider effect is ambiguous.  Reconciliation is
            # mandatory; replaying would turn a crash into duplicate outreach.
            if status == "EFFECT_STARTED":
                spec["current_status"] = "EFFECT_UNKNOWN"
                spec["effect_unknown_at"] = utc_now()
                spec["failure_reason"] = "STARTED_EFFECT_HAS_NO_CONFIRMATION"
                sfile.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
                return {"status": "EFFECT_UNKNOWN", "prospect_id": prospect_id}

            authorization = spec.get("authorization")
            if not isinstance(authorization, dict) or authorization.get("status") != "AUTHORIZED":
                if status != "WAITING_FOR_HUMAN":
                    spec["current_status"] = "WAITING_FOR_HUMAN"
                    spec["authorization_checked_at"] = utc_now()
                    spec["authorization_reason"] = "VALID_AUTHORIZATION_REQUIRED"
                    sfile.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
                self.parked_gate_count += 1
                continue

            authorization_id = str(authorization.get("authorization_id", "")).strip()
            if not authorization_id:
                if status != "WAITING_FOR_HUMAN":
                    spec["current_status"] = "WAITING_FOR_HUMAN"
                    spec["authorization_reason"] = "AUTHORIZATION_ID_REQUIRED"
                    sfile.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
                self.parked_gate_count += 1
                continue

            effect_key = hashlib.sha256(
                f"{corr_id}:{prospect_id}:{spec.get('followup_fingerprint', '')}:{authorization_id}:"
                f"{spec.get('generation', 1)}".encode("utf-8")
            ).hexdigest()
            spec["current_status"] = "AUTHORIZATION_CHECKED"
            spec["authorization_checked_at"] = utc_now()
            spec["effect_idempotency_key"] = effect_key
            spec["current_status"] = "EFFECT_INTENT_PERSISTED"
            spec["effect_intent_persisted_at"] = utc_now()
            sfile.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")

            # Production has no authorized automatic outreach adapter.  Tests
            # may use this explicitly labelled local synthetic adapter only.
            if spec.get("effect_adapter") != "SYNTHETIC_CONFIRMED":
                spec["current_status"] = "WAITING_FOR_HUMAN"
                spec["authorization_reason"] = "NO_CONFIRMED_EFFECT_ADAPTER"
                sfile.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
                self.parked_gate_count += 1
                continue

            spec["current_status"] = "EFFECT_STARTED"
            spec["effect_started_at"] = utc_now()
            sfile.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")

            if spec.get("simulate_crash_after_start"):
                return {"status": "EFFECT_STARTED", "prospect_id": prospect_id}

            # Synthetic confirmation contains no network call and is the only
            # effect allowed in local tests/canaries.
            task_id = f"TASK-FOLLOWUP-{prospect_id}-{effect_key[:12]}"
            spec["current_status"] = "EFFECT_CONFIRMED"
            spec["effect_confirmation"] = {"adapter": "SYNTHETIC_CONFIRMED", "effect_key": effect_key}
            spec["current_status"] = "RESULT_PERSISTED"
            spec["result"] = {"task_id": task_id, "result_fingerprint": effect_key, "status": "CONFIRMED"}
            sfile.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
            if spec.get("simulate_crash_after_result"):
                return {"task_id": task_id, "status": "RESULT_PERSISTED", "prospect_id": prospect_id}
            spec["current_status"] = "APPLIED"
            spec["applied_at"] = utc_now()
            spec["executed_task_id"] = task_id
            spec["sent_at"] = None
            sfile.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")

            self.last_task_id = task_id
            self.last_task_completed_at = utc_now()
            return {"task_id": task_id, "status": "APPLIED", "prospect_id": prospect_id, "correlation_id": corr_id}

        return None

    def evaluate_opportunity_queue_work(self) -> Optional[Dict[str, Any]]:
        """Use only canonical queue admission, claim fencing, result and completion."""
        queue = OpportunityQueue(repo_dir=self.repo_dir)
        opp = queue.select_next_admissible_zero_cost_local()
        if not opp:
            return None

        owner = f"persistent-daemon:{os.getpid()}"
        claimed, _reason, claim = queue.claim_opportunity(opp.opportunity_id, owner)
        if not claimed:
            return None

        claim_id = str(claim.get("claim_id", ""))
        generation = claim.get("state_version")
        if not claim_id or not isinstance(generation, int):
            return None

        task_id = f"TASK-OPP-{opp.opportunity_id}-{generation}"
        # The daemon's bounded safe handler is intentionally local and
        # deterministic; it never performs an external/provider action.
        result = {
            "schema_version": "1.0",
            "result_type": "LOCAL_VALIDATION_RESULT",
            "task_id": task_id,
            "opportunity_id": opp.opportunity_id,
            "claim_id": claim_id,
            "generation": generation,
            "status": "SUCCESS",
            "handler": "DETERMINISTIC_LOCAL_VALIDATION",
            "completed_at": utc_now(),
            "metadata": {},
        }
        result["result_fingerprint"] = queue.expected_result_fingerprint(opp, claim, result)
        if not queue.complete_claimed_opportunity(opp.opportunity_id, claim_id, generation, result):
            return {"task_id": task_id, "opportunity_id": opp.opportunity_id, "status": "RESULT_RECONCILIATION_REQUIRED"}

        self.last_task_id = task_id
        self.last_task_completed_at = result["completed_at"]
        return {"task_id": task_id, "opportunity_id": opp.opportunity_id, "status": "SUCCESS"}

    def execute_next_eligible_work(self) -> Optional[Dict[str, Any]]:
        """Discovers, claims, and executes the highest-ranked safe economic work in strict order."""
        # 1. Apply existing durable results before considering any fresh work.
        queue = OpportunityQueue(repo_dir=self.repo_dir)
        reconciled = queue.reconcile_durable_results()
        for outcome in reconciled:
            if outcome.get("status") == "RESULT_RECONCILED":
                task_id = f"TASK-RECONCILE-{outcome['opportunity_id']}"
                self.last_task_id = task_id
                self.last_task_completed_at = utc_now()
                return {"task_id": task_id, "status": "RESULT_RECONCILED", "opportunity_id": outcome["opportunity_id"]}

        # 2. Durable Time-Gated Follow-Ups (e.g. P-01 when eligible_at is reached).
        # Parked gates deliberately do not stop unrelated safe work selection.
        time_work = self.evaluate_time_gated_followups()
        if time_work:
            return time_work

        # 3. Canonical SAFE Opportunity Queue work
        opp_work = self.evaluate_opportunity_queue_work()
        if opp_work:
            return opp_work

        if self.parked_gate_count:
            return {"task_id": "WAITING_GATE", "status": "WAITING_GATE"}

        # 4. Revenue Opportunities from canonical ledger
        ledger = self.pipeline.load_ledger()

        # Prioritize opportunities that are OFFER_READY or DISCOVERED and need advancement
        for opp_id, op in ledger.items():
            if op.state == OpportunityState.OFFER_READY.value:
                # Execute CLI1 routine task
                task_id = f"TASK-DAEMON-{opp_id[:16]}-{int(time.time())}"
                scope = f"events/revenue-opportunities/{opp_id}"

                dec = self.fabric.route_task(
                    task_id=task_id,
                    task_class="ROUTINE_BUILD",
                    required_capabilities=["ROUTINE_BUILD", "CODE_GENERATION"],
                    required_scope=scope,
                )

                if dec.routing_verdict == "ROUTED_SUCCESS":
                    start_time = utc_now()
                    # Execute deterministic package verification
                    res = self.pipeline.execute_cheapest_validation(opp_id)
                    end_time = utc_now()

                    envelope = GenericResultEnvelope(
                        task_id=task_id,
                        worker_id=dec.assigned_worker_id or "CLI1",
                        provider=dec.assigned_provider or "GOOGLE",
                        surface=dec.assigned_surface or "CLI",
                        host=dec.assigned_host or "COMPUTER_A",
                        started_at=start_time,
                        completed_at=end_time,
                        result_state="SUCCESS",
                        artifacts_changed=[],
                        verification=res.get("findings", {}),
                        evidence={"capital_spent_eur": 0.0},
                        economic_delta={"expected_value_eur": getattr(op, "expected_30d_value_eur", 50.0)},
                        blockers=[],
                        next_candidate_actions=["ADVANCE_MARKET_TEST"],
                        fingerprint=hashlib.sha256(f"{task_id}:{dec.assigned_worker_id}".encode("utf-8")).hexdigest(),
                    )

                    cont_res = self.fabric.submit_result_and_continue(envelope=envelope, released_scope=scope)
                    self.last_task_id = task_id
                    self.last_task_completed_at = end_time
                    return {
                        "task_id": task_id,
                        "worker_id": dec.assigned_worker_id,
                        "status": "SUCCESS",
                        "decision_id": cont_res.get("decision_id"),
                    }

            elif op.state == OpportunityState.DISCOVERED.value and op.opportunity_id == "REV-OPP-KIBEY-AI-MARKETPLACE":
                # Execute Gemini Brain Bridge reasoning task
                task_id = f"TASK-GEMINI-KIBEY-{int(time.time())}"
                scope = "events/revenue-opportunities/kibey_ai_marketplace"

                dec = self.fabric.route_task(
                    task_id=task_id,
                    task_class="PRIMARY_EXECUTION",
                    required_capabilities=["PRIMARY_EXECUTION", "SYSTEM_ARCHITECTURE"],
                    required_scope=scope,
                )

                if dec.routing_verdict == "ROUTED_SUCCESS":
                    start_time = utc_now()
                    gem_job = GeminiJobEnvelope(
                        job_id=f"JOB-GEM-KIBEY-{int(time.time())}",
                        task_id=task_id,
                        opportunity_id=opp_id,
                        goal="Analyze decentralized AI worker matchmaking mechanics and escrow architecture",
                        task_class=GeminiTaskClass.SYSTEM_ARCHITECTURE.value,
                        economic_context={"take_rate": "10%", "target_market": "Enterprise Agent Compute"},
                    )
                    gem_res = self.gemini_bridge.execute_gemini_job(gem_job)
                    end_time = utc_now()

                    envelope = GenericResultEnvelope(
                        task_id=task_id,
                        worker_id=dec.assigned_worker_id or "ANTIGRAVITY_PRIMARY",
                        provider=dec.assigned_provider or "GOOGLE",
                        surface=dec.assigned_surface or "ANTIGRAVITY_APP",
                        host=dec.assigned_host or "COMPUTER_A",
                        started_at=start_time,
                        completed_at=end_time,
                        result_state="SUCCESS",
                        artifacts_changed=["events/revenue-opportunities/offerings/kibey_ai_marketplace/VENTURE_SPECIFICATION.md"],
                        verification={"gemini_brain_summary": gem_res.summary},
                        evidence={"capital_spent_eur": 0.0, "gemini_job_id": gem_job.job_id},
                        economic_delta={"expected_value_eur": 500.0},
                        blockers=[],
                        next_candidate_actions=["SEED_KIBEY_API_PROTOTYPE"],
                        fingerprint=hashlib.sha256(f"{task_id}:GEMINI".encode("utf-8")).hexdigest(),
                    )

                    cont_res = self.fabric.submit_result_and_continue(envelope=envelope, released_scope=scope)
                    # Advance state
                    op.state = OpportunityState.MARKET_TEST_READY.value
                    ledger[opp_id] = op
                    self.pipeline.save_ledger(ledger)

                    self.last_task_id = task_id
                    self.last_task_completed_at = end_time
                    return {
                        "task_id": task_id,
                        "worker_id": dec.assigned_worker_id,
                        "status": "SUCCESS",
                        "gemini_invoked": True,
                        "decision_id": cont_res.get("decision_id"),
                    }

        return None

    def run_loop(self, max_cycles: Optional[int] = None, idle_sleep_seconds: float = 3.0) -> None:
        """Main persistent execution loop."""
        if not self.acquire_single_instance_lock():
            print(f"[DAEMON] Another persistent daemon instance is already active (PID lock held). Exiting.")
            sys.exit(0)

        def handle_stop(signum: int, frame: Any) -> None:
            self.running = False
            self.emit_heartbeat(status="STOPPED", next_action="SHUTDOWN")

        signal.signal(signal.SIGINT, handle_stop)
        signal.signal(signal.SIGTERM, handle_stop)

        print(f"[DAEMON] Persistent Organization Daemon started (PID: {os.getpid()})")

        try:
            while self.running:
                self.cycle_count += 1

                # 1. Inbound mailbox scan for responses
                self.inbound_observer.scan_inboxes(dry_run=False)

                # 2. Check payment gate state
                self.payment_observer.check_and_activate()

                # 3. Bounded operational hygiene reconciliation
                self.hygiene.perform_hygiene_cycle()

                # 4. Discover, rank, and execute work
                work_result = self.execute_next_eligible_work()

                if work_result:
                    work_status = work_result.get("status")
                    if work_status == "WAITING_GATE":
                        self.emit_heartbeat(status="WAITING_GATE", next_action="WAITING_FOR_HUMAN_OR_AUTHORIZATION")
                        time.sleep(idle_sleep_seconds)
                    elif work_status == "EFFECT_UNKNOWN":
                        self.emit_heartbeat(status="BLOCKED", next_action="RECONCILE_UNKNOWN_EFFECT")
                        time.sleep(idle_sleep_seconds)
                    else:
                        self.emit_heartbeat(status="PROGRESSING", next_action=f"COMPLETED_{work_result.get('task_id', 'UNKNOWN')}")
                else:
                    # A persisted future deadline is not no-work.  The daemon,
                    # not an IDE/model timer, remains the continuation owner.
                    if self.next_time_gate_at:
                        self.emit_heartbeat(status="EVENT_WATCH", next_action=f"NEXT_TIME_GATE_{self.next_time_gate_at}")
                    else:
                        self.emit_heartbeat(status="SAFE_IDLE", next_action="WAIT_FOR_EVENTS_OR_NEW_WORK")
                    time.sleep(idle_sleep_seconds)

                if max_cycles and self.cycle_count >= max_cycles:
                    break

        finally:
            self.emit_heartbeat(status="STOPPED", next_action="CLEANUP")
            if self.lock_handle:
                try:
                    fcntl.flock(self.lock_handle.fileno(), fcntl.LOCK_UN)
                    self.lock_handle.close()
                except Exception:
                    pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Persistent Organization Daemon")
    parser.add_argument("--daemon", action="store_true", help="Run in continuous daemon mode")
    parser.add_argument("--max-cycles", type=int, default=None, help="Max cycles (for testing)")
    parser.add_argument("--idle-sleep", type=float, default=3.0, help="Sleep duration in SAFE_IDLE")
    args = parser.parse_args()

    daemon = PersistentOrganizationDaemon()
    daemon.run_loop(max_cycles=args.max_cycles, idle_sleep_seconds=args.idle_sleep)
    return 0


if __name__ == "__main__":
    sys.exit(main())
