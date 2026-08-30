#!/usr/bin/env python3
"""Deterministic SNITCH runtime watchdog.

SNITCH observes local runtime evidence and writes one bounded Courier alert per
workflow/correlation/classification.  It never kills, restarts, repairs, or
dispatches a worker: Chief remains the authority for any follow-up routing.
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
THRESHOLD_SECONDS = 300
PERSISTENT_SERVICE_MARKERS = ("run_visual_studio_server.py",)


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
    elapsed_seconds: float
    task_id: str | None = None
    workflow_id: str | None = None
    correlation_id: str | None = None
    started_at: str | None = None
    last_progress_at: str | None = None
    heartbeat_at: str | None = None
    human_gate: bool = False
    waiting_for_agent: bool = False
    waiting_for_external_result: bool = False
    persistent_service: bool = False
    evidence: dict[str, Any] | None = None


class SnitchWatchdog:
    """Classifies observations and emits deduplicated, provenance-safe alerts."""

    def __init__(self, repo_dir: Path = COURIER_DIR, threshold_seconds: int = THRESHOLD_SECONDS):
        self.repo_dir = repo_dir
        self.threshold_seconds = threshold_seconds
        self.states_dir = repo_dir / "events/agent-states"
        self.alerts_dir = repo_dir / "events/runtime-alerts"

    def classify(self, observation: RuntimeObservation, now: dt.datetime | None = None) -> tuple[str, str]:
        now = now or utc_now()
        if observation.human_gate:
            return "WAITING_FOR_HUMAN", "An explicit human approval gate is active."
        if observation.waiting_for_agent:
            return "WAITING_FOR_AGENT", "A referenced worker is still pending."
        if observation.waiting_for_external_result:
            return "WAITING_FOR_EXTERNAL_RESULT", "An external result is pending."
        if observation.persistent_service or any(marker in observation.process for marker in PERSISTENT_SERVICE_MARKERS):
            return "EXPECTED_LONG_RUNNING", "Persistent Studio service is intentionally running."
        if observation.elapsed_seconds <= self.threshold_seconds:
            return "MONITORING", "Runtime remains inside the observation threshold."
        progress_at = parse_time(observation.last_progress_at) or parse_time(observation.heartbeat_at)
        if progress_at and (now - progress_at).total_seconds() <= self.threshold_seconds:
            return "SLOW_BUT_PROGRESSING", "Runtime exceeds threshold but recent progress is recorded."
        if not observation.workflow_id or not observation.correlation_id:
            return "UNKNOWN", "No complete workflow/correlation provenance is available for an alert."
        return "STALLED", "Runtime exceeds threshold without a recent heartbeat or progress record."

    def _alert_key(self, observation: RuntimeObservation, classification: str) -> str:
        payload = "|".join([
            observation.workflow_id or "", observation.correlation_id or "",
            observation.task_id or "", observation.process, classification,
        ])
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _existing_alert(self, alert_key: str) -> Path | None:
        if not self.alerts_dir.exists():
            return None
        for path in self.alerts_dir.glob("*.json"):
            if load_json(path).get("dedupe_key") == alert_key:
                return path
        return None

    def _write_state(self, observation: RuntimeObservation, classification: str, reason: str, alert_path: Path | None) -> dict[str, Any]:
        state = {
            "schema_version": "2.0",
            "id": "agent-snitch",
            "name": "SNITCH",
            "role": "RUNTIME WATCHDOG / DELAY SENTINEL",
            "state": "ALERT_SENT" if alert_path else classification,
            "task": observation.task_id,
            "progress": 1.0 if alert_path else 0.0,
            "position_hint": "workstation_snitch",
            "workflow": observation.workflow_id,
            "correlation_id": observation.correlation_id,
            "last_action": reason,
            "next_action": "Chief review required" if alert_path else "Continue evidence-based monitoring",
            "result": {"alert_file": alert_path.name} if alert_path else None,
            "blocked": classification in {"WAITING_FOR_HUMAN", "BLOCKED"},
            "human_gate": "REQUIRE_EXPLICIT_HUMAN_APPROVAL" if observation.human_gate else None,
            "updated_at": iso_now(),
        }
        save_json(self.states_dir / "agent-snitch.json", state)
        return state

    def scan(self, observation: RuntimeObservation, now: dt.datetime | None = None) -> dict[str, Any]:
        classification, reason = self.classify(observation, now)
        alert_path = None
        # Only evidence-backed abnormal states with full provenance enter Courier.
        if classification in {"SUSPECTED_STALL", "STALLED", "BLOCKED"}:
            alert_key = self._alert_key(observation, classification)
            alert_path = self._existing_alert(alert_key)
            if alert_path is None:
                alert = {
                    "schema_version": "2.0",
                    "message_id": f"runtime-alert-{uuid.uuid4().hex[:12]}",
                    "agent_id": "agent-snitch",
                    "task_id": observation.task_id,
                    "workflow_id": observation.workflow_id,
                    "correlation_id": observation.correlation_id,
                    "process": {"identity": observation.process, "started_at": observation.started_at},
                    "elapsed_seconds": observation.elapsed_seconds,
                    "last_progress_at": observation.last_progress_at,
                    "classification": classification,
                    "reason": reason,
                    "evidence": observation.evidence or {},
                    "recommended_next_action": "Chief reviews the alert and selects a free appropriate agent.",
                    "created_at": iso_now(),
                    "dedupe_key": alert_key,
                }
                alert_path = self.alerts_dir / f"{alert['message_id']}.json"
                save_json(alert_path, alert)
        state = self._write_state(observation, classification, reason, alert_path)
        return {"classification": classification, "reason": reason, "alert_path": alert_path, "state": state}


def inspect_local_processes() -> list[RuntimeObservation]:
    """Read-only local process snapshot; no process control is performed."""
    result = subprocess.run(["ps", "-axo", "etime=,command="], text=True, capture_output=True, check=False)
    observations: list[RuntimeObservation] = []
    for line in result.stdout.splitlines():
        if "run_visual_studio_server.py" in line:
            observations.append(RuntimeObservation(process=line.strip(), elapsed_seconds=0, persistent_service=True))
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
