#!/usr/bin/env python3
"""Mission 208: Automatic Deterministic Result Handoff Layer.

Connects asynchronous worker results directly into the Registry, Chief Alerts,
HQ Telemetry, and next-worker signals without human copy/paste intervention:
- Ingests structured results from GOOGLE, CLI1, CLI2, and CODEX
- Fast path: mtime/size check before SHA-256 fingerprint hashing
- Emits deterministic signaling events:
  * GOOGLE_CANDIDATE_AVAILABLE (Google -> CLI2)
  * RELEASE_BLOCKER_FOUND (CLI2 new high blocker -> Chief alert)
  * FINAL_ACCEPTANCE_READY (CLI2 pass matching candidate -> Codex)
  * RELEASE_ACCEPTED (Codex release -> Chief)
  * REMEDIATION_REQUIRED (Codex remediation -> Google)
  * EXECUTION_SURFACE_BLOCK (Surface / environment block)
- 100% deterministic local execution (0 model calls, 0 EUR spend)
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
    from hq_telemetry_bridge import HQTelemetryBridge
except ImportError:
    from scripts.live_worker_registry import (
        AvailabilityClass,
        EventType,
        LiveWorkerRegistry,
        WorkerRecord,
        WorkerState,
    )
    from scripts.hq_telemetry_bridge import HQTelemetryBridge


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


class HandoffSignal(str, enum.Enum):
    GOOGLE_CANDIDATE_AVAILABLE = "GOOGLE_CANDIDATE_AVAILABLE"
    RELEASE_BLOCKER_FOUND = "RELEASE_BLOCKER_FOUND"
    FINAL_ACCEPTANCE_READY = "FINAL_ACCEPTANCE_READY"
    RELEASE_ACCEPTED = "RELEASE_ACCEPTED"
    REMEDIATION_REQUIRED = "REMEDIATION_REQUIRED"
    EXECUTION_SURFACE_BLOCK = "EXECUTION_SURFACE_BLOCK"
    NO_ACTION = "NO_ACTION"


@dataclass
class WorkerResultEnvelope:
    worker: str
    mission: str
    state: str
    candidate_fingerprint: Optional[str] = None
    target_fingerprint: Optional[str] = None
    severity: str = "INFO"
    new_high: bool = False
    tests: Dict[str, Any] = field(default_factory=dict)
    ready_for_next: bool = False
    next: Optional[str] = None
    execution_surface_block: bool = False
    block_reason: Optional[str] = None
    result_id: str = field(default_factory=lambda: f"res-{uuid.uuid4().hex[:8]}")
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AutomaticResultHandoff:
    """Deterministic result handoff orchestrator routing signals across the agent fleet."""

    def __init__(self, repo_dir: Path = COURIER_DIR):
        self.repo_dir = repo_dir.resolve()
        self.results_dir = self.repo_dir / "events" / "results"
        self.alerts_dir = self.repo_dir / "events" / "runtime-alerts"
        self.events_dir = self.repo_dir / "events" / "worker-events"
        self.state_dir = self.repo_dir / "events" / "runtime-state"
        self.handoff_file = self.state_dir / "latest_handoff_signals.json"

        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.alerts_dir.mkdir(parents=True, exist_ok=True)
        self.events_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)

        self.registry = LiveWorkerRegistry(repo_dir=self.repo_dir)
        self.bridge = HQTelemetryBridge(repo_dir=self.repo_dir)

        self._seen_file_mtimes: Dict[str, Tuple[float, int]] = {}
        self._seen_fingerprints: Set[str] = self._load_processed_fingerprints()
        self.active_google_candidate: Optional[str] = None

        self.telemetry = {
            "results_processed": 0,
            "duplicates_suppressed": 0,
            "signals_emitted": 0,
            "model_calls": 0,
        }

    def _load_processed_fingerprints(self) -> Set[str]:
        fps: Set[str] = set()
        for f in self.events_dir.glob("*.json"):
            data = safe_load_json(f)
            if "fingerprint" in data:
                fps.add(data["fingerprint"])
        return fps

    def compute_result_fingerprint(self, res: WorkerResultEnvelope) -> str:
        raw = f"{res.worker}|{res.mission}|{res.state}|{res.candidate_fingerprint or 'NONE'}|{res.target_fingerprint or 'NONE'}|{res.new_high}|{res.execution_surface_block}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def ingest_and_route_result(self, result_dict: Dict[str, Any], source_file: Optional[Path] = None) -> Tuple[HandoffSignal, Optional[str]]:
        """Processes a structured worker result and routes deterministic signals."""
        self.telemetry["results_processed"] += 1

        # Fast path check on source file mtime & size
        if source_file and source_file.is_file():
            stat = source_file.stat()
            key = str(source_file)
            if key in self._seen_file_mtimes:
                old_mtime, old_size = self._seen_file_mtimes[key]
                if stat.st_mtime == old_mtime and stat.st_size == old_size:
                    self.telemetry["duplicates_suppressed"] += 1
                    return HandoffSignal.NO_ACTION, "FAST_PATH_UNCHANGED"
            self._seen_file_mtimes[key] = (stat.st_mtime, stat.st_size)

        # Parse Envelope
        res = WorkerResultEnvelope(
            worker=result_dict.get("worker", "UNKNOWN"),
            mission=result_dict.get("mission", "NONE"),
            state=result_dict.get("state", "COMPLETED"),
            candidate_fingerprint=result_dict.get("candidate_fingerprint"),
            target_fingerprint=result_dict.get("target_fingerprint"),
            severity=result_dict.get("severity", "INFO"),
            new_high=bool(result_dict.get("new_high", False)),
            tests=result_dict.get("tests", {}),
            ready_for_next=bool(result_dict.get("ready_for_next", False)),
            next=result_dict.get("next"),
            execution_surface_block=bool(result_dict.get("execution_surface_block", False)),
            block_reason=result_dict.get("block_reason"),
            result_id=result_dict.get("result_id", f"res-{uuid.uuid4().hex[:8]}"),
        )

        fp = self.compute_result_fingerprint(res)

        # Duplicate check
        if fp in self._seen_fingerprints:
            self.telemetry["duplicates_suppressed"] += 1
            return HandoffSignal.NO_ACTION, "DUPLICATE_FINGERPRINT"

        self._seen_fingerprints.add(fp)

        # ----------------------------------------------------------------------
        # Deterministic Signal Classifier
        # ----------------------------------------------------------------------

        # Rule 1: Execution-Surface Block (Environment / Infrastructure)
        if res.execution_surface_block:
            self._emit_handoff_event(
                signal=HandoffSignal.EXECUTION_SURFACE_BLOCK,
                worker_id=res.worker,
                mission_id=res.mission,
                fingerprint=fp,
                severity="HIGH",
                evidence={"block_reason": res.block_reason or "Infrastructure execution surface unavailable"},
                recommended_action="RETRY_WITH_LOCAL_ENVIRONMENT_FALLBACK",
            )
            return HandoffSignal.EXECUTION_SURFACE_BLOCK, "EXECUTION_SURFACE_BLOCK"

        # Rule 2: Google Builder Completion -> GOOGLE_CANDIDATE_AVAILABLE
        if res.worker.upper() in ("GOOGLE", "BUILDER") and res.state == "COMPLETED" and res.candidate_fingerprint:
            self.active_google_candidate = res.candidate_fingerprint
            self.registry.record_worker_completed(
                worker_id="GOOGLE",
                result_id=res.result_id,
                completion_evidence={"candidate_fingerprint": res.candidate_fingerprint, "mission": res.mission},
            )
            self._emit_handoff_event(
                signal=HandoffSignal.GOOGLE_CANDIDATE_AVAILABLE,
                worker_id="GOOGLE",
                mission_id=res.mission,
                fingerprint=fp,
                severity="INFO",
                evidence={"candidate_fingerprint": res.candidate_fingerprint},
                recommended_action="TRIGGER_CLI2_ADVERSARIAL_REVIEW",
            )
            self.bridge.compile_hq_telemetry()
            return HandoffSignal.GOOGLE_CANDIDATE_AVAILABLE, f"CANDIDATE_{res.candidate_fingerprint[:8]}"

        # Rule 3: CLI2 New HIGH Blocker Found -> RELEASE_BLOCKER_FOUND
        if res.worker.upper() in ("CLI2", "ADVERSARY") and res.new_high:
            self._emit_handoff_event(
                signal=HandoffSignal.RELEASE_BLOCKER_FOUND,
                worker_id="CLI2",
                mission_id=res.mission,
                fingerprint=fp,
                severity="HIGH",
                evidence={"block_reason": res.block_reason, "tests": res.tests},
                recommended_action="NOTIFY_CHIEF_AND_REMEDIATE",
            )
            self.bridge.compile_hq_telemetry()
            return HandoffSignal.RELEASE_BLOCKER_FOUND, "HIGH_DEFECT_DETECTED"

        # Rule 4: CLI2 PASS Matching Google Candidate Fingerprint -> FINAL_ACCEPTANCE_READY
        if res.worker.upper() in ("CLI2", "ADVERSARY") and res.state == "COMPLETED" and not res.new_high:
            # Verify candidate fingerprint match
            if res.target_fingerprint and self.active_google_candidate and res.target_fingerprint != self.active_google_candidate:
                return HandoffSignal.NO_ACTION, "MISMATCHED_TARGET_FINGERPRINT"

            self.registry.record_worker_completed(
                worker_id="CLI2",
                result_id=res.result_id,
                completion_evidence={"tests": res.tests, "target_fingerprint": res.target_fingerprint},
            )
            self._emit_handoff_event(
                signal=HandoffSignal.FINAL_ACCEPTANCE_READY,
                worker_id="CODEX",
                mission_id=res.mission,
                fingerprint=fp,
                severity="INFO",
                evidence={"verified_candidate": res.target_fingerprint or self.active_google_candidate},
                recommended_action="TRIGGER_CODEX_FINAL_ACCEPTANCE",
            )
            self.bridge.compile_hq_telemetry()
            return HandoffSignal.FINAL_ACCEPTANCE_READY, "ADVERSARIAL_MATRIX_GREEN"

        # Rule 5: Codex Release -> RELEASE_ACCEPTED
        if res.worker.upper() in ("CODEX", "CHIEF_ORACLE") and res.state == "RELEASE":
            self.registry.record_worker_completed(
                worker_id="CODEX",
                result_id=res.result_id,
                completion_evidence={"release_certified": True},
            )
            self._emit_handoff_event(
                signal=HandoffSignal.RELEASE_ACCEPTED,
                worker_id="CODEX",
                mission_id=res.mission,
                fingerprint=fp,
                severity="INFO",
                evidence={"release_decision": "CERTIFIED_ACCEPTANCE_PASS"},
                recommended_action="CHIEF_RELEASE_DEPLOYMENT",
            )
            self.bridge.compile_hq_telemetry()
            return HandoffSignal.RELEASE_ACCEPTED, "RELEASE_CERTIFIED"

        # Rule 6: Codex Remediation -> REMEDIATION_REQUIRED
        if res.worker.upper() in ("CODEX", "CHIEF_ORACLE") and res.state in ("REMEDIATE", "FAILED"):
            self._emit_handoff_event(
                signal=HandoffSignal.REMEDIATION_REQUIRED,
                worker_id="GOOGLE",
                mission_id=res.mission,
                fingerprint=fp,
                severity="HIGH",
                evidence={"oracle_feedback": res.block_reason or "Acceptance oracle criteria unfulfilled"},
                recommended_action="DISPATCH_GOOGLE_REMEDIATION_ROUND",
            )
            self.bridge.compile_hq_telemetry()
            return HandoffSignal.REMEDIATION_REQUIRED, "ORACLE_REMEDIATION_REQUESTED"

        # Rule 7: CLI1 Operations Self Completion
        if res.worker.upper() == "CLI1" and res.state == "COMPLETED":
            self.registry.record_worker_completed(
                worker_id="CLI1",
                result_id=res.result_id,
                completion_evidence={"mission": res.mission, "tests": res.tests},
            )
            self.bridge.compile_hq_telemetry()
            return HandoffSignal.NO_ACTION, "CLI1_COMPLETED"

        # Ensure Courier state/completion handoff
        try:
            from scripts.completion_handoff_engine import CompletionHandoffEngine
            engine = CompletionHandoffEngine(repo_dir=self.repo_dir)
            task_id = result_dict.get("request_id", res.result_id)
            
            # Ensure the task is opened and claimed so record_result doesn't return UNKNOWN
            engine.open(task_id, fp)
            engine.claim(task_id, res.worker)
            
            engine.record_result(
                task_id=task_id,
                semantic_fingerprint=fp,
                evidence_reference=str(source_file) if source_file else None,
                acceptance_satisfied=(res.state == "COMPLETED")
            )
        except Exception as e:
            print(f"Handoff engine error: {e}")

        return HandoffSignal.NO_ACTION, "UNCLASSIFIED_RESULT"

    def _emit_handoff_event(
        self,
        signal: HandoffSignal,
        worker_id: str,
        mission_id: str,
        fingerprint: str,
        severity: str,
        evidence: Dict[str, Any],
        recommended_action: Optional[str] = None,
    ) -> Path:
        """Emits structured event to worker-events and runtime-alerts."""
        self.telemetry["signals_emitted"] += 1
        event_id = f"evt-handoff-{uuid.uuid4().hex[:10]}"

        payload = {
            "schema_version": "3.0",
            "event_id": event_id,
            "event_type": signal.value,
            "worker_id": worker_id,
            "mission_id": mission_id,
            "fingerprint": fingerprint,
            "severity": severity,
            "evidence": evidence,
            "recommended_action": recommended_action,
            "created_at": utc_now(),
            "acknowledged": False,
        }

        # Write to worker-events
        evt_path = self.events_dir / f"{event_id}.json"
        safe_write_json(evt_path, payload)

        # Write to runtime-alerts if HIGH/CRITICAL or high-value signal
        if severity in ("WARNING", "HIGH", "CRITICAL") or signal in (HandoffSignal.FINAL_ACCEPTANCE_READY, HandoffSignal.RELEASE_ACCEPTED):
            alert_path = self.alerts_dir / f"alert-{event_id}.json"
            safe_write_json(alert_path, payload)

        # Update latest handoff signals cache
        safe_write_json(self.handoff_file, {
            "last_signal": signal.value,
            "worker_id": worker_id,
            "mission_id": mission_id,
            "updated_at": utc_now(),
            "telemetry": self.telemetry,
        })
        return evt_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Automatic Deterministic Result Handoff (Mission 208)")
    parser.add_argument("--scan", action="store_true", help="Scan results directory and route pending results")
    args = parser.parse_args()

    handoff = AutomaticResultHandoff()
    if args.scan:
        count = 0
        for rf in sorted(handoff.results_dir.glob("*.json")):
            data = safe_load_json(rf)
            sig, reason = handoff.ingest_and_route_result(data, source_file=rf)
            if sig != HandoffSignal.NO_ACTION:
                print(f"[HANDOFF] Processed {rf.name} -> {sig.value} ({reason})")
                count += 1
        print(f"[HANDOFF] Scan complete. Total new signals emitted: {count}")
        return 0

    print("[HANDOFF] Automatic result handoff router operational.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
