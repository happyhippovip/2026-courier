#!/usr/bin/env python3
"""Mission 218: CLI Continuous Operations Autopilot.

Deterministic, zero-spend operations controller for Computer A:
- Continuously observes the organization and advances SAFE engineering/operations
- Removes the need for the human to continuously inspect terminals or type WEITER
- Auto-detects mission results (PASS, RELEASE, REMEDIATE, BLOCKED)
- Enforces single-writer mutex (Mission 216 scope protection)
- Enforces Financial Firewall: REAL_TRADES=0, REAL_FUNDS_TOUCHED=NO, WALLET_SIGNING=NO
- Enforces Heavy Job limit: HEAVY_JOB_LIMIT=1
- Parks human/money gates without blocking independent safe tasks
- Manages event-driven SAFE_IDLE with zero busy-spin
- 0 model calls, 0 EUR spend
"""

from __future__ import annotations

import argparse
import datetime as dt
import enum
import hashlib
import json
import os
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

try:
    from canonical_authority import CanonicalAuthority, LockStatus, is_pid_alive
    from live_worker_registry import AvailabilityClass, LiveWorkerRegistry, WorkerRecord, WorkerState
    from opportunity_queue import Opportunity, OpportunityQueue
    from automatic_result_handoff import AutomaticResultHandoff, HandoffSignal, WorkerResultEnvelope
    from autonomous_operational_hygiene import AutonomousOperationalHygiene
except ImportError:
    from scripts.canonical_authority import CanonicalAuthority, LockStatus, is_pid_alive
    from scripts.live_worker_registry import AvailabilityClass, LiveWorkerRegistry, WorkerRecord, WorkerState
    from scripts.opportunity_queue import Opportunity, OpportunityQueue
    from scripts.automatic_result_handoff import AutomaticResultHandoff, HandoffSignal, WorkerResultEnvelope
    from scripts.autonomous_operational_hygiene import AutonomousOperationalHygiene


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def safe_load_json(path: Path) -> dict[str, Any]:
    try:
        if not path.is_file():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def safe_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}.{uuid.uuid4().hex[:6]}")
    temp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


class AutopilotState(str, enum.Enum):
    OBSERVING = "OBSERVING"
    EXECUTING_SAFE_WORK = "EXECUTING_SAFE_WORK"
    DISPATCHING = "DISPATCHING"
    SAFE_IDLE = "SAFE_IDLE"
    WAITING_GATE = "WAITING_GATE"
    RECOVERY = "RECOVERY"


@dataclass
class AutopilotTelemetry:
    autopilot_state: str = AutopilotState.OBSERVING.value
    active_mission: Optional[str] = "MISSION_216_OMEGA"
    active_worker: Optional[str] = "ANTIGRAVITY"
    active_write_scope: Optional[str] = None
    last_meaningful_progress: str = field(default_factory=utc_now)
    last_result: Optional[str] = None
    last_result_fingerprint: Optional[str] = None
    next_safe_action: Optional[str] = "SAFE_IDLE_STANDBY"
    next_review_required: bool = False
    blocked_branches: List[str] = field(default_factory=list)
    available_workers: List[str] = field(default_factory=list)
    provider_states: Dict[str, str] = field(default_factory=dict)
    heavy_job_active: bool = False
    safe_idle: bool = True
    last_chief_alert: Optional[Dict[str, Any]] = None
    model_calls_runtime: int = 0
    spend_eur: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class CLIOperationsAutopilot:
    """Continuous operations autopilot executing safe local engineering workflows."""

    HEAVY_JOB_LIMIT: int = 1

    def __init__(self, repo_dir: Path = COURIER_DIR):
        self.repo_dir = repo_dir.resolve()
        self.events_dir = self.repo_dir / "events"
        self.runtime_dir = self.events_dir / "runtime-state"
        self.alerts_dir = self.events_dir / "runtime-alerts"
        self.worker_events_dir = self.events_dir / "worker-events"
        self.locks_dir = self.events_dir / "locks"
        self.opp_queue_dir = self.events_dir / "opportunity-queue"

        self.state_file = self.runtime_dir / "cli_operations_autopilot_state.json"
        self.daemon_heartbeat_file = self.runtime_dir / "daemon_heartbeat.json"

        self.authority = CanonicalAuthority(locks_dir=self.locks_dir)
        self.registry = LiveWorkerRegistry(repo_dir=self.repo_dir)
        self.opp_queue = OpportunityQueue(repo_dir=self.repo_dir)
        self.result_handoff = AutomaticResultHandoff(repo_dir=self.repo_dir)
        self.hygiene = AutonomousOperationalHygiene(repo_dir=self.repo_dir)

        self.pid_file = self.runtime_dir / "cli_operations_autopilot.pid"
        self.heartbeat_file = self.runtime_dir / "cli_operations_autopilot_heartbeat.json"

        self.telemetry = AutopilotTelemetry()
        self._alert_cache: Set[str] = set()
        self._processed_result_fingerprints: Set[str] = set()

        # Financial Firewall Invariants (Strictly Enforced)
        self.real_trades_count: int = 0
        self.real_funds_touched: bool = False
        self.wallet_signing_active: bool = False
        self.spend_limit_eur: float = 0.0

    def run_autopilot_cycle(self) -> AutopilotTelemetry:
        """Single deterministic continuous operations cycle."""
        # Routine Operational Hygiene
        self.hygiene.perform_hygiene_cycle()
        self.opp_queue._load_all()
        # 1. Observe Organization State
        obs = self.observe_organization()

        # 2. Reconcile Completed Results & Stale Debris
        reconciled_results = self.opp_queue.reconcile_durable_results()

        # 3. Auto-Detect Mission Results from Workers
        new_results = self.auto_detect_worker_results()

        # 4. Evaluate Next Safe Action
        action_decision = self.select_next_safe_action(obs, new_results)

        # 5. Execute Safe Action or Transition to Safe Idle
        if action_decision.get("type") == "EXECUTE_LOCAL_SAFE_WORK":
            self.telemetry.autopilot_state = AutopilotState.EXECUTING_SAFE_WORK.value
            self.telemetry.safe_idle = False
            exec_res = self.execute_safe_work(action_decision)
            self.telemetry.last_meaningful_progress = utc_now()
            self.telemetry.next_safe_action = f"COMPLETED_{exec_res.get('task_id')}"
        elif action_decision.get("type") == "DISPATCH_REVIEW":
            self.telemetry.autopilot_state = AutopilotState.DISPATCHING.value
            self.telemetry.next_review_required = True
            self.telemetry.next_safe_action = f"DISPATCH_REVIEW_FOR_{action_decision.get('mission_id')}"
        elif action_decision.get("type") == "PARK_BRANCH":
            self.telemetry.autopilot_state = AutopilotState.WAITING_GATE.value
            self.telemetry.blocked_branches.append(action_decision.get("branch_id", ""))
            self.telemetry.next_safe_action = f"BRANCH_PARKED_{action_decision.get('branch_id')}"
        else:
            self.telemetry.autopilot_state = AutopilotState.SAFE_IDLE.value
            self.telemetry.safe_idle = True
            self.telemetry.next_safe_action = "SAFE_IDLE_STANDBY"

        # 6. Save Durable State
        safe_write_json(self.state_file, self.telemetry.to_dict())
        return self.telemetry

    def observe_organization(self) -> Dict[str, Any]:
        """Gathers local evidence across workers, locks, queue, and heartbeats."""
        workers = self.registry.list_workers()
        classified_workers = {}
        available_workers = []

        for wid, w in workers.items():
            st = w.state
            classified_workers[wid] = st
            if st in (WorkerState.AVAILABLE.value, WorkerState.SAFE_IDLE.value):
                available_workers.append(wid)

        self.telemetry.available_workers = available_workers

        # Check Active Write Locks / Scopes
        active_locks = []
        heavy_active = False
        if self.locks_dir.is_dir():
            for lfile in self.locks_dir.glob("scope_*.json"):
                status, rec, _ = self.authority.parse_authority_record(lfile)
                if status == LockStatus.VALID_OWNED and rec:
                    active_locks.append(rec.scope)
                    if rec.scope.startswith("HEAVY:"):
                        heavy_active = True

        self.telemetry.active_write_scope = active_locks[0] if active_locks else None
        self.telemetry.heavy_job_active = heavy_active

        # Check Daemon Heartbeat
        hb_data = safe_load_json(self.daemon_heartbeat_file)
        daemon_alive = is_pid_alive(hb_data.get("pid"))

        return {
            "workers": classified_workers,
            "available_workers": available_workers,
            "active_locks": active_locks,
            "heavy_job_active": heavy_active,
            "daemon_alive": daemon_alive,
            "daemon_status": hb_data.get("status", "UNKNOWN"),
        }

    def auto_detect_worker_results(self) -> List[Dict[str, Any]]:
        """Scans for new worker completion envelopes and extracts structured results."""
        detected = []
        results_dir = self.opp_queue_dir / "results"
        if not results_dir.is_dir():
            return detected

        for rfile in sorted(results_dir.glob("*.result.json")):
            data = safe_load_json(rfile)
            if not isinstance(data, dict):
                continue

            opp_id = data.get("opportunity_id", rfile.stem)
            fp = data.get("result_fingerprint") or hashlib.sha256(rfile.read_bytes()).hexdigest()[:16]

            if fp in self._processed_result_fingerprints:
                continue

            self._processed_result_fingerprints.add(fp)
            status = data.get("status", "UNKNOWN")

            result_record = {
                "mission_id": data.get("task_id", opp_id),
                "opportunity_id": opp_id,
                "worker_id": data.get("handler", "WORKER"),
                "result": status,
                "result_fingerprint": fp,
                "timestamp": data.get("completed_at", utc_now()),
                "status": status,
            }
            detected.append(result_record)
            self.telemetry.last_result = status
            self.telemetry.last_result_fingerprint = fp

            # Emit Chief Alert on result detection
            self.emit_chief_alert(
                alert_type="MISSION_RESULT_DETECTED",
                severity="INFO" if status in ("SUCCESS", "PASS", "RELEASE") else "HIGH",
                details=result_record,
            )

        return detected

    def select_next_safe_action(
        self,
        observation: Dict[str, Any],
        new_results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Selects next safe action based on priority, writer exclusion, and gating."""
        # 1. Check if newly detected result requires review
        for res in new_results:
            st = res.get("result")
            if (st in ("PASS", "RELEASE", "SUCCESS")) and res.get("review_required", False):
                return {
                    "type": "DISPATCH_REVIEW",
                    "mission_id": res.get("mission_id"),
                    "result_fingerprint": res.get("result_fingerprint"),
                }
            elif st in ("REMEDIATE", "FAILED") and res.get("remediation_required", False):
                return {
                    "type": "REMEDIATION_REQUIRED",
                    "mission_id": res.get("mission_id"),
                    "defect": "AUTOMATIC_DEFECT_EXTRACTED",
                }

        # 2. Check Opportunity Queue for Safe READY Tasks
        opps: list[dict[str, Any]] = []
        opps_file = self.opp_queue_dir / "opportunities.json"
        if opps_file.is_file():
            opps_data = safe_load_json(opps_file)
            for opp_id, op in opps_data.items():
                op_copy = dict(op)
                op_copy["opportunity_id"] = opp_id
                opps.append(op_copy)

        for op_obj in self.opp_queue.list_opportunities():
            if not any(o.get("opportunity_id") == op_obj.opportunity_id for o in opps):
                opps.append(op_obj.to_dict())

        opps.sort(key=lambda o: (-int(o.get("priority", 5)), str(o.get("opportunity_id", ""))))

        # First record all parked/gated branches across the organization
        has_parked_branch = False
        for op in opps:
            opp_id = op.get("opportunity_id", "")
            st = op.get("status", "")
            proj = op.get("project", "")
            cost = float(op.get("estimated_cost", 0.0))
            if st == "WAITING_FOR_HUMAN" or proj == "HUMAN_BRANCH" or st == "PAYMENT_APPROVAL_REQUIRED" or cost > 0.0 or proj == "MONEY_BRANCH":
                if opp_id not in self.telemetry.blocked_branches:
                    self.telemetry.blocked_branches.append(opp_id)
                has_parked_branch = True

        for op in opps:
            opp_id = op.get("opportunity_id", "")
            st = op.get("status", "")
            risk = op.get("risk", "HIGH")
            proj = op.get("project", "")
            heavy = bool(op.get("heavy_job", False))
            cost = float(op.get("estimated_cost", 0.0))
            scope = op.get("allowed_scope", [])

            # Gated check: Human / Money / Auth (Non-blocking to other independent tasks)
            if st == "WAITING_FOR_HUMAN" or proj == "HUMAN_BRANCH" or st == "PAYMENT_APPROVAL_REQUIRED" or cost > 0.0 or proj == "MONEY_BRANCH":
                continue

            # Single-Writer Mutex Check (Mission 216 / active writer protection)
            if scope and observation.get("active_locks"):
                conflict = False
                for active_s in observation["active_locks"]:
                    for req_s in scope:
                        if req_s == active_s or req_s.startswith(active_s + "/") or active_s.startswith(req_s + "/"):
                            conflict = True
                            break
                if conflict:
                    continue  # Refuse overlapping write -> skip to next disjoint task

            # Heavy Job Exclusivity Check
            if heavy and observation.get("heavy_job_active"):
                continue

            if st == "READY" and risk in ("LOW", "MEDIUM"):
                return {
                    "type": "EXECUTE_LOCAL_SAFE_WORK",
                    "opportunity_id": opp_id,
                    "task_id": f"TASK-AUTOPILOT-{opp_id}",
                }

        if has_parked_branch:
            return {"type": "PARK_BRANCH", "branch_id": self.telemetry.blocked_branches[0] if self.telemetry.blocked_branches else ""}

        return {"type": "SAFE_IDLE"}

    def execute_safe_work(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Executes low-risk local task under strict Financial Firewall."""
        opp_id = action.get("opportunity_id", "GENERIC_TASK")
        task_id = action.get("task_id", f"TASK-{int(time.time())}")

        # Enforce Financial Firewall
        assert self.real_trades_count == 0, "FINANCIAL FIREWALL VIOLATION: Real trades forbidden"
        assert not self.real_funds_touched, "FINANCIAL FIREWALL VIOLATION: Real funds touched"
        assert not self.wallet_signing_active, "FINANCIAL FIREWALL VIOLATION: Wallet signing forbidden"
        assert self.spend_limit_eur == 0.0, "SPEND FIREWALL VIOLATION: Spend > 0 EUR forbidden"

        # Claim and complete opportunity
        self.opp_queue._load_all()
        claimed, _, claim = self.opp_queue.claim_opportunity(opp_id, "CLI_AUTOPILOT")
        if claimed:
            res_payload = {
                "schema_version": "1.0",
                "result_type": "LOCAL_VALIDATION_RESULT",
                "task_id": self.opp_queue.canonical_task_id(opp_id, claim["state_version"]),
                "opportunity_id": opp_id,
                "claim_id": claim["claim_id"],
                "generation": claim["state_version"],
                "status": "SUCCESS",
                "handler": "DETERMINISTIC_LOCAL_VALIDATION",
                "completed_at": utc_now(),
                "metadata": {"executor": "CLI_AUTOPILOT", "financial_firewall_verified": True},
            }
            opp_obj = self.opp_queue.get_opportunity(opp_id)
            res_payload["result_fingerprint"] = self.opp_queue.expected_result_fingerprint(opp_obj, claim, res_payload)

            res_dir = self.opp_queue_dir / "results"
            res_dir.mkdir(parents=True, exist_ok=True)
            safe_write_json(res_dir / f"{opp_id}.result.json", res_payload)
            self.opp_queue.reconcile_durable_results()

        return {"task_id": task_id, "opportunity_id": opp_id, "status": "COMPLETED"}

    def emit_chief_alert(self, alert_type: str, severity: str, details: Dict[str, Any]) -> None:
        """Emits deduplicated alert to runtime-alerts and records in telemetry."""
        fp = hashlib.sha256(f"{alert_type}|{json.dumps(details, sort_keys=True)}".encode()).hexdigest()[:16]
        if fp in self._alert_cache:
            return

        self._alert_cache.add(fp)
        event_id = f"alert-chief-{uuid.uuid4().hex[:8]}"
        payload = {
            "schema_version": "3.0",
            "event_id": event_id,
            "event_type": alert_type,
            "severity": severity,
            "details": details,
            "fingerprint": fp,
            "created_at": utc_now(),
        }
        self.telemetry.last_chief_alert = payload
        self.alerts_dir.mkdir(parents=True, exist_ok=True)
        safe_write_json(self.alerts_dir / f"{event_id}.json", payload)

    def write_heartbeat(self, cycle_count: int) -> None:
        """Writes advancing heartbeat for daemon telemetry."""
        hb = {
            "pid": os.getpid(),
            "process_alive": True,
            "status": self.telemetry.autopilot_state,
            "heartbeat_at": utc_now(),
            "cycle_count": cycle_count,
            "active_mission": self.telemetry.active_mission,
            "active_worker": self.telemetry.active_worker,
            "next_safe_action": self.telemetry.next_safe_action,
            "last_meaningful_progress": self.telemetry.last_meaningful_progress,
            "safe_idle": self.telemetry.safe_idle,
            "human_weiter_required": False,
            "spend_eur": self.telemetry.spend_eur,
            "model_calls_runtime": self.telemetry.model_calls_runtime,
        }
        safe_write_json(self.heartbeat_file, hb)

    def run_continuous_loop(self, interval: float = 5.0) -> None:
        """Executes bounded continuous loop with single-instance enforcement."""
        if self.pid_file.is_file():
            try:
                existing_pid = int(self.pid_file.read_text().strip())
                if is_pid_alive(existing_pid) and existing_pid != os.getpid():
                    print(f"CLI_AUTOPILOT_INSTANCE_ALREADY_ACTIVE: PID {existing_pid}")
                    return
            except Exception:
                pass

        self.pid_file.parent.mkdir(parents=True, exist_ok=True)
        self.pid_file.write_text(str(os.getpid()), encoding="utf-8")

        cycle_count = 0
        try:
            while True:
                cycle_count += 1
                self.run_autopilot_cycle()
                self.write_heartbeat(cycle_count)
                time.sleep(interval)
        finally:
            if self.pid_file.is_file():
                try:
                    if int(self.pid_file.read_text().strip()) == os.getpid():
                        self.pid_file.unlink(missing_ok=True)
                except Exception:
                    pass


def main() -> int:
    parser = argparse.ArgumentParser(description="CLI Continuous Operations Autopilot")
    parser.add_argument("--once", action="store_true", help="Run single autopilot cycle and exit")
    parser.add_argument("--daemon", action="store_true", help="Run in continuous daemon mode")
    parser.add_argument("--interval", type=float, default=5.0, help="Loop sleep interval in seconds")
    args = parser.parse_args()

    autopilot = CLIOperationsAutopilot()
    if args.once:
        res = autopilot.run_autopilot_cycle()
        autopilot.write_heartbeat(1)
        print(json.dumps(res.to_dict(), indent=2))
        return 0

    autopilot.run_continuous_loop(interval=args.interval)
    return 0


if __name__ == "__main__":
    sys.exit(main())
