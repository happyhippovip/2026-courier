#!/usr/bin/env python3
"""Deterministic SNITCH 2.0 runtime watchdog.

SNITCH 2.0 observes local runtime evidence, classifies execution states, and
writes bounded, deduplicated incidents/alerts to Courier events.

CRITICAL INVARIANTS:
- RUNTIME > 5 MINUTES != ERROR: Distinguishes EXPECTED_LONG_RUNNING (persistent
  services) and SLOW_BUT_PROGRESSING (advancing tasks) from true stalls/runaways.
- AUTO-KILL IS DISABLED: SNITCH never kills processes, deletes files, or resets git.
  Chief remains the authority for any repair or reserve bodyguard routing.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
THRESHOLD_SECONDS = 300  # 5-minute review threshold

PERSISTENT_SERVICE_MARKERS = (
    "run_visual_studio_server.py",
    "launch_visual_studio.py",
)


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat()


def parse_time(value: str | None) -> dt.datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
    temp.replace(path)


@dataclass(frozen=True)
class RuntimeObservation:
    process: str
    process_type: str = "BOUNDED_JOB"  # PERSISTENT_SERVICE, BOUNDED_JOB, INTERACTIVE_WAIT, UNKNOWN
    elapsed_seconds: float = 0.0
    task_id: str | None = None
    workflow_id: str | None = None
    correlation_id: str | None = None
    agent_id: str | None = None
    pid: int | None = None
    ppid: int | None = None
    started_at: str | None = None
    last_progress_at: str | None = None
    heartbeat_at: str | None = None
    task_state: str | None = None
    chief_wait_state: str | None = None
    human_gate: bool = False
    waiting_for_agent: bool = False
    waiting_for_external_result: bool = False
    persistent_service: bool = False
    expected_max_seconds: float | None = None
    expected_max_frames: int | None = None
    current_frames: int | None = None
    output_file: str | None = None
    output_bytes: int | None = None
    port: int | None = None
    port_healthy: bool | None = None
    task_completed: bool = False
    is_orphan: bool = False
    deadlock_suspected: bool = False
    evidence: dict[str, Any] | None = None


class SnitchWatchdog:
    """SNITCH 2.0 runtime watchdog: classifies observations and emits deduplicated alerts."""

    def __init__(self, repo_dir: Path = COURIER_DIR, threshold_seconds: int = THRESHOLD_SECONDS):
        self.repo_dir = repo_dir
        self.threshold_seconds = threshold_seconds
        self.states_dir = repo_dir / "events/agent-states"
        self.alerts_dir = repo_dir / "events/runtime-alerts"
        self.incidents_dir = repo_dir / "events/incidents"

    def classify(self, obs: RuntimeObservation, now: dt.datetime | None = None) -> tuple[str, str]:
        now = now or utc_now()

        # 1. Human Approval Gate
        if obs.human_gate or obs.task_state in {"BLOCKED_HUMAN_GATE", "WAITING_FOR_HUMAN"}:
            return "WAITING_FOR_HUMAN", "An explicit human approval gate is active."

        # 2. Waiting for other workers or external completion
        if obs.waiting_for_agent:
            return "WAITING_FOR_AGENT", "A referenced worker task is currently executing."
        if obs.waiting_for_external_result:
            return "WAITING_FOR_EXTERNAL_RESULT", "An external execution result is pending."

        # 3. Persistent Services (Never marked stalled purely based on time)
        if obs.persistent_service or obs.process_type == "PERSISTENT_SERVICE" or any(marker in obs.process for marker in PERSISTENT_SERVICE_MARKERS):
            return "EXPECTED_LONG_RUNNING", "The Studio server is intentionally persistent. No action needed."

        # 4. Deadlock Detection
        if obs.deadlock_suspected:
            return "DEADLOCK_SUSPECTED", "A cyclic inter-task dependency or deadlock state is suspected."

        # 5. Orphan / Zombie Process
        if obs.is_orphan or (obs.task_completed and obs.pid and obs.elapsed_seconds > 60):
            return "ORPHANED_PROCESS", "A process is running without matching active workflow task linkage."

        # 6. Runaway Risk (Contract Exceeded)
        if obs.expected_max_seconds is not None and obs.elapsed_seconds > obs.expected_max_seconds:
            return "RUNAWAY_RISK", f"Process exceeded its execution contract limit of {obs.expected_max_seconds}s (elapsed: {obs.elapsed_seconds}s)."
        if obs.expected_max_frames is not None and obs.current_frames is not None and obs.current_frames > obs.expected_max_frames:
            return "RUNAWAY_RISK", f"Render exceeded maximum frame boundary limit of {obs.expected_max_frames} (frames rendered: {obs.current_frames})."

        # 7. Normal execution inside 5-minute threshold
        if obs.elapsed_seconds <= self.threshold_seconds:
            return "MONITORING", "I'm monitoring running tasks. Everything looks healthy."

        # 8. Execution > 5 minutes: Check for recent progress (RUNTIME > 5 MIN != ERROR)
        progress_at = parse_time(obs.last_progress_at) or parse_time(obs.heartbeat_at)
        if progress_at and (now - progress_at).total_seconds() <= self.threshold_seconds:
            return "SLOW_BUT_PROGRESSING", "This task has exceeded five minutes, but progress is still detected."

        # Frame or file advancement evidence
        if obs.evidence and (obs.evidence.get("frames_progressing") or obs.evidence.get("output_growing") or obs.evidence.get("cpu_time_advancing")):
            return "SLOW_BUT_PROGRESSING", "This task has exceeded five minutes, but progress is still detected."

        # 9. Provenance check before alerting
        if not obs.workflow_id or not obs.correlation_id:
            return "UNKNOWN", "No complete workflow/correlation provenance is available for an alert."

        # 10. True Stall
        if obs.elapsed_seconds > (self.threshold_seconds * 2):
            return "STALLED", "No meaningful progress detected. I informed Chief."
        return "SUSPECTED_STALL", "Task runtime exceeds 5 minutes without recent progress heartbeat."

    def generate_speech(self, classification: str) -> str:
        """Deterministic speech bubble text corresponding to SNITCH visual state."""
        speech_map = {
            "MONITORING": "I'm monitoring running tasks. Everything looks healthy.",
            "EXPECTED_LONG_RUNNING": "The Studio server is intentionally persistent. No action needed.",
            "SLOW_BUT_PROGRESSING": "This task has exceeded five minutes, but progress is still detected.",
            "SUSPECTED_STALL": "No meaningful progress detected. I informed Chief.",
            "STALLED": "No meaningful progress detected. I informed Chief.",
            "RUNAWAY_RISK": "A bounded process exceeded its safety contract. I raised a high-priority incident.",
            "WAITING_FOR_HUMAN": "A workflow task is paused at the Human Gate awaiting sign-off.",
            "WAITING_FOR_AGENT": "Waiting for referenced worker task to conclude.",
            "WAITING_FOR_EXTERNAL_RESULT": "Waiting for external result returns.",
            "ORPHANED_PROCESS": "Detected orphaned process without active task linkage.",
            "DEADLOCK_SUSPECTED": "Suspected cyclic wait condition detected.",
            "RESOLVED": "The incident has been resolved. Returning to regular monitoring.",
            "ALERT_SENT": "Runtime alert sent to Courier. Awaiting Chief decision.",
            "UNKNOWN": "Monitoring standby.",
        }
        return speech_map.get(classification, "Monitoring operations floor.")

    def _alert_key(self, obs: RuntimeObservation, classification: str) -> str:
        payload = "|".join([
            obs.workflow_id or "",
            obs.correlation_id or "",
            obs.task_id or "",
            obs.process,
            classification,
        ])
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _existing_alert(self, alert_key: str) -> Path | None:
        for directory in (self.alerts_dir, self.incidents_dir):
            if directory.exists():
                for path in directory.glob("*.json"):
                    if load_json(path).get("dedupe_key") == alert_key:
                        return path
        return None

    def _determine_severity(self, classification: str) -> str:
        if classification in {"RUNAWAY_RISK", "DEADLOCK_SUSPECTED"}:
            return "CRITICAL"
        if classification in {"STALLED", "ORPHANED_PROCESS"}:
            return "HIGH"
        if classification in {"SUSPECTED_STALL", "BLOCKED"}:
            return "MEDIUM"
        return "LOW"

    def _write_state(
        self,
        obs: RuntimeObservation,
        classification: str,
        reason: str,
        alert_path: Path | None,
    ) -> dict[str, Any]:
        speech = self.generate_speech(classification)
        state = {
            "schema_version": "2.0",
            "id": "agent-snitch",
            "name": "SNITCH",
            "role": "OPERATIONS WATCHDOG / DELAY SENTINEL",
            "state": "ALERT_SENT" if alert_path else classification,
            "task": obs.task_id or "Active Monitoring",
            "progress": 1.0 if alert_path else 0.0,
            "position_hint": "workstation_snitch",
            "workflow": obs.workflow_id,
            "correlation_id": obs.correlation_id,
            "last_action": reason,
            "next_action": "Chief review required" if alert_path else "Continue evidence-based monitoring",
            "speech": speech,
            "incident": {
                "active": alert_path is not None,
                "classification": classification,
                "alert_file": alert_path.name if alert_path else None,
                "severity": self._determine_severity(classification),
            },
            "blocked": classification in {"WAITING_FOR_HUMAN", "BLOCKED"},
            "human_gate": "REQUIRE_EXPLICIT_HUMAN_APPROVAL" if obs.human_gate else None,
            "auto_kill_policy": "DISABLED (CHIEF_ESCALATION_ONLY)",
            "updated_at": iso_now(),
        }
        save_json(self.states_dir / "agent-snitch.json", state)
        return state

    def scan(self, obs: RuntimeObservation, now: dt.datetime | None = None) -> dict[str, Any]:
        classification, reason = self.classify(obs, now)
        alert_path = None

        # Material abnormalities trigger a deduplicated Courier alert
        alertable_states = {
            "SUSPECTED_STALL",
            "STALLED",
            "RUNAWAY_RISK",
            "ORPHANED_PROCESS",
            "DEADLOCK_SUSPECTED",
            "BLOCKED",
        }

        if classification in alertable_states:
            alert_key = self._alert_key(obs, classification)
            alert_path = self._existing_alert(alert_key)
            if alert_path is None:
                message_id = f"runtime-alert-{uuid.uuid4().hex[:12]}"
                severity = self._determine_severity(classification)
                alert = {
                    "schema_version": "2.0",
                    "message_id": message_id,
                    "incident_id": f"inc-{uuid.uuid4().hex[:8]}",
                    "agent_id": "agent-snitch",
                    "task_id": obs.task_id,
                    "workflow_id": obs.workflow_id,
                    "correlation_id": obs.correlation_id,
                    "target_agent": obs.agent_id or "UNKNOWN",
                    "process": {
                        "identity": obs.process,
                        "process_type": obs.process_type,
                        "pid": obs.pid,
                        "started_at": obs.started_at,
                    },
                    "elapsed_seconds": obs.elapsed_seconds,
                    "last_progress_at": obs.last_progress_at,
                    "classification": classification,
                    "severity": severity,
                    "status": "OPEN",
                    "reason": reason,
                    "evidence": obs.evidence or {},
                    "recommended_next_action": "Chief reviews the alert and assigns a free specialist or reserve Bodyguard.",
                    "created_at": iso_now(),
                    "dedupe_key": alert_key,
                }
                alert_path = self.alerts_dir / f"{message_id}.json"
                save_json(alert_path, alert)

        state = self._write_state(obs, classification, reason, alert_path)
        return {
            "classification": classification,
            "reason": reason,
            "alert_path": alert_path,
            "speech": state.get("speech"),
            "state": state,
        }

    def resolve_incident(self, alert_key: str, resolution_reason: str = "Resolved by Chief") -> bool:
        """Mark an incident as RESOLVED without alert duplication."""
        found = False
        for directory in (self.alerts_dir, self.incidents_dir):
            if directory.exists():
                for path in directory.glob("*.json"):
                    data = load_json(path)
                    if data.get("dedupe_key") == alert_key:
                        data["status"] = "RESOLVED"
                        data["resolution"] = resolution_reason
                        data["resolved_at"] = iso_now()
                        save_json(path, data)
                        found = True
        return found


def inspect_local_processes() -> list[RuntimeObservation]:
    """Read-only local process snapshot; no process control is performed."""
    result = subprocess.run(["ps", "-axo", "etime=,command="], text=True, capture_output=True, check=False)
    observations: list[RuntimeObservation] = []
    for line in result.stdout.splitlines():
        if "run_visual_studio_server.py" in line:
            observations.append(RuntimeObservation(
                process=line.strip(),
                process_type="PERSISTENT_SERVICE",
                elapsed_seconds=0,
                persistent_service=True,
            ))
    return observations


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one deterministic SNITCH scan.")
    parser.add_argument("--scan-local", action="store_true", help="Inspect known local persistent services read-only.")
    args = parser.parse_args()
    watchdog = SnitchWatchdog()
    observations = inspect_local_processes() if args.scan_local else []
    for observation in observations:
        outcome = watchdog.scan(observation)
        print(json.dumps({"process": observation.process, "classification": outcome["classification"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
