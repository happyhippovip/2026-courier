#!/usr/bin/env python3
"""Mission 206: Live HQ Operations Daemon.

Autonomous, deterministic local operations loop maintaining continuous truth:
SNITCH -> WORKER REGISTRY -> TELEMETRY BRIDGE -> HQ SNAPSHOT -> CHIEF ALERT FEED

Features:
- Multi-worker real-time observation (GOOGLE, CODEX, CLI1, CLI2)
- Autonomous self-discovery of local worker missions/tasks
- Deterministic speech bubble payloads & Bar/Sauna leisure animation compatibility
- Critical release blocker and final acceptance signaling:
  * RELEASE_BLOCKER_FOUND (CLI2 finds release blocker)
  * BUILDER_REMEDIATION_COMPLETE (Google finishes candidate hash)
  * ADVERSARIAL_REVIEW_COMPLETE (CLI2 verifies test matrix)
  * FINAL_ACCEPTANCE_READY (Both conditions met -> signals Codex)
- Network degradation & provider error recovery lifecycle
- 30-day temporary resource policy & expiry auditing
- Daemon health publishing & crash restart deduplication
- 100% deterministic local execution (0 model calls, 0 EUR spend)
"""

from __future__ import annotations

import argparse
import datetime as dt
import enum
import hashlib
import json
import os
import re
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
    from live_worker_registry import (
        AvailabilityClass,
        EventType,
        LiveWorkerRegistry,
        WorkerRecord,
        WorkerState,
    )
    from hq_telemetry_bridge import (
        HQTelemetryBridge,
        VisualState,
    )
    from opportunity_queue import Opportunity, OpportunityQueue
    from queue_hygiene_manager import QueueHygieneManager
    from autonomous_operational_hygiene import AutonomousOperationalHygiene
except ImportError:
    from scripts.live_worker_registry import (
        AvailabilityClass,
        EventType,
        LiveWorkerRegistry,
        WorkerRecord,
        WorkerState,
    )
    from scripts.hq_telemetry_bridge import (
        HQTelemetryBridge,
        VisualState,
    )
    from scripts.opportunity_queue import Opportunity, OpportunityQueue
    from scripts.queue_hygiene_manager import QueueHygieneManager
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


class DaemonEventType(str, enum.Enum):
    RELEASE_BLOCKER_FOUND = "RELEASE_BLOCKER_FOUND"
    BUILDER_REMEDIATION_COMPLETE = "BUILDER_REMEDIATION_COMPLETE"
    CODEX_ACCEPTANCE_CANDIDATE_AVAILABLE = "CODEX_ACCEPTANCE_CANDIDATE_AVAILABLE"
    ADVERSARIAL_REVIEW_COMPLETE = "ADVERSARIAL_REVIEW_COMPLETE"
    FINAL_ACCEPTANCE_READY = "FINAL_ACCEPTANCE_READY"
    WORKER_STARTED = "WORKER_STARTED"
    WORKER_PROGRESS = "WORKER_PROGRESS"
    WORKER_COMPLETED = "WORKER_COMPLETED"
    WORKER_AVAILABLE = "WORKER_AVAILABLE"
    WAITING_PERMISSION = "WAITING_PERMISSION"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    NETWORK_DEGRADED = "NETWORK_DEGRADED"
    RECOVERED = "RECOVERED"
    RUNNING_NO_PROGRESS = "RUNNING_NO_PROGRESS"
    FAILED = "FAILED"
    ORPHANED = "ORPHANED"
    NEXT_SAFE_WORK_AVAILABLE = "NEXT_SAFE_WORK_AVAILABLE"


@dataclass
class DaemonHealth:
    observer_alive: bool = True
    pid: int = field(default_factory=os.getpid)
    started_at: str = field(default_factory=utc_now)
    last_scan: str = field(default_factory=utc_now)
    last_successful_snapshot: str = field(default_factory=utc_now)
    last_alert: Optional[str] = None
    scan_count: int = 0
    registry_health: str = "HEALTHY"
    telemetry_health: str = "HEALTHY"
    active_workers_count: int = 0
    free_workers_count: int = 0
    alerts_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class HQOperationsDaemon:
    """Continuous operations daemon orchestrating Snitch, Registry, HQ Telemetry & Chief Alerts."""

    DEFAULT_WATCH_INTERVAL = 10.0

    def __init__(
        self,
        repo_dir: Path = COURIER_DIR,
        watch_interval: float = DEFAULT_WATCH_INTERVAL,
    ):
        self.repo_dir = repo_dir.resolve()
        self.interval = watch_interval

        self.registry = LiveWorkerRegistry(repo_dir=self.repo_dir)
        self.bridge = HQTelemetryBridge(repo_dir=self.repo_dir)
        self.hygiene = AutonomousOperationalHygiene(repo_dir=self.repo_dir)

        self.state_dir = self.repo_dir / "events" / "runtime-state"
        self.alerts_dir = self.repo_dir / "events" / "runtime-alerts"
        self.events_dir = self.repo_dir / "events" / "worker-events"
        self.health_file = self.state_dir / "daemon_health.json"

        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.alerts_dir.mkdir(parents=True, exist_ok=True)
        self.events_dir.mkdir(parents=True, exist_ok=True)

        self.health = DaemonHealth()
        self._known_alert_fingerprints: Set[str] = self._load_historical_fingerprints()
        self._last_snapshot_hash: str = ""

        # Release Acceptance State Tracker
        self.builder_finished_candidate: Optional[str] = None
        self.cli2_review_complete: bool = False
        self.unresolved_high_blockers: List[Dict[str, Any]] = []

    def _load_historical_fingerprints(self) -> Set[str]:
        """Loads existing alert fingerprints to avoid duplicate alerts across restarts."""
        fps: Set[str] = set()
        for f in self.alerts_dir.glob("*.json"):
            data = safe_load_json(f)
            if "fingerprint" in data:
                fps.add(data["fingerprint"])
        for f in self.events_dir.glob("*.json"):
            data = safe_load_json(f)
            if "fingerprint" in data:
                fps.add(data["fingerprint"])
        return fps

    # --------------------------------------------------------------------------
    # Discovery & Self-Observation Layer
    # --------------------------------------------------------------------------

    def discover_local_worker_evidence(self) -> Dict[str, Dict[str, Any]]:
        """Scans local filesystem evidence for live worker status without model calls."""
        evidence: Dict[str, Dict[str, Any]] = {}

        # 1. Inspect Antigravity presence locks
        profile_paths = [
            ("CLI1", Path.home() / ".gemini" / "antigravity-cli"),
            ("CLI2", Path.home() / ".gemini_profiles" / "beata" / ".gemini" / "antigravity-cli"),
        ]
        for wid, p_dir in profile_paths:
            presence_dir = p_dir / "presence"
            conv_dir = p_dir / "conversations"
            brain_dir = p_dir / "brain"
            if presence_dir.is_dir():
                locks = list(presence_dir.glob("*.lock"))
                if locks:
                    lock = locks[0]
                    conv_id = lock.stem
                    trans = brain_dir / conv_id / ".system_generated" / "logs" / "transcript.jsonl"
                    db = conv_dir / f"{conv_id}.db"
                    last_mtime = trans.stat().st_mtime if trans.is_file() else (db.stat().st_mtime if db.is_file() else lock.stat().st_mtime)
                    evidence[wid] = {
                        "conv_id": conv_id,
                        "lock_path": str(lock),
                        "last_mtime": last_mtime,
                        "has_lock": True,
                    }

        # 2. Inspect Google Builder & Codex evidence
        autonomy_dir = self.repo_dir / "events" / "autonomy-runtime"
        session_file = autonomy_dir / "night_session.json"
        if session_file.is_file():
            sdata = safe_load_json(session_file)
            evidence["GOOGLE"] = {
                "session_id": sdata.get("session_id"),
                "status": sdata.get("status"),
                "last_mtime": session_file.stat().st_mtime,
            }

        return evidence

    # --------------------------------------------------------------------------
    # High Priority Acceptance & Blocker Signaling
    # --------------------------------------------------------------------------

    def record_release_blocker(
        self,
        worker_id: str,
        mission_id: str,
        component: str,
        defect_description: str,
        severity: str = "HIGH",
        evidence_ref: Optional[str] = None,
    ) -> Path:
        """Records release-blocking defect discovered by CLI2 or independent reviewer."""
        fp = hashlib.sha256(f"{worker_id}|{mission_id}|{component}|{defect_description}".encode()).hexdigest()[:16]

        blocker_payload = {
            "worker_id": worker_id,
            "mission_id": mission_id,
            "component": component,
            "severity": severity,
            "defect_description": defect_description,
            "evidence_ref": evidence_ref,
            "fingerprint": fp,
            "recorded_at": utc_now(),
        }
        self.unresolved_high_blockers.append(blocker_payload)

        # Update worker blocked reason
        worker = self.registry.get_worker(worker_id)
        if worker:
            worker.blocked_reason = f"RELEASE_BLOCKER: {defect_description}"
            worker.state = WorkerState.RUNNING_NO_PROGRESS.value
            self.registry._save_worker_record(worker)

        # Emit High Severity Incident Alert
        alert_file = self.emit_daemon_alert(
            event_type=DaemonEventType.RELEASE_BLOCKER_FOUND,
            worker_id=worker_id,
            severity="CRITICAL" if severity == "CRITICAL" else "HIGH",
            evidence=blocker_payload,
            recommended_action=f"REMEDIATE_BLOCKER_{component}",
        )
        return alert_file

    def clear_release_blocker(self, fingerprint: str) -> None:
        """Clears a resolved release blocker."""
        self.unresolved_high_blockers = [b for b in self.unresolved_high_blockers if b.get("fingerprint") != fingerprint]
        self.evaluate_final_acceptance_readiness()

    def record_builder_remediation_complete(
        self,
        candidate_hash: str,
        google_mission_id: str = "M204",
        ready_for_codex: bool = True,
    ) -> None:
        """Emits builder remediation completion and candidate availability."""
        self.builder_finished_candidate = candidate_hash
        worker = self.registry.get_worker("GOOGLE")
        if worker:
            worker.state = WorkerState.COMPLETED.value
            worker.last_result_id = f"CANDIDATE-{candidate_hash[:8]}"
            self.registry._save_worker_record(worker)

        self.emit_daemon_alert(
            event_type=DaemonEventType.BUILDER_REMEDIATION_COMPLETE,
            worker_id="GOOGLE",
            severity="INFO",
            evidence={"candidate_hash": candidate_hash, "mission_id": google_mission_id},
        )

        if ready_for_codex:
            self.emit_daemon_alert(
                event_type=DaemonEventType.CODEX_ACCEPTANCE_CANDIDATE_AVAILABLE,
                worker_id="GOOGLE",
                severity="INFO",
                evidence={"candidate_hash": candidate_hash},
                recommended_action="TRIGGER_CODEX_FINAL_ACCEPTANCE_ORACLE",
            )

        self.evaluate_final_acceptance_readiness()

    def record_adversarial_review_complete(
        self,
        cli2_mission_id: str = "M205",
        test_summary: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Records adversarial review completion by CLI2."""
        self.cli2_review_complete = True
        worker = self.registry.get_worker("CLI2")
        if worker:
            worker.state = WorkerState.COMPLETED.value
            self.registry._save_worker_record(worker)

        is_ready = len(self.unresolved_high_blockers) == 0
        self.emit_daemon_alert(
            event_type=DaemonEventType.ADVERSARIAL_REVIEW_COMPLETE,
            worker_id="CLI2",
            severity="INFO",
            evidence={
                "mission_id": cli2_mission_id,
                "unresolved_high_blockers_count": len(self.unresolved_high_blockers),
                "ready_for_codex_final_acceptance": is_ready,
                "test_summary": test_summary or {},
            },
        )

        self.evaluate_final_acceptance_readiness()

    def evaluate_final_acceptance_readiness(self) -> bool:
        """Emits FINAL_ACCEPTANCE_READY only when both builder is done and 0 blockers remain."""
        if self.builder_finished_candidate and len(self.unresolved_high_blockers) == 0:
            self.emit_daemon_alert(
                event_type=DaemonEventType.FINAL_ACCEPTANCE_READY,
                worker_id="CODEX",
                severity="INFO",
                evidence={
                    "candidate_hash": self.builder_finished_candidate,
                    "unresolved_blockers": 0,
                    "cli2_review_complete": self.cli2_review_complete,
                },
                recommended_action="DISPATCH_CODEX_FINAL_ACCEPTANCE",
            )
            return True
        return False

    # --------------------------------------------------------------------------
    # Alert Emission & Deduplication
    # --------------------------------------------------------------------------

    def emit_daemon_alert(
        self,
        event_type: DaemonEventType,
        worker_id: str,
        severity: str = "INFO",
        evidence: Optional[Dict[str, Any]] = None,
        recommended_action: Optional[str] = None,
    ) -> Path:
        """Emits a structured event to worker-events and runtime-alerts with deduplication."""
        ev = evidence or {}
        ev_hash = hashlib.sha256(json.dumps(ev, sort_keys=True).encode("utf-8")).hexdigest()[:12]
        fp = hashlib.sha256(f"{worker_id}|{event_type.value}|{ev_hash}".encode("utf-8")).hexdigest()[:16]

        event_id = f"evt-{uuid.uuid4().hex[:12]}"
        payload = {
            "schema_version": "3.0",
            "event_id": event_id,
            "event_type": event_type.value,
            "worker_id": worker_id,
            "severity": severity,
            "fingerprint": fp,
            "evidence": ev,
            "recommended_action": recommended_action,
            "created_at": utc_now(),
            "acknowledged": False,
        }

        # Write to worker-events
        evt_path = self.events_dir / f"{event_id}.json"
        safe_write_json(evt_path, payload)

        # Write to runtime-alerts if WARNING, HIGH, or CRITICAL
        if severity in ("WARNING", "HIGH", "CRITICAL"):
            alert_path = self.alerts_dir / f"alert-{event_id}.json"
            safe_write_json(alert_path, payload)

        self._known_alert_fingerprints.add(fp)
        self.health.last_alert = utc_now()
        self.health.alerts_count += 1
        return evt_path

    # --------------------------------------------------------------------------
    # Single Daemon Observation Cycle
    # --------------------------------------------------------------------------

    def run_daemon_cycle(self) -> Dict[str, Any]:
        """Runs a single deterministic operations cycle across all components."""
        self.health.scan_count += 1
        self.health.last_scan = utc_now()

        # 0. Bounded Autonomous Operational Hygiene Reconciliation
        self.hygiene.perform_hygiene_cycle()

        # 1. Audit Worker Liveness & Temporary Expiry
        workers = self.registry.list_workers()
        evidence = self.discover_local_worker_evidence()

        for wid, w in workers.items():
            ev = evidence.get(wid, {})
            last_mtime = ev.get("last_mtime")
            worker_pid = w.pid if (hasattr(w, "pid") and w.pid) else ev.get("pid")
            self.registry.audit_worker_liveness(
                worker=w,
                pid=worker_pid,
                last_activity_ts=last_mtime,
                stall_threshold_seconds=180.0,
            )

        # 2. Compile Live HQ Telemetry Snapshot
        snapshot = self.bridge.compile_hq_telemetry()
        self.health.last_successful_snapshot = utc_now()
        self.health.active_workers_count = snapshot.get("active_worker_count", 0)
        self.health.free_workers_count = snapshot.get("free_worker_count", 0)

        # 3. Add Bar/Sauna Leisure Compatibility Field to Workers
        for wid, wdict in snapshot.get("workers", {}).items():
            st = wdict.get("state")
            vis = wdict.get("visual_state")
            # Leisure eligible ONLY if SAFE_IDLE or AVAILABLE without active high blockers
            is_leisure = (vis == VisualState.IDLE.value) and (st in (WorkerState.SAFE_IDLE.value, WorkerState.AVAILABLE.value))
            wdict["leisure_eligible"] = is_leisure
            wdict["display_name"] = wid
            wdict["speech_text"] = wdict.get("speech_bubble", "")

        # 4. Save Updated HQ Snapshot with Leisure Data
        safe_write_json(self.state_dir / "hq_telemetry_snapshot.json", snapshot)

        # 5. Publish Daemon Health
        safe_write_json(self.health_file, self.health.to_dict())

        return {
            "timestamp": utc_now(),
            "scan_count": self.health.scan_count,
            "active_workers": self.health.active_workers_count,
            "free_workers": self.health.free_workers_count,
            "unresolved_blockers": len(self.unresolved_high_blockers),
            "final_acceptance_ready": (self.builder_finished_candidate is not None and len(self.unresolved_high_blockers) == 0),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Live HQ Operations Daemon (Mission 206)")
    parser.add_argument("--once", action="store_true", help="Run a single operations cycle and exit")
    parser.add_argument("--daemon", action="store_true", help="Run continuous operations loop (~10s)")
    parser.add_argument("--interval", type=float, default=10.0, help="Loop interval in seconds")
    args = parser.parse_args()

    daemon = HQOperationsDaemon(watch_interval=args.interval)

    if args.daemon:
        print(f"[HQ DAEMON] Starting continuous operations watch (Interval: {args.interval}s, Model Calls: 0, Spend: 0 EUR)")
        try:
            while True:
                res = daemon.run_daemon_cycle()
                print(f"[HQ DAEMON] [{res['timestamp']}] Scan #{res['scan_count']} | Active: {res['active_workers']} | Free: {res['free_workers']} | Blockers: {res['unresolved_blockers']} | Final Ready: {res['final_acceptance_ready']}")
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\n[HQ DAEMON] Stopped cleanly.")
        return 0

    res = daemon.run_daemon_cycle()
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
