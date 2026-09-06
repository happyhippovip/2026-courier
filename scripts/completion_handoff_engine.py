#!/usr/bin/env python3
"""Product-5C deterministic completion/handoff reducer using the existing runtime event ledger."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List

from scripts.productivity_engine import WorkCandidate


COURIER_DIR = Path(__file__).resolve().parent.parent
GATE_REASONS = {"HUMAN_GATE", "MONEY_GATE", "PUBLICATION_GATE"}
HANDOFF_REASONS = {"CAPABILITY_MISMATCH", "PROVIDER_UNAVAILABLE", "SCOPE_CONFLICT", "EXECUTION_FAILURE", "QUALITY_FAILURE"}


def _read(path: Path) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


class CompletionHandoffEngine:
    """Evidence-required task completion. Its only durable store is event_ledger.json completion_stamps."""

    def __init__(self, repo_dir: Path = COURIER_DIR):
        self.repo_dir = Path(repo_dir)
        self.ledger_path = self.repo_dir / "events" / "autonomy-runtime" / "event_ledger.json"
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        self.ledger = _read(self.ledger_path)
        self.ledger.setdefault("events", [])
        self.ledger.setdefault("processed_event_hashes", [])
        self.ledger.setdefault("completion_stamps", {})
        self.model_calls = 0

    def _save(self) -> None:
        data = json.dumps(self.ledger, indent=2, sort_keys=True) + "\n"
        fd, temp_name = tempfile.mkstemp(prefix="completion-ledger-", dir=str(self.ledger_path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, self.ledger_path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    def open(self, task_id: str, semantic_fingerprint: str, goal_ref: str = "") -> Dict[str, Any]:
        current = self.ledger["completion_stamps"].get(task_id)
        if current:
            return current
        item = {"task_id": task_id, "semantic_fingerprint": semantic_fingerprint, "goal_ref": goal_ref,
                "status": "OPEN", "claims": [], "evidence_reference": None, "reason": None}
        self.ledger["completion_stamps"][task_id] = item
        self._save()
        return item

    def claim(self, task_id: str, worker: str, dependencies_satisfied: bool = True) -> Dict[str, Any]:
        item = self.ledger["completion_stamps"].get(task_id)
        if not item:
            return {"accepted": False, "status": "UNKNOWN"}
        if item["status"] == "DONE":
            return {"accepted": False, "status": "DONE"}
        if item["status"] == "CLAIMED":
            return {"accepted": False, "status": "CLAIMED"}
        if item["status"] in GATE_REASONS:
            return {"accepted": False, "status": item["status"]}
        if not dependencies_satisfied:
            item["status"] = "WAITING_DEPENDENCY"
            self._save()
            return {"accepted": False, "status": "WAITING_DEPENDENCY"}
        item["status"] = "CLAIMED"
        item["worker"] = worker
        item["claims"].append(worker)
        self._save()
        return {"accepted": True, "status": "CLAIMED", "worker": worker}

    def not_done(self, task_id: str, reason: str) -> Dict[str, Any]:
        item = self.ledger["completion_stamps"].get(task_id)
        if not item or item.get("status") == "DONE":
            return {"status": "UNKNOWN" if not item else "DONE"}
        item["reason"] = reason
        if reason == "DEPENDENCY_WAIT":
            item["status"] = "WAITING_DEPENDENCY"
        elif reason in GATE_REASONS:
            item["status"] = reason
        elif reason in HANDOFF_REASONS:
            prior = item.get("handoff_reason")
            if prior == reason and len(item.get("claims", [])) >= 2:
                item["status"] = "BLOCKED"
            else:
                item["status"] = "HANDOFF_REQUIRED"
                item["handoff_reason"] = reason
        else:
            item["status"] = "BLOCKED"
        self._save()
        return {"status": item["status"], "reason": reason}

    def handoff(self, task_id: str, workers: Iterable[str]) -> Dict[str, Any]:
        item = self.ledger["completion_stamps"].get(task_id)
        if not item or item.get("status") != "HANDOFF_REQUIRED":
            return {"accepted": False, "status": item.get("status", "UNKNOWN") if item else "UNKNOWN"}
        previous = set(item.get("claims", []))
        next_worker = next((worker for worker in workers if worker not in previous), None)
        if not next_worker:
            item["status"] = "BLOCKED"
            self._save()
            return {"accepted": False, "status": "BLOCKED"}
        return self.claim(task_id, next_worker)

    def record_result(self, task_id: str, semantic_fingerprint: str, evidence_reference: str | None, acceptance_satisfied: bool) -> Dict[str, Any]:
        item = self.ledger["completion_stamps"].get(task_id)
        if not item:
            return {"status": "UNKNOWN"}
        if item.get("semantic_fingerprint") != semantic_fingerprint or not evidence_reference or not acceptance_satisfied:
            return self.not_done(task_id, "QUALITY_FAILURE" if evidence_reference else "UNKNOWN_BLOCKER")
        item["status"] = "DONE"
        item["evidence_reference"] = evidence_reference
        item["reason"] = None
        self._save()
        return {"status": "DONE", "evidence_reference": evidence_reference}

    def recover(self, live_workers: Iterable[str]) -> List[str]:
        """Preserve DONE; turn orphaned CLAIMED records into bounded handoff candidates."""
        changed = []
        live = set(live_workers)
        for task_id, item in self.ledger["completion_stamps"].items():
            if item.get("status") == "CLAIMED" and item.get("worker") not in live:
                item["status"] = "HANDOFF_REQUIRED"
                item["reason"] = "PROVIDER_UNAVAILABLE"
                changed.append(task_id)
        if changed:
            self._save()
        return changed

    def eligible_candidates(self, candidates: Iterable[WorkCandidate]) -> List[WorkCandidate]:
        """Product-4/Product-4C compatibility: terminal and currently claimed work cannot re-enter a batch."""
        output = []
        for candidate in candidates:
            item = self.ledger["completion_stamps"].get(candidate.task_id)
            if item and item.get("status") in {"DONE", "CLAIMED", "WAITING_DEPENDENCY", *GATE_REASONS, "BLOCKED"}:
                continue
            output.append(candidate)
        return output
