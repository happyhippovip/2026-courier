#!/usr/bin/env python3
"""Autonomous Operational Hygiene Controller.

Standing Autonomy Invariant:
Before declaring SAFE_IDLE, every autonomous operations cycle must perform
a bounded deterministic hygiene reconciliation:
- Expired scope locks & dead-owner leases
- Stale opportunity claims & orphaned worker records
- Persisted RUNNING without authoritative liveness
- Expired temporary worker registrations
- Fail-closed handling on corrupt authority records (Snitch alert emitted once)
- Zero model calls (0 EUR spend), live owners NEVER displaced.
"""

from __future__ import annotations

import argparse
import datetime as dt
import enum
import hashlib
import json
import os
import sys
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
if str(COURIER_DIR) not in sys.path:
    sys.path.insert(0, str(COURIER_DIR))

try:
    from scripts.canonical_authority import (
        AuthorityRecord,
        CanonicalAuthority,
        LockStatus,
        is_pid_alive,
    )
    from scripts.live_worker_registry import (
        AvailabilityClass,
        LiveWorkerRegistry,
        WorkerRecord,
        WorkerState,
    )
except ImportError:
    from canonical_authority import (
        AuthorityRecord,
        CanonicalAuthority,
        LockStatus,
        is_pid_alive,
    )
    from live_worker_registry import (
        AvailabilityClass,
        LiveWorkerRegistry,
        WorkerRecord,
        WorkerState,
    )


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


class HygieneClassification(str, enum.Enum):
    LIVE_AUTHORITY = "LIVE_AUTHORITY"
    STALE_BUT_SAFE_TO_RECOVER = "STALE_BUT_SAFE_TO_RECOVER"
    CORRUPT_OR_AMBIGUOUS = "CORRUPT_OR_AMBIGUOUS"
    GATED_HUMAN_OR_MONEY = "GATED_HUMAN_OR_MONEY"


@dataclass
class HygieneTelemetry:
    hygiene_items_found: int = 0
    hygiene_items_recovered: int = 0
    hygiene_items_blocked: int = 0
    stale_locks: int = 0
    stale_claims: int = 0
    orphaned_workers: int = 0
    false_running_records: int = 0
    last_reconciliation_at: str = field(default_factory=utc_now)
    last_reconciliation_result: str = "PASS"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AutonomousOperationalHygiene:
    """Bounded, deterministic operational hygiene controller."""

    def __init__(self, repo_dir: Path = COURIER_DIR):
        self.repo_dir = repo_dir.resolve()
        self.events_dir = self.repo_dir / "events"
        self.locks_dir = self.events_dir / "locks"
        self.claims_dir = self.events_dir / "opportunity-claims"
        self.queue_claims_dir = self.events_dir / "opportunity-queue" / "claims"
        self.state_dir = self.events_dir / "runtime-state"
        self.alerts_dir = self.events_dir / "runtime-alerts"
        self.autonomy_dir = self.events_dir / "autonomy-runtime"
        self.worker_events_dir = self.events_dir / "worker-events"

        self.telemetry_file = self.state_dir / "hygiene_telemetry.json"
        self.authority = CanonicalAuthority(locks_dir=self.locks_dir)
        self.registry = LiveWorkerRegistry(repo_dir=self.repo_dir)

        self._alert_cache: Set[str] = set()

    def perform_hygiene_cycle(self) -> HygieneTelemetry:
        """Executes a single bounded deterministic hygiene reconciliation cycle."""
        telemetry = HygieneTelemetry(last_reconciliation_at=utc_now())

        # 1. Reconcile Scope Locks & Authority Records
        stale_locks, corrupt_locks = self._reconcile_scope_locks()
        telemetry.stale_locks = len(stale_locks)
        telemetry.hygiene_items_found += len(stale_locks) + len(corrupt_locks)
        telemetry.hygiene_items_recovered += len(stale_locks)
        telemetry.hygiene_items_blocked += len(corrupt_locks)

        # 2. Reconcile Stale Opportunity Claims
        stale_claims = self._reconcile_opportunity_claims()
        telemetry.stale_claims = len(stale_claims)
        telemetry.hygiene_items_found += len(stale_claims)
        telemetry.hygiene_items_recovered += len(stale_claims)

        # 3. Reconcile Orphaned Worker Records & False RUNNING States
        orphans, false_running = self._reconcile_worker_registry_and_sessions()
        telemetry.orphaned_workers = len(orphans)
        telemetry.false_running_records = len(false_running)
        telemetry.hygiene_items_found += len(orphans) + len(false_running)
        telemetry.hygiene_items_recovered += len(orphans) + len(false_running)

        # 4. Determine Cycle Result
        if len(corrupt_locks) > 0:
            telemetry.last_reconciliation_result = "BLOCKED_CORRUPTION_DETECTED"
        else:
            telemetry.last_reconciliation_result = "PASS"

        # 5. Persist Telemetry
        safe_write_json(self.telemetry_file, telemetry.to_dict())

        # 6. Emit Structured Event if Debris was Recovered
        if telemetry.hygiene_items_recovered > 0:
            self._emit_reconciliation_event(telemetry)

        return telemetry

    def _reconcile_scope_locks(self) -> Tuple[List[Path], List[Path]]:
        """Scans events/locks/*.json for stale recoverable locks or corrupt records."""
        stale_recovered: List[Path] = []
        corrupt_blocked: List[Path] = []

        if not self.locks_dir.is_dir():
            return stale_recovered, corrupt_blocked

        for lock_file in list(self.locks_dir.glob("scope_*.json")):
            status, record, err = self.authority.parse_authority_record(lock_file)

            if status == LockStatus.CORRUPT_BLOCKED:
                corrupt_blocked.append(lock_file)
                self._emit_snitch_alert(
                    alert_type="CORRUPT_AUTHORITY_RECORD",
                    severity="HIGH",
                    target_file=str(lock_file),
                    error=err or "Malformed authority JSON",
                )
            elif status == LockStatus.STALE_RECOVERABLE and record:
                # Prove owner dead + lease expired
                if not is_pid_alive(record.pid):
                    lock_file.unlink(missing_ok=True)
                    stale_recovered.append(lock_file)
            elif status == LockStatus.VALID_OWNED:
                # Live owner -> Leave strictly untouched
                pass

        return stale_recovered, corrupt_blocked

    def _reconcile_opportunity_claims(self) -> List[Path]:
        """Scans opportunity claims for dead holding PIDs."""
        recovered: List[Path] = []
        claim_dirs = [self.claims_dir, self.queue_claims_dir]

        for c_dir in claim_dirs:
            if not c_dir.is_dir():
                continue
            for claim_file in list(c_dir.glob("*.json")):
                data = safe_load_json(claim_file)
                pid = data.get("pid")
                if pid and not is_pid_alive(int(pid)):
                    claim_file.unlink(missing_ok=True)
                    recovered.append(claim_file)

        return recovered

    def _reconcile_worker_registry_and_sessions(self) -> Tuple[List[str], List[str]]:
        """Reconciles dead worker PIDs in active_workers.json and runtime sessions."""
        orphans: List[str] = []
        false_running: List[str] = []

        # 1. Active Worker Registry
        workers = self.registry.list_workers()
        changed = False
        for wid, w in workers.items():
            # Check 30-day temporary resource expiry
            if w.is_expired() and w.availability_class != AvailabilityClass.EXPIRED.value:
                w.availability_class = AvailabilityClass.EXPIRED.value
                w.state = WorkerState.UNKNOWN.value
                w.blocked_reason = "30_DAY_RESOURCE_WINDOW_EXPIRED"
                self.registry._save_worker_record(w)
                orphans.append(wid)
                changed = True
                continue

            # Check false progressing on dead PID
            if w.state == WorkerState.PROGRESSING.value and w.pid is not None and not is_pid_alive(w.pid):
                w.state = WorkerState.ORPHANED.value
                w.blocked_reason = f"PID_{w.pid}_NOT_ALIVE"
                self.registry._save_worker_record(w)
                false_running.append(wid)
                changed = True

        # 2. Session state files
        session_files = [
            self.autonomy_dir / "session_state.json",
            self.autonomy_dir / "session_controller_state.json",
        ]
        for sf in session_files:
            if sf.is_file():
                sdata = safe_load_json(sf)
                st = sdata.get("status")
                pid = sdata.get("pid")
                if st in ("RUNNING", "IN_PROGRESS") and (not pid or not is_pid_alive(pid)):
                    sdata["status"] = "STALE_RUNNING_OFFLINE"
                    sdata["stop_reason"] = f"ORPHAN_RECONCILED_PID_{pid}"
                    safe_write_json(sf, sdata)
                    false_running.append(sf.name)

        return orphans, false_running

    def _emit_snitch_alert(self, alert_type: str, severity: str, target_file: str, error: str) -> None:
        """Emits deduplicated Snitch alert when corruption is encountered."""
        fp = hashlib.sha256(f"{alert_type}|{target_file}|{error}".encode()).hexdigest()[:16]
        if fp in self._alert_cache:
            return

        self._alert_cache.add(fp)
        event_id = f"alert-hygiene-{uuid.uuid4().hex[:8]}"
        payload = {
            "schema_version": "3.0",
            "event_id": event_id,
            "event_type": alert_type,
            "severity": severity,
            "target_file": target_file,
            "error_detail": error,
            "fingerprint": fp,
            "created_at": utc_now(),
            "acknowledged": False,
        }
        self.alerts_dir.mkdir(parents=True, exist_ok=True)
        safe_write_json(self.alerts_dir / f"{event_id}.json", payload)

    def _emit_reconciliation_event(self, telemetry: HygieneTelemetry) -> None:
        """Emits structured reconciliation event to worker-events."""
        event_id = f"evt-hygiene-{uuid.uuid4().hex[:8]}"
        payload = {
            "schema_version": "3.0",
            "event_id": event_id,
            "event_type": "HYGIENE_RECONCILIATION_COMPLETED",
            "evidence": telemetry.to_dict(),
            "created_at": utc_now(),
        }
        self.worker_events_dir.mkdir(parents=True, exist_ok=True)
        safe_write_json(self.worker_events_dir / f"{event_id}.json", payload)


def main() -> int:
    parser = argparse.ArgumentParser(description="Autonomous Operational Hygiene Controller")
    parser.add_argument("--reconcile", action="store_true", help="Perform bounded hygiene reconciliation cycle")
    args = parser.parse_args()

    hygiene = AutonomousOperationalHygiene()
    res = hygiene.perform_hygiene_cycle()
    print(json.dumps(res.to_dict(), indent=2))
    return 0 if res.last_reconciliation_result == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
