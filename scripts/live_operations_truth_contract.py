#!/usr/bin/env python3
"""Read-only, deterministic Live Operations truth contract for Product-1C."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List


COURIER_DIR = Path(__file__).resolve().parent.parent
SENSITIVE_TOKENS = ("secret", "password", "credential", "authorization", "private_key", "bearer")
NORMALIZED_STATES = {
    "IDLE", "ACTIVE", "WAITING", "BLOCKED", "HUMAN_GATE", "MONEY_GATE",
    "REVIEW", "RESULT_READY", "ANOMALY", "UNKNOWN",
}


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return default


def _safe_value(value: Any, key: str = "") -> Any:
    """Remove sensitive-value fields; the snapshot keeps only safe operational metadata."""
    if any(token in key.lower() for token in SENSITIVE_TOKENS):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(k): _safe_value(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_safe_value(item, key) for item in value]
    return value


def _state_from_job(status: str) -> str:
    normalized = (status or "").upper()
    if normalized in {"DISPATCHED", "RUNNING", "EXECUTING", "ACTIVE"}:
        return "ACTIVE"
    if normalized in {"PREPARED", "RECONCILIATION_REQUIRED", "WAITING", "DEPENDENCY_WAIT"}:
        return "WAITING"
    if normalized in {"PARKED_HUMAN_GATE", "HUMAN_GATE", "WAITING_FOR_HUMAN"}:
        return "HUMAN_GATE"
    if normalized in {"PARKED_MONEY_GATE", "PAYMENT_APPROVAL_REQUIRED", "MONEY_GATE"}:
        return "MONEY_GATE"
    if normalized in {"EXECUTED_SUCCESS", "RESULT_READY", "COMPLETED"}:
        return "RESULT_READY"
    if normalized in {"EXECUTED_FAIL", "FAILED", "BLOCKED"}:
        return "BLOCKED"
    return "UNKNOWN"


def _parse_timestamp(value: Any) -> dt.datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class LiveOperationsTruthContract:
    """Reduces existing local Courier evidence into a UI-safe snapshot; it never writes."""

    def __init__(self, repo_dir: Path = COURIER_DIR):
        self.repo_dir = Path(repo_dir)
        self.events = self.repo_dir / "events"
        self.model_calls = 0

    def _jobs(self) -> List[Dict[str, Any]]:
        jobs_dir = self.events / "autonomy-runtime" / "jobs"
        return [item for path in sorted(jobs_dir.glob("*.json")) if isinstance((item := _read_json(path, {})), dict)]

    def _opportunities(self) -> List[Dict[str, Any]]:
        queue = self.events / "opportunity-queue"
        return [item for path in sorted(queue.glob("*.json")) if isinstance((item := _read_json(path, {})), dict)]

    def _event_entries(self) -> List[Dict[str, Any]]:
        ledger = _read_json(self.events / "autonomy-runtime" / "event_ledger.json", {})
        return ledger.get("events", []) if isinstance(ledger, dict) and isinstance(ledger.get("events"), list) else []

    def reduce_tasks(self, jobs: Iterable[Dict[str, Any]], events: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """One canonical task id yields one deterministic record or an UNKNOWN conflict."""
        by_task: Dict[str, List[Dict[str, Any]]] = {}
        for job in jobs:
            task_id = job.get("task_id")
            if isinstance(task_id, str) and task_id:
                by_task.setdefault(task_id, []).append(job)

        output: List[Dict[str, Any]] = []
        for task_id in sorted(by_task):
            records = by_task[task_id]
            signatures = {
                (str(record.get("owner", "")), str(record.get("provider", "")), str(record.get("scope", "")))
                for record in records
            }
            states = {_state_from_job(str(record.get("status", ""))) for record in records}
            latest = max(records, key=lambda r: _parse_timestamp(r.get("created_at")) or dt.datetime.min.replace(tzinfo=dt.timezone.utc))
            state = next(iter(states)) if len(states) == 1 and len(signatures) == 1 else "UNKNOWN"
            event_matches = [event for event in events if event.get("task_id") == task_id]
            last_event = event_matches[-1] if event_matches else None
            item = {
                "task_id": task_id,
                "owner_agent": latest.get("owner") if state != "UNKNOWN" else None,
                "provider": latest.get("provider") if state != "UNKNOWN" else None,
                "resource": latest.get("resource_class") if state != "UNKNOWN" else None,
                "scope": latest.get("scope") if state != "UNKNOWN" else None,
                "status": state,
                "started_at": latest.get("created_at"),
                "dependency_wait_reason": "DEPENDENCY_WAIT" if state == "WAITING" else None,
                "last_meaningful_event": _safe_value(last_event) if last_event else None,
                "result_reference": latest.get("correlation_id") if state == "RESULT_READY" else None,
                "next_action": "WAIT_FOR_EVIDENCE" if state in {"WAITING", "UNKNOWN"} else None,
            }
            output.append(_safe_value(item))
        return output

    def _gate_tasks(self, session: Dict[str, Any]) -> List[Dict[str, Any]]:
        output: List[Dict[str, Any]] = []
        for key, state in (("human_gates_encountered", "HUMAN_GATE"), ("money_gates_encountered", "MONEY_GATE")):
            values = session.get(key, []) if isinstance(session, dict) else []
            for item in values if isinstance(values, list) else []:
                if isinstance(item, dict) and isinstance(item.get("task_id"), str):
                    output.append({"task_id": item["task_id"], "status": state, "reason": _safe_value(item.get("reason"))})
        return output

    def _anomalies(self) -> List[Dict[str, Any]]:
        ledger = _read_json(self.events / "anomalies" / "anomaly_ledger.json", {})
        if not isinstance(ledger, dict):
            return []
        output = []
        for fingerprint, entry in sorted(ledger.items()):
            if not isinstance(entry, dict):
                continue
            output.append({
                "fingerprint": fingerprint,
                "classification": entry.get("severity", "UNKNOWN"),
                "affected_branch": entry.get("affected_branch"),
                "affected_scope": entry.get("affected_scope"),
                "quarantined": bool(entry.get("severity") == "CRITICAL" and not entry.get("resolved", False)),
                "resolved": bool(entry.get("resolved", False)),
            })
        return output

    def _endurance(self) -> Dict[str, Any]:
        heartbeat = _read_json(self.events / "autonomy-runtime" / "heartbeat.json", {})
        if not isinstance(heartbeat, dict) or heartbeat.get("session_id") != "session-188g-endurance-1788216021":
            return {"status": "NOT_AVAILABLE", "endurance_proven": "PENDING"}
        elapsed = heartbeat.get("elapsed_seconds")
        target = heartbeat.get("duration_target_hours")
        target_seconds = target * 3600 if isinstance(target, (int, float)) else None
        proven = "YES" if isinstance(elapsed, (int, float)) and target_seconds and elapsed >= target_seconds and heartbeat.get("status") == "COMPLETED" else "PENDING"
        return _safe_value({
            "session_id": heartbeat.get("session_id"), "status": heartbeat.get("status", "UNKNOWN"),
            "elapsed_seconds": elapsed, "target_seconds": target_seconds,
            "heartbeat_timestamp": heartbeat.get("timestamp"), "jobs_completed": heartbeat.get("jobs_completed"),
            "endurance_proven": proven,
        })

    def snapshot(self) -> Dict[str, Any]:
        """Read the local evidence once. This method never invokes a model or writes state."""
        session = _read_json(self.events / "autonomy-runtime" / "current_session.json", {})
        session = session if isinstance(session, dict) else {}
        tasks = self.reduce_tasks(self._jobs(), self._event_entries())
        tasks.extend(self._gate_tasks(session))
        deduped: Dict[str, Dict[str, Any]] = {}
        for task in tasks:
            task_id = task.get("task_id")
            if not isinstance(task_id, str):
                continue
            existing = deduped.get(task_id)
            deduped[task_id] = task if existing is None else {"task_id": task_id, "status": "UNKNOWN"}
        normalized_tasks = [deduped[key] for key in sorted(deduped)]
        active = [task for task in normalized_tasks if task.get("status") == "ACTIVE"]
        return _safe_value({
            "contract_version": "PRODUCT_1C_V1",
            "current_goal": session.get("goal") or "NOT_AVAILABLE",
            "organization_status": "ACTIVE" if active else ("IDLE" if not normalized_tasks else "WAITING"),
            "tasks": normalized_tasks,
            "active_task": active[0]["task_id"] if active else None,
            "active_agent": active[0].get("owner_agent") if active else None,
            "active_provider": active[0].get("provider") if active else None,
            "anomalies": self._anomalies(),
            "endurance_188g": self._endurance(),
            "model_calls": self.model_calls,
        })
