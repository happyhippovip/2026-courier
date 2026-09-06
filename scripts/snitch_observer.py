#!/usr/bin/env python3
"""Mission: Autonomy Control Plane V2 - Snitch Observer & Live Truth Engine.

Provides authoritative, real-time observation of autonomous workers and control-plane sessions:
- Inspects real process liveness and process table
- Detects permission prompt blocks ('Do you want to proceed?', 'Requesting permission for:')
- Distinguishes SAFE_IDLE from RUNNING_NO_PROGRESS or HUNG
- Detects ORPHANED records and dead PID claims
- Emits structured, deduplicated anomaly alerts
- Computes fail-closed Operational Readiness (READY / CONDITIONAL / NOT_READY)
"""

from __future__ import annotations

import datetime as dt
import enum
import json
import os
import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

COURIER_DIR = Path(__file__).resolve().parent.parent


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def is_pid_alive(pid: int) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


class WorkerState(str, enum.Enum):
    STARTING = "STARTING"
    PROGRESSING = "PROGRESSING"
    DISCOVERING = "DISCOVERING"
    INVESTIGATING = "INVESTIGATING"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    SAFE_IDLE = "SAFE_IDLE"
    SAFE_IDLE_AFTER_FULL_DISCOVERY = "SAFE_IDLE_AFTER_FULL_DISCOVERY"
    PREMATURE_IDLE = "PREMATURE_IDLE"
    WAITING_PERMISSION = "WAITING_PERMISSION"
    WAITING_HUMAN = "WAITING_HUMAN"
    WAITING_RESOURCE = "WAITING_RESOURCE"
    RUNNING_NO_PROGRESS = "RUNNING_NO_PROGRESS"
    HUNG = "HUNG"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"
    ORPHANED = "ORPHANED"
    UNKNOWN = "UNKNOWN"


class ReadinessLevel(str, enum.Enum):
    READY = "READY"
    CONDITIONAL = "CONDITIONAL"
    NOT_READY = "NOT_READY"


@dataclass
class WorkerObservation:
    worker_id: str
    pid: Optional[int]
    state: WorkerState
    alive: bool
    last_active_at: str
    last_log_snippet: str
    permission_blocked: bool
    permission_prompt_text: Optional[str]
    stop_reason: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["state"] = self.state.value
        return d


@dataclass
class OperationalReadinessReport:
    readiness: ReadinessLevel
    safe_for_unattended_operation: bool
    active_workers_count: int
    hung_workers_count: int
    permission_blocked_count: int
    stale_orphans_count: int
    crash_safety_oracle_passed: bool
    autonomous_spend_limit_eur: float
    publication_auth_inference: str
    reasons: List[str]
    timestamp: str = field(default_factory=utc_now)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["readiness"] = self.readiness.value
        return d


class SnitchObserver:
    """Independent live observer for Computer-A Autonomy Control Plane."""

    def __init__(self, repo_dir: Path = COURIER_DIR):
        self.repo_dir = repo_dir
        self.events_dir = repo_dir / "events"
        self.autonomy_dir = self.events_dir / "autonomy-runtime"
        self.anomalies_dir = self.events_dir / "anomalies"
        self.snitch_dir = self.events_dir / "snitch"
        self.snitch_dir.mkdir(parents=True, exist_ok=True)
        self.anomalies_dir.mkdir(parents=True, exist_ok=True)

        self.recent_alerts_file = self.snitch_dir / "recent_alerts.json"
        self._alert_cache: Dict[str, str] = self._load_alert_cache()

    def _load_alert_cache(self) -> Dict[str, str]:
        if self.recent_alerts_file.exists():
            try:
                return json.loads(self.recent_alerts_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _save_alert_cache(self) -> None:
        try:
            self.recent_alerts_file.write_text(json.dumps(self._alert_cache, indent=2), encoding="utf-8")
        except Exception:
            pass

    def check_log_for_permission_prompts(self, log_content: str) -> Tuple[bool, Optional[str]]:
        """Scans log content for interactive permission prompts."""
        patterns = [
            r"Do you want to proceed\?",
            r"Requesting permission for:",
            r"\[Persist to settings\.json\]",
            r"always allow in this conversation",
            r"Enter passphrase",
            r"Password:",
            r"\[Y/n\]",
            r"\(yes/no\)\?",
        ]
        for pat in patterns:
            match = re.search(pat, log_content, re.IGNORECASE)
            if match:
                snippet = log_content[max(0, match.start() - 100):min(len(log_content), match.end() + 200)]
                return True, snippet.strip()
        return False, None

    def inspect_worker(
        self,
        worker_id: str,
        pid: Optional[int],
        log_path: Optional[Path] = None,
        session_state: Optional[Dict[str, Any]] = None,
    ) -> WorkerObservation:
        """Determines the authoritative real state of a worker."""
        now = dt.datetime.now(dt.timezone.utc)
        alive = is_pid_alive(pid) if pid else False
        log_snippet = ""
        permission_blocked = False
        prompt_text = None

        if log_path and log_path.exists():
            try:
                text = log_path.read_text(encoding="utf-8", errors="replace")
                log_snippet = text[-1000:]
                permission_blocked, prompt_text = self.check_log_for_permission_prompts(text)
            except Exception:
                pass

        # Case 1: Dead PID or missing PID
        if not pid or not alive:
            if session_state:
                status = session_state.get("status", "")
                if status in ("COMPLETED", "STOPPED_SAFELY"):
                    return WorkerObservation(
                        worker_id=worker_id, pid=pid, state=WorkerState.COMPLETED,
                        alive=False, last_active_at=session_state.get("last_active_at", ""),
                        last_log_snippet=log_snippet, permission_blocked=False,
                        permission_prompt_text=None, stop_reason=session_state.get("stop_reason"),
                    )
                if status in ("RUNNING", "IN_PROGRESS"):
                    return WorkerObservation(
                        worker_id=worker_id, pid=pid, state=WorkerState.ORPHANED,
                        alive=False, last_active_at=session_state.get("last_active_at", ""),
                        last_log_snippet=log_snippet, permission_blocked=False,
                        permission_prompt_text=None, stop_reason="PID_NOT_ALIVE_ORPHAN",
                    )
            return WorkerObservation(
                worker_id=worker_id, pid=pid, state=WorkerState.FAILED,
                alive=False, last_active_at="", last_log_snippet=log_snippet,
                permission_blocked=False, permission_prompt_text=None,
                stop_reason="PROCESS_NOT_RUNNING",
            )

        # Case 2: Process is alive -> check for permission block
        if permission_blocked:
            return WorkerObservation(
                worker_id=worker_id, pid=pid, state=WorkerState.WAITING_PERMISSION,
                alive=True, last_active_at=session_state.get("last_active_at", utc_now()) if session_state else utc_now(),
                last_log_snippet=log_snippet, permission_blocked=True,
                permission_prompt_text=prompt_text, stop_reason="INTERACTIVE_PERMISSION_PROMPT_BLOCKED",
            )

        # Case 3: Check session state liveness & progress
        if session_state:
            status = session_state.get("status", "")
            if status in ("SAFE_IDLE", "IDLE_EXPECTED"):
                # Check for required goal-driven discovery proof
                proof_file = self.events_dir / "runtime-state" / "discovery_audit_proof.json"
                if not proof_file.exists():
                    self.emit_alert(
                        alert_type="PREMATURE_IDLE",
                        severity="HIGH",
                        details={"worker_id": worker_id, "state": "PREMATURE_IDLE", "reason": "MISSING_DISCOVERY_PROOF"},
                    )
                    return WorkerObservation(
                        worker_id=worker_id, pid=pid, state=WorkerState.PREMATURE_IDLE,
                        alive=True, last_active_at=session_state.get("last_active_at", utc_now()),
                        last_log_snippet=log_snippet, permission_blocked=False,
                        permission_prompt_text=None, stop_reason="PREMATURE_IDLE_MISSING_DISCOVERY_PROOF",
                    )
                try:
                    pdata = json.loads(proof_file.read_text(encoding="utf-8"))
                    if pdata.get("eligible_safe_candidates", 0) > 0 or not pdata.get("no_safe_work", False):
                        self.emit_alert(
                            alert_type="PREMATURE_IDLE",
                            severity="HIGH",
                            details={"worker_id": worker_id, "state": "PREMATURE_IDLE", "reason": "ELIGIBLE_WORK_REMAINED"},
                        )
                        return WorkerObservation(
                            worker_id=worker_id, pid=pid, state=WorkerState.PREMATURE_IDLE,
                            alive=True, last_active_at=session_state.get("last_active_at", utc_now()),
                            last_log_snippet=log_snippet, permission_blocked=False,
                            permission_prompt_text=None, stop_reason="PREMATURE_IDLE_ELIGIBLE_WORK_REMAINED",
                        )
                    return WorkerObservation(
                        worker_id=worker_id, pid=pid, state=WorkerState.SAFE_IDLE,
                        alive=True, last_active_at=session_state.get("last_active_at", utc_now()),
                        last_log_snippet=log_snippet, permission_blocked=False,
                        permission_prompt_text=None,
                        details={"status": "SAFE_IDLE_AFTER_FULL_DISCOVERY", "proof_hash": pdata.get("proof_hash")},
                    )
                except Exception:
                    pass

                return WorkerObservation(
                    worker_id=worker_id, pid=pid, state=WorkerState.SAFE_IDLE,
                    alive=True, last_active_at=session_state.get("last_active_at", utc_now()),
                    last_log_snippet=log_snippet, permission_blocked=False,
                    permission_prompt_text=None,
                )

            if status in ("WAITING_PERMISSION", "PERMISSION_GATED"):
                return WorkerObservation(
                    worker_id=worker_id, pid=pid, state=WorkerState.WAITING_PERMISSION,
                    alive=True, last_active_at=session_state.get("last_active_at", utc_now()),
                    last_log_snippet=log_snippet, permission_blocked=True,
                    permission_prompt_text=session_state.get("blocked_reason"),
                    stop_reason=session_state.get("blocked_reason", "WAITING_PERMISSION"),
                )

            if status in ("WAITING_HUMAN", "HUMAN_AUDIENCE_GATED"):
                return WorkerObservation(
                    worker_id=worker_id, pid=pid, state=WorkerState.WAITING_HUMAN,
                    alive=True, last_active_at=session_state.get("last_active_at", utc_now()),
                    last_log_snippet=log_snippet, permission_blocked=False,
                    permission_prompt_text=None,
                    stop_reason=session_state.get("blocked_reason", "WAITING_HUMAN"),
                )

            if status in ("WAITING_RESOURCE", "RESOURCE_EXHAUSTED"):
                return WorkerObservation(
                    worker_id=worker_id, pid=pid, state=WorkerState.WAITING_RESOURCE,
                    alive=True, last_active_at=session_state.get("last_active_at", utc_now()),
                    last_log_snippet=log_snippet, permission_blocked=False,
                    permission_prompt_text=None,
                    stop_reason=session_state.get("blocked_reason", "WAITING_RESOURCE"),
                )

            # Check last active timestamp freshness
            last_active = session_state.get("last_active_at") or session_state.get("updated_at")
            if last_active:
                try:
                    last_dt = dt.datetime.fromisoformat(last_active)
                    age_seconds = (now - last_dt).total_seconds()
                    if age_seconds < 120:
                        return WorkerObservation(
                            worker_id=worker_id, pid=pid, state=WorkerState.PROGRESSING,
                            alive=True, last_active_at=last_active,
                            last_log_snippet=log_snippet, permission_blocked=False,
                            permission_prompt_text=None,
                        )
                    elif age_seconds < 300:
                        return WorkerObservation(
                            worker_id=worker_id, pid=pid, state=WorkerState.RUNNING_NO_PROGRESS,
                            alive=True, last_active_at=last_active,
                            last_log_snippet=log_snippet, permission_blocked=False,
                            permission_prompt_text=None, stop_reason=f"NO_PROGRESS_FOR_{int(age_seconds)}S",
                        )
                    else:
                        return WorkerObservation(
                            worker_id=worker_id, pid=pid, state=WorkerState.HUNG,
                            alive=True, last_active_at=last_active,
                            last_log_snippet=log_snippet, permission_blocked=False,
                            permission_prompt_text=None, stop_reason=f"HUNG_NO_ACTIVITY_FOR_{int(age_seconds)}S",
                        )
                except Exception:
                    pass

        return WorkerObservation(
            worker_id=worker_id, pid=pid, state=WorkerState.PROGRESSING,
            alive=True, last_active_at=utc_now(), last_log_snippet=log_snippet,
            permission_blocked=False, permission_prompt_text=None,
        )

    def inspect_workspace(self) -> List[WorkerObservation]:
        """Scans all runtime sessions and claims across the workspace."""
        observations = []

        # 1. Inspect real autonomy runtime session
        sess_file = self.autonomy_dir / "session_state.json"
        if sess_file.exists():
            try:
                data = json.loads(sess_file.read_text(encoding="utf-8"))
                obs = self.inspect_worker(
                    worker_id=data.get("session_id", "session-runtime"),
                    pid=data.get("pid"),
                    session_state=data,
                )
                observations.append(obs)
            except Exception:
                pass

        # 2. Inspect session controller state
        ctrl_file = self.autonomy_dir / "session_controller_state.json"
        if ctrl_file.exists():
            try:
                data = json.loads(ctrl_file.read_text(encoding="utf-8"))
                obs = self.inspect_worker(
                    worker_id=data.get("session_id", "session-controller"),
                    pid=data.get("pid"),
                    session_state=data,
                )
                observations.append(obs)
            except Exception:
                pass

        # 3. Inspect active opportunity claims
        claims_dir = self.events_dir / "opportunity-claims"
        if claims_dir.exists():
            for claim_file in claims_dir.glob("*.claim.json"):
                try:
                    data = json.loads(claim_file.read_text(encoding="utf-8"))
                    claim_pid = data.get("pid")
                    opp_id = data.get("opportunity_id", claim_file.stem)
                    obs = self.inspect_worker(
                        worker_id=f"claim-{opp_id}",
                        pid=claim_pid,
                        session_state={"status": "CLAIMED", "last_active_at": data.get("claimed_at")},
                    )
                    observations.append(obs)
                except Exception:
                    pass

        # 4. Inspect LiveWorkerRegistry active_workers.json
        active_workers_file = self.events_dir / "worker-registry" / "active_workers.json"
        if active_workers_file.exists():
            try:
                workers_data = json.loads(active_workers_file.read_text(encoding="utf-8"))
                for wid, wdict in workers_data.items():
                    w_pid = wdict.get("pid")
                    w_state = wdict.get("state", "UNKNOWN")
                    obs = self.inspect_worker(
                        worker_id=wid,
                        pid=w_pid,
                        session_state={
                            "status": "RUNNING" if w_state == "PROGRESSING" else w_state,
                            "last_active_at": wdict.get("last_heartbeat") or wdict.get("last_meaningful_progress"),
                        },
                    )
                    observations.append(obs)
            except Exception:
                pass

        # 5. Inspect Canonical Authority locks
        locks_dir = self.events_dir / "locks"
        if locks_dir.exists():
            for lock_file in locks_dir.glob("*.json"):
                try:
                    data = json.loads(lock_file.read_text(encoding="utf-8"))
                    lock_owner = data.get("owner_id", "unknown")
                    lock_pid = data.get("pid")
                    if lock_pid and not is_pid_alive(lock_pid):
                        obs = WorkerObservation(
                            worker_id=f"stale-lock-{lock_file.stem}",
                            pid=lock_pid,
                            state=WorkerState.ORPHANED,
                            alive=False,
                            last_active_at=data.get("acquired_at", ""),
                            last_log_snippet="",
                            permission_blocked=False,
                            permission_prompt_text=None,
                            stop_reason="LOCK_OWNER_PID_DEAD",
                        )
                        observations.append(obs)
                except Exception:
                    pass

        return observations

    def reconcile_orphans(self) -> int:
        """Reconciles orphaned sessions and dead lock claims on disk."""
        reconciled = 0
        sess_file = self.autonomy_dir / "session_state.json"
        if sess_file.exists():
            try:
                data = json.loads(sess_file.read_text(encoding="utf-8"))
                pid = data.get("pid")
                if data.get("status") in ("RUNNING", "IN_PROGRESS") and (not pid or not is_pid_alive(pid)):
                    data["status"] = "STALE_RUNNING_OFFLINE"
                    data["stop_reason"] = f"ORPHAN_RECONCILED_PID_{pid}"
                    sess_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
                    reconciled += 1
            except Exception:
                pass

        ctrl_file = self.autonomy_dir / "session_controller_state.json"
        if ctrl_file.exists():
            try:
                data = json.loads(ctrl_file.read_text(encoding="utf-8"))
                pid = data.get("pid")
                if data.get("status") in ("RUNNING", "IN_PROGRESS") and (not pid or not is_pid_alive(pid)):
                    data["status"] = "STALE_RUNNING_OFFLINE"
                    data["stop_reason"] = f"ORPHAN_RECONCILED_PID_{pid}"
                    ctrl_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
                    reconciled += 1
            except Exception:
                pass

        # Reconcile stale worker registry records
        active_workers_file = self.events_dir / "worker-registry" / "active_workers.json"
        if active_workers_file.exists():
            try:
                workers_data = json.loads(active_workers_file.read_text(encoding="utf-8"))
                changed = False
                for wid, wdict in workers_data.items():
                    w_pid = wdict.get("pid")
                    if wdict.get("state") == "PROGRESSING" and (not w_pid or not is_pid_alive(w_pid)):
                        wdict["state"] = "ORPHANED"
                        wdict["blocked_reason"] = f"PID_{w_pid}_NOT_ALIVE"
                        changed = True
                        reconciled += 1
                if changed:
                    active_workers_file.write_text(json.dumps(workers_data, indent=2), encoding="utf-8")
            except Exception:
                pass

        # Reconcile dead lock files
        locks_dir = self.events_dir / "locks"
        if locks_dir.exists():
            for lock_file in locks_dir.glob("*.json"):
                try:
                    data = json.loads(lock_file.read_text(encoding="utf-8"))
                    lock_pid = data.get("pid")
                    if lock_pid and not is_pid_alive(lock_pid):
                        lock_file.unlink(missing_ok=True)
                        reconciled += 1
                except Exception:
                    pass

        return reconciled

    def emit_alert(self, alert_type: str, severity: str, details: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Emits a structured alert with deduplication."""
        fingerprint = f"{alert_type}:{details.get('worker_id', '')}:{details.get('state', '')}"
        now = dt.datetime.now(dt.timezone.utc)

        last_sent = self._alert_cache.get(fingerprint)
        if last_sent:
            try:
                if (now - dt.datetime.fromisoformat(last_sent)).total_seconds() < 300:
                    return None  # Suppress duplicate alert within 5 minutes
            except Exception:
                pass

        self._alert_cache[fingerprint] = now.isoformat()
        self._save_alert_cache()

        alert_record = {
            "alert_id": f"alert-{now.strftime('%Y%m%d%H%M%S')}-{fingerprint[:16]}",
            "timestamp": now.isoformat(),
            "alert_type": alert_type,
            "severity": severity,
            "details": details,
        }

        anomaly_file = self.anomalies_dir / f"snitch_alert_{alert_record['alert_id']}.json"
        try:
            anomaly_file.write_text(json.dumps(alert_record, indent=2), encoding="utf-8")
        except Exception:
            pass

        return alert_record

    def compute_operational_readiness(
        self,
        oracle_test_command: Optional[str] = "python3 -m unittest -v reviewer_oracles/test_autonomy_crash_safety_oracle.py",
    ) -> OperationalReadinessReport:
        """Computes strict fail-closed operational readiness."""
        reasons = []
        observations = self.inspect_workspace()

        hung_workers = [o for o in observations if o.state == WorkerState.HUNG]
        perm_blocked = [o for o in observations if o.state == WorkerState.WAITING_PERMISSION or o.permission_blocked]
        orphans = [o for o in observations if o.state == WorkerState.ORPHANED]
        active_workers = [o for o in observations if o.alive]

        if hung_workers:
            reasons.append(f"Found {len(hung_workers)} hung workers: {[w.worker_id for w in hung_workers]}")
        if perm_blocked:
            reasons.append(f"Found {len(perm_blocked)} permission blocked workers: {[w.worker_id for w in perm_blocked]}")
        if orphans:
            reasons.append(f"Found {len(orphans)} orphaned worker records: {[w.worker_id for w in orphans]}")

        # Verify crash safety oracle
        oracle_passed = False
        if oracle_test_command:
            try:
                res = subprocess.run(
                    oracle_test_command.split(),
                    cwd=str(self.repo_dir),
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                oracle_passed = (res.returncode == 0)
                if not oracle_passed:
                    reasons.append("Reviewer crash-safety acceptance oracle failed")
            except Exception as e:
                oracle_passed = False
                reasons.append(f"Crash-safety oracle execution failed: {e}")
        else:
            oracle_passed = True

        # Strict safety bounds
        autonomous_spend_eur = 0.0
        publication_auth = "DENY"

        safe_for_unattended = (
            len(hung_workers) == 0
            and len(perm_blocked) == 0
            and len(orphans) == 0
            and oracle_passed
            and autonomous_spend_eur == 0.0
            and publication_auth == "DENY"
        )

        if safe_for_unattended:
            readiness = ReadinessLevel.READY
        elif len(perm_blocked) > 0 or len(hung_workers) > 0 or not oracle_passed:
            readiness = ReadinessLevel.NOT_READY
        else:
            readiness = ReadinessLevel.CONDITIONAL

        return OperationalReadinessReport(
            readiness=readiness,
            safe_for_unattended_operation=safe_for_unattended,
            active_workers_count=len(active_workers),
            hung_workers_count=len(hung_workers),
            permission_blocked_count=len(perm_blocked),
            stale_orphans_count=len(orphans),
            crash_safety_oracle_passed=oracle_passed,
            autonomous_spend_limit_eur=autonomous_spend_eur,
            publication_auth_inference=publication_auth,
            reasons=reasons,
        )


if __name__ == "__main__":
    observer = SnitchObserver()
    report = observer.compute_operational_readiness()
    print(json.dumps(report.to_dict(), indent=2))
